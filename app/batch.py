"""命令行批处理：递归扫描目录，逐个识别，输出同名 .txt。

用法：
    python -m app.batch <输入目录> -o <输出目录>
"""

from __future__ import annotations

import argparse
import logging
import sys
import time
from pathlib import Path

from app.config import ALLOWED_EXTENSIONS, IMAGE_EXTENSIONS, ensure_dirs, model_files_ok
from app.ocr_engine import ocr_image, ocr_image_file
from app.pdf_utils import PdfTooManyPagesError, iter_pdf_pages

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("batch")


def find_inputs(input_dir: Path) -> list[Path]:
    """递归找出支持的 PDF 和图片。"""
    files: list[Path] = []
    for p in sorted(input_dir.rglob("*")):
        if p.is_file() and p.suffix.lower() in ALLOWED_EXTENSIONS:
            files.append(p)
    return files


def ocr_file(path: Path) -> str:
    """识别单个文件，返回全文。"""
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        parts: list[str] = []
        for idx, image in enumerate(iter_pdf_pages(path), start=1):
            logger.info("  第 %d 页…", idx)
            text = ocr_image(image)
            parts.append(f"\n----- 第 {idx} 页 -----\n")
            parts.append(text.rstrip() + "\n")
        return f"# 来源文件：{path.name}\n" + "".join(parts)
    if suffix in IMAGE_EXTENSIONS:
        text = ocr_image_file(path)
        return f"# 来源文件：{path.name}\n\n----- 第 1 页 -----\n{text.rstrip()}\n"
    raise ValueError(f"不支持的类型：{suffix}")


def relative_out_path(src: Path, input_root: Path, output_root: Path) -> Path:
    """保持相对目录结构，扩展名改为 .txt。"""
    rel = src.relative_to(input_root)
    return output_root / rel.with_suffix(".txt")


def run(input_dir: Path, output_dir: Path) -> int:
    if not input_dir.is_dir():
        logger.error("输入目录不存在：%s", input_dir)
        return 2

    ok, missing = model_files_ok()
    if not ok:
        logger.error("缺少模型文件：")
        for m in missing:
            logger.error("  - %s", m)
        logger.error("请先放到 models/ 或设置环境变量，详见 README.md")
        return 2

    ensure_dirs()
    output_dir.mkdir(parents=True, exist_ok=True)

    files = find_inputs(input_dir)
    if not files:
        logger.warning("未找到可识别的 PDF/图片：%s", input_dir)
        return 0

    logger.info("共发现 %d 个文件，开始串行识别…", len(files))
    success = 0
    failed = 0
    t0 = time.time()

    for i, src in enumerate(files, start=1):
        out = relative_out_path(src, input_dir, output_dir)
        out.parent.mkdir(parents=True, exist_ok=True)
        logger.info("[%d/%d] %s", i, len(files), src)
        start = time.time()
        try:
            text = ocr_file(src)
            out.write_text(text, encoding="utf-8")
            elapsed = time.time() - start
            logger.info("  → 成功 %.1fs → %s", elapsed, out)
            success += 1
        except PdfTooManyPagesError as exc:
            elapsed = time.time() - start
            logger.error("  → 失败 %.1fs：%s", elapsed, exc)
            failed += 1
        except Exception as exc:  # noqa: BLE001
            elapsed = time.time() - start
            logger.exception("  → 失败 %.1fs：%s", elapsed, exc)
            failed += 1

    total_elapsed = time.time() - t0
    logger.info(
        "完成：成功 %d，失败 %d，共 %d，总耗时 %.1fs",
        success,
        failed,
        len(files),
        total_elapsed,
    )
    return 0 if failed == 0 else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="批量识别目录下的 PDF/图片，输出同名 .txt",
    )
    parser.add_argument("input_dir", type=Path, help="输入目录（递归扫描）")
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        required=True,
        help="输出目录",
    )
    args = parser.parse_args(argv)
    return run(args.input_dir.resolve(), args.output.resolve())


if __name__ == "__main__":
    sys.exit(main())
