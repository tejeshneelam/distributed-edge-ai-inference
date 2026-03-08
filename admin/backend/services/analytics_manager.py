import threading
from collections import defaultdict
from typing import Dict, List

from ..models import DetectionEvent, AnalyticsResponse

MAX_TIMELINE = 100


class AnalyticsManager:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._total_vehicles: int = 0
        self._per_camera: Dict[str, int] = defaultdict(int)
        self._type_distribution: Dict[str, int] = defaultdict(int)
        self._timeline: List[dict] = []

    def record(self, event: DetectionEvent) -> None:
        with self._lock:
            self._total_vehicles += event.detected_vehicles
            self._per_camera[event.camera_id] += event.detected_vehicles
            for vtype in event.vehicle_types:
                self._type_distribution[vtype] += 1
            entry = {
                "timestamp": event.timestamp,
                "camera_id": event.camera_id,
                "detected_vehicles": event.detected_vehicles,
                "vehicle_types": event.vehicle_types,
            }
            self._timeline.append(entry)
            if len(self._timeline) > MAX_TIMELINE:
                self._timeline = self._timeline[-MAX_TIMELINE:]

    def get_summary(self) -> AnalyticsResponse:
        with self._lock:
            return AnalyticsResponse(
                total_vehicles=self._total_vehicles,
                per_camera=dict(self._per_camera),
                type_distribution=dict(self._type_distribution),
                timeline=list(self._timeline),
            )


analytics_manager = AnalyticsManager()


def get_analytics_manager() -> AnalyticsManager:
    return analytics_manager
