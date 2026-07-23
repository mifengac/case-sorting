"""RapidOCR 封装：初始化、识别单张图片、按阅读顺序拼接文本。"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Optional, Union

from PIL import Image

from app.config import (
    CLS_MODEL_PATH,
    DET_MODEL_PATH,
    LINE_Y_RATIO,
    PARAGRAPH_GAP_RATIO,
    REC_MODEL_PATH,
    model_files_ok,
)

logger = logging.getLogger(__name__)

# 延迟加载，避免 import 阶段就占内存
_engine = None


def get_ocr_engine():
    """获取全局 RapidOCR 实例（单例，串行任务下安全）。"""
    global _engine
    if _engine is not None:
        return _engine

    ok, missing = model_files_ok()
    if not ok:
        raise FileNotFoundError(
            "缺少 OCR 模型文件，请放到 models/ 目录或通过环境变量指定路径：\n"
            + "\n".join(f"  - {m}" for m in missing)
        )

    from rapidocr_onnxruntime import RapidOCR

    # RapidOCR 通过 det_model_path / cls_model_path / rec_model_path 传入自定义模型
    logger.info("加载 OCR 模型：det=%s", DET_MODEL_PATH)
    logger.info("加载 OCR 模型：cls=%s", CLS_MODEL_PATH)
    logger.info("加载 OCR 模型：rec=%s", REC_MODEL_PATH)

    _engine = RapidOCR(
        det_model_path=str(DET_MODEL_PATH),
        cls_model_path=str(CLS_MODEL_PATH),
        rec_model_path=str(REC_MODEL_PATH),
    )
    return _engine


def _box_metrics(box: list) -> tuple[float, float, float, float]:
    """从四点框算中心 x/y、高度、宽度。

    box 格式：[[x1,y1],[x2,y2],[x3,y3],[x4,y4]]
    """
    xs = [float(p[0]) for p in box]
    ys = [float(p[1]) for p in box]
    cx = sum(xs) / 4.0
    cy = sum(ys) / 4.0
    height = max(ys) - min(ys)
    width = max(xs) - min(xs)
    if height < 1.0:
        height = 1.0
    return cx, cy, height, width


def sort_and_join_ocr_result(
    result: Optional[list],
    line_y_ratio: float = LINE_Y_RATIO,
    paragraph_gap_ratio: float = PARAGRAPH_GAP_RATIO,
) -> str:
    """把 RapidOCR 带坐标的结果排成可读段落文本。

    规则：
    - 从上到下分行，行内从左到右
    - 同一行的文本框用空格连接
    - 行间换行
    - 纵向间距明显大于行高时插入空行分段
    """
    if not result:
        return ""

    items: list[dict[str, Any]] = []
    for row in result:
        # 正常格式：[box, text, score]，box 为 4 点
        if not row or len(row) < 2:
            continue
        box, text = row[0], row[1]
        if not text or not isinstance(text, str):
            continue
        text = text.strip()
        if not text:
            continue
        try:
            cx, cy, h, w = _box_metrics(box)
        except (TypeError, IndexError, ValueError):
            # 没有有效坐标时，按出现顺序排到最后
            cx, cy, h, w = 0.0, 1e9, 20.0, 20.0
        items.append(
            {
                "text": text,
                "cx": cx,
                "cy": cy,
                "h": h,
                "w": w,
            }
        )

    if not items:
        return ""

    # 先按 y 再按 x 粗排
    items.sort(key=lambda it: (it["cy"], it["cx"]))

    # 分行：中心 y 差小于 行高 * 系数 视为同一行
    lines: list[list[dict[str, Any]]] = []
    current: list[dict[str, Any]] = [items[0]]
    for it in items[1:]:
        ref = current[0]
        # 用当前行已有框的平均高度作参考
        avg_h = sum(x["h"] for x in current) / len(current)
        threshold = max(avg_h * line_y_ratio, 8.0)
        if abs(it["cy"] - ref["cy"]) <= threshold:
            current.append(it)
        else:
            lines.append(current)
            current = [it]
    lines.append(current)

    # 行内从左到右
    for line in lines:
        line.sort(key=lambda it: it["cx"])

    # 拼接：行内空格，行间换行，大间距插空行
    out_lines: list[str] = []
    prev_cy: Optional[float] = None
    prev_h: Optional[float] = None

    for line in lines:
        line_text = " ".join(it["text"] for it in line)
        avg_cy = sum(it["cy"] for it in line) / len(line)
        avg_h = sum(it["h"] for it in line) / len(line)

        if prev_cy is not None and prev_h is not None:
            gap = avg_cy - prev_cy
            # 行中心间距相对行高过大 → 分段空行
            if gap > max(prev_h, avg_h) * paragraph_gap_ratio:
                out_lines.append("")

        out_lines.append(line_text)
        prev_cy = avg_cy
        prev_h = avg_h

    return "\n".join(out_lines).strip() + ("\n" if out_lines else "")


def ocr_image(
    image: Union[str, Path, Image.Image, bytes],
) -> str:
    """识别单张图片，返回排版后的纯文本。"""
    engine = get_ocr_engine()

    # RapidOCR 支持路径 / ndarray / bytes；PIL Image 转成 RGB 再交给它
    if isinstance(image, Image.Image):
        import numpy as np

        img_rgb = image.convert("RGB")
        img_arr = np.array(img_rgb)
        # RapidOCR / opencv 期望 BGR
        img_arr = img_arr[:, :, ::-1].copy()
        result, _elapse = engine(img_arr)
    elif isinstance(image, Path):
        result, _elapse = engine(str(image))
    else:
        result, _elapse = engine(image)

    return sort_and_join_ocr_result(result)


def ocr_image_file(path: Union[str, Path]) -> str:
    """按文件路径识别。"""
    return ocr_image(Path(path))
