"""
config.py — Worker node configuration.

Values can be overridden via environment variables using the same names.
"""

import os

# ── Coordinator connection ────────────────────────────────────────────────────
COORDINATOR_HOST: str = os.getenv("COORDINATOR_HOST", "10.233.199.56")
COORDINATOR_PORT: int = int(os.getenv("COORDINATOR_PORT", "5000"))

# ── Inference ─────────────────────────────────────────────────────────────────
MODEL_NAME: str = os.getenv("MODEL_NAME", "yolov8n.pt")
CONFIDENCE_THRESHOLD: float = float(os.getenv("CONFIDENCE_THRESHOLD", "0.4"))

# ── REST API (optional — for registering with the FastAPI backend) ─────────────
API_BASE_URL: str = os.getenv("API_BASE_URL", "http://localhost:8000")
WORKER_ID: str = os.getenv("WORKER_ID", "worker-1")
