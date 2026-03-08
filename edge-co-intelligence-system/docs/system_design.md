# System Design — Edge Co-Intelligence

## Overview

Edge Co-Intelligence is a distributed ML inference system that distributes video frame processing across multiple edge devices (laptops/servers), aggregates YOLOv8 detection results, and surfaces them through a real-time Angular dashboard.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        Frontend                             │
│   Angular 19 Dashboard  ◄──── HTTP / MJPEG ────────────────┐│
└─────────────────────────────────────────────────────────────┘│
                                                               │
┌─────────────────────────────────────────────────────────────┐│
│                  FastAPI Backend (Coordinator)               ││
│                                                             ││
│  /register-worker   /workers   /frame-result               ││
│  /results           /metrics   /video-stream               ││
│                                                             ││
│  WorkerManager ── ResultAggregator ── MetricsService        ││
│  FrameDistributor                                           ││
└───────────────────────────────┬─────────────────────────────┘│
                                │ TCP sockets                   │
                    ┌───────────▼────────────────┐             │
                    │    Socket Coordinator       │─────────────┘
                    │    (frame_distributor)      │
                    │  Round-robin dispatch       │
                    │  Failure recovery           │
                    └───────┬──────────┬──────────┘
                            │          │
               ┌────────────▼──┐  ┌────▼───────────┐
               │   Worker 1    │  │   Worker 2      │
               │  YOLOv8n.pt   │  │  YOLOv8n.pt     │
               │  JPEG decode  │  │  JPEG decode    │
               │  inference    │  │  inference      │
               └───────────────┘  └─────────────────┘
```

---

## Component Responsibilities

| Component          | File(s)                                 | Responsibility                     |
| ------------------ | --------------------------------------- | ---------------------------------- |
| FastAPI backend    | `backend/main.py`                       | REST API, CORS, route assembly     |
| Worker routes      | `backend/routes/worker_routes.py`       | Register/list/remove workers       |
| Result routes      | `backend/routes/result_routes.py`       | Submit and query inference results |
| Metrics routes     | `backend/routes/metrics_routes.py`      | Live FPS/worker/frame counts       |
| Video routes       | `backend/routes/video_routes.py`        | MJPEG stream endpoint              |
| Worker manager     | `backend/services/worker_manager.py`    | Thread-safe worker registry        |
| Result aggregator  | `backend/services/result_aggregator.py` | Per-frame result storage           |
| Metrics service    | `backend/services/metrics_service.py`   | FPS calculation                    |
| Frame distributor  | `backend/services/frame_distributor.py` | MJPEG push buffer                  |
| Frame encoder      | `backend/utils/frame_encoder.py`        | JPEG encode/decode/annotate        |
| Networking         | `backend/utils/networking.py`           | TCP length-prefixed protocol       |
| Worker entry point | `workers/worker.py`                     | Main loop, connect, dispatch       |
| Inference          | `workers/inference.py`                  | YOLOv8 model + decode              |
| Network client     | `workers/network_client.py`             | TCP recv/send helpers              |
| Angular dashboard  | `frontend/src/`                         | Real-time UI                       |

---

## Wire Protocol (TCP)

```
Coordinator → Worker:
  [4B frame_id (big-endian uint32)]
  [4B payload_len (big-endian uint32)]
  [payload_len bytes JPEG]

Worker → Coordinator:
  [4B frame_id]
  [4B result_len]
  [result_len bytes JSON]

Shutdown sentinel:
  frame_id == 0, payload_len == 0
```

---

## Data Flow

1. Coordinator reads `traffic.mp4`, encodes frames as JPEG.
2. Frames are dispatched round-robin to connected TCP worker sockets.
3. Each worker decodes the JPEG, runs YOLOv8, returns JSON detections.
4. Coordinator annotates the frame (bounding boxes) and pushes it to `FrameDistributor`.
5. Workers may also POST results directly to `POST /frame-result` (REST mode).
6. Angular dashboard polls `/workers`, `/results`, `/metrics` every 5 s.
7. Dashboard `<img>` tag consumes the `GET /video-stream` MJPEG feed.
