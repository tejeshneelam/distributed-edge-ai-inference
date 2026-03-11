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

@router.get("/admin-analytics")
def get_admin_analytics():
    """Proxy admin analytics from the configured ADMIN_URL to the frontend dashboard."""
    from backend.config import ADMIN_URL
    import httpx
    if not ADMIN_URL:
        from fastapi import HTTPException
        raise HTTPException(status_code=503, detail="ADMIN_URL not configured")
    try:
        r = httpx.get(f"{ADMIN_URL}/analytics", timeout=5.0)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        from fastapi import HTTPException
        raise HTTPException(status_code=502, detail=f"Admin unreachable: {e}")
