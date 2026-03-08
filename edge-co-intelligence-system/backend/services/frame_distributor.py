"""
frame_distributor.py — Manages the MJPEG video stream buffer.

Workers push annotated JPEG frames here; streaming clients pull from here.
"""
from __future__ import annotations

from threading import Condition, Lock


class FrameDistributor:
    """
    Thread-safe single-frame buffer with push-notification for stream clients.

    Usage:
        # Worker side (after inference + annotation):
        distributor.push(jpeg_bytes)

        # Stream endpoint:
        for chunk in distributor.iter_frames():
            yield chunk
    """

    def __init__(self) -> None:
        self._lock = Lock()
        self._latest_jpeg: bytes | None = None
        self._cond = Condition()
        self._version: int = 0  # incremented on every push

    def push(self, jpeg_bytes: bytes) -> None:
        """Store the latest annotated frame and wake stream clients."""
        with self._lock:
            self._latest_jpeg = jpeg_bytes
        with self._cond:
            self._version += 1
            self._cond.notify_all()

    def iter_frames(self, boundary: str = "frame", timeout: float = 5.0):
        """
        Generator that yields multipart/x-mixed-replace chunks indefinitely.

        Blocks up to *timeout* seconds for the next frame; falls back to a
        grey placeholder so the MJPEG stream never stalls.
        """
        import cv2
        import numpy as np

        HEADER = f"--{boundary}\r\nContent-Type: image/jpeg\r\n\r\n"

        def _placeholder() -> bytes:
            img = np.full((360, 640, 3), 40, dtype=np.uint8)
            cv2.putText(
                img, "Waiting for frames...", (100, 190),
                cv2.FONT_HERSHEY_SIMPLEX, 1.0, (180, 180, 180), 2,
            )
            _, buf = cv2.imencode(".jpg", img)
            return buf.tobytes()

        last_seen = 0
        while True:
            with self._cond:
                self._cond.wait_for(lambda: self._version > last_seen, timeout=timeout)
                last_seen = self._version
            with self._lock:
                jpeg = self._latest_jpeg
            if jpeg is None:
                jpeg = _placeholder()
            yield HEADER.encode() + jpeg + b"\r\n"
