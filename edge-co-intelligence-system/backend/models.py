from __future__ import annotations

from datetime import datetime
from typing import Any, Literal, Optional
from pydantic import BaseModel, Field


# ── Worker models ──────────────────────────────────────────────────────────────

class WorkerRegisterRequest(BaseModel):
    worker_id: str = Field(..., description="Unique identifier for the worker node")
    host: str = Field(..., description="Worker hostname or IP (informational)")
    port: int = Field(..., ge=1, le=65535, description="Worker's listening port")
    capabilities: list[str] = Field(default_factory=list, description="Model names this worker supports")


class WorkerNodeRequest(BaseModel):
    """Payload for POST /register-worker."""
    worker_id: str = Field(..., description="Unique identifier for the worker node")
    hostname: str = Field(..., description="Human-readable hostname of the worker")
    ip_address: str = Field(..., description="IP address of the worker node")
    port: int = Field(..., ge=1, le=65535, description="Port the worker agent is listening on")
    capabilities: list[str] = Field(default_factory=list, description="Model names this worker supports")


class WorkerInfo(BaseModel):
    worker_id: str
    host: str
    port: int
    hostname: str = ""
    ip_address: str = ""
    registered_at: datetime
    frames_processed: int = 0
    capabilities: list[str] = []             # models this worker can run
    # ── Fault tolerance / load balancing ──────────────────────────────────────
    status: Literal["active", "idle", "offline"] = "active"
    last_heartbeat: Optional[datetime] = None   # None = never seen (REST-only workers)
    pending_frames: int = 0                  # frames dispatched but not yet returned
    avg_processing_ms: float = 0.0           # exponential moving average of inference latency


# ── Detection / inference models ───────────────────────────────────────────────

class BoundingBox(BaseModel):
    x1: int
    y1: int
    x2: int
    y2: int


class Detection(BaseModel):
    label: str
    confidence: float = Field(..., ge=0.0, le=1.0)
    box: BoundingBox


class InferenceResultRequest(BaseModel):
    worker_id: str = Field(..., description="ID of the worker that processed the frame")
    frame_id: int = Field(..., ge=1, description="Frame number from the source video")
    detections: list[Detection] = Field(default_factory=list)
    processing_time_ms: float = Field(
        default=0.0, ge=0.0, description="Time taken to run inference (ms)"
    )


class FrameResultRequest(BaseModel):
    """Payload for POST /frame-result."""
    frame_id: int = Field(..., ge=1, description="Frame number from the source video")
    worker_id: str = Field(..., description="ID of the worker that processed the frame")
    detected_objects: list[str] = Field(
        default_factory=list,
        description="List of detected object labels (e.g. ['car', 'person'])",
    )
    processing_time: float = Field(
        default=0.0, ge=0.0, description="Time taken to process this frame (seconds)"
    )


class FrameResult(BaseModel):
    frame_id: int
    worker_id: str
    detections: list[Detection]
    object_counts: dict[str, int]
    processing_time_ms: float
    received_at: datetime
    status: Literal["pending", "completed", "failed"] = "completed"
    job_id: Optional[str] = None  # link back to the upload job


# ── Aggregated result models ───────────────────────────────────────────────────

class AggregatedResults(BaseModel):
    total_frames_processed: int
    total_detections: int
    object_counts: dict[str, int]
    frames: list[FrameResult]
    worker_summary: dict[str, int]          # worker_id → frames processed


# ── Metrics model ─────────────────────────────────────────────────────────────

class WorkerStatusSummary(BaseModel):
    total: int
    active: int
    idle: int
    offline: int


class LatencyStats(BaseModel):
    avg_ms: float
    p95_ms: float
    samples: int


class SystemMetrics(BaseModel):
    workers: WorkerStatusSummary
    queue: dict[str, int]           # pending / inflight
    frames: dict[str, float]        # total / fps
    latency_ms: LatencyStats
    retry_count: int                # total retried tasks since start
    dropped_count: int              # tasks dropped after MAX_RETRIES
    system_start_time: datetime
    # ── Legacy fields kept for backwards compatibility ─────────────────────
    number_of_workers: int
    total_frames_processed: int
    processing_fps: float


# ── Generic response wrapper ───────────────────────────────────────────────────

class SuccessResponse(BaseModel):
    success: bool = True
    message: str
    data: Any = None


# ── Frame distribution models ──────────────────────────────────────────────────

class FrameTask(BaseModel):
    """A unit of work dispatched from coordinator to a worker node."""
    task_id: str = Field(..., description="Unique task identifier")
    frame_id: int = Field(..., description="Frame sequence number")
    jpeg_b64: str = Field(..., description="Base64-encoded JPEG bytes")
    dispatched_at: datetime
    assigned_worker: str
    retries: int = 0
    required_capability: str = "yolov8n"   # capability the receiving worker must have


class ProcessFrameRequest(BaseModel):
    """Payload sent from FrameQueue to a worker's POST /process-frame endpoint."""
    task_id: str
    frame_id: int
    jpeg_b64: str


# ── Job lifecycle tracking ──────────────────────────────────────────────────────

class JobStatus(BaseModel):
    """Tracks the lifecycle of a video upload / inference job."""
    job_id: str
    filename: str
    size_bytes: int
    status: Literal["queued", "processing", "completed", "failed"] = "queued"
    submitted_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    total_frames: int = 0        # frames extracted from the video
    processed_frames: int = 0    # frames that have finished inference
    detections_found: int = 0    # cumulative detections across all frames
    error: Optional[str] = None  # error message if status == "failed"
    progress_pct: float = 0.0    # 0-100


class AlertEvent(BaseModel):
    """High-confidence detection event raised autonomously by an edge worker."""
    worker_id: str
    frame_id: int
    timestamp: datetime
    detections: list[Detection]
    alert_labels: list[str]   # subset of labels that triggered the alert
