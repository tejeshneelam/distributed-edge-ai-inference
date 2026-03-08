# Edge Co-Intelligence System

Distributed ML inference platform that distributes **YOLOv8** object detection across edge worker nodes and streams annotated results to a real-time **Angular** dashboard. Includes a separate **Admin Portal** for coordinating and monitoring camera-laptop nodes.

![Python](https://img.shields.io/badge/Python-3.9+-blue?logo=python&logoColor=white)
![Angular](https://img.shields.io/badge/Angular-21-red?logo=angular&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.111-009688?logo=fastapi&logoColor=white)
![YOLOv8](https://img.shields.io/badge/YOLOv8-ultralytics-purple)
![License](https://img.shields.io/badge/License-MIT-green)

---

## Features

### Edge Co-Intelligence System (ports 8000 / 4200)

- **Distributed Inference** — coordinator dispatches video frames to a pool of worker nodes for parallel YOLOv8 detection
- **Live MJPEG Stream** — annotated frames with bounding boxes streamed in real-time
- **Job Pipeline** — upload videos, track processing lifecycle (queued → processing → completed/failed)
- **Detection Summary** — per-class object counts (cars, trucks, persons, etc.) with visual breakdown
- **Worker Management** — auto-registration, heartbeat monitoring, circuit breaker, weighted load balancing
- **Toast Notifications** — real-time toasts for job lifecycle events
- **Fault Tolerance** — retry queues, circuit breakers, graceful degradation
- **System Metrics** — FPS, latency (avg/P95), worker status, queue depth

### Admin Portal (ports 8001 / 4201)

- **Camera Node Registry** — register Camera Laptop 1 & 2, heartbeat-based online/offline tracking
- **Live Analytics** — total vehicles, per-camera counts, type distribution (car/truck/bus/…), detection timeline
- **Detection Event Log** — scrollable flat-table feed of all incoming detection events
- **Camera Control** — send `start` / `stop` / `restart` commands to any registered camera via WebSocket
- **WebSocket Broadcast** — real-time push to all connected dashboard clients on every detection event

---

## Architecture

### Edge Co-Intelligence System

```
┌─────────────────┐        HTTP/REST         ┌──────────────────────┐
│  Angular 21     │ ◄──────────────────────►  │  FastAPI Coordinator │
│  Dashboard      │    polling + upload       │  (port 8000)         │
│  (port 4200)    │ ◄── MJPEG stream ──────   │                      │
└─────────────────┘                           └──────────┬───────────┘
                                                         │
                                              ┌──────────┴───────────┐
                                              │   Frame Queue /      │
                                              │   Worker Manager     │
                                              └──────────┬───────────┘
                                                         │
                              ┌───────────────┬──────────┴──────────┬───────────────┐
                              │ Worker Node 1 │  Worker Node 2      │  coordinator- │
                              │ (remote)      │  (remote)           │  local        │
                              │ YOLOv8 + GPU  │  YOLOv8 + GPU      │  (built-in)   │
                              └───────────────┴─────────────────────┴───────────────┘
```

### Admin Portal

```
┌──────────────────┐    HTTP/REST + WebSocket    ┌───────────────────────┐
│  Angular 21      │ ◄────────────────────────►  │  FastAPI Admin        │
│  Admin Dashboard │    polling + WS stream      │  (port 8001)          │
│  (port 4201)     │                             └──────────┬────────────┘
└──────────────────┘                                        │
                                                ┌───────────┴────────────┐
                                                │  Camera Manager /      │
                                                │  Analytics Manager /   │
                                                │  WebSocket Manager     │
                                                └───────────┬────────────┘
                                                            │
                                         ┌──────────────────┴──────────────────┐
                                         │ Camera Laptop 1   Camera Laptop 2   │
                                         │ POST /camera-detection              │
                                         │ (YOLOv8 results → Admin backend)    │
                                         └─────────────────────────────────────┘
```

---

## Project Structure

```
edge-ai-project/
├── edge-co-intelligence-system/
│   └── backend/
│       ├── main.py                    # FastAPI app entry point
│       ├── config.py                  # Configuration (env-overridable)
│       ├── models.py                  # Pydantic models (Worker, Detection, Job, etc.)
│       ├── routes/
│       │   ├── worker_routes.py       # Worker registration, heartbeat, listing
│       │   ├── result_routes.py       # Frame results, summary, alerts
│       │   ├── metrics_routes.py      # System metrics endpoint
│       │   └── video_routes.py        # MJPEG stream, upload, job lifecycle
│       ├── services/
│       │   ├── worker_manager.py      # Registry, circuit breaker, load balancing
│       │   ├── result_aggregator.py   # Sharded-lock result store, O(1) summary
│       │   ├── metrics_service.py     # FPS, latency, uptime computation
│       │   ├── frame_distributor.py   # MJPEG push buffer (Condition + version)
│       │   ├── frame_queue.py         # Parallel dispatch, retry, circuit breaker
│       │   └── job_tracker.py         # Job lifecycle state machine
│       ├── utils/
│       │   ├── frame_encoder.py       # JPEG encode/decode/annotate
│       │   └── networking.py          # TCP protocol helpers
│       └── requirements.txt
│
├── admin/                             # Admin Portal (Camera Laptop coordinator)
│   ├── backend/
│   │   ├── main.py                    # FastAPI admin app (port 8001)
│   │   ├── config.py                  # Env-overridable settings
│   │   ├── models.py                  # Pydantic models (CameraInfo, DetectionEvent, etc.)
│   │   ├── routes/
│   │   │   ├── camera_routes.py       # Camera register, heartbeat, list, delete
│   │   │   ├── analytics_routes.py    # Aggregate analytics endpoint
│   │   │   └── control_routes.py      # Detection ingest + camera control commands
│   │   ├── services/
│   │   │   ├── camera_manager.py      # Thread-safe camera registry + heartbeat timeout
│   │   │   ├── analytics_manager.py   # Running totals, type distribution, timeline
│   │   │   └── websocket_manager.py   # WS connection set, broadcast
│   │   ├── utils/
│   │   │   └── helpers.py             # Shared utilities
│   │   └── requirements.txt
│   └── frontend/                      # Angular 21 standalone app (port 4201)
│       ├── src/app/
│       │   ├── components/
│       │   │   ├── dashboard/         # Root layout + topbar
│       │   │   ├── camera-status/     # Camera node table (online/offline chips)
│       │   │   ├── analytics-panel/   # Stats grid + bar/pie/line charts (Chart.js)
│       │   │   ├── detection-logs/    # Flat detection event table
│       │   │   └── camera-control/    # Start/stop/restart command panel
│       │   ├── models/
│       │   │   ├── camera.model.ts
│       │   │   ├── analytics.model.ts
│       │   │   └── detection.model.ts
│       │   └── services/
│       │       ├── api.service.ts     # HTTP client for all admin endpoints
│       │       └── websocket.service.ts # WS client with auto-reconnect
│       ├── package.json
│       └── angular.json
│
├── edge-dashboard/                    # Angular 21 frontend
│   ├── src/app/
│   │   ├── components/
│   │   │   ├── dashboard/             # Root layout + topbar
│   │   │   ├── video-stream/          # MJPEG viewer + video upload + job tracking
│   │   │   ├── detection-summary/     # Per-class object count breakdown
│   │   │   ├── job-status/            # Job pipeline table with progress bars
│   │   │   ├── worker-status/         # Worker node table
│   │   │   ├── metrics-panel/         # System metrics grid
│   │   │   ├── frame-results/         # Frame detection log
│   │   │   ├── alerts-panel/          # Alert feed
│   │   │   └── toast/                 # Toast notification overlay
│   │   └── services/
│   │       ├── api.service.ts         # HTTP client for all backend endpoints
│   │       └── notification.service.ts # Cross-component toast events
│   ├── package.json
│   └── angular.json
│
├── worker_agent.py                    # Standalone edge worker (run on remote nodes)
└── .gitignore
```

---

## Quick Start

### Prerequisites

| Tool    | Version |
| ------- | ------- |
| Python  | 3.9+    |
| Node.js | 20+ LTS |
| npm     | 10+     |

### 1. Clone & install

```bash
git clone https://github.com/<your-username>/edge-ai-project.git
cd edge-ai-project

# Create virtual environment (recommended)
python3 -m venv .venv
source .venv/bin/activate

# Install edge system dependencies
pip install -r edge-co-intelligence-system/backend/requirements.txt

# Install admin portal dependencies
pip install -r admin/backend/requirements.txt
```

### 2. Start the Edge Co-Intelligence backend

```bash
PYTHONPATH=edge-co-intelligence-system \
  uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
```

API docs: [http://localhost:8000/docs](http://localhost:8000/docs)

### 3. Start the Admin Portal backend

```bash
python3 -m uvicorn admin.backend.main:app --host 0.0.0.0 --port 8001 --reload
```

API docs: [http://localhost:8001/docs](http://localhost:8001/docs)

### 4. Install & start the Edge dashboard

```bash
cd edge-dashboard
npm install
npx ng serve --port 4200
```

Open [http://localhost:4200](http://localhost:4200)

### 5. Install & start the Admin dashboard

```bash
cd admin/frontend
npm install
npx ng serve --port 4201
```

Open [http://localhost:4201](http://localhost:4201)

### 6. (Optional) Start remote worker nodes

```bash
python worker_agent.py \
  --coordinator http://<coordinator-ip>:8000 \
  --port 9001
```

---

## API Endpoints

### Edge Co-Intelligence System (port 8000)

| Method | Path               | Description                               |
| ------ | ------------------ | ----------------------------------------- |
| GET    | `/health`          | Liveness check                            |
| POST   | `/register-worker` | Register an edge worker node              |
| GET    | `/workers`         | List all registered workers               |
| POST   | `/heartbeat/{id}`  | Worker heartbeat                          |
| DELETE | `/workers/{id}`    | Remove a worker                           |
| POST   | `/upload-video`    | Upload video for YOLOv8 inference         |
| GET    | `/video-stream`    | MJPEG annotated frame stream              |
| GET    | `/jobs`            | List all jobs (newest first)              |
| GET    | `/jobs/{id}`       | Get status of a specific job              |
| POST   | `/process-frame`   | Coordinator local-worker inference        |
| POST   | `/frame-result`    | Submit inference result from a worker     |
| GET    | `/results`         | All frame results + aggregated counts     |
| GET    | `/results/summary` | Summary: total frames, detections, counts |
| GET    | `/metrics`         | System metrics (FPS, latency, workers)    |
| GET    | `/alerts`          | Detection alert feed                      |
| GET    | `/queue/stats`     | Frame queue depth, retries, drops         |

### Admin Portal (port 8001)

| Method    | Path                | Description                                        |
| --------- | ------------------- | -------------------------------------------------- |
| GET       | `/health`           | Liveness check                                     |
| POST      | `/register-camera`  | Register a camera laptop node                      |
| GET       | `/cameras`          | List all cameras with online/offline status        |
| POST      | `/heartbeat/{id}`   | Camera heartbeat (keeps node online)               |
| DELETE    | `/cameras/{id}`     | Remove a camera                                    |
| POST      | `/camera-detection` | Ingest detection event from a camera               |
| GET       | `/analytics`        | Aggregate analytics (totals, per-camera, timeline) |
| POST      | `/camera-control`   | Send command (start/stop/restart) to a camera      |
| WebSocket | `/ws/cameras`       | Real-time broadcast of detection events            |

---

## Configuration

### Edge Co-Intelligence System (`edge-co-intelligence-system/backend/config.py`)

| Variable               | Default | Description                         |
| ---------------------- | ------- | ----------------------------------- |
| `CONFIDENCE_THRESHOLD` | `0.4`   | Minimum YOLOv8 detection confidence |
| `STREAM_TIMEOUT`       | `5.0`   | MJPEG frame timeout (seconds)       |
| `CORS_ORIGINS`         | `*`     | Allowed CORS origins                |

### Admin Portal (`admin/backend/config.py`)

| Variable                   | Default   | Description                               |
| -------------------------- | --------- | ----------------------------------------- |
| `HOST`                     | `0.0.0.0` | Bind address                              |
| `PORT`                     | `8001`    | Server port                               |
| `CORS_ORIGINS`             | `*`       | Allowed CORS origins                      |
| `CAMERA_HEARTBEAT_TIMEOUT` | `30`      | Seconds before a camera is marked offline |

---

## Tech Stack

**Backend**

- [FastAPI](https://fastapi.tiangolo.com/) — async REST API
- [Uvicorn](https://www.uvicorn.org/) — ASGI server
- [Ultralytics YOLOv8](https://docs.ultralytics.com/) — object detection
- [OpenCV](https://opencv.org/) — frame processing
- [httpx](https://www.python-httpx.org/) — async HTTP for worker dispatch
- [Pydantic v2](https://docs.pydantic.dev/) — data validation & serialisation

**Frontend**

- [Angular 21](https://angular.dev/) — standalone components, no NgModule
- [Angular Material 21](https://material.angular.io/) — select / form-field / snack-bar
- [Chart.js 4](https://www.chartjs.org/) — bar, pie, line charts (admin portal)
- [RxJS](https://rxjs.dev/) — reactive polling, WebSocket streams
- IBM Plex Mono / Sans — typography

---

## License

MIT
