"""
result_aggregator.py — Stores per-frame inference results and computes aggregates.

Improvements over the original:
  - Running totals (O(1) aggregation instead of O(n) on every GET)
  - Memory cap: only the most recent MAX_STORED_FRAMES results are kept
  - Latency tracking: maintains sorted sample list for P95 computation
"""
from __future__ import annotations

import statistics
from collections import OrderedDict
from datetime import datetime, timezone
from threading import Lock
from typing import Optional

# Number of independent lock shards — reduces contention when many workers
# submit results simultaneously. Must be a power of two for clean modulo.
_N_SHARDS = 16

from backend.models import (
    AggregatedResults,
    BoundingBox,
    Detection,
    FrameResult,
    FrameResultRequest,
    InferenceResultRequest,
)
from backend.services.worker_manager import WorkerManager

# Keep at most this many frames in memory; evict oldest when limit is reached.
MAX_STORED_FRAMES: int = 2000
MAX_STORED_ALERTS: int = 200


class ResultAggregator:
    """
    Thread-safe store for per-frame inference results.

    Uses an OrderedDict capped at MAX_STORED_FRAMES to bound memory usage.
    Maintains running counters so GET /results is O(1) instead of O(n).
    """

    def __init__(self, worker_manager: WorkerManager) -> None:
        # Sharded locks: each shard guards frame_ids where frame_id % _N_SHARDS == shard.
        # Reduces lock contention when many workers submit results in parallel.
        self._shards: list[Lock] = [Lock() for _ in range(_N_SHARDS)]
        # Single meta-lock for running totals (grabbed only for counter updates)
        self._totals_lock = Lock()
        # OrderedDict preserves insertion order — oldest entries are first
        self._results: OrderedDict[int, FrameResult] = OrderedDict()
        self._worker_manager = worker_manager

        # Running totals — updated on every store, avoids full recomputation
        self._total_detections: int = 0
        self._total_counts: dict[str, int] = {}
        self._worker_summary: dict[str, int] = {}   # worker_id → frames processed

        # Latency samples (processing_time_ms) — capped at 500 for P95 accuracy
        self._latency_samples: list[float] = []
        self._MAX_LATENCY_SAMPLES: int = 500

        # Alert events raised by edge workers
        self._alerts: list[dict] = []
        self._alerts_lock = Lock()

    # ── Writes ────────────────────────────────────────────────────────────────

    def add_result(self, req: InferenceResultRequest) -> FrameResult:
        """Store a result submitted with full Detection objects (socket flow)."""
        counts: dict[str, int] = {}
        for det in req.detections:
            counts[det.label] = counts.get(det.label, 0) + 1

        result = FrameResult(
            frame_id=req.frame_id,
            worker_id=req.worker_id,
            detections=req.detections,
            object_counts=counts,
            processing_time_ms=req.processing_time_ms,
            received_at=datetime.now(timezone.utc),
        )
        self._store(result)
        self._worker_manager.increment_frames(req.worker_id)
        return result

    def add_frame_result(self, req: FrameResultRequest) -> FrameResult:
        """Store a result submitted via the REST /frame-result endpoint."""
        detections = [
            Detection(label=label, confidence=1.0, box=BoundingBox(x1=0, y1=0, x2=0, y2=0))
            for label in req.detected_objects
        ]
        counts: dict[str, int] = {}
        for label in req.detected_objects:
            counts[label] = counts.get(label, 0) + 1

        result = FrameResult(
            frame_id=req.frame_id,
            worker_id=req.worker_id,
            detections=detections,
            object_counts=counts,
            processing_time_ms=req.processing_time * 1000,  # s → ms
            received_at=datetime.now(timezone.utc),
        )
        self._store(result)
        self._worker_manager.increment_frames(req.worker_id)
        return result

    def store_frame_result(self, frame_id: int, result: FrameResult, worker_id: str) -> FrameResult:
        """Store a fully-constructed FrameResult directly (used by YOLO inference pipeline)."""
        self._store(result)
        self._worker_manager.increment_frames(worker_id)
        return result

    # ── Reads ─────────────────────────────────────────────────────────────────

    def get_summary(self) -> dict:
        """O(1) metrics snapshot — never builds the full frame list."""
        with self._totals_lock:
            return {
                "total_frames": len(self._results),
                "total_detections": self._total_detections,
                "object_counts": dict(self._total_counts),
                "worker_summary": dict(self._worker_summary),
            }

    def get_aggregated(self) -> AggregatedResults:
        """Full result set — use get_summary() for dashboard polling."""
        with self._totals_lock:
            frames = list(self._results.values())
            total_counts = dict(self._total_counts)
            worker_summary = dict(self._worker_summary)
            total_detections = self._total_detections

        return AggregatedResults(
            total_frames_processed=len(frames),
            total_detections=total_detections,
            object_counts=total_counts,
            frames=sorted(frames, key=lambda f: f.frame_id),
            worker_summary=worker_summary,
        )

    def count(self) -> int:
        with self._totals_lock:
            return len(self._results)

    def latency_stats(self) -> dict:
        """Return avg and P95 latency in ms across stored samples."""
        with self._totals_lock:
            samples = list(self._latency_samples)
        if not samples:
            return {"avg_ms": 0.0, "p95_ms": 0.0, "samples": 0}
        avg = round(statistics.mean(samples), 2)
        sorted_s = sorted(samples)
        idx = max(0, int(len(sorted_s) * 0.95) - 1)
        p95 = round(sorted_s[idx], 2)
        return {"avg_ms": avg, "p95_ms": p95, "samples": len(samples)}

    # ── Alerts ──────────────────────────────────────────────────────────────────

    def add_alert(self, alert: dict) -> None:
        """Store a high-confidence alert event from an edge worker."""
        with self._alerts_lock:
            if len(self._alerts) >= MAX_STORED_ALERTS:
                self._alerts.pop(0)
            self._alerts.append(alert)

    def get_alerts(self) -> list[dict]:
        """Return recent alerts, newest first."""
        with self._alerts_lock:
            return list(reversed(self._alerts))

    # ── Internal ──────────────────────────────────────────────────────────────
    @staticmethod
    def _merge_results(a: FrameResult, b: FrameResult) -> FrameResult:
        """
        Consensus merge: two workers saw the same frame independently.
        Keep the highest-confidence detection per label across both sets.
        Worker ID becomes 'a.worker_id+b.worker_id' to record merged origin.
        """
        best: dict[str, Detection] = {}
        for det in (*a.detections, *b.detections):
            if det.label not in best or det.confidence > best[det.label].confidence:
                best[det.label] = det
        merged_detections = list(best.values())
        merged_counts = {d.label: 1 for d in merged_detections}
        return FrameResult(
            frame_id=a.frame_id,
            worker_id=f"{a.worker_id}+{b.worker_id}",
            detections=merged_detections,
            object_counts=merged_counts,
            processing_time_ms=min(a.processing_time_ms, b.processing_time_ms),
            received_at=b.received_at,
        )
    def _store(self, result: FrameResult) -> None:
        """
        Thread-safe write with:
          - Sharded per-frame locking: frame_id % _N_SHARDS selects the shard,
            so concurrent writes to different frames never block each other.
          - Consensus merge when the same frame_id arrives from a different worker
          - Memory cap eviction (oldest entry removed when over limit)
          - Running counter updates
        """
        shard = self._shards[result.frame_id % _N_SHARDS]
        with shard, self._totals_lock:
            existing = self._results.get(result.frame_id)

            # ── Consensus merge: different workers processed the same frame ──
            if existing is not None and existing.worker_id != result.worker_id:
                result = self._merge_results(existing, result)
                # Fall through: the normal "overwrite" path below subtracts
                # existing's contribution and adds the merged result's.

            # If overwriting an existing frame_id, subtract its contribution first
            if existing is not None:
                self._total_detections -= len(existing.detections)
                for label, cnt in existing.object_counts.items():
                    self._total_counts[label] = max(0, self._total_counts.get(label, 0) - cnt)
                    if self._total_counts[label] == 0:
                        del self._total_counts[label]
                old_worker = existing.worker_id
                self._worker_summary[old_worker] = max(0, self._worker_summary.get(old_worker, 0) - 1)

            # Evict oldest entry if at capacity
            if len(self._results) >= MAX_STORED_FRAMES and result.frame_id not in self._results:
                oldest_id, oldest = next(iter(self._results.items()))
                self._results.pop(oldest_id)
                self._total_detections -= len(oldest.detections)
                for label, cnt in oldest.object_counts.items():
                    self._total_counts[label] = max(0, self._total_counts.get(label, 0) - cnt)
                    if self._total_counts[label] == 0:
                        del self._total_counts[label]
                self._worker_summary[oldest.worker_id] = max(
                    0, self._worker_summary.get(oldest.worker_id, 0) - 1
                )

            # Store new result and update running totals
            self._results[result.frame_id] = result
            self._total_detections += len(result.detections)
            for label, cnt in result.object_counts.items():
                self._total_counts[label] = self._total_counts.get(label, 0) + cnt
            self._worker_summary[result.worker_id] = (
                self._worker_summary.get(result.worker_id, 0) + 1
            )

            # Latency sample (ring buffer)
            if result.processing_time_ms > 0:
                if len(self._latency_samples) >= self._MAX_LATENCY_SAMPLES:
                    self._latency_samples.pop(0)
                self._latency_samples.append(result.processing_time_ms)

