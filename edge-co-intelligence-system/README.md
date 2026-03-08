# Edge Co-Intelligence System

Distributed ML inference platform — distributes YOLOv8 object detection across multiple edge devices and streams annotated results to a live Angular dashboard.

## Project Structure

```
edge-co-intelligence-system/
├── backend/                     # FastAPI coordinator backend
│   ├── main.py                  # FastAPI entry point
│   ├── config.py                # Configuration (env-overridable)
│   ├── models.py                # Pydantic request/response models
│   ├── routes/
│   │   ├── worker_routes.py     # POST /register-worker, GET /workers
│   │   ├── result_routes.py     # POST /frame-result, GET /results
│   │   ├── metrics_routes.py    # GET /metrics
│   │   └── video_routes.py      # GET /video-stream (MJPEG)
│   ├── services/
│   │   ├── worker_manager.py    # Thread-safe worker registry
│   │   ├── result_aggregator.py # Per-frame result storage + aggregation
│   │   ├── metrics_service.py   # FPS / uptime computation
│   │   └── frame_distributor.py # MJPEG push buffer
│   ├── utils/
│   │   ├── frame_encoder.py     # JPEG encode/decode/annotate
│   │   └── networking.py        # TCP length-prefixed protocol helpers
│   └── requirements.txt
│
├── workers/                     # Edge worker nodes
│   ├── worker.py                # Main loop
│   ├── inference.py             # YOLOv8 inference logic
│   ├── network_client.py        # TCP communication helpers
│   └── config.py                # Worker configuration
│
├── frontend/                    # Angular 19 dashboard
│   └── src/app/
│       ├── components/          # dashboard, video-stream, worker-status,
│       │                        #   frame-results, metrics-panel
│       ├── services/
│       │   └── api.service.ts   # HttpClient service
│       └── models/
│           ├── worker.model.ts
│           ├── result.model.ts
│           └── metrics.model.ts
│
├── data/
│   └── traffic.mp4              # Demo video
│
└── docs/
    ├── system_design.md
    └── report.md
```

## Quick Start

### Prerequisites

- Python 3.12+
- Node.js 20+ / npm
- `pip install -r backend/requirements.txt`

### 1. Start the FastAPI backend

```bash
uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
```

API docs available at <http://localhost:8000/docs>

### 2. Start one or more workers

```bash
# Default: connects to 127.0.0.1:5000
python -m workers.worker

# Remote coordinator
COORDINATOR_HOST=192.168.1.10 python -m workers.worker
```

### 3. Start the Angular dashboard

```bash
cd frontend
npm install
npx ng serve
# Open http://localhost:4200
```

## API Endpoints

| Method | Path               | Description                  |
| ------ | ------------------ | ---------------------------- |
| POST   | `/register-worker` | Register a worker node       |
| GET    | `/workers`         | List all workers             |
| DELETE | `/workers/{id}`    | Remove a worker              |
| POST   | `/frame-result`    | Submit inference result      |
| GET    | `/results`         | Aggregated detection results |
| GET    | `/metrics`         | Live FPS / worker count      |
| GET    | `/video-stream`    | MJPEG annotated frame stream |
| GET    | `/health`          | Liveness check               |

## Configuration

All settings are in `backend/config.py` and `workers/config.py` and can be overridden via environment variables:

| Variable               | Default      | Description                                    |
| ---------------------- | ------------ | ---------------------------------------------- |
| `COORDINATOR_PORT`     | `5000`       | TCP port for worker sockets                    |
| `WORKER_WAIT_SECS`     | `5`          | Seconds to wait for workers before dispatching |
| `MODEL_NAME`           | `yolov8n.pt` | YOLOv8 model variant                           |
| `CONFIDENCE_THRESHOLD` | `0.4`        | Minimum detection confidence                   |
| `JPEG_QUALITY`         | `85`         | JPEG encoding quality for frame transport      |
| `CORS_ORIGINS`         | `*`          | Allowed CORS origins (comma-separated)         |
