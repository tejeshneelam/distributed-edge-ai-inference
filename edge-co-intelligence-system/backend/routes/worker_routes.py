"""
worker_routes.py — API endpoints for worker node registration, heartbeat, and management.

Implements:
  - POST /register-worker         — worker self-registers (REST flow)
  - POST /workers/register        — socket-based registration
  - POST /workers/{id}/heartbeat  — fault tolerance: keep-alive ping
  - GET  /workers                 — list all workers with status
  - DELETE /workers/{id}          — deregister a worker
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from backend.models import SuccessResponse, WorkerInfo, WorkerNodeRequest, WorkerRegisterRequest
from backend.services import worker_manager

router = APIRouter(tags=["Workers"])


@router.post("/register-worker", response_model=SuccessResponse, status_code=201)
def register_worker_node(req: WorkerNodeRequest):
    """Register a worker node by hostname and IP address."""
    worker = worker_manager.register_node(req)
    return SuccessResponse(
        message=f"Worker '{worker.worker_id}' registered successfully.",
        data=worker,
    )


@router.post("/workers/register", response_model=SuccessResponse, status_code=201)
def register_worker(req: WorkerRegisterRequest):
    """Register a worker node by host and port (socket coordinator flow)."""
    worker = worker_manager.register(req)
    return SuccessResponse(
        message=f"Worker '{worker.worker_id}' registered successfully.",
        data=worker,
    )


@router.post("/workers/{worker_id}/heartbeat", response_model=SuccessResponse)
def worker_heartbeat(worker_id: str):
    """
    Fault-tolerance heartbeat endpoint.
    Workers call this every ~10 s to signal they are alive.
    Workers silent for >30 s are marked 'offline' by the eviction task.
    """
    ok = worker_manager.heartbeat(worker_id)
    if not ok:
        raise HTTPException(
            status_code=404,
            detail=f"Worker '{worker_id}' is not registered. Register first.",
        )
    return SuccessResponse(message=f"Heartbeat recorded for '{worker_id}'.")


@router.get("/workers", response_model=list[WorkerInfo])
def list_workers():
    """Return all currently registered worker nodes with their status and load."""
    return worker_manager.get_all()


@router.delete("/workers/{worker_id}", response_model=SuccessResponse)
def remove_worker(worker_id: str):
    """Unregister a worker node."""
    removed = worker_manager.remove(worker_id)
    if not removed:
        raise HTTPException(status_code=404, detail=f"Worker '{worker_id}' not found.")
    return SuccessResponse(message=f"Worker '{worker_id}' removed.")


# ── Queue management routes ───────────────────────────────────────────────────

@router.get("/queue/stats", summary="Distributed task queue statistics")
def queue_stats():
    """Return the number of pending and in-flight frame tasks."""
    from backend.services import frame_queue
    return frame_queue.stats()


@router.post("/queue/acknowledge/{task_id}", response_model=SuccessResponse)
def acknowledge_task(task_id: str):
    """
    Called by a worker agent after it has successfully POSTed its result.
    Removes the task from the in-flight table so the watchdog won't retry it.
    """
    from backend.services import frame_queue
    frame_queue.acknowledge(task_id)
    return SuccessResponse(message=f"Task '{task_id}' acknowledged.")
