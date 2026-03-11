"""
inference_service.py — In-process YOLOv8 inference for the coordinator-local worker.

Eliminates the HTTP round-trip overhead when the coordinator processes frames locally.
The YOLO model is loaded once and guarded by a threading lock (ultralytics is not
thread-safe).  Remote workers still use the HTTP dispatch path in frame_queue.py.

Smart alerts:
  - Pedestrian Near Traffic (critical): person + heavy vehicle in same frame
  - Traffic Congestion (warning): vehicle count exceeds threshold
  - Slow Inference (warning): processing time exceeds threshold
"""
from __future__ import annotations

import threading
import time
from typing import Optional

import cv2  # type: ignore
import numpy as np  # type: ignore

from backend.config import (
    CONFIDENCE_THRESHOLD,
    MODEL_NAME,
    ALERT_CONFIDENCE,
    ALERT_CONGESTION_THRESHOLD,
    ALERT_SLOW_INFERENCE_MS,
)
from backend.models import BoundingBox, Detection, FrameResult
from datetime import datetime, timezone

# Labels used by alert logic
_HEAVY_VEHICLES = frozenset({"truck", "bus"})
_ALL_VEHICLES = frozenset({"car", "truck", "bus", "motorcycle", "bicycle"})


class InferenceService:
    """Thread-safe, singleton-style YOLO inference runner."""

    def __init__(self) -> None:
        self._model: Optional[object] = None
        self._lock = threading.Lock()

    def load_model(self) -> None:
        """Eagerly load the YOLO model at startup."""
        from ultralytics import YOLO  # type: ignore
        self._model = YOLO(MODEL_NAME)
        print(f"[inference] YOLOv8 model '{MODEL_NAME}' loaded")

    def _get_model(self):
        if self._model is None:
            self.load_model()
        return self._model

    def run(self, jpeg_bytes: bytes, frame_id: int) -> FrameResult:
        """
        Run YOLOv8 inference on raw JPEG bytes.

        Returns a fully-constructed FrameResult ready for the ResultAggregator.
        Thread-safe: only one inference runs at a time.
        """
        nparr = np.frombuffer(jpeg_bytes, np.uint8)
        frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        if frame is None:
            return FrameResult(
                frame_id=frame_id,
                worker_id="coordinator-local",
                detections=[],
                object_counts={},
                processing_time_ms=0.0,
                received_at=datetime.now(timezone.utc),
            )

        with self._lock:
            model = self._get_model()
            t0 = time.perf_counter()
            results = model(frame, verbose=False)
            elapsed_ms = (time.perf_counter() - t0) * 1000

        detections: list[Detection] = []
        counts: dict[str, int] = {}
        for r in results:
            boxes = r.boxes
            if boxes is None:
                continue
            for box in boxes:
                conf = float(box.conf[0])
                if conf < CONFIDENCE_THRESHOLD:
                    continue
                label = model.names[int(box.cls[0])]
                x1, y1, x2, y2 = box.xyxy[0].tolist()
                detections.append(Detection(
                    label=label,
                    confidence=round(conf, 3),
                    box=BoundingBox(x1=int(x1), y1=int(y1), x2=int(x2), y2=int(y2)),
                ))
                counts[label] = counts.get(label, 0) + 1

        result = FrameResult(
            frame_id=frame_id,
            worker_id="coordinator-local",
            detections=detections,
            object_counts=counts,
            processing_time_ms=round(elapsed_ms, 2),
            received_at=datetime.now(timezone.utc),
        )

        # Push annotated frame to MJPEG live stream
        self._push_annotated(frame, detections)

        # Evaluate smart alerts
        self._evaluate_alerts(frame_id, detections, counts, elapsed_ms)

        return result

    def _evaluate_alerts(
        self,
        frame_id: int,
        detections: list[Detection],
        counts: dict[str, int],
        elapsed_ms: float,
    ) -> None:
        """Generate smart alerts based on detection results and system metrics."""
        from backend.services import result_aggregator
        from backend.config import ADMIN_URL

        now = datetime.now(timezone.utc)
        labels_in_frame = set(counts.keys())
        high_conf = [d for d in detections if d.confidence >= ALERT_CONFIDENCE]
        generated: list[dict] = []

        # 1. Pedestrian Near Traffic (critical)
        has_person = "person" in labels_in_frame
        has_heavy = bool(labels_in_frame & _HEAVY_VEHICLES)
        if has_person and has_heavy:
            heavy_names = sorted(labels_in_frame & _HEAVY_VEHICLES)
            generated.append({
                "worker_id": "coordinator-local",
                "frame_id": frame_id,
                "timestamp": now.isoformat(),
                "detections": [d.model_dump(mode="json") for d in high_conf] if high_conf else [],
                "alert_labels": ["person"] + heavy_names,
                "level": "critical",
                "message": f"Pedestrian detected near {', '.join(heavy_names)} — safety hazard",
            })

        # 2. Traffic Congestion (warning)
        vehicle_count = sum(counts.get(v, 0) for v in _ALL_VEHICLES)
        if vehicle_count >= ALERT_CONGESTION_THRESHOLD:
            vehicle_labels = sorted(l for l in labels_in_frame if l in _ALL_VEHICLES)
            generated.append({
                "worker_id": "coordinator-local",
                "frame_id": frame_id,
                "timestamp": now.isoformat(),
                "detections": [d.model_dump(mode="json") for d in high_conf] if high_conf else [],
                "alert_labels": vehicle_labels,
                "level": "warning",
                "message": f"Traffic congestion — {vehicle_count} vehicles detected in frame",
            })

        # 3. Slow Inference (warning)
        if elapsed_ms > ALERT_SLOW_INFERENCE_MS:
            generated.append({
                "worker_id": "coordinator-local",
                "frame_id": frame_id,
                "timestamp": now.isoformat(),
                "detections": [],
                "alert_labels": ["slow_inference"],
                "level": "warning",
                "message": f"Slow inference — {elapsed_ms:.0f}ms (threshold {ALERT_SLOW_INFERENCE_MS:.0f}ms)",
            })

        # Store locally + push to Admin (fire-and-forget)
        for alert in generated:
            result_aggregator.add_alert(alert)
            if ADMIN_URL:
                threading.Thread(
                    target=self._push_alert_to_admin, args=(alert,), daemon=True
                ).start()

    def _push_alert_to_admin(self, alert: dict) -> None:
        """Fire-and-forget: POST alert to Admin portal."""
        try:
            from backend.services.admin_reporter import get_reporter
            get_reporter().report_alert(alert)
        except Exception:
            pass  # best-effort; don't crash inference loop

    def _push_annotated(self, frame, detections: list[Detection]) -> None:
        """Draw bounding boxes on the frame and push to the MJPEG stream."""
        from backend.services import frame_distributor

        _BOX_COLOURS = [
            (0, 255, 0), (255, 0, 0), (0, 165, 255), (255, 255, 0),
            (0, 255, 255), (255, 0, 255), (128, 255, 0), (0, 128, 255),
        ]
        for i, det in enumerate(detections):
            colour = _BOX_COLOURS[i % len(_BOX_COLOURS)]
            b = det.box
            cv2.rectangle(frame, (b.x1, b.y1), (b.x2, b.y2), colour, 2)
            label_text = f"{det.label} {det.confidence:.0%}"
            (tw, th), _ = cv2.getTextSize(label_text, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
            cv2.rectangle(frame, (b.x1, b.y1 - th - 6), (b.x1 + tw + 4, b.y1), colour, -1)
            cv2.putText(frame, label_text, (b.x1 + 2, b.y1 - 4),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 1)

        ok, jpeg_buf = cv2.imencode(".jpg", frame)
        if ok:
            frame_distributor.push(jpeg_buf.tobytes())
