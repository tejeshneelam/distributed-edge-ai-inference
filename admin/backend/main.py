import logging

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from .routes.camera_routes import router as camera_router
from .routes.analytics_routes import router as analytics_router
from .routes.control_routes import router as control_router
from .services.websocket_manager import get_websocket_manager

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

app = FastAPI(title="Edge Admin Portal", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(camera_router)
app.include_router(analytics_router)
app.include_router(control_router)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.websocket("/ws/cameras")
async def websocket_endpoint(websocket: WebSocket) -> None:
    manager = get_websocket_manager()
    await manager.connect(websocket)
    try:
        while True:
            # Keep connection alive; camera laptops may also send messages here
            data = await websocket.receive_text()
            logger.debug("WS message received: %s", data[:120])
    except WebSocketDisconnect:
        manager.disconnect(websocket)
