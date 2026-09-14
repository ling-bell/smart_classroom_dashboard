"""FastAPI 服务入口。

启动方式（项目根目录下）：
    D:/python/python.exe -m webapp.server
或
    uvicorn webapp.server:app --host 0.0.0.0 --port 8000

接口概览：
    GET  /                      前端单页
    POST /api/analyze           上传图片/视频，返回 job_id（异步执行）
    GET  /api/jobs              历史任务列表
    GET  /api/jobs/{id}         查询单个任务状态/进度/结果
    GET  /api/jobs/{id}/report  报告纯文本
    GET  /outputs/...           任务产物（看板/报告/标注媒体）
"""
from __future__ import annotations

import logging
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles

from webapp.manager import JobManager

BASE_DIR = Path(__file__).resolve().parent.parent  # 项目根目录
OUTPUT_DIR = BASE_DIR / "output"
STATIC_DIR = Path(__file__).resolve().parent / "static"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

app = FastAPI(title="智慧课堂分析系统", description="课堂专注度分析 Web 服务", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

manager = JobManager(OUTPUT_DIR)
# 把旧版本用 mp4v 编码生成的历史标注视频自动转码为浏览器可播放的 H.264
manager.repair_legacy_videos()

# 任务产物目录（看板/报告/标注媒体）
app.mount("/outputs", StaticFiles(directory=str(OUTPUT_DIR)), name="outputs")
# 前端静态资源
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/", include_in_schema=False)
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/api/analyze")
async def analyze(file: UploadFile = File(...)) -> dict:
    filename = file.filename or "upload"
    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="文件内容为空")
    try:
        job = manager.submit_file(filename, content)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"job": job}


@app.get("/api/jobs")
def list_jobs() -> dict:
    return {"jobs": manager.list_jobs()}


@app.get("/api/jobs/{job_id}")
def get_job(job_id: str) -> dict:
    job = manager.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="任务不存在")
    return {"job": job}


@app.get("/api/jobs/{job_id}/report")
def get_report(job_id: str):
    text = manager.report_text(job_id)
    if text is None:
        raise HTTPException(status_code=404, detail="报告不存在或尚未生成")
    return PlainTextResponse(text)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("webapp.server:app", host="0.0.0.0", port=8000, reload=False)
