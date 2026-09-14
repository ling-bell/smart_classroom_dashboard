"""后台分析任务管理器。

设计要点：
- 上传文件保存到独立任务目录 ``output/jobs/<id>/``，分析产物（看板/报告/标注视频）也
  写入该目录，天然自包含，便于静态托管、下载与清理。
- 使用单 worker 线程顺序执行分析：YOLO 推理并非线程安全，且分析引擎里缓存了模型，
  串行执行最稳妥，长任务自动排队。
- 分析引擎懒加载：首次真正跑任务时才加载 YOLO 模型，避免服务启动过慢。
- 历史索引持久化到 ``output/jobs/_history.json``，重启后仍可查看。
"""
from __future__ import annotations

import json
import logging
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path

logger = logging.getLogger("smart_classroom.web")

ALLOWED_IMAGE = {".jpg", ".jpeg", ".png", ".bmp"}
ALLOWED_VIDEO = {".mp4", ".avi", ".mov", ".mkv"}
ALLOWED = ALLOWED_IMAGE | ALLOWED_VIDEO

# 返回给前端的指标字段（剔除 detailed_data 等大对象，控制 JSON 体积）
SUMMARY_KEYS = [
    "total_samples", "unique_students", "avg_attention", "min_attention",
    "max_attention", "median_attention", "is_video", "video_duration",
]


