from fastapi import APIRouter, Depends, HTTPException

from ..models import CameraRegisterRequest, CameraInfo
from ..services.camera_manager import CameraManager, get_camera_manager

router = APIRouter()


@router.post("/register-camera", response_model=CameraInfo)
def register_camera(
    payload: CameraRegisterRequest,
    manager: CameraManager = Depends(get_camera_manager),
) -> CameraInfo:
    return manager.register(payload.camera_id, payload.hostname, payload.ip_address)


@router.get("/cameras", response_model=list[CameraInfo])
def list_cameras(manager: CameraManager = Depends(get_camera_manager)) -> list[CameraInfo]:
    return manager.get_all()


@router.post("/heartbeat/{camera_id}", status_code=200)
def heartbeat(camera_id: str, manager: CameraManager = Depends(get_camera_manager)) -> dict:
    if not manager.update_last_seen(camera_id):
        raise HTTPException(status_code=404, detail="Camera not registered")
    return {"status": "ok", "camera_id": camera_id}


@router.delete("/cameras/{camera_id}", status_code=200)
def remove_camera(camera_id: str, manager: CameraManager = Depends(get_camera_manager)) -> dict:
    manager.remove(camera_id)
    return {"status": "removed", "camera_id": camera_id}
