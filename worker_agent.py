"""
worker_agent.py — Standalone FastAPI app for edge worker nodes.

Each laptop / edge device runs this script.  It:
  1. Registers itself with the coordinator on startup.
  2. Sends a heartbeat every HEARTBEAT_INTERVAL_SECS seconds.
  3. Exposes  POST /process-frame  — receives a JPEG frame, runs YOLOv8n locally,
     then POSTs the FrameResult back to the coordinator's  POST /results  endpoint.
  4. Exposes  GET  /health         — liveness probe.

Usage
-----
    python3 worker_agent.py \\
        --coordinator http://192.168.1.100:8000 \\
        --worker-id   laptop-2 \\
        --host        0.0.0.0 \\
        --port        8001

The --worker-id defaults to the machine's hostname if not specified.
"""
from __future__ import annotations

import argparse
import base64
import socket
import sys
import threading
import time
from datetime import datetime, timezone
from typing import Any

import httpx
import uvicorn
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

# ── CLI args (parsed before the FastAPI app is created) ──────────────────────

def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Edge worker agent")
    parser.add_argument(
        "--coordinator",
        required=True,
        help="Base URL of the coordinator, e.g. http://192.168.1.100:8000",
    )
    parser.add_argument(
        "--worker-id",
        default=socket.gethostname(),
        help="Unique worker identifier (default: hostname)",
    )
    parser.add_argument("--host", default="0.0.0.0", help="Bind host (default 0.0.0.0)")
    parser.add_argument("--port", type=int, default=8001, help="Listen port (default 8001)")
    parser.add_argument(
        "--confidence-threshold",
        type=float,
        default=0.4,
        help="Minimum detection confidence to report (default 0.4)",
    )
    return parser.parse_args()


_args = _parse_args()

COORDINATOR_URL: str = _args.coordinator.rstrip("/")
WORKER_ID: str = _args.worker_id
WORKER_HOST: str = _args.host
WORKER_PORT: int = _args.port
HEARTBEAT_INTERVAL_SECS: int = 10
CONFIDENCE_THRESHOLD: float = _args.confidence_threshold

# Labels that trigger an immediate alert to the coordinator when detected
# at high confidence (≥0.75). Add/remove labels to tune alert sensitivity.
ALERT_LABELS: frozenset[str] = frozenset({
    "person", "car", "truck", "bus", "motorcycle", "bicycle",
})
ALERT_CONFIDENCE: float = 0.75

# ── Lazy-loaded YOLO model ────────────────────────────────────────────────────

_yolo_model: Any = None
_yolo_lock = threading.Lock()  # serialise concurrent inference calls (YOLO is not thread-safe)


def _get_model() -> Any:
    global _yolo_model
    if _yolo_model is None:
        from ultralytics import YOLO  # type: ignore
        _yolo_model = YOLO("yolov8n.pt")
    return _yolo_model


# ── FastAPI app ───────────────────────────────────────────────────────────────

app = FastAPI(title=f"Edge Worker Agent [{WORKER_ID}]", version="1.0.0")


def _post_alert(payload: dict) -> None:
    """Fire-and-forget: POST alert to coordinator without blocking the request handler."""
    try:
        httpx.post(f"{COORDINATOR_URL}/alerts", json=payload, timeout=4.0)
        print(f"[worker] ALERT → {payload['alert_labels']} in frame {payload['frame_id']}")
    except httpx.HTTPError as exc:
        print(f"[worker] alert POST failed (non-fatal): {exc}")


class ProcessFrameRequest(BaseModel):
    task_id: str
    frame_id: int
    jpeg_b64: str   # base64-encoded JPEG bytes


