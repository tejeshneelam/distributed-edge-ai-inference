"""
config.py — Central configuration for the FastAPI coordinator backend.

Values can be overridden via environment variables using the same names.
A .env file in the project root is loaded automatically if python-dotenv is installed.
"""

import os

# Load .env file if present (pip install python-dotenv)
try:
    from dotenv import load_dotenv  # type: ignore
    load_dotenv()
except ImportError:
    pass  # python-dotenv not installed — rely on real env vars

# ── Server ──────────────────────────────────────────────────────────────────
HOST: str = os.getenv("HOST", "0.0.0.0")
PORT: int = int(os.getenv("PORT", "8000"))

# ── CORS ────────────────────────────────────────────────────────────────────
# In production, replace "*" with your deployed frontend origin.
CORS_ORIGINS: list[str] = os.getenv("CORS_ORIGINS", "*").split(",")

# ── TCP coordinator (socket-based frame distribution) ───────────────────────
COORDINATOR_HOST: str = os.getenv("COORDINATOR_HOST", "0.0.0.0")
COORDINATOR_PORT: int = int(os.getenv("COORDINATOR_PORT", "5000"))
WORKER_WAIT_SECS: int = int(os.getenv("WORKER_WAIT_SECS", "5"))

# ── Inference ────────────────────────────────────────────────────────────────
MODEL_NAME: str = os.getenv("MODEL_NAME", "yolov8n.pt")
CONFIDENCE_THRESHOLD: float = float(os.getenv("CONFIDENCE_THRESHOLD", "0.4"))

# ── Video ────────────────────────────────────────────────────────────────────
VIDEO_PATH: str = os.getenv("VIDEO_PATH", "../data/traffic.mp4")
JPEG_QUALITY: int = int(os.getenv("JPEG_QUALITY", "85"))
MAX_FRAME_BUFFER: int = int(os.getenv("MAX_FRAME_BUFFER", "30"))

# ── Stream ───────────────────────────────────────────────────────────────────
STREAM_TIMEOUT: float = float(os.getenv("STREAM_TIMEOUT", "5.0"))
STREAM_BOUNDARY: str = "frame"

# ── Admin Portal integration ──────────────────────────────────────────────────
# Set ADMIN_URL to the Admin laptop's address so this camera reports to it.
# Leave blank to disable reporting (standalone mode).
# Example: ADMIN_URL=http://192.168.1.10:8001
ADMIN_URL: str = os.getenv("ADMIN_URL", "")
# Unique ID for this camera node shown in the Admin dashboard.
CAMERA_ID: str = os.getenv("CAMERA_ID", "cam1")
CAMERA_NAME: str = os.getenv("CAMERA_NAME", CAMERA_ID)

# ── Alert thresholds ─────────────────────────────────────────────────────────
ALERT_CONFIDENCE: float = float(os.getenv("ALERT_CONFIDENCE", "0.75"))
ALERT_CONGESTION_THRESHOLD: int = int(os.getenv("ALERT_CONGESTION_THRESHOLD", "8"))
ALERT_SLOW_INFERENCE_MS: float = float(os.getenv("ALERT_SLOW_INFERENCE_MS", "500"))
