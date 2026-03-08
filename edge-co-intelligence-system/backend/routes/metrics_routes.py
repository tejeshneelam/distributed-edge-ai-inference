"""
metrics_routes.py — API endpoint for live system metrics.
"""
from __future__ import annotations

from fastapi import APIRouter

from backend.models import SystemMetrics
from backend.services import metrics_service

router = APIRouter(tags=["Metrics"])


@router.get("/metrics", response_model=SystemMetrics)
def get_metrics():
    """
    Return live system metrics.

    - number_of_workers: currently registered workers
    - total_frames_processed: frames stored so far
    - processing_fps: frames per second since system start
    - system_start_time: UTC timestamp when the server started
    """
    return metrics_service.get_metrics()
