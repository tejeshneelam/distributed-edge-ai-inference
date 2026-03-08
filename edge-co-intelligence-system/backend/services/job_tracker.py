"""
job_tracker.py — Tracks the lifecycle of video upload / inference jobs.

Each upload-video call creates a job. The processing pipeline updates its state
as frames are extracted, dispatched, and completed.
"""
from __future__ import annotations

from collections import OrderedDict
from datetime import datetime, timezone
from threading import Lock

from backend.models import JobStatus

MAX_JOBS = 100


class JobTracker:
    """Thread-safe store for job lifecycle state."""

    def __init__(self) -> None:
        self._lock = Lock()
        self._jobs: OrderedDict[str, JobStatus] = OrderedDict()

    # ── Writes ────────────────────────────────────────────────────────────────

    def create(self, job_id: str, filename: str, size_bytes: int) -> JobStatus:
        job = JobStatus(
            job_id=job_id,
            filename=filename,
            size_bytes=size_bytes,
            status="queued",
            submitted_at=datetime.now(timezone.utc),
        )
        with self._lock:
            if len(self._jobs) >= MAX_JOBS:
                self._jobs.popitem(last=False)
            self._jobs[job_id] = job
        return job

    def mark_processing(self, job_id: str, total_frames: int) -> None:
        with self._lock:
            job = self._jobs.get(job_id)
            if job:
                job.status = "processing"
                job.started_at = datetime.now(timezone.utc)
                job.total_frames = total_frames

    def increment_progress(self, job_id: str, detections: int = 0) -> None:
        with self._lock:
            job = self._jobs.get(job_id)
            if job:
                job.processed_frames += 1
                job.detections_found += detections
                if job.total_frames > 0:
                    job.progress_pct = round(100 * job.processed_frames / job.total_frames, 1)

    def mark_completed(self, job_id: str) -> None:
        with self._lock:
            job = self._jobs.get(job_id)
            if job:
                job.status = "completed"
                job.completed_at = datetime.now(timezone.utc)
                job.progress_pct = 100.0

    def mark_failed(self, job_id: str, error: str) -> None:
        with self._lock:
            job = self._jobs.get(job_id)
            if job:
                job.status = "failed"
                job.completed_at = datetime.now(timezone.utc)
                job.error = error

    # ── Reads ─────────────────────────────────────────────────────────────────

    def get(self, job_id: str) -> JobStatus | None:
        with self._lock:
            return self._jobs.get(job_id)

    def get_all(self) -> list[JobStatus]:
        with self._lock:
            return list(reversed(self._jobs.values()))