@app.post("/process-frame", summary="Receive a frame, run YOLOv8, return result to coordinator")
def process_frame(req: ProcessFrameRequest) -> dict:
    # Decode JPEG
    try:
        jpeg_bytes = base64.b64decode(req.jpeg_b64)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Invalid base64 payload: {exc}")

    import cv2  # type: ignore
    import numpy as np

    nparr = np.frombuffer(jpeg_bytes, np.uint8)
    frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    if frame is None:
        raise HTTPException(status_code=400, detail="Could not decode JPEG frame.")

    # Run local YOLOv8 inference
    model = _get_model()
    t0 = time.perf_counter()
    with _yolo_lock:
        results = model(frame, verbose=False)
    elapsed_ms = (time.perf_counter() - t0) * 1000

    detections: list[dict] = []
    counts: dict[str, int] = {}

    for r in results:
        boxes = r.boxes
        if boxes is None:
            continue
        for box in boxes:
            conf = float(box.conf[0])
            # ── Edge autonomy: filter below local confidence threshold ──
            if conf < CONFIDENCE_THRESHOLD:
                continue
            label = model.names[int(box.cls[0])]
            x1, y1, x2, y2 = box.xyxy[0].tolist()
            detections.append({
                "label": label,
                "confidence": round(conf, 3),
                "box": {"x1": int(x1), "y1": int(y1), "x2": int(x2), "y2": int(y2)},
            })
            counts[label] = counts.get(label, 0) + 1

    # ── Event-driven alerts: raise high-confidence events without waiting for poll ──
    alert_hits = [
        d for d in detections
        if d["confidence"] >= ALERT_CONFIDENCE and d["label"] in ALERT_LABELS
    ]
    if alert_hits:
        alert_payload = {
            "worker_id": WORKER_ID,
            "frame_id": req.frame_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "detections": alert_hits,
            "alert_labels": list({d["label"] for d in alert_hits}),
        }
        threading.Thread(target=_post_alert, args=(alert_payload,), daemon=True).start()

    # Build FrameResult payload for the coordinator
    frame_result = {
        "frame_id": req.frame_id,
        "worker_id": WORKER_ID,
        "detections": detections,
        "object_counts": counts,
        "processing_time_ms": round(elapsed_ms, 2),
        "received_at": datetime.now(timezone.utc).isoformat(),
    }

    # POST result back to coordinator
    try:
        resp = httpx.post(
            f"{COORDINATOR_URL}/results",
            json=frame_result,
            timeout=8.0,
        )
        resp.raise_for_status()
    except httpx.HTTPError as exc:
        print(f"[worker] WARNING: failed to POST result to coordinator: {exc}")
        # Still return the result locally — coordinator watchdog will handle retry
        return {"status": "result_delivery_failed", "result": frame_result}

    # Acknowledge task in coordinator's in-flight queue
    try:
        httpx.post(
            f"{COORDINATOR_URL}/queue/acknowledge/{req.task_id}",
            timeout=4.0,
        )
    except httpx.HTTPError:
        pass  # Non-fatal — watchdog cleans up stale tasks

    print(
        f"[worker] frame {req.frame_id} | {len(detections)} detections "
        f"| {elapsed_ms:.1f} ms | task {req.task_id}"
    )
    return {"status": "ok", "task_id": req.task_id, "detections": len(detections)}


@app.get("/health", summary="Liveness check")
def health() -> dict:
    return {"status": "ok", "worker_id": WORKER_ID}


# ── Background: registration + heartbeat ─────────────────────────────────────

def _register_with_coordinator() -> None:
    """POST /register-worker on startup; retries up to 5 times."""
    payload = {
        "worker_id": WORKER_ID,
        "hostname": socket.gethostname(),
        "ip_address": _local_ip(),
        "port": WORKER_PORT,
        "capabilities": ["yolov8n"],
    }
    for attempt in range(1, 6):
        try:
            resp = httpx.post(
                f"{COORDINATOR_URL}/register-worker",
                json=payload,
                timeout=6.0,
            )
            resp.raise_for_status()
            print(f"[worker] registered with coordinator as '{WORKER_ID}'")
            return
        except httpx.HTTPError as exc:
            print(f"[worker] registration attempt {attempt}/5 failed: {exc}")
            time.sleep(3)
    print("[worker] ERROR: could not register with coordinator — check --coordinator URL")


def _heartbeat_loop() -> None:
    """Send heartbeat to coordinator every HEARTBEAT_INTERVAL_SECS seconds."""
    while True:
        time.sleep(HEARTBEAT_INTERVAL_SECS)
        try:
            resp = httpx.post(
                f"{COORDINATOR_URL}/workers/{WORKER_ID}/heartbeat",
                timeout=4.0,
            )
            # 404 means coordinator restarted and lost our registration — re-register now
            if resp.status_code == 404:
                print(f"[worker] heartbeat 404 — coordinator lost registration, re-registering")
                threading.Thread(target=_register_with_coordinator, daemon=True, name="re-register").start()
        except httpx.HTTPError as exc:
            print(f"[worker] heartbeat failed: {exc}")


def _local_ip() -> str:
    """Best-effort: return the machine's LAN IP address."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"


@app.on_event("startup")
async def startup() -> None:
    """Register with coordinator and start heartbeat thread."""
    threading.Thread(target=_register_with_coordinator, daemon=True, name="register").start()
    threading.Thread(target=_heartbeat_loop, daemon=True, name="heartbeat").start()
    print(f"[worker] agent '{WORKER_ID}' starting on port {WORKER_PORT}")
    print(f"[worker] coordinator: {COORDINATOR_URL}")


@app.on_event("shutdown")
async def shutdown() -> None:
    """Deregister from coordinator immediately so it stops dispatching frames."""
    try:
        httpx.delete(f"{COORDINATOR_URL}/workers/{WORKER_ID}", timeout=3.0)
        print(f"[worker] deregistered '{WORKER_ID}' from coordinator")
    except httpx.HTTPError:
        pass


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    uvicorn.run(
        "worker_agent:app",
        host=WORKER_HOST,
        port=WORKER_PORT,
        reload=False,
    )
