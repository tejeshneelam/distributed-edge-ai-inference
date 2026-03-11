"""
video_routes.py — MJPEG video stream + video upload with real YOLOv8 inference.
"""
from __future__ import annotations

import os
import tempfile
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import StreamingResponse

from backend.config import STREAM_BOUNDARY, STREAM_TIMEOUT
from backend.models import ProcessFrameRequest
from backend.services import frame_distributor, job_tracker

router = APIRouter(tags=["Stream"])

# Dedicated thread pool — one thread per CPU core keeps multiple uploads running in parallel
_executor = ThreadPoolExecutor(max_workers=max(2, (os.cpu_count() or 2)), thread_name_prefix="yolo")


@router.post(
    "/process-frame",
    summary="Coordinator local-worker: YOLOv8n inference on a dispatched JPEG frame",
)
def coordinator_process_frame(req: ProcessFrameRequest):
    """
    Kept for backward compatibility (remote workers still POST results here).
    Internally delegates to the shared InferenceService — same model, zero duplication.
    """
    import base64
    from backend.services import result_aggregator, frame_queue, inference_service

    try:
        jpeg_bytes = base64.b64decode(req.jpeg_b64)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Invalid base64: {exc}")

    result = inference_service.run(jpeg_bytes, req.frame_id)
    result_aggregator.store_frame_result(req.frame_id, result, "coordinator-local")
    frame_queue.acknowledge(req.task_id)

    return {"status": "ok", "task_id": req.task_id, "detections": len(result.detections)}


