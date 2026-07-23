#!/usr/bin/env bash
# 启动网页服务
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"

VENV_DIR="${VENV_DIR:-$ROOT/.venv}"
HOST="${BILU_OCR_HOST:-0.0.0.0}"
PORT="${BILU_OCR_PORT:-8000}"

if [[ -x "$VENV_DIR/bin/uvicorn" ]]; then
  UVICORN="$VENV_DIR/bin/uvicorn"
elif command -v uvicorn >/dev/null 2>&1; then
  UVICORN="uvicorn"
else
  echo "找不到 uvicorn。请先执行: bash scripts/install_offline.sh"
  echo "或有网环境: python3 -m venv .venv && .venv/bin/pip install -r requirements.txt"
  exit 1
fi

mkdir -p data/uploads data/results

echo "启动笔录 OCR 服务: http://${HOST}:${PORT}"
exec "$UVICORN" app.main:app --host "$HOST" --port "$PORT"
