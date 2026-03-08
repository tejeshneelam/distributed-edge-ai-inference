# Edge Co-Intelligence System

Distributed ML inference platform that distributes **YOLOv8** object detection across edge worker nodes and streams annotated results to a real-time **Angular** dashboard.

![Python](https://img.shields.io/badge/Python-3.9+-blue?logo=python&logoColor=white)
![Angular](https://img.shields.io/badge/Angular-21-red?logo=angular&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.111-009688?logo=fastapi&logoColor=white)
![YOLOv8](https://img.shields.io/badge/YOLOv8-ultralytics-purple)
![License](https://img.shields.io/badge/License-MIT-green)

---

## Features

- **Distributed Inference** — coordinator dispatches video frames to a pool of worker nodes for parallel YOLOv8 detection
- **Live MJPEG Stream** — annotated frames with bounding boxes streamed in real-time
- **Job Pipeline** — upload videos, track processing lifecycle (queued → processing → completed/failed)
- **Detection Summary** — per-class object counts (cars, trucks, persons, etc.) with visual breakdown
- **Worker Management** — auto-registration, heartbeat monitoring, circuit breaker, weighted load balancing
- **Toast Notifications** — real-time toasts for job lifecycle events
- **Fault Tolerance** — retry queues, circuit breakers, graceful degradation
- **System Metrics** — FPS, latency (avg/P95), worker status, queue depth

---

## Architecture

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

### 1. Clone & install backend

```bash
git clone https://github.com/<your-username>/edge-ai-project.git
cd edge-ai-project

# Create virtual environment (recommended)
python3 -m venv .venv
source .venv/bin/activate

# Install Python dependencies
pip install -r edge-co-intelligence-system/backend/requirements.txt
```

### 2. Start the FastAPI backend

```bash
PYTHONPATH=edge-co-intelligence-system \
  uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
```

API docs: [http://localhost:8000/docs](http://localhost:8000/docs)

### 3. Install & start the Angular dashboard

```bash
cd edge-dashboard
npm install
npx ng serve --port 4200
```

Open [http://localhost:4200](http://localhost:4200)

### 4. (Optional) Start remote worker nodes

```bash
python worker_agent.py \
  --coordinator http://<coordinator-ip>:8000 \
  --port 9001
```

---

## API Endpoints

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

---

## Configuration

All backend settings live in `edge-co-intelligence-system/backend/config.py` and can be overridden via environment variables:

| Variable               | Default | Description                         |
| ---------------------- | ------- | ----------------------------------- |
| `CONFIDENCE_THRESHOLD` | `0.4`   | Minimum YOLOv8 detection confidence |
| `STREAM_TIMEOUT`       | `5.0`   | MJPEG frame timeout (seconds)       |
| `CORS_ORIGINS`         | `*`     | Allowed CORS origins                |

---

## Tech Stack

**Backend**

- [FastAPI](https://fastapi.tiangolo.com/) — async REST API
- [Uvicorn](https://www.uvicorn.org/) — ASGI server
- [Ultralytics YOLOv8](https://docs.ultralytics.com/) — object detection
- [OpenCV](https://opencv.org/) — frame processing
- [httpx](https://www.python-httpx.org/) — async HTTP for worker dispatch

**Frontend**

- [Angular 21](https://angular.dev/) — standalone components
- [Angular Material](https://material.angular.io/) — icons
- [RxJS](https://rxjs.dev/) — reactive polling & streams
- IBM Plex Mono / Sans — typography

---

## License

MIT
# distributed-edge-ai-inference
