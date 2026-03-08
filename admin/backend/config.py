import os

HOST: str = os.getenv("HOST", "0.0.0.0")
PORT: int = int(os.getenv("PORT", "8001"))
CORS_ORIGINS: str = os.getenv("CORS_ORIGINS", "*")
CAMERA_HEARTBEAT_TIMEOUT: int = int(os.getenv("CAMERA_HEARTBEAT_TIMEOUT", "30"))
