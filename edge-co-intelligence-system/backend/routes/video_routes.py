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
from typing import Optional

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import StreamingResponse

from backend.config import STREAM_BOUNDARY, STREAM_TIMEOUT, CONFIDENCE_THRESHOLD
from backend.models import ProcessFrameRequest
from backend.services import frame_distributor, job_tracker

router = APIRouter(tags=["Stream"])

# Colour palette for drawing bounding boxes
_BOX_COLOURS = [
    (0, 255, 0), (255, 0, 0), (0, 165, 255), (255, 255, 0),
    (0, 255, 255), (255, 0, 255), (128, 255, 0), (0, 128, 255),
]

# Dedicated thread pool — one thread per CPU core keeps multiple uploads running in parallel
_executor = ThreadPoolExecutor(max_workers=max(2, (os.cpu_count() or 2)), thread_name_prefix="yolo")

# Module-level YOLO model — loaded once, reused across uploads
_yolo_model: Optional[object] = None


def _get_model():
    """Lazy-load YOLOv8n; downloads ~6 MB weights on first call."""
    global _yolo_model
    if _yolo_model is None:
        from ultralytics import YOLO  # type: ignore
        _yolo_model = YOLO("yolov8n.pt")
    return _yolo_model


@router.post(
    "/process-frame",
    summary="Coordinator local-worker: YOLOv8n inference on a dispatched JPEG frame",
)
def coordinator_process_frame(req: ProcessFrameRequest):
    """
    Allows the coordinator to act as a worker in its own distributed pool.
    FrameQueue dispatches frames here when 'coordinator-local' is least-loaded.
    Applies the configured CONFIDENCE_THRESHOLD before storing results.
    """
    import base64
    import cv2  # type: ignore
    import numpy as np  # type: ignore
    from backend.models import Detection, BoundingBox, FrameResult
    from backend.services import result_aggregator, frame_queue
    from datetime import datetime, timezone
    from fastapi import HTTPException

    try:
        jpeg_bytes = base64.b64decode(req.jpeg_b64)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Invalid base64: {exc}")

    nparr = np.frombuffer(jpeg_bytes, np.uint8)
    frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    if frame is None:
        raise HTTPException(status_code=400, detail="Could not decode JPEG frame.")

    model = _get_model()
    t0 = time.perf_counter()
    results = model(frame, verbose=False)
    elapsed_ms = (time.perf_counter() - t0) * 1000

    detections: list[Detection] = []
    counts: dict[str, int] = {}
    for r in results:
        boxes = r.boxes
        if boxes is None:
            continue
        for box in boxes:
            conf = float(box.conf[0])
            if conf < CONFIDENCE_THRESHOLD:        # edge autonomy: local filter
                continue
            label = model.names[int(box.cls[0])]
            x1, y1, x2, y2 = box.xyxy[0].tolist()
            detections.append(Detection(
                label=label,
                confidence=round(conf, 3),
                box=BoundingBox(x1=int(x1), y1=int(y1), x2=int(x2), y2=int(y2)),
            ))
            counts[label] = counts.get(label, 0) + 1

    stored = FrameResult(
        frame_id=req.frame_id,
        worker_id="coordinator-local",
        detections=detections,
        object_counts=counts,
        processing_time_ms=round(elapsed_ms, 2),
        received_at=datetime.now(timezone.utc),
    )
    result_aggregator.store_frame_result(req.frame_id, stored, "coordinator-local")
    frame_queue.acknowledge(req.task_id)

    # ── Push annotated frame to the MJPEG live stream ─────────────────────
    _push_annotated_frame(frame, detections)

    return {"status": "ok", "task_id": req.task_id, "detections": len(detections)}


def _push_annotated_frame(frame, detections) -> None:
    """Draw bounding boxes + labels on the frame and push to MJPEG stream."""
    import cv2
    for i, det in enumerate(detections):
        colour = _BOX_COLOURS[i % len(_BOX_COLOURS)]
        b = det.box
        cv2.rectangle(frame, (b.x1, b.y1), (b.x2, b.y2), colour, 2)
        label_text = f"{det.label} {det.confidence:.0%}"
        (tw, th), _ = cv2.getTextSize(label_text, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
        cv2.rectangle(frame, (b.x1, b.y1 - th - 6), (b.x1 + tw + 4, b.y1), colour, -1)
        cv2.putText(frame, label_text, (b.x1 + 2, b.y1 - 4),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 1)
    ok, jpeg_buf = cv2.imencode(".jpg", frame)
    if ok:
        frame_distributor.push(jpeg_buf.tobytes())


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
    try:
        _run_yolo_inference(path, job_id)
        job_tracker.mark_completed(job_id)
    except Exception as exc:
        print(f"[video] YOLOv8 inference failed ({exc}), falling back to cv2-only mode")
        try:
            _process_with_cv2_only(path, job_id)
            job_tracker.mark_completed(job_id)
        except Exception as exc2:
            print(f"[video] cv2 also failed ({exc2})")
            job_tracker.mark_failed(job_id, str(exc2))
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass


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
