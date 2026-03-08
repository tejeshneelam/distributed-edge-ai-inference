"""
frame_encoder.py — JPEG encoding/decoding utilities for video frames.
"""
from __future__ import annotations

import cv2
import numpy as np

from backend.config import JPEG_QUALITY


def encode_frame(frame: "cv2.Mat", quality: int = JPEG_QUALITY) -> bytes:
    """
    Encode an OpenCV BGR frame as JPEG bytes.

    Args:
        frame: OpenCV BGR image array.
        quality: JPEG quality (1–100). Higher = larger file, better quality.

    Returns:
        Raw JPEG bytes ready for network transmission or MJPEG streaming.
    """
    success, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, quality])
    if not success:
        raise RuntimeError("cv2.imencode failed — could not encode frame as JPEG.")
    return buf.tobytes()


def decode_frame(jpeg_bytes: bytes) -> "cv2.Mat":
    """
    Decode JPEG bytes back into an OpenCV BGR frame.

    Args:
        jpeg_bytes: Raw JPEG bytes received from the network.

    Returns:
        OpenCV BGR image array.

    Raises:
        ValueError: If the data is not a valid JPEG.
    """
    arr = np.frombuffer(jpeg_bytes, dtype=np.uint8)
    frame = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if frame is None:
        raise ValueError("cv2.imdecode returned None — invalid JPEG data.")
    return frame


def annotate_frame(
    jpeg_bytes: bytes,
    detections: list[dict],
    frame_id: int,
) -> bytes:
    """
    Draw bounding boxes, labels, and a frame counter on a JPEG frame.

    Args:
        jpeg_bytes: Raw JPEG bytes of the original frame.
        detections: List of dicts with keys ``label``, ``confidence``, ``box``
                    where ``box`` is ``[x1, y1, x2, y2]``.
        frame_id: Frame number shown in the top-left corner.

    Returns:
        Annotated JPEG bytes.
    """
    frame = decode_frame(jpeg_bytes)
    counts: dict[str, int] = {}

    for det in detections:
        label = det["label"]
        conf = det["confidence"]
        x1, y1, x2, y2 = det["box"]
        counts[label] = counts.get(label, 0) + 1

        cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
        cv2.putText(
            frame, f"{label} {conf:.2f}", (x1, max(y1 - 6, 0)),
            cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 255, 0), 1,
        )

    # Frame ID overlay
    cv2.putText(
        frame, f"Frame #{frame_id}", (8, 24),
        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2,
    )

    # Object count summary
    if counts:
        summary = "  ".join(f"{k}:{v}" for k, v in counts.items())
        cv2.putText(
            frame, summary, (8, 50),
            cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 255, 255), 1,
        )

    return encode_frame(frame)
