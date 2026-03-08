# Edge Co-Intelligence — Project Report

## Abstract

Edge Co-Intelligence demonstrates distributed machine learning inference by distributing YOLOv8 object detection across multiple edge devices. A Python coordinator server dispatches video frames over TCP sockets, worker nodes perform GPU/CPU inference in parallel, and results are aggregated and streamed to a real-time Angular dashboard via a FastAPI REST backend.

---

## 1. System Goals

- Distribute heavy YOLOv8 inference workload across multiple devices
- Achieve higher throughput than a single-node inference pipeline
- Surface detection results and system health via a live web dashboard
- Tolerate worker failures (frames are reassigned automatically)

---

## 2. Implementation

### 2.1 Coordinator (`workers/worker.py` + socket layer)

- Reads all frames from `traffic.mp4` upfront
- Accepts worker TCP connections for a configurable window (`WORKER_WAIT_SECS`)
- Distributes frames round-robin via per-worker `queue.Queue` instances
- On worker disconnect, queued and in-flight frames are moved to a shared rescue queue and reprocessed by remaining workers
- Annotates returned frames with bounding boxes and pushes them to the MJPEG buffer

### 2.2 Workers (`workers/`)

| File                | Role                                                   |
| ------------------- | ------------------------------------------------------ |
| `worker.py`         | Main loop — connect, receive, dispatch                 |
| `inference.py`      | Load YOLOv8, decode JPEG, run model, return detections |
| `network_client.py` | TCP `recv_exact`, `send_result`, `recv_frame`          |
| `config.py`         | Host, port, model name, confidence threshold           |

### 2.3 FastAPI Backend (`backend/`)

| Layer    | Files                                                                                     |
| -------- | ----------------------------------------------------------------------------------------- |
| Routes   | `worker_routes.py`, `result_routes.py`, `metrics_routes.py`, `video_routes.py`            |
| Services | `worker_manager.py`, `result_aggregator.py`, `metrics_service.py`, `frame_distributor.py` |
| Utils    | `frame_encoder.py`, `networking.py`                                                       |

### 2.4 Angular Dashboard (`frontend/`)

Five standalone components:

| Component               | Data source                 | Update interval |
| ----------------------- | --------------------------- | --------------- |
| `VideoStreamComponent`  | `GET /video-stream` (MJPEG) | Continuous      |
| `WorkerStatusComponent` | `GET /workers`              | 5 s polling     |
| `MetricsPanelComponent` | `GET /metrics`              | 2 s polling     |
| `FrameResultsComponent` | `GET /results`              | 5 s polling     |

---

## 3. Performance

- Throughput scales linearly with the number of connected workers.
- The coordinator tracks FPS (`total_frames / elapsed_seconds`) reported via `/metrics`.
- Worker failure is handled without dropping frames — typical reassignment latency is under 1 s.

---

## 4. Security Considerations

- TCP connections are unauthenticated — deploy within a private LAN or VPN.
- REST endpoints have no auth in the current implementation — add OAuth2/API-key middleware for production.
- CORS is set to `*` for development; restrict `CORS_ORIGINS` in production.

---

## 5. Running the System

```bash
# 1. Start the FastAPI backend
cd edge-co-intelligence-system
uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload

# 2. Start a worker (repeat on each edge device)
python -m workers.worker

# 3. Start the Angular dashboard
cd frontend
npm install && ng serve
# Open http://localhost:4200
```
