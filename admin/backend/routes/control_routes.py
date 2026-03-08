from fastapi import APIRouter, Depends

from ..models import DetectionEvent, CameraControlRequest
from ..services.camera_manager import CameraManager, get_camera_manager
from ..services.analytics_manager import AnalyticsManager, get_analytics_manager
from ..services.websocket_manager import WebSocketManager, get_websocket_manager

router = APIRouter()


@router.post("/camera-detection", status_code=200)
async def receive_detection(
    payload: DetectionEvent,
    camera_mgr: CameraManager = Depends(get_camera_manager),
    analytics_mgr: AnalyticsManager = Depends(get_analytics_manager),
    ws_mgr: WebSocketManager = Depends(get_websocket_manager),
) -> dict:
    camera_mgr.update_last_seen(payload.camera_id)
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
