import threading
from datetime import datetime, timezone
from typing import Dict

from ..models import CameraInfo
from ..config import CAMERA_HEARTBEAT_TIMEOUT


class CameraManager:
    def __init__(self) -> None:
        self._cameras: Dict[str, CameraInfo] = {}
        self._lock = threading.Lock()

    def register(self, camera_id: str, hostname: str, ip_address: str) -> CameraInfo:
        with self._lock:
            now = datetime.now(timezone.utc).isoformat()
            if camera_id in self._cameras:
                cam = self._cameras[camera_id]
                cam.status = "active"
                cam.hostname = hostname
                cam.ip_address = ip_address
                cam.last_seen = now
            else:
                cam = CameraInfo(
                    camera_id=camera_id,
                    hostname=hostname,
                    ip_address=ip_address,
                    status="active",
                    registered_at=now,
                    last_seen=now,
                )
                self._cameras[camera_id] = cam
            return cam

    def get_all(self) -> list[CameraInfo]:
        with self._lock:
            self._refresh_status()
            return list(self._cameras.values())

    def update_last_seen(self, camera_id: str) -> None:
        with self._lock:
            if camera_id in self._cameras:
                self._cameras[camera_id].last_seen = datetime.now(timezone.utc).isoformat()
                self._cameras[camera_id].status = "active"

    def _refresh_status(self) -> None:
        """Mark cameras offline if heartbeat timeout exceeded (called while lock held)."""
        now = datetime.now(timezone.utc)
        for cam in self._cameras.values():
            try:
                last = datetime.fromisoformat(cam.last_seen)
                if last.tzinfo is None:
                    last = last.replace(tzinfo=timezone.utc)
                elapsed = (now - last).total_seconds()
                if elapsed > CAMERA_HEARTBEAT_TIMEOUT:
                    cam.status = "offline"
            except (ValueError, TypeError):
                pass


camera_manager = CameraManager()


def get_camera_manager() -> CameraManager:
    return camera_manager
