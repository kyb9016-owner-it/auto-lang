"""구독 큐·HOOK 검증 테스트 (stdlib unittest). 실행: python3 -m unittest discover -s tests"""
import copy
import importlib
import json
import os
import random
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "scripts"))

from generator import history, hook_queue  # noqa: E402
from generator.hook_prompt import validate_hook  # noqa: E402
import fill_hook_queue as fhq  # noqa: E402

SAMPLE = {
    "hook": "이거 영어로 말하면 99%가 틀림",
    "wrong": "I am boring",
    "wrong_ko_phonetic": "아이 엠 보링",
    "right": "I'm bored",
    "right_ko_phonetic": "아임 보드",
    "right_ko": "나 지루해",
    "pronunciation": None,
    "tts_parts": {"intro": "많은 사람들이 틀려요", "bridge": "올바른 표현은", "outro": "나 지루해"},
    "subtitle_lines": ["99%가 틀림", "❌ I am boring", "→ 나는 지루한 사람", "✅ I'm bored", "→ 나 지루해"],
    "explanation": "boring은 사람을 지루하게 만드는 쪽, bored는 지루함을 느끼는 쪽이에요.",
    "cta": "이거 몰랐으면 저장해두세요",
    "vocab": [
        {"word": "bored", "type": "형용사", "meaning": "지루한", "phonetic": "보드"},
        {"word": "boring", "type": "형용사", "meaning": "지루하게 하는", "phonetic": "보링"},
        {"word": "feel", "type": "동사", "meaning": "느끼다", "phonetic": "필"},
    ],
    "dialogue": [
        {"speaker": "A", "line": "What's wrong?", "pronunciation": None, "korean_phonetic": "왓츠 롱", "korean": "무슨 일이야?"},
        {"speaker": "B", "line": "I'm bored.", "pronunciation": None, "korean_phonetic": "아임 보드", "korean": "지루해."},
    ],
}


def make(**over):
    d = copy.deepcopy(SAMPLE)
    d.update(over)
    return d


class ValidateHookTest(unittest.TestCase):
    def test_ok(self):
        self.assertEqual(validate_hook(SAMPLE), [])

    def test_vocab_two(self):
        self.assertTrue(validate_hook(make(vocab=SAMPLE["vocab"][:2])))

    def test_dialogue_one(self):
        self.assertTrue(validate_hook(make(dialogue=SAMPLE["dialogue"][:1])))

    def test_right_not_in_dialogue(self):
        d = make(right="I'm exhausted")
        self.assertTrue(any("right" in p for p in validate_hook(d)))

    def test_right_loose_match(self):
        self.assertEqual(validate_hook(make(right="i'm  BORED!")), [])

    def test_cta_emoji(self):
        self.assertTrue(validate_hook(make(cta="저장해두세요 🔥")))

    def test_missing_key(self):
        d = make()
        del d["explanation"]
        self.assertTrue(validate_hook(d))


class SimilarWrongTest(unittest.TestCase):
    def test_exact(self):
        self.assertTrue(history.is_similar_wrong("I am boring", ["I am boring"]))

    def test_similar(self):
        self.assertTrue(history.is_similar_wrong("I am boring.", ["I am boring"]))

    def test_unrelated(self):
        self.assertFalse(history.is_similar_wrong("Where is the station", ["I am boring"]))

    def test_empty(self):
        self.assertFalse(history.is_similar_wrong("x", []))


class PopTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.q = os.path.join(self.tmp.name, "q")
        os.makedirs(os.path.join(self.q, "en"))
        os.environ["HOOK_QUEUE_DIR"] = self.q
        self.addCleanup(os.environ.pop, "HOOK_QUEUE_DIR", None)
        self.hist = os.path.join(self.tmp.name, "history.json")
        self._old = history.HISTORY_PATH
        history.HISTORY_PATH = self.hist
        self.addCleanup(setattr, history, "HISTORY_PATH", self._old)

    def put(self, name, data=None, raw=None):
        p = os.path.join(self.q, "en", name)
        with open(p, "w", encoding="utf-8") as f:
            f.write(raw if raw is not None else json.dumps({"lang": "en", "data": data}))
        return p

    def test_pop_moves_to_used(self):
        self.put("a.json", SAMPLE)
        self.assertEqual(hook_queue.count("en"), 1)
        self.assertEqual(hook_queue.pop("en"), SAMPLE)
        self.assertTrue(os.path.exists(os.path.join(self.q, "used", "a.json")))
        self.assertEqual(hook_queue.count("en"), 0)
        self.assertIsNone(hook_queue.pop("en"))

    def test_pop_with_prerendered_video(self):
        self.put("a.json", SAMPLE)
        with open(os.path.join(self.q, "en", "a.mp4"), "wb") as f:
            f.write(b"\x00mp4")
        got = hook_queue.pop("en")
        used_mp4 = os.path.join(self.q, "used", "a.mp4")
        self.assertEqual(got["_reel_path"], used_mp4)
        self.assertTrue(os.path.exists(used_mp4))
        self.assertEqual(got["wrong"], SAMPLE["wrong"])

    def test_empty_video_ignored(self):
        self.put("a.json", SAMPLE)
        open(os.path.join(self.q, "en", "a.mp4"), "wb").close()
        self.assertNotIn("_reel_path", hook_queue.pop("en"))

    def test_broken_json_rejected(self):
        self.put("a.json", raw="{not json")
        self.put("b.json", SAMPLE)
        self.assertEqual(hook_queue.pop("en"), SAMPLE)
        self.assertTrue(os.path.exists(os.path.join(self.q, "rejected", "a.json")))

    def test_invalid_rejected(self):
        self.put("a.json", make(vocab=[]))
        self.assertIsNone(hook_queue.pop("en"))
        self.assertTrue(os.path.exists(os.path.join(self.q, "rejected", "a.json")))

    def test_duplicate_rejected(self):
        history.add_hook("en", "I am boring", "I'm bored")
        self.put("a.json", SAMPLE)
        self.assertIsNone(hook_queue.pop("en"))
        self.assertTrue(os.path.exists(os.path.join(self.q, "rejected", "a.json")))

    def test_tmp_ignored(self):
        self.put("a.json.tmp", SAMPLE)
        self.assertIsNone(hook_queue.pop("en"))
        self.assertEqual(hook_queue.count("en"), 0)

    def test_ascending_order(self):
        self.put("20260101T000002_b.json", make(wrong="Second wrong phrase here"))
        self.put("20260101T000001_a.json", SAMPLE)
        self.assertEqual(hook_queue.pop("en")["wrong"], "I am boring")

    def test_missing_dir(self):
        self.assertIsNone(hook_queue.pop("zh"))


class FillScriptPureTest(unittest.TestCase):
    def test_args(self):
        a = fhq.build_claude_args("m", "sys", {"type": "object"})
        self.assertIn("--safe-mode", a)
        self.assertNotIn("--bare", a)
        i = a.index("--tools")
        self.assertEqual(a[i + 1], "")
        self.assertEqual(a[a.index("--setting-sources") + 1], "")

    def test_env(self):
        env = fhq.subscription_env({"ANTHROPIC_API_KEY": "x", "ANTHROPIC_BASE_URL": "y", "PATH": "/bin"}, "sk-ant-oat-z")
        self.assertNotIn("ANTHROPIC_API_KEY", env)
        self.assertNotIn("ANTHROPIC_BASE_URL", env)
        self.assertEqual(env["PATH"], "/bin")
        self.assertEqual(env["CLAUDE_CODE_OAUTH_TOKEN"], "sk-ant-oat-z")
        self.assertNotIn("CLAUDE_CODE_OAUTH_TOKEN", fhq.subscription_env({}, None))

    def test_parse_structured(self):
        out = json.dumps({"is_error": False, "structured_output": {"a": 1}})
        self.assertEqual(fhq.parse_claude_output(out), {"a": 1})

    def test_parse_error(self):
        with self.assertRaises(ValueError):
            fhq.parse_claude_output(json.dumps({"is_error": True, "result": "x"}))

    def test_parse_fence_fallback(self):
        out = json.dumps({"result": "```json\n{\"a\": 2}\n```"})
        self.assertEqual(fhq.parse_claude_output(out), {"a": 2})

    def test_parse_nothing(self):
        with self.assertRaises(ValueError):
            fhq.parse_claude_output(json.dumps({"result": ""}))


