#!/usr/bin/env bash
# ============================================================
# LangCard Studio — Worker 서버 초기 설정 스크립트
# Hetzner Ubuntu 22.04 기준
#
# 사용법:
#   sudo bash deploy/setup_worker.sh
# ============================================================
set -euo pipefail

REPO_URL="https://github.com/YOUR_USERNAME/auto-lang.git"  # ← 실제 레포 URL로 변경
INSTALL_DIR="/opt/auto-lang"
SERVICE_USER="langcard"

echo "=========================================="
echo " LangCard Worker 서버 설정 시작"
echo "=========================================="

# ── 시스템 패키지 ─────────────────────────────────────────────────────────────
echo "[1/7] 시스템 패키지 설치..."
apt-get update -qq
apt-get install -y --no-install-recommends \
    python3.11 python3.11-venv python3-pip \
    ffmpeg \
    fonts-noto-color-emoji fonts-noto-cjk \
    git curl ca-certificates

# ── 서비스 유저 ──────────────────────────────────────────────────────────────
echo "[2/7] 서비스 유저 생성..."
id -u "$SERVICE_USER" &>/dev/null || useradd -r -s /bin/bash -m "$SERVICE_USER"

# ── 코드 클론 ────────────────────────────────────────────────────────────────
echo "[3/7] 코드 클론..."
if [ -d "$INSTALL_DIR/.git" ]; then
    echo "  → 이미 존재, git pull"
    git -C "$INSTALL_DIR" pull
else
    git clone "$REPO_URL" "$INSTALL_DIR"
fi
chown -R "$SERVICE_USER:$SERVICE_USER" "$INSTALL_DIR"

# ── Python 가상환경 ──────────────────────────────────────────────────────────
echo "[4/7] Python 가상환경 설정..."
sudo -u "$SERVICE_USER" python3.11 -m venv "$INSTALL_DIR/.venv"
sudo -u "$SERVICE_USER" "$INSTALL_DIR/.venv/bin/pip" install --upgrade pip -q
sudo -u "$SERVICE_USER" "$INSTALL_DIR/.venv/bin/pip" install \
    fastapi uvicorn[standard] \
    anthropic \
    Pillow \
    cloudinary \
    requests \
    python-dotenv \
    edge-tts \
    -q
echo "  ✓ pip 패키지 설치 완료"

# ── output 디렉토리 ──────────────────────────────────────────────────────────
echo "[5/7] 디렉토리 준비..."
sudo -u "$SERVICE_USER" mkdir -p "$INSTALL_DIR/output/tts"

# ── .env 파일 ────────────────────────────────────────────────────────────────
echo "[6/7] .env 파일 설정..."
if [ ! -f "$INSTALL_DIR/.env" ]; then
    cat > "$INSTALL_DIR/.env" << 'ENV'
# Worker 서버 .env
ANTHROPIC_API_KEY=여기에_입력
CLOUDINARY_URL=cloudinary://api_key:api_secret@cloud_name
WORKER_SECRET=여기에_랜덤_토큰_입력
ENV
    chown "$SERVICE_USER:$SERVICE_USER" "$INSTALL_DIR/.env"
    chmod 600 "$INSTALL_DIR/.env"
    echo "  ⚠ $INSTALL_DIR/.env 를 편집해서 실제 값을 입력하세요!"
else
    echo "  → .env 이미 존재, 건너뜀"
fi

# ── systemd 서비스 ───────────────────────────────────────────────────────────
echo "[7/7] systemd 서비스 등록..."
cp "$INSTALL_DIR/deploy/langcard-worker.service" /etc/systemd/system/
systemctl daemon-reload
systemctl enable langcard-worker

echo ""
echo "=========================================="
echo " 설정 완료!"
echo ""
echo " 다음 단계:"
echo "   1. nano $INSTALL_DIR/.env  (API 키 입력)"
echo "   2. sudo systemctl start langcard-worker"
echo "   3. sudo systemctl status langcard-worker"
echo "   4. curl http://localhost:8000/health"
echo "=========================================="
