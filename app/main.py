"""FastAPI 入口：网页上传、任务查询、结果下载。"""

from __future__ import annotations

import logging
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.config import (
    ALLOWED_EXTENSIONS,
    MAX_PDF_PAGES,
    MAX_UPLOAD_BYTES,
    UPLOAD_DIR,
    ensure_dirs,
)
from app.pdf_utils import get_pdf_page_count
from app.tasks import task_manager

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

APP_DIR = Path(__file__).resolve().parent


@asynccontextmanager
async def lifespan(_app: FastAPI):
    ensure_dirs()
    task_manager.start()
    logger.info("笔录 OCR 服务已就绪")
    yield
    task_manager.stop()


app = FastAPI(
    title="笔录扫描件转文本",
    description="离线 OCR：PDF/图片 → 纯文本",
    version="1.0.0",
    lifespan=lifespan,
)

app.mount("/static", StaticFiles(directory=str(APP_DIR / "static")), name="static")
templates = Jinja2Templates(directory=str(APP_DIR / "templates"))


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """首页：单页上传与结果展示。"""
    return templates.TemplateResponse(
        request,
        "index.html",
        {
            "max_upload_mb": MAX_UPLOAD_BYTES // (1024 * 1024),
            "max_pdf_pages": MAX_PDF_PAGES,
        },
    )


@app.get("/api/health")
async def health():
    return {"status": "ok"}


@app.post("/api/upload")
async def upload(files: list[UploadFile] = File(...)):
    """上传一个或多个 PDF/图片，入队识别，返回任务 ID 列表。"""
    if not files:
        raise HTTPException(status_code=400, detail="请选择至少一个文件")

    ensure_dirs()
    created: list[dict] = []
    errors: list[str] = []

    for uf in files:
        original = uf.filename or "unknown"
        suffix = Path(original).suffix.lower()
        if suffix not in ALLOWED_EXTENSIONS:
            errors.append(f"{original}：不支持的文件类型，仅支持 PDF 和常见图片")
            continue

        task_uuid = uuid.uuid4().hex
        save_name = f"{task_uuid}{suffix}"
        save_path = UPLOAD_DIR / save_name

        size = 0
        too_large = False
        try:
            with save_path.open("wb") as out:
                while True:
                    chunk = await uf.read(1024 * 1024)
                    if not chunk:
                        break
                    size += len(chunk)
                    if size > MAX_UPLOAD_BYTES:
                        too_large = True
                        break
                    out.write(chunk)
        except Exception as exc:  # noqa: BLE001
            save_path.unlink(missing_ok=True)
            errors.append(f"{original}：保存失败 - {exc}")
            continue

        if too_large:
            save_path.unlink(missing_ok=True)
            limit_mb = MAX_UPLOAD_BYTES // (1024 * 1024)
            errors.append(f"{original}：文件超过 {limit_mb} MB 限制")
            continue
        if size == 0:
            save_path.unlink(missing_ok=True)
            errors.append(f"{original}：文件为空")
            continue

        # PDF 页数预检
        if suffix == ".pdf":
            try:
                pages = get_pdf_page_count(save_path)
                if pages > MAX_PDF_PAGES:
                    save_path.unlink(missing_ok=True)
                    errors.append(
                        f"{original}：共 {pages} 页，超过上限 {MAX_PDF_PAGES} 页"
                    )
                    continue
            except Exception as exc:  # noqa: BLE001
                save_path.unlink(missing_ok=True)
                errors.append(f"{original}：无法读取 PDF - {exc}")
                continue

        task = task_manager.create_task(original_name=original, saved_path=save_path)
        created.append(
            {
                "task_id": task.task_id,
                "original_name": original,
                "status": task.status.value,
            }
        )

    if not created and errors:
        raise HTTPException(status_code=400, detail="；".join(errors))

    return {
        "tasks": created,
        "errors": errors,
    }


@app.get("/api/tasks/{task_id}")
async def get_task(task_id: str):
    """查询单个任务状态与结果（供前端轮询）。"""
    task = task_manager.get_task(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="任务不存在或已过期清理")
    return task.to_dict()


@app.get("/api/tasks")
async def list_tasks():
    """最近任务列表。"""
    tasks = task_manager.list_tasks()
    return {"tasks": [t.to_dict() for t in tasks]}


@app.get("/api/tasks/{task_id}/download")
async def download_result(task_id: str):
    """下载识别结果 .txt。"""
    task = task_manager.get_task(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="任务不存在或已过期清理")
    if (
        task.status.value != "done"
        or not task.result_path
        or not task.result_path.is_file()
    ):
        raise HTTPException(status_code=400, detail="结果尚未生成")

    stem = Path(task.original_name).stem
    download_name = f"{stem}.txt"
    return FileResponse(
        path=str(task.result_path),
        media_type="text/plain; charset=utf-8",
        filename=download_name,
    )


@app.exception_handler(HTTPException)
async def http_exception_handler(_request: Request, exc: HTTPException):
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})
