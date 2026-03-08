from pydantic import BaseModel
from typing import Literal, Optional


class CameraRegisterRequest(BaseModel):
    camera_id: str
    hostname: str
    ip_address: str


class CameraInfo(BaseModel):
    camera_id: str
    hostname: str
    ip_address: str
    status: str = "active"
    registered_at: str
    last_seen: str


class DetectionEvent(BaseModel):
    camera_id: str
    timestamp: str
    detected_vehicles: int
    vehicle_types: list[str]
    object_counts: dict[str, int] = {}


class CameraControlRequest(BaseModel):
    camera_id: str
    command: Literal["start", "stop"]


class AnalyticsResponse(BaseModel):
    total_vehicles: int
    per_camera: dict[str, int]
    type_distribution: dict[str, int]
    timeline: list[dict]
