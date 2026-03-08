"""
main.py — FastAPI application entry point for the Edge Co-Intelligence backend.

Run with:
    uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
"""
from __future__ import annotations

import threading
import time

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.config import CORS_ORIGINS
from backend.routes.worker_routes import router as worker_router
from backend.routes.result_routes import router as result_router
from backend.routes.metrics_routes import router as metrics_router
from backend.routes.video_routes import router as video_router

app = FastAPI(
    title="Edge Co-Intelligence API",
    description=(
        "Distributed ML inference coordinator — manages worker nodes, "
        "aggregates YOLOv8 detection results, and streams annotated frames."
    ),
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(worker_router)
app.include_router(result_router)
app.include_router(metrics_router)
app.include_router(video_router)


# ── Fault-Tolerance: background eviction thread ───────────────────────────────

def _eviction_loop() -> None:
    """
    Runs every 10 s in a daemon thread.
    Marks workers 'offline' when their last heartbeat is older than 30 s.
    Also keeps 'coordinator-local' alive — it has no external heartbeat sender.
    """
    from backend.services import worker_manager  # late import avoids circular deps
    while True:
        time.sleep(10)
        # Refresh coordinator-local so evict_stale() never marks it offline
        worker_manager.heartbeat("coordinator-local")
        evicted = worker_manager.evict_stale()
        for wid in evicted:
            print(f"[coordinator] worker '{wid}' marked offline — heartbeat timeout")


@app.on_event("startup")
async def startup() -> None:
    """Start background maintenance threads and register coordinator as local worker."""
    threading.Thread(target=_eviction_loop, daemon=True, name="worker-eviction").start()
    print("[coordinator] eviction watchdog started")

    # Start Admin reporter if ADMIN_URL is configured
    from backend.config import ADMIN_URL
    if ADMIN_URL:
        from backend.services.admin_reporter import AdminReporter
        reporter = AdminReporter()
        reporter.start()
        print(f"[coordinator] admin reporter started → {ADMIN_URL}")

    # Register the coordinator itself as a worker so it participates in load balancing.
    # Frames are dispatched to http://127.0.0.1:8000/process-frame when coordinator-local
    # is the least-loaded node — eliminating the need for a separate local YOLO fallback.
    from backend.services import worker_manager
    from backend.models import WorkerRegisterRequest
    worker_manager.register(WorkerRegisterRequest(
        worker_id="coordinator-local",
        host="127.0.0.1",
        port=8000,
        capabilities=["yolov8n"],
    ))
    print("[coordinator] registered coordinator-local as worker (port 8000)")


# ── Health ─────────────────────────────────────────────────────────────────────

@app.get("/health", tags=["Health"])
def health():
    """Liveness check."""
    return {"status": "ok"}
