"""用 PyMuPDF 把 PDF 按指定 DPI 渲染成图片。"""

from __future__ import annotations

from pathlib import Path
from typing import Iterator, Union

import fitz  # PyMuPDF
from PIL import Image

from app.config import MAX_PDF_PAGES, PDF_DPI


class PdfTooManyPagesError(ValueError):
    """PDF 页数超限。"""

    def __init__(self, page_count: int, limit: int = MAX_PDF_PAGES):
        self.page_count = page_count
        self.limit = limit
        super().__init__(
            f"PDF 共 {page_count} 页，超过上限 {limit} 页，请拆分后再上传。"
        )


def get_pdf_page_count(pdf_path: Union[str, Path]) -> int:
    """返回 PDF 页数。"""
    with fitz.open(str(pdf_path)) as doc:
        return doc.page_count


def render_pdf_to_images(
    pdf_path: Union[str, Path],
    dpi: int = PDF_DPI,
    max_pages: int = MAX_PDF_PAGES,
) -> list[Image.Image]:
    """把 PDF 每一页渲染成 PIL Image（RGB），页数超限抛 PdfTooManyPagesError。"""
    return list(iter_pdf_pages(pdf_path, dpi=dpi, max_pages=max_pages))


def iter_pdf_pages(
    pdf_path: Union[str, Path],
    dpi: int = PDF_DPI,
    max_pages: int = MAX_PDF_PAGES,
) -> Iterator[Image.Image]:
    """逐页 yield PIL Image，省内存。"""
    pdf_path = Path(pdf_path)
    with fitz.open(str(pdf_path)) as doc:
        page_count = doc.page_count
        if page_count > max_pages:
            raise PdfTooManyPagesError(page_count, max_pages)

        # 72 是 PDF 默认用户单位，按 dpi 缩放
        zoom = dpi / 72.0
        matrix = fitz.Matrix(zoom, zoom)

        for page_index in range(page_count):
            page = doc.load_page(page_index)
            pix = page.get_pixmap(matrix=matrix, alpha=False)
            # pix.samples 是 RGB 字节
            img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
            yield img
