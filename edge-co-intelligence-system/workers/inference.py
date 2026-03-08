"""
inference.py — YOLOv8 inference logic for edge worker nodes.
"""

import cv2
import numpy as np
from ultralytics import YOLO

from workers.config import CONFIDENCE_THRESHOLD, MODEL_NAME


def load_model(model_name: str = MODEL_NAME) -> YOLO:
    """Load and return a YOLOv8 model."""
    model = YOLO(model_name)
    print(f"[inference] Model '{model_name}' loaded.", flush=True)
    return model


def decode_frame(jpeg_bytes: bytes) -> cv2.Mat:
    """
    Decode JPEG bytes into an OpenCV BGR frame.

    Raises:
        ValueError: If the bytes are not a valid JPEG.
    """
    arr = np.frombuffer(jpeg_bytes, dtype=np.uint8)
    frame = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if frame is None:
        raise ValueError("cv2.imdecode returned None — invalid JPEG data.")
    return frame


def run_inference(model: YOLO, frame: cv2.Mat, confidence: float = CONFIDENCE_THRESHOLD) -> dict:
    """
    Run YOLOv8 on a single frame.

    Returns a dict with:
        - ``detections``: list of ``{label, confidence, box: [x1,y1,x2,y2]}``
        - ``counts``:     ``{label: count}`` aggregated across all detections
    """
    results = model(frame, verbose=False)
    detections: list[dict] = []
    counts: dict[str, int] = {}

    for box in results[0].boxes:
        conf = float(box.conf[0])
        if conf < confidence:
            continue

        cls_id = int(box.cls[0])
        label = results[0].names[cls_id]
        x1, y1, x2, y2 = [int(v) for v in box.xyxy[0]]

        detections.append({
            "label": label,
            "confidence": round(conf, 4),
            "box": [x1, y1, x2, y2],
        })
        counts[label] = counts.get(label, 0) + 1

    return {"detections": detections, "counts": counts}