class JobManager:
    def __init__(self, output_root: Path) -> None:
        self.output_root = Path(output_root)
        self.jobs_root = self.output_root / "jobs"
        self.jobs_root.mkdir(parents=True, exist_ok=True)
        self._history_path = self.jobs_root / "_history.json"
        self._lock = threading.Lock()
        self._jobs: dict[str, dict] = {}
        self._engine = None
        self._engine_lock = threading.Lock()
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="analysis")
        self._load_history()

    # ------------------------------------------------------------------ #
    # 公共 API
    # ------------------------------------------------------------------ #
    def submit_file(self, filename: str, content: bytes) -> dict:
        ext = Path(filename).suffix.lower()
        if ext not in ALLOWED:
            raise ValueError(f"不支持的文件格式: {filename}（支持 {'/'.join(sorted(ALLOWED))}）")
        if not content:
            raise ValueError("文件内容为空")

        job_id = uuid.uuid4().hex[:16]
        job_dir = self.jobs_root / job_id
        job_dir.mkdir(parents=True, exist_ok=True)
        (job_dir / ("source" + ext)).write_bytes(content)

        job = {
            "id": job_id,
            "filename": Path(filename).name,
            "ext": ext,
            "file_kind": "video" if ext in ALLOWED_VIDEO else "image",
            "status": "pending",
            "progress": 0,
            "message": "等待处理",
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "finished_at": None,
            "error": None,
            "files": {},
            "summary": {},
        }
        with self._lock:
            self._jobs[job_id] = job
        self._persist()
        self._executor.submit(self._run, job_id)
        return dict(job)

    def get(self, job_id: str) -> dict | None:
        with self._lock:
            job = self._jobs.get(job_id)
            return dict(job) if job else None

    def list_jobs(self) -> list[dict]:
        with self._lock:
            jobs = list(self._jobs.values())
        jobs.sort(key=lambda j: j["created_at"], reverse=True)
        return [dict(j) for j in jobs]

    def report_text(self, job_id: str) -> str | None:
        job_dir = self.jobs_root / job_id
        if not job_dir.is_dir():
            return None
        reports = sorted(job_dir.glob("report_*.md"))
        if not reports:
            return None
        try:
            return reports[0].read_text(encoding="utf-8")
        except Exception:
            logger.exception("读取报告失败: %s", job_id)
            return None

    def repair_legacy_videos(self) -> int:
        """把历史任务里遗留的 mp4v 标注视频转码为浏览器可播放的 H.264。

        旧版本用 OpenCV 的 mp4v 编码写视频，浏览器无法播放；此方法在服务启动时
        自动修复，无需重新跑 YOLO。返回修复数量。
        """
        from media_utils import ensure_h264, is_browser_playable  # 延迟导入

        repaired = 0
        for vid in sorted(self.jobs_root.glob("*/annotated_video_*.mp4")):
            if vid.name.endswith("_raw.mp4"):
                continue
            if is_browser_playable(vid):
                continue
            tmp = vid.with_name(vid.stem + "_h264_tmp.mp4")
            try:
                ensure_h264(str(vid), str(tmp))
                if tmp.exists() and tmp != vid:
                    vid.unlink(missing_ok=True)
                    tmp.replace(vid)
                repaired += 1
            except Exception:  # noqa: BLE001
                logger.exception("修复历史视频失败: %s", vid)
        if repaired:
            logger.info("已修复 %d 个历史标注视频为 H.264", repaired)
        return repaired

    # ------------------------------------------------------------------ #
    # 内部实现
    # ------------------------------------------------------------------ #
    def _engine_instance(self):
        """懒加载共享分析引擎（含 YOLO 模型），只在首次执行任务时初始化。"""
        if self._engine is None:
            with self._engine_lock:
                if self._engine is None:
                    from main import SmartClassroomDashboard  # 延迟导入避免拖慢启动

                    logger.info("首次任务：正在加载分析引擎（YOLO 模型）...")
                    self._engine = SmartClassroomDashboard()
                    logger.info("分析引擎就绪")
        return self._engine

    def _run(self, job_id: str) -> None:
        job = self.get(job_id)
        if job is None:
            return
        self._update(job_id, status="running", progress=1, message="加载模型中…")

        try:
            engine = self._engine_instance()
        except Exception as exc:  # noqa: BLE001
            logger.exception("引擎加载失败: %s", job_id)
            self._fail(job_id, f"模型加载失败：{exc}")
            return

        job_dir = self.jobs_root / job_id
        source = job_dir / ("source" + job["ext"])
        try:
            dashboard_path, _report_path, results = engine.run_analysis(
                str(source),
                output_dir=str(job_dir),
                progress=lambda p, m: self._update(job_id, progress=p, message=m),
            )
            files = {
                "dashboard": "/outputs/jobs/" + job_id + "/" + Path(dashboard_path).name,
                "report": "/outputs/jobs/" + job_id + "/" + Path(_report_path).name,
            }
            media = self._find_media(job_dir)
            if media:
                files["media"] = "/outputs/jobs/" + job_id + "/" + media
            summary = {k: results.get(k) for k in SUMMARY_KEYS}
            self._update(
                job_id,
                status="done",
                progress=100,
                message="分析完成",
                finished_at=datetime.now().isoformat(timespec="seconds"),
                files=files,
                summary=summary,
            )
        except Exception as exc:  # noqa: BLE001
            logger.exception("任务执行失败: %s", job_id)
            self._fail(job_id, str(exc))

    def _find_media(self, job_dir: Path) -> str | None:
        for pattern in ("annotated_video_*.mp4", "annotated_image_*.jpg"):
            hits = sorted(job_dir.glob(pattern))
            if hits:
                return hits[0].name
        return None

    def _fail(self, job_id: str, message: str) -> None:
        self._update(
            job_id,
            status="error",
            message="处理失败",
            error=message,
            finished_at=datetime.now().isoformat(timespec="seconds"),
        )

    def _update(self, job_id: str, **fields) -> None:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                return
            for key, value in fields.items():
                if value is None:
                    continue
                if key == "summary" and isinstance(value, dict):
                    job["summary"] = {k: value.get(k) for k in SUMMARY_KEYS}
                else:
                    job[key] = value
        if fields.get("status") in ("done", "error"):
            self._persist()

    def _persist(self) -> None:
        try:
            with self._lock:
                snapshot = list(self._jobs.values())
            tmp = self._history_path.with_suffix(".tmp")
            tmp.write_text(json.dumps(snapshot, ensure_ascii=False, indent=1), encoding="utf-8")
            tmp.replace(self._history_path)
        except Exception:  # noqa: BLE001
            logger.exception("保存历史索引失败")

    def _load_history(self) -> None:
        if not self._history_path.exists():
            return
        try:
            data = json.loads(self._history_path.read_text(encoding="utf-8"))
            for job in data:
                if job.get("id"):
                    self._jobs[job["id"]] = job
            logger.info("已载入历史任务 %d 条", len(self._jobs))
        except Exception:  # noqa: BLE001
            logger.exception("读取历史索引失败")
