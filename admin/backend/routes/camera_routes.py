from fastapi import APIRouter, Depends

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
