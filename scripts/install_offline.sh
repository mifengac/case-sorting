#!/usr/bin/env bash
# 在「离线内网」机器上运行：创建虚拟环境并用本地 wheels 安装依赖，检查模型文件。
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

PYTHON="${PYTHON:-python3}"
VENV_DIR="${VENV_DIR:-$ROOT/.venv}"
WHEELS_DIR="${WHEELS_DIR:-$ROOT/wheels}"
MODELS_DIR="${MODELS_DIR:-$ROOT/models}"

echo "==> 项目目录: $ROOT"
echo "==> 使用解释器: $($PYTHON --version 2>&1)"

if [[ ! -d "$WHEELS_DIR" ]]; then
  echo "错误：找不到 wheels 目录: $WHEELS_DIR"
  echo "请先在有网机器运行 scripts/download_offline_bundle.sh，再把 wheels/ 拷过来。"
  exit 1
fi

# 检查模型
MISSING=0
for f in PP-OCRv5_mobile_det.onnx PP_OCRv4_mobile_cls.onnx PP-OCRv5_mobile_rec.onnx; do
  if [[ ! -f "$MODELS_DIR/$f" ]]; then
    echo "错误：缺少模型文件: $MODELS_DIR/$f"
    MISSING=1
  fi
done
if [[ "$MISSING" -ne 0 ]]; then
  echo "请把 3 个 ONNX 模型放到 models/ 后再执行本脚本。详见 README.md"
  exit 1
fi
echo "==> 模型文件检查通过"

if [[ ! -d "$VENV_DIR" ]]; then
  echo "==> 创建虚拟环境: $VENV_DIR"
  $PYTHON -m venv "$VENV_DIR"
fi

# shellcheck disable=SC1091
source "$VENV_DIR/bin/activate"

echo "==> 离线安装依赖（--no-index --find-links=wheels）"
pip install --upgrade pip --no-index --find-links="$WHEELS_DIR" || true
pip install --no-index --find-links="$WHEELS_DIR" -r requirements.txt

mkdir -p data/uploads data/results

echo ""
echo "==> 安装完成。"
echo "启动服务："
echo "  bash run.sh"
echo "或："
echo "  $VENV_DIR/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000"
echo ""
echo "批量识别："
echo "  $VENV_DIR/bin/python -m app.batch /path/to/输入 -o /path/to/输出"
