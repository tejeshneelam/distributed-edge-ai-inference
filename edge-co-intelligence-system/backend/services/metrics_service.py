"""
metrics_service.py — Computes live system metrics from current service state.
"""
from __future__ import annotations

from datetime import datetime, timezone

from backend.models import LatencyStats, SystemMetrics, WorkerStatusSummary
from backend.services.result_aggregator import ResultAggregator
from backend.services.worker_manager import WorkerManager


class MetricsService:
    """Derives real-time metrics from WorkerManager and ResultAggregator."""

    def __init__(
        self,
        worker_manager: WorkerManager,
        result_aggregator: ResultAggregator,
    ) -> None:
        self._worker_manager = worker_manager
        self._result_aggregator = result_aggregator
        self._start_time: datetime = datetime.now(timezone.utc)
        # frame_queue is injected lazily to avoid circular import at startup
        self._frame_queue = None

    def set_frame_queue(self, frame_queue) -> None:
        """Called from services/__init__.py after all singletons are created."""
        self._frame_queue = frame_queue

    def get_metrics(self) -> SystemMetrics:
        workers = self._worker_manager.get_all()
        status_summary = WorkerStatusSummary(
            total=len(workers),
            active=sum(1 for w in workers if w.status == "active"),
            idle=sum(1 for w in workers if w.status == "idle"),
            offline=sum(1 for w in workers if w.status == "offline"),
        )

        queue_stats = self._frame_queue.stats() if self._frame_queue else {"pending": 0, "inflight": 0}

        total_frames = self._result_aggregator.count()
        elapsed = (datetime.now(timezone.utc) - self._start_time).total_seconds()
        fps = round(total_frames / elapsed, 4) if elapsed > 0 else 0.0

        lat = self._result_aggregator.latency_stats()
        latency = LatencyStats(
            avg_ms=lat["avg_ms"],
            p95_ms=lat["p95_ms"],
            samples=lat["samples"],
        )

        retry_count, dropped_count = (
            (self._frame_queue.retry_count, self._frame_queue.dropped_count)
            if self._frame_queue
            else (0, 0)
        )

        return SystemMetrics(
            workers=status_summary,
            queue=queue_stats,
            frames={"total": float(total_frames), "fps": fps},
            latency_ms=latency,
            retry_count=retry_count,
            dropped_count=dropped_count,
            system_start_time=self._start_time,
            # legacy fields
            number_of_workers=len(workers),
            total_frames_processed=total_frames,
            processing_fps=fps,
        )
