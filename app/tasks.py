"""串行任务队列与内存态任务管理。

识别是 CPU 密集型，用单线程队列逐个处理，避免并发把 CPU 打满。
任务状态存在内存里，进程重启后丢失（可接受）。
"""

from __future__ import annotations

import logging
import threading
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Optional

from app.config import (
    CLEANUP_INTERVAL_SECONDS,
    IMAGE_EXTENSIONS,
    RESULT_DIR,
    RESULT_TTL_HOURS,
    UPLOAD_DIR,
    ensure_dirs,
)
from app.ocr_engine import ocr_image, ocr_image_file
from app.pdf_utils import PdfTooManyPagesError, get_pdf_page_count, iter_pdf_pages

logger = logging.getLogger(__name__)


class TaskStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    DONE = "done"
    ERROR = "error"


@dataclass
class PageResult:
    page_index: int  # 从 1 开始
    text: str


@dataclass
class Task:
    task_id: str
    original_name: str
    file_path: Path
    status: TaskStatus = TaskStatus.PENDING
    progress: float = 0.0  # 0~100
    message: str = "排队中"
    pages: list[PageResult] = field(default_factory=list)
    full_text: str = ""
    result_path: Optional[Path] = None
    error: Optional[str] = None
    created_at: float = field(default_factory=time.time)
    finished_at: Optional[float] = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "original_name": self.original_name,
            "status": self.status.value,
            "progress": round(self.progress, 1),
            "message": self.message,
            "error": self.error,
            "page_count": len(self.pages),
            "pages": [
                {"page_index": p.page_index, "text": p.text} for p in self.pages
            ],
            "full_text": self.full_text if self.status == TaskStatus.DONE else "",
            "has_download": bool(
                self.result_path and self.result_path.is_file() and self.status == TaskStatus.DONE
            ),
            "created_at": self.created_at,
            "finished_at": self.finished_at,
        }


