from fastapi import APIRouter, Depends

from ..models import DetectionEvent, CameraControlRequest, CameraAlertEvent
from ..services.camera_manager import CameraManager, get_camera_manager
from ..services.analytics_manager import AnalyticsManager, get_analytics_manager
from ..services.websocket_manager import WebSocketManager, get_websocket_manager

router = APIRouter()

# ── In-memory alert store (newest last) ───────────────────────────────────────
_MAX_ALERTS = 200
_alerts: list[dict] = []
_alerts_lock = __import__("threading").Lock()


@router.post("/camera-detection", status_code=200)
async def receive_detection(
    payload: DetectionEvent,
    camera_mgr: CameraManager = Depends(get_camera_manager),
    analytics_mgr: AnalyticsManager = Depends(get_analytics_manager),
    ws_mgr: WebSocketManager = Depends(get_websocket_manager),
) -> dict:
    camera_mgr.update_last_seen(payload.camera_id)  # auto-register keepalive
    analytics_mgr.record(payload)
    await ws_mgr.broadcast({"type": "detection", "data": payload.model_dump()})
    return {"status": "ok"}


@router.post("/camera-control", status_code=200)
async def camera_control(
    payload: CameraControlRequest,
    ws_mgr: WebSocketManager = Depends(get_websocket_manager),
) -> dict:
    await ws_mgr.broadcast({"type": "control", "data": payload.model_dump()})
    return {"status": "ok", "camera_id": payload.camera_id, "command": payload.command}


@router.post("/camera-alerts", status_code=201)
async def receive_alert(
    payload: CameraAlertEvent,
    ws_mgr: WebSocketManager = Depends(get_websocket_manager),
) -> dict:
    """Accept a smart alert pushed from a coordinator node."""
    alert_dict = payload.model_dump()
    with _alerts_lock:
        if len(_alerts) >= _MAX_ALERTS:
            _alerts.pop(0)
        _alerts.append(alert_dict)
    await ws_mgr.broadcast({"type": "alert", "data": alert_dict})
    return {"status": "ok"}


@router.get("/camera-alerts", status_code=200)
def get_alerts() -> list[dict]:
    """Return recent alerts from all coordinators, newest first."""
    with _alerts_lock:
        return list(reversed(_alerts))
