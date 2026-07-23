"""配置项：模型路径、目录、上传限制等。

优先读环境变量，未设置则用项目内默认路径。
"""

from __future__ import annotations

import os
from pathlib import Path

# 项目根目录：case-sorting/
PROJECT_ROOT = Path(__file__).resolve().parent.parent

# ---------- 模型路径（可用环境变量覆盖） ----------
MODELS_DIR = Path(os.getenv("BILU_OCR_MODELS_DIR", str(PROJECT_ROOT / "models")))

DET_MODEL_PATH = Path(
    os.getenv(
        "BILU_OCR_DET_MODEL",
        str(MODELS_DIR / "PP-OCRv5_mobile_det.onnx"),
    )
)
CLS_MODEL_PATH = Path(
    os.getenv(
        "BILU_OCR_CLS_MODEL",
        str(MODELS_DIR / "PP_OCRv4_mobile_cls.onnx"),
    )
)
REC_MODEL_PATH = Path(
    os.getenv(
        "BILU_OCR_REC_MODEL",
        str(MODELS_DIR / "PP-OCRv5_mobile_rec.onnx"),
    )
)

# ---------- 数据目录 ----------
DATA_DIR = Path(os.getenv("BILU_OCR_DATA_DIR", str(PROJECT_ROOT / "data")))
UPLOAD_DIR = DATA_DIR / "uploads"
RESULT_DIR = DATA_DIR / "results"

# ---------- 上传与处理限制 ----------
MAX_UPLOAD_BYTES = int(os.getenv("BILU_OCR_MAX_UPLOAD_MB", "50")) * 1024 * 1024
MAX_PDF_PAGES = int(os.getenv("BILU_OCR_MAX_PDF_PAGES", "100"))
PDF_DPI = int(os.getenv("BILU_OCR_PDF_DPI", "300"))

# 允许的上传扩展名
ALLOWED_EXTENSIONS = {
    ".pdf",
    ".jpg",
    ".jpeg",
    ".png",
    ".bmp",
    ".webp",
}
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}

# ---------- 结果清理 ----------
# 上传文件与结果默认保留小时数
RESULT_TTL_HOURS = float(os.getenv("BILU_OCR_RESULT_TTL_HOURS", "24"))
# 清理扫描间隔（秒）
CLEANUP_INTERVAL_SECONDS = int(os.getenv("BILU_OCR_CLEANUP_INTERVAL", "3600"))

# ---------- 服务 ----------
HOST = os.getenv("BILU_OCR_HOST", "0.0.0.0")
PORT = int(os.getenv("BILU_OCR_PORT", "8000"))

# ---------- 文本行排序参数 ----------
# 判定「同一行」：两个框中心 y 差小于 行高 * 该系数
LINE_Y_RATIO = float(os.getenv("BILU_OCR_LINE_Y_RATIO", "0.6"))
# 判定「段落空行」：行间距大于 行高 * 该系数
PARAGRAPH_GAP_RATIO = float(os.getenv("BILU_OCR_PARAGRAPH_GAP_RATIO", "1.8"))


def ensure_dirs() -> None:
    """确保上传、结果目录存在。"""
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    RESULT_DIR.mkdir(parents=True, exist_ok=True)


def model_files_ok() -> tuple[bool, list[str]]:
    """检查三个模型文件是否都在。返回 (是否齐全, 缺失列表)。"""
    missing: list[str] = []
    for p in (DET_MODEL_PATH, CLS_MODEL_PATH, REC_MODEL_PATH):
        if not p.is_file():
            missing.append(str(p))
    return (len(missing) == 0, missing)