class TaskManager:
    """内存任务表 + 单 worker 串行队列。"""

    def __init__(self) -> None:
        self._tasks: dict[str, Task] = {}
        self._lock = threading.Lock()
        self._queue: list[str] = []
        self._cv = threading.Condition(self._lock)
        self._worker: Optional[threading.Thread] = None
        self._cleaner: Optional[threading.Thread] = None
        self._stop = False

    def start(self) -> None:
        ensure_dirs()
        self._stop = False
        if self._worker is None or not self._worker.is_alive():
            self._worker = threading.Thread(
                target=self._worker_loop, name="ocr-worker", daemon=True
            )
            self._worker.start()
        if self._cleaner is None or not self._cleaner.is_alive():
            self._cleaner = threading.Thread(
                target=self._cleanup_loop, name="ocr-cleaner", daemon=True
            )
            self._cleaner.start()
        logger.info("任务管理器已启动（串行队列 + 定时清理）")

    def stop(self) -> None:
        with self._cv:
            self._stop = True
            self._cv.notify_all()

    def create_task(self, original_name: str, saved_path: Path) -> Task:
        task_id = uuid.uuid4().hex
        task = Task(
            task_id=task_id,
            original_name=original_name,
            file_path=saved_path,
        )
        with self._cv:
            self._tasks[task_id] = task
            self._queue.append(task_id)
            self._cv.notify()
        return task

    def get_task(self, task_id: str) -> Optional[Task]:
        with self._lock:
            return self._tasks.get(task_id)

    def list_tasks(self, limit: int = 50) -> list[Task]:
        with self._lock:
            tasks = sorted(
                self._tasks.values(), key=lambda t: t.created_at, reverse=True
            )
            return tasks[:limit]

    def _worker_loop(self) -> None:
        while True:
            with self._cv:
                while not self._queue and not self._stop:
                    self._cv.wait()
                if self._stop:
                    return
                task_id = self._queue.pop(0)
                task = self._tasks.get(task_id)
            if task is None:
                continue
            try:
                self._process_task(task)
            except Exception as exc:  # noqa: BLE001 — 任务级兜底
                logger.exception("任务 %s 处理失败", task_id)
                with self._lock:
                    task.status = TaskStatus.ERROR
                    task.error = str(exc)
                    task.message = "识别失败"
                    task.finished_at = time.time()

    def _process_task(self, task: Task) -> None:
        with self._lock:
            task.status = TaskStatus.PROCESSING
            task.message = "开始识别"
            task.progress = 0.0

        path = task.file_path
        suffix = path.suffix.lower()
        pages: list[PageResult] = []

        try:
            if suffix == ".pdf":
                pages = self._ocr_pdf(task, path)
            elif suffix in IMAGE_EXTENSIONS:
                pages = self._ocr_single_image(task, path)
            else:
                raise ValueError(f"不支持的文件类型：{suffix}")
        except PdfTooManyPagesError as exc:
            with self._lock:
                task.status = TaskStatus.ERROR
                task.error = str(exc)
                task.message = "页数超限"
                task.finished_at = time.time()
            return

        full_text = self._join_pages(pages, task.original_name)
        result_path = RESULT_DIR / f"{task.task_id}.txt"
        result_path.write_text(full_text, encoding="utf-8")

        with self._lock:
            task.pages = pages
            task.full_text = full_text
            task.result_path = result_path
            task.status = TaskStatus.DONE
            task.progress = 100.0
            task.message = "识别完成"
            task.finished_at = time.time()

        logger.info("任务 %s 完成，共 %d 页", task.task_id, len(pages))

    def _ocr_pdf(self, task: Task, path: Path) -> list[PageResult]:
        total = get_pdf_page_count(path)
        pages: list[PageResult] = []
        for idx, image in enumerate(iter_pdf_pages(path), start=1):
            with self._lock:
                task.message = f"正在识别第 {idx}/{total} 页"
                task.progress = (idx - 1) / max(total, 1) * 100.0
            text = ocr_image(image)
            pages.append(PageResult(page_index=idx, text=text))
            with self._lock:
                task.pages = list(pages)
                task.progress = idx / max(total, 1) * 100.0
        return pages

    def _ocr_single_image(self, task: Task, path: Path) -> list[PageResult]:
        with self._lock:
            task.message = "正在识别图片"
            task.progress = 10.0
        text = ocr_image_file(path)
        with self._lock:
            task.progress = 90.0
        return [PageResult(page_index=1, text=text)]

    @staticmethod
    def _join_pages(pages: list[PageResult], original_name: str) -> str:
        parts: list[str] = [f"# 来源文件：{original_name}\n"]
        for p in pages:
            parts.append(f"\n----- 第 {p.page_index} 页 -----\n")
            parts.append(p.text.rstrip() + "\n")
        return "".join(parts)

    def _cleanup_loop(self) -> None:
        while not self._stop:
            try:
                self.cleanup_expired()
            except Exception:  # noqa: BLE001
                logger.exception("清理过期文件时出错")
            # 分段 sleep，方便 stop
            for _ in range(CLEANUP_INTERVAL_SECONDS):
                if self._stop:
                    return
                time.sleep(1)

    def cleanup_expired(self) -> int:
        """删除超过 TTL 的上传文件、结果文件和内存任务记录。返回清理数量。"""
        ttl_seconds = RESULT_TTL_HOURS * 3600
        now = time.time()
        removed = 0

        with self._lock:
            expired_ids = [
                tid
                for tid, t in self._tasks.items()
                if (now - t.created_at) > ttl_seconds
                and tid not in self._queue
                and t.status in (TaskStatus.DONE, TaskStatus.ERROR)
            ]
            for tid in expired_ids:
                task = self._tasks.pop(tid, None)
                if task is None:
                    continue
                for p in (task.file_path, task.result_path):
                    if p and Path(p).is_file():
                        try:
                            Path(p).unlink()
                            removed += 1
                        except OSError:
                            pass

        # 扫目录兜底：删掉孤儿文件
        cutoff = now - ttl_seconds
        for folder in (UPLOAD_DIR, RESULT_DIR):
            if not folder.is_dir():
                continue
            for f in folder.iterdir():
                if not f.is_file() or f.name == ".gitkeep":
                    continue
                try:
                    if f.stat().st_mtime < cutoff:
                        f.unlink()
                        removed += 1
                except OSError:
                    pass

        if removed:
            logger.info("清理过期文件 %d 个", removed)
        return removed


# 全局单例
task_manager = TaskManager()