@router.get(
    "/video-stream",
    summary="MJPEG stream of annotated detection frames",
    response_description="Continuous multipart/x-mixed-replace JPEG stream",
)
def video_stream():
    return StreamingResponse(
        frame_distributor.iter_frames(boundary=STREAM_BOUNDARY, timeout=STREAM_TIMEOUT),
        media_type=f"multipart/x-mixed-replace; boundary={STREAM_BOUNDARY}",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ── Job lifecycle endpoints ───────────────────────────────────────────────────

@router.get("/jobs", summary="List all video processing jobs (newest first)")
def list_jobs():
    return job_tracker.get_all()


@router.get("/jobs/{job_id}", summary="Get status of a specific job")
def get_job(job_id: str):
    job = job_tracker.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found.")
    return job


@router.post("/upload-video", summary="Upload a video file for real YOLOv8 frame inference")
async def upload_video(file: UploadFile = File(...)):
    content_type = file.content_type or ""
    if not content_type.startswith("video/") and not (file.filename or "").lower().endswith(
        (".mp4", ".avi", ".mov", ".mkv", ".webm", ".flv")
    ):
        raise HTTPException(status_code=400, detail="Only video files are accepted.")

    content = await file.read()
    if len(content) == 0:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    suffix = Path(file.filename or "upload.mp4").suffix or ".mp4"
    # mkstemp is safe (atomic create); avoids TOCTOU race of the deprecated mktemp()
    fd, tmp_path = tempfile.mkstemp(suffix=suffix)
    with os.fdopen(fd, "wb") as fh:
        fh.write(content)

    job_id = uuid.uuid4().hex[:8]
    job_tracker.create(job_id, file.filename or "upload", len(content))
    # Submit to dedicated executor — keeps uvicorn event loop free
    _executor.submit(_process_video_file, tmp_path, job_id, file.filename or "upload")

    return {
        "job_id": job_id,
        "filename": file.filename,
        "size_bytes": len(content),
        "status": "processing",
        "message": "Video received. Real YOLOv8 inference running — results will appear shortly.",
    }


# ── Processing pipeline ───────────────────────────────────────────────────────

def _process_video_file(path: str, job_id: str, filename: str) -> None:
    # Snapshot cumulative counts BEFORE this job so we can compute the delta
    from backend.services import result_aggregator as _ra
    counts_before: dict = dict(_ra.get_summary().get("object_counts", {}))
    try:
        _run_yolo_inference(path, job_id)
        job_tracker.mark_completed(job_id)
        _report_to_admin(counts_before)
    except Exception as exc:
        print(f"[video] YOLOv8 inference failed ({exc}), falling back to cv2-only mode")
        try:
            _process_with_cv2_only(path, job_id)
            job_tracker.mark_completed(job_id)
            _report_to_admin(counts_before)
        except Exception as exc2:
            print(f"[video] cv2 also failed ({exc2})")
            job_tracker.mark_failed(job_id, str(exc2))
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass


def _report_to_admin(counts_before: dict) -> None:
    """Push the per-job detection delta (all object types) to the Admin Portal."""
    from backend.config import ADMIN_URL
    if not ADMIN_URL:
        return
    try:
        from backend.services.admin_reporter import get_reporter
        from backend.services import result_aggregator
        counts_after: dict = result_aggregator.get_summary().get("object_counts", {})
        # Delta = only what was detected in THIS job
        counts_delta = {
            k: counts_after.get(k, 0) - counts_before.get(k, 0)
            for k in counts_after
            if counts_after.get(k, 0) > counts_before.get(k, 0)
        }
        total_count = sum(counts_delta.values())
        object_types = [k for k, v in counts_delta.items() for _ in range(v)]
        get_reporter().report_job_summary(total_count, object_types, counts_delta)
    except Exception as e:
        print(f"[video] admin report error: {e}")


def _run_yolo_inference(path: str, job_id: str) -> None:
    """
    Extract 1 frame/second and dispatch each to the distributed worker pool.
    'coordinator-local' is always registered, so frames are processed locally
    unless a faster remote worker is available.
    """
    import cv2  # type: ignore
    from backend.services import frame_queue

    cap = cv2.VideoCapture(path)
    fps = cap.get(cv2.CAP_PROP_FPS) or 25
    total_frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    step = max(1, int(fps))          # sample 1 frame per second
    estimated_samples = min(60, max(1, total_frame_count // step)) if total_frame_count > 0 else 60
    job_tracker.mark_processing(job_id, estimated_samples)
    frame_num = 0
    sampled = 0

    while cap.isOpened() and sampled < 60:
        ret, frame = cap.read()
        if not ret:
            break

        if frame_num % step == 0:
            frame_id = int(time.time() * 1000) % 999999 + sampled
            ok, jpeg_buf = cv2.imencode(".jpg", frame)
            if ok:
                task_id = frame_queue.enqueue(frame_id, jpeg_buf.tobytes())
                if task_id is None:
                    print(f"[video] frame {frame_id} dropped — no workers registered")
                else:
                    job_tracker.increment_progress(job_id)
            sampled += 1

        frame_num += 1

    cap.release()
    # Update job with actual frame count (may differ from estimate)
    job_tracker.mark_processing(job_id, sampled)
    print(f"[video] job {job_id}: dispatched {sampled} frames to distributed worker pool")


def _process_with_cv2_only(path: str, job_id: str) -> None:
    """Fallback: extract frames with cv2, no inference (empty detections per frame)."""
    import cv2  # type: ignore
    from backend.models import FrameResult
    from backend.services import result_aggregator
    from datetime import datetime, timezone

    cap = cv2.VideoCapture(path)
    fps = cap.get(cv2.CAP_PROP_FPS) or 25
    step = max(1, int(fps))
    frame_num = 0
    sampled = 0
    worker_id = f"upload-{job_id}"

    while cap.isOpened() and sampled < 30:
        ret, _ = cap.read()
        if not ret:
            break
        if frame_num % step == 0:
            frame_id = int(time.time() * 1000) % 999999 + sampled
            result = FrameResult(
                frame_id=frame_id,
                worker_id=worker_id,
                detections=[],
                object_counts={},
                processing_time_ms=0.0,
                received_at=datetime.now(timezone.utc),
            )
            result_aggregator.store_frame_result(frame_id, result, worker_id)
            sampled += 1
        frame_num += 1

    cap.release()
