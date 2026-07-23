#!/usr/bin/env bash
# 在「有网」机器上运行：下载全部 pip 依赖到 wheels/，并下载 3 个 OCR 模型到 models/。
# 建议与目标内网机器同系统（Ubuntu 22.04）同 Python 大版本（3.10）。
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

WHEELS_DIR="${WHEELS_DIR:-$ROOT/wheels}"
mkdir -p "$WHEELS_DIR"

PYTHON="${PYTHON:-python3}"
echo "==> 使用解释器: $($PYTHON --version 2>&1)"
echo "==> 下载依赖到: $WHEELS_DIR"

# 按 requirements 下载（含全部传递依赖）
$PYTHON -m pip download -r requirements.txt -d "$WHEELS_DIR"
# 裸 Ubuntu 服务器缺 libGL/libxcb，需用 headless 版 opencv 替换（见 install_offline.sh）
$PYTHON -m pip download opencv-python-headless -d "$WHEELS_DIR"

echo ""
echo "==> pip 依赖已下载完成。"
echo ""

# ---------- 下载 3 个 OCR 模型 ----------
# 来源：魔搭社区 RapidAI/RapidOCR 官方仓库（RapidOCR 全部模型统一托管于此）
MODELS_DIR="${MODELS_DIR:-$ROOT/models}"
mkdir -p "$MODELS_DIR"
MS_BASE="https://www.modelscope.cn/models/RapidAI/RapidOCR/resolve/master"

download_model() {
  local url="$1" dest="$2"
  if [[ -f "$dest" ]]; then
    echo "    已存在，跳过: $(basename "$dest")"
    return 0
  fi
  echo "    下载: $url"
  curl -fL --retry 3 -o "$dest" "$url"
}

echo "==> 下载 OCR 模型到: $MODELS_DIR"
download_model "$MS_BASE/onnx/PP-OCRv5/det/ch_PP-OCRv5_det_mobile.onnx" \
  "$MODELS_DIR/PP-OCRv5_mobile_det.onnx"
download_model "$MS_BASE/onnx/PP-OCRv4/cls/ch_ppocr_mobile_v2.0_cls_mobile.onnx" \
  "$MODELS_DIR/PP_OCRv4_mobile_cls.onnx"
download_model "$MS_BASE/onnx/PP-OCRv5/rec/ch_PP-OCRv5_rec_mobile.onnx" \
  "$MODELS_DIR/PP-OCRv5_mobile_rec.onnx"

echo ""
echo "============================================================"
echo "  离线包准备完成"
echo "============================================================"
echo ""
echo "若上面某个模型下载失败，可手动到魔搭仓库下载后重命名："
echo "  仓库: https://www.modelscope.cn/models/RapidAI/RapidOCR/files"
echo "    onnx/PP-OCRv5/det/ch_PP-OCRv5_det_mobile.onnx   -> PP-OCRv5_mobile_det.onnx"
echo "    onnx/PP-OCRv4/cls/ch_ppocr_mobile_v2.0_cls_mobile.onnx -> PP_OCRv4_mobile_cls.onnx"
echo "    onnx/PP-OCRv5/rec/ch_PP-OCRv5_rec_mobile.onnx   -> PP-OCRv5_mobile_rec.onnx"
echo ""
echo "打包拷贝到内网时，至少带上这些内容："
echo "  - 整个 case-sorting 项目代码"
echo "  - wheels/ 目录"
echo "  - models/ 下的 3 个 .onnx 文件"
echo ""
echo "内网机器上执行：  bash scripts/install_offline.sh"
echo "============================================================"
