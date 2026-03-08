"""
worker_manager.py — Thread-safe registry of connected worker nodes.

Implements:
  - Worker registration / removal
  - Heartbeat tracking  (fault tolerance)
  - Stale-worker eviction (fault tolerance)
  - Capability-aware least-loaded worker selection (load balancing)
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from threading import Lock
from typing import Callable

from backend.models import WorkerInfo, WorkerNodeRequest, WorkerRegisterRequest

# Max consecutive task timeouts before a worker is proactively marked offline
CIRCUIT_BREAKER_THRESHOLD: int = 3


class WorkerManager:
    """Maintains an in-memory registry of all registered worker nodes."""

    HEARTBEAT_TIMEOUT_SECS: int = 30  # workers silent longer than this are marked offline

    def __init__(self) -> None:
        self._lock = Lock()
        self._workers: dict[str, WorkerInfo] = {}
        # consecutive_timeouts[worker_id] → count of unacknowledged task timeouts
        self._consecutive_timeouts: dict[str, int] = {}
        # Pluggable callback so FrameQueue can cancel inflight tasks on re-registration
        self._on_worker_reregister: Callable[[str], None] | None = None

    # ── Registration ──────────────────────────────────────────────────────────

    def register(self, req: WorkerRegisterRequest) -> WorkerInfo:
        """Register via host/port (socket-based coordinator flow)."""
        worker = WorkerInfo(
            worker_id=req.worker_id,
            host=req.host,
            port=req.port,
            capabilities=req.capabilities,
            registered_at=datetime.now(timezone.utc),
            last_heartbeat=datetime.now(timezone.utc),
        )
        self._do_register(req.worker_id, worker)
        return worker

    def register_node(self, req: WorkerNodeRequest) -> WorkerInfo:
        """Register via hostname/ip_address (REST API flow)."""
        worker = WorkerInfo(
            worker_id=req.worker_id,
            host=req.ip_address,
            port=req.port,
            hostname=req.hostname,
            ip_address=req.ip_address,
            capabilities=req.capabilities,
            registered_at=datetime.now(timezone.utc),
            last_heartbeat=datetime.now(timezone.utc),
        )
        self._do_register(req.worker_id, worker)
        return worker

    def _do_register(self, worker_id: str, worker: WorkerInfo) -> None:
        """Internal: write worker into registry and trigger re-registration callback if replacing an existing entry."""
        is_reregister = False
        with self._lock:
            if worker_id in self._workers:
                is_reregister = True
            self._workers[worker_id] = worker
            self._consecutive_timeouts[worker_id] = 0
        # Cancel any inflight tasks assigned to this worker ID before the restart
        if is_reregister and self._on_worker_reregister:
            self._on_worker_reregister(worker_id)
            print(f"[coordinator] worker '{worker_id}' re-registered — inflight tasks cancelled")

    # ── Queries ───────────────────────────────────────────────────────────────

    def get_all(self) -> list[WorkerInfo]:
        with self._lock:
            return list(self._workers.values())

    def get(self, worker_id: str) -> WorkerInfo | None:
        with self._lock:
            return self._workers.get(worker_id)

    def remove(self, worker_id: str) -> bool:
        with self._lock:
            return self._workers.pop(worker_id, None) is not None

    def count(self) -> int:
        with self._lock:
            return len(self._workers)

    # ── Frame counters ────────────────────────────────────────────────────────

    def increment_frames(self, worker_id: str, processing_ms: float = 0.0) -> None:
        """Record a completed frame; update EMA of processing latency for scheduler."""
        with self._lock:
            w = self._workers.get(worker_id)
            if w:
                w.frames_processed += 1
                w.pending_frames = max(0, w.pending_frames - 1)
                w.status = "active"
                if processing_ms > 0:
                    alpha = 0.2  # EMA smoothing factor
                    w.avg_processing_ms = (
                        processing_ms if w.avg_processing_ms == 0.0
                        else (1 - alpha) * w.avg_processing_ms + alpha * processing_ms
                    )

    def increment_pending(self, worker_id: str) -> None:
        """Called when a frame is dispatched to a worker (not yet returned)."""
        with self._lock:
            w = self._workers.get(worker_id)
            if w:
                w.pending_frames += 1

    def decrement_pending(self, worker_id: str) -> None:
        with self._lock:
            w = self._workers.get(worker_id)
            if w:
                w.pending_frames = max(0, w.pending_frames - 1)

    def record_timeout(self, worker_id: str) -> bool:
        """
        Increment the consecutive-timeout counter for a worker.
        Returns True (and marks worker offline) if the circuit-breaker threshold
        is reached — this stops further dispatch without waiting for heartbeat expiry.
        """
        with self._lock:
            w = self._workers.get(worker_id)
            if w is None:
                return False
            self._consecutive_timeouts[worker_id] = (
                self._consecutive_timeouts.get(worker_id, 0) + 1
            )
            if self._consecutive_timeouts[worker_id] >= CIRCUIT_BREAKER_THRESHOLD:
                if w.status != "offline":
                    w.status = "offline"
                    w.pending_frames = 0
                    print(
                        f"[coordinator] circuit breaker OPEN for '{worker_id}' "
                        f"after {CIRCUIT_BREAKER_THRESHOLD} consecutive timeouts"
                    )
                return True
        return False

    def reset_timeout_counter(self, worker_id: str) -> None:
        """Called when a task is successfully acknowledged — resets the circuit breaker."""
        with self._lock:
            self._consecutive_timeouts[worker_id] = 0

    # ── Load balancing ────────────────────────────────────────────────────────

    def least_loaded(self, required_capability: str = "") -> WorkerInfo | None:
        """
        Return the active (or idle) worker with the lowest weighted load score.
        Score = pending_frames * avg_processing_ms; this penalises slow workers
        more than fast ones, preventing queue pile-up on heterogeneous hardware.
        Workers with no latency history default to 1000 ms (assumed slow).
        """
        with self._lock:
            candidates = [
                w for w in self._workers.values()
                if w.status in ("active", "idle")
                and (not required_capability or required_capability in w.capabilities)
            ]
        if not candidates:
            return None

        def _score(w: WorkerInfo) -> float:
            speed = w.avg_processing_ms if w.avg_processing_ms > 0 else 1000.0
            return w.pending_frames * speed

        return min(candidates, key=_score)

    # ── Fault tolerance: heartbeat ────────────────────────────────────────────

    def heartbeat(self, worker_id: str) -> bool:
        """
        Record a heartbeat from a worker.
        Returns False if the worker is not registered.
        """
        with self._lock:
            w = self._workers.get(worker_id)
            if w is None:
                return False
            w.last_heartbeat = datetime.now(timezone.utc)
            w.status = "active"
        return True

    def mark_idle(self, worker_id: str) -> None:
        """Worker signals it has no pending work."""
        with self._lock:
            w = self._workers.get(worker_id)
            if w:
                w.status = "idle"

    # ── Fault tolerance: stale eviction ──────────────────────────────────────

    def evict_stale(self) -> list[str]:
        """
        Mark workers as 'offline' if their last heartbeat is older than
        HEARTBEAT_TIMEOUT_SECS. Returns list of evicted worker IDs.

        Called periodically by the background eviction task in main.py.
        """
        cutoff = datetime.now(timezone.utc) - timedelta(
            seconds=self.HEARTBEAT_TIMEOUT_SECS
        )
        evicted: list[str] = []
        with self._lock:
            for w in self._workers.values():
                if w.last_heartbeat is not None and w.last_heartbeat < cutoff:
                    if w.status != "offline":
                        w.status = "offline"
                        w.pending_frames = 0   # reset so re-registration starts clean
                        evicted.append(w.worker_id)
        return evicted
