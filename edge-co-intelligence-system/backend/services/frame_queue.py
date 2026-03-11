"""
frame_queue.py — Distributed task queue for frame dispatch.

Implements:
  - Task distribution: enqueue JPEG frames, assign to least-loaded worker
  - Parallel processing: multiple workers pull tasks concurrently via HTTP POST
  - Fault tolerance: unacknowledged tasks are re-queued after TASK_TIMEOUT_SECS
  - Retry limit: tasks that fail MAX_RETRIES times are dropped with logging
"""
from __future__ import annotations

import base64
import concurrent.futures
import threading
import time
import uuid
from collections import deque
from datetime import datetime, timedelta, timezone
from typing import Optional

import httpx

from backend.models import FrameTask

# Max parallel HTTP dispatch threads for the watchdog drain phase
_DISPATCH_WORKERS = 16


MAX_RETRIES = 3
TASK_TIMEOUT_SECS = 5    # re-queue if worker doesn't respond in this time (was 15)
DISPATCH_TIMEOUT_SECS = 8
MAX_PENDING = 500         # max buffered tasks; frames dropped beyond this cap


class FrameQueue:
    """
    Thread-safe queue that distributes JPEG frames to registered worker nodes.

    Flow:
        coordinator                worker laptop
        ──────────                 ─────────────
        enqueue(jpeg) ──POST /process-frame──► run YOLO
                      ◄──POST /results────────  return detections

    Fault tolerance:
        A watchdog thread scans inflight tasks every 5 s.
        Tasks older than TASK_TIMEOUT_SECS without a result are re-queued
        (up to MAX_RETRIES times), then discarded.
    """

    def __init__(self, worker_manager, result_aggregator, inference_service=None) -> None:
        self._wm = worker_manager
        self._ra = result_aggregator
        self._inference = inference_service
        self._lock = threading.Lock()
        self._pending: deque[FrameTask] = deque()           # waiting for a free worker
        self._inflight: dict[str, FrameTask] = {}           # dispatched, awaiting result
        self._stop_event = threading.Event()
        # Counters for monitoring
        self.retry_count: int = 0
        self.dropped_count: int = 0
        # Register cancel callback so WorkerManager can purge inflight tasks on re-registration
        self._wm._on_worker_reregister = self._cancel_inflight_for_worker
        self._watchdog = threading.Thread(
            target=self._watchdog_loop, daemon=True, name="frame-queue-watchdog"
        )
        self._watchdog.start()

    # ── Public API ────────────────────────────────────────────────────────────

    def enqueue(self, frame_id: int, jpeg_bytes: bytes, required_capability: str = "yolov8n") -> Optional[str]:
        """
        Attempt to dispatch a frame immediately to the least-loaded worker that
        advertises required_capability.  If no capable workers are available,
        buffer the task in _pending for the watchdog to retry.
        Returns the task_id, or None only if truly no workers of any kind exist.
        """
        task = FrameTask(
            task_id=uuid.uuid4().hex[:12],
            frame_id=frame_id,
            jpeg_b64=base64.b64encode(jpeg_bytes).decode(),
            dispatched_at=datetime.now(timezone.utc),
            assigned_worker="",
            required_capability=required_capability,
        )
        return self._try_dispatch_or_buffer(task)

    def _try_dispatch_or_buffer(self, task: FrameTask) -> Optional[str]:
        """Dispatch immediately if a capable worker is available, otherwise buffer."""
        worker = self._wm.least_loaded(required_capability=task.required_capability)
        if worker is None:
            # No capable remote workers registered — signal caller
            return None

        task = task.model_copy(update={"assigned_worker": worker.worker_id})
        self._wm.increment_pending(worker.worker_id)

        # ── Local fast-path: run inference in-process, skip HTTP ──────────
        if worker.worker_id == "coordinator-local" and self._inference is not None:
            success = self._dispatch_local(task)
        else:
            target_url = f"http://{worker.ip_address or worker.host}:{worker.port}/process-frame"
            success = self._dispatch(task, target_url)

        if success:
            with self._lock:
                self._inflight[task.task_id] = task
            return task.task_id
        else:
            self._wm.decrement_pending(worker.worker_id)
            # Worker failed: buffer the task so the watchdog can retry later
            with self._lock:
                if len(self._pending) >= MAX_PENDING:
                    self.dropped_count += 1
                    print(f"[queue] frame {task.frame_id} dropped — pending buffer full ({MAX_PENDING})")
                    return None
                self._pending.append(task)
            return task.task_id  # return non-None so caller doesn't run locally

    def acknowledge(self, task_id: str) -> None:
        """Called when a worker's result arrives — removes the task from inflight."""
        with self._lock:
            task = self._inflight.pop(task_id, None)
        if task and task.assigned_worker:
            self._wm.reset_timeout_counter(task.assigned_worker)

    def _cancel_inflight_for_worker(self, worker_id: str) -> None:
        """Move all inflight tasks belonging to worker_id back to the pending buffer."""
        with self._lock:
            cancelled = [
                t for t in self._inflight.values()
                if t.assigned_worker == worker_id
            ]
            for t in cancelled:
                del self._inflight[t.task_id]
                # Re-queue as a fresh task (reset retry counter — the worker restarted)
                requeued = t.model_copy(update={"retries": 0, "assigned_worker": ""})
                self._pending.appendleft(requeued)
        if cancelled:
            print(f"[queue] {len(cancelled)} inflight task(s) requeued after '{worker_id}' re-registered")

    def stats(self) -> dict:
        with self._lock:
            return {
                "pending": len(self._pending),
                "inflight": len(self._inflight),
                "retry_count": self.retry_count,
                "dropped_count": self.dropped_count,
            }

    def stop(self) -> None:
        self._stop_event.set()

    # ── Internal dispatch ─────────────────────────────────────────────────────

    def _dispatch_local(self, task: FrameTask) -> bool:
        """
        In-process fast-path: decode base64, run YOLO directly, store result.
        No HTTP round-trip, no JSON serialisation overhead.
        """
        try:
            jpeg_bytes = base64.b64decode(task.jpeg_b64)
            result = self._inference.run(jpeg_bytes, task.frame_id)
            self._ra.store_frame_result(task.frame_id, result, "coordinator-local")
            self.acknowledge(task.task_id)
            return True
        except Exception as exc:
            print(f"[queue] local inference failed for frame {task.frame_id}: {exc}")
            return False

    def _dispatch(self, task: FrameTask, url: str) -> bool:
        """
        HTTP POST the frame task to a remote worker.
        Returns True on success, False on any network error.
        """
        try:
            payload = {
                "task_id": task.task_id,
                "frame_id": task.frame_id,
                "jpeg_b64": task.jpeg_b64,
            }
            resp = httpx.post(url, json=payload, timeout=DISPATCH_TIMEOUT_SECS)
            return resp.status_code == 200
        except Exception as exc:
            print(f"[queue] dispatch to {url} failed: {exc}")
            return False

    # ── Fault tolerance watchdog ──────────────────────────────────────────────

    def _watchdog_loop(self) -> None:
        """
        Periodically:
          1. Drains the _pending buffer by trying to dispatch buffered tasks.
          2. Re-queues inflight tasks that have timed out.
          3. Drops tasks that exceed MAX_RETRIES.
        """
        while not self._stop_event.is_set():
            time.sleep(5)

            # ── Drain pending buffer (parallel dispatch) ──────────────────────
            drained: list[FrameTask] = []
            with self._lock:
                while self._pending:
                    drained.append(self._pending.popleft())

            # Build (dispatched_task, url_or_None) pairs first so we only hold the lock briefly
            dispatch_batch: list[tuple[FrameTask, str | None]] = []
            no_worker_tasks: list[FrameTask] = []
            for task in drained:
                worker = self._wm.least_loaded(required_capability=task.required_capability)
                if worker is None:
                    no_worker_tasks.append(task)
                    continue
                dispatched = task.model_copy(
                    update={"assigned_worker": worker.worker_id,
                            "dispatched_at": datetime.now(timezone.utc)}
                )
                self._wm.increment_pending(worker.worker_id)
                if worker.worker_id == "coordinator-local" and self._inference is not None:
                    dispatch_batch.append((dispatched, None))  # None = local fast-path
                else:
                    url = f"http://{worker.ip_address or worker.host}:{worker.port}/process-frame"
                    dispatch_batch.append((dispatched, url))

            # Re-buffer tasks that had no eligible worker
            with self._lock:
                for task in no_worker_tasks:
                    self._pending.appendleft(task)

            # Dispatch all ready tasks in parallel — avoids blocking on slow workers
            with concurrent.futures.ThreadPoolExecutor(max_workers=_DISPATCH_WORKERS) as ex:
                future_to_task = {}
                for t, url in dispatch_batch:
                    if url is None:
                        # Local fast-path: in-process inference
                        future_to_task[ex.submit(self._dispatch_local, t)] = t
                    else:
                        future_to_task[ex.submit(self._dispatch, t, url)] = t
                for future in concurrent.futures.as_completed(future_to_task):
                    dispatched = future_to_task[future]
                    if future.result():
                        with self._lock:
                            self._inflight[dispatched.task_id] = dispatched
                    else:
                        self._wm.decrement_pending(dispatched.assigned_worker)
                        with self._lock:
                            self._pending.append(dispatched)  # back to pending

            # ── Handle inflight timeouts ──────────────────────────────────────
            now = datetime.now(timezone.utc)
            cutoff = now - timedelta(seconds=TASK_TIMEOUT_SECS)

            with self._lock:
                timed_out = [
                    t for t in self._inflight.values()
                    if t.dispatched_at < cutoff
                ]

            for task in timed_out:
                with self._lock:
                    self._inflight.pop(task.task_id, None)

                self._wm.decrement_pending(task.assigned_worker)
                # Circuit breaker: too many consecutive timeouts → mark worker offline now
                self._wm.record_timeout(task.assigned_worker)

                if task.retries >= MAX_RETRIES:
                    self.dropped_count += 1
                    print(
                        f"[queue] task {task.task_id} frame {task.frame_id} "
                        f"dropped after {MAX_RETRIES} retries"
                    )
                    continue

                worker = self._wm.least_loaded(required_capability=task.required_capability)
                if worker is None:
                    print(f"[queue] retry buffered — no workers for frame {task.frame_id}")
                    retried = task.model_copy(update={"retries": task.retries + 1})
                    with self._lock:
                        self._pending.append(retried)
                    continue

                retried = task.model_copy(
                    update={
                        "task_id": uuid.uuid4().hex[:12],
                        "dispatched_at": datetime.now(timezone.utc),
                        "assigned_worker": worker.worker_id,
                        "retries": task.retries + 1,
                    }
                )
                target_url = f"http://{worker.ip_address or worker.host}:{worker.port}/process-frame"
                self._wm.increment_pending(worker.worker_id)
                self.retry_count += 1
                print(
                    f"[queue] retrying frame {task.frame_id} "
                    f"(attempt {retried.retries}/{MAX_RETRIES}) → {worker.worker_id}"
                )
                if self._dispatch(retried, target_url):
                    with self._lock:
                        self._inflight[retried.task_id] = retried
                else:
                    self._wm.decrement_pending(worker.worker_id)
                    with self._lock:
                        self._pending.append(retried)
