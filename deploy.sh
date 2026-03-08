#!/bin/bash
# 양쪽 서버 배포 + worker 재시작
set -e

echo "=== GitHub push ==="
git push origin main

echo "=== kong-main pull + 봇 재시작 ==="
ssh kong-main "cd /opt/auto-lang && git pull origin main && systemctl restart langcard-bot.service && sleep 2 && systemctl is-active langcard-bot.service"

echo "=== sns-worker pull + 재시작 ==="
ssh sns-worker "cd /opt/auto-lang && git pull origin main && systemctl restart langcard-worker.service && sleep 2 && systemctl is-active langcard-worker.service"

echo "✅ 배포 완료"