class StyleTest(unittest.TestCase):
    def test_choose_excludes_last_two(self):
        av = ["a", "b", "c", "d"]
        for seed in range(50):
            got = fhq.choose_style(av, ["a", "b", "c"], random.Random(seed))
            self.assertIn(got, ["a", "d"])  # 마지막 2개(b,c) 제외

    def test_choose_fallback_all(self):
        got = fhq.choose_style(["a", "b"], ["a", "b"], random.Random(1))
        self.assertIn(got, ["a", "b"])
        self.assertEqual(fhq.choose_style(["a"], ["a"], random.Random(1)), "a")

    def test_choose_deterministic(self):
        av = ["a", "b", "c", "d", "e"]
        r1 = [fhq.choose_style(av, [], random.Random(7)) for _ in range(3)]
        self.assertEqual(len(set(r1)), 1)
        self.assertEqual(fhq.choose_style(av, [], random.Random(7)), random.Random(7).choice(av))

    def test_choose_empty_raises(self):
        with self.assertRaises(ValueError):
            fhq.choose_style([], [], random.Random(0))

    def test_list_styles(self):
        with tempfile.TemporaryDirectory() as t:
            for n in ["a", "b", "_x"]:
                os.makedirs(os.path.join(t, "styles", n))
                open(os.path.join(t, "styles", n, "index.html"), "w").close()
            os.makedirs(os.path.join(t, "styles", "c"))
            self.assertEqual(fhq.list_styles(t), ["a", "b"])
            self.assertEqual(fhq.list_styles(t, ["b", "c", "zzz"]), ["b"])
            self.assertEqual(fhq.list_styles(t, []), ["a", "b"])

    def test_history_save_load_cap(self):
        with tempfile.TemporaryDirectory() as t:
            path = os.path.join(t, "sub", "dir", "h.json")
            self.assertEqual(fhq.load_style_history(path), [])
            for i in range(35):
                fhq.record_style(f"s{i}", path)
            hist = fhq.load_style_history(path)
            self.assertEqual(len(hist), 30)
            self.assertEqual(hist[0], "s5")
            self.assertEqual(hist[-1], "s34")

    def test_history_default_path_override(self):
        with tempfile.TemporaryDirectory() as t:
            old = fhq.STYLE_HISTORY_PATH
            fhq.STYLE_HISTORY_PATH = os.path.join(t, "x", "h.json")
            self.addCleanup(setattr, fhq, "STYLE_HISTORY_PATH", old)
            fhq.record_style("a")
            fhq.record_style("b")
            self.assertEqual(fhq.load_style_history(), ["a", "b"])

    def test_history_corrupt(self):
        with tempfile.TemporaryDirectory() as t:
            path = os.path.join(t, "h.json")
            with open(path, "w") as f:
                f.write("{broken")
            self.assertEqual(fhq.load_style_history(path), [])


class BackfillPureTest(unittest.TestCase):
    def test_missing_videos(self):
        names = ["b.json", "a.json", "a.mp4", "c.json", "c.mp4", "d.json.tmp", "x.mp4"]
        self.assertEqual(fhq.missing_videos(names), ["b.json"])
        self.assertEqual(fhq.missing_videos([]), [])

    def test_parse_listing(self):
        out = "en/a.json\nen/a.mp4\nzh/b.json\n\ngarbage\n"
        self.assertEqual(fhq.parse_queue_listing(out), {"en": ["a.json", "a.mp4"], "zh": ["b.json"]})


class ClaudeGenTest(unittest.TestCase):
    def test_import_without_key_or_anthropic(self):
        code = ("import sys; sys.modules['anthropic']=None; import generator.claude_gen as g;"
                "print('ok', 'anthropic' in [m for m in sys.modules if sys.modules[m] is not None])")
        env = {k: v for k, v in os.environ.items() if k != "ANTHROPIC_API_KEY"}
        r = subprocess.run([sys.executable, "-c", code], cwd=ROOT, env=env, capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue(r.stdout.startswith("ok"))

    def test_empty_queue_raises(self):
        from generator import claude_gen
        with tempfile.TemporaryDirectory() as t:
            os.environ["HOOK_QUEUE_DIR"] = t
            os.environ.pop("AI_BACKEND", None)
            try:
                with self.assertRaises(RuntimeError) as cm:
                    claude_gen.generate_hook("en")
                self.assertIn("구독 큐", str(cm.exception))
            finally:
                os.environ.pop("HOOK_QUEUE_DIR", None)


if __name__ == "__main__":
    unittest.main()
