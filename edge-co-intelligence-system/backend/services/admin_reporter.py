"""
admin_reporter.py — reports this camera's detection results to the Admin Portal.

Activated only when ADMIN_URL is set in the environment.
Does three things:
  1. Registers this camera with Admin on startup (retries until success).
  2. Sends a heartbeat to Admin every HEARTBEAT_INTERVAL seconds.
  3. Exposes report_job_summary(job_id) so video_routes can push a detection
     event to Admin immediately when a video job finishes.
"""
from __future__ import annotations

import socket
import threading
import time
from datetime import datetime, timezone
from typing import Optional

import requests

from backend.config import ADMIN_URL, CAMERA_ID, CAMERA_NAME

HEARTBEAT_INTERVAL = 15   # seconds between heartbeats


def _local_ip() -> str:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


class AdminReporter:
    """Background worker that keeps Admin informed about this camera."""

    def __init__(self) -> None:
        self._stop = threading.Event()
        self._registered = False

    def start(self) -> None:
        threading.Thread(target=self._run, daemon=True, name="admin-reporter").start()

    def stop(self) -> None:
        self._stop.set()

    # ── Registration ──────────────────────────────────────────────────────────

    def _register(self) -> bool:
        payload = {
            "camera_id": CAMERA_ID,
            "hostname": CAMERA_NAME,
            "ip_address": _local_ip(),
        }
        try:
            r = requests.post(f"{ADMIN_URL}/register-camera", json=payload, timeout=5)
            r.raise_for_status()
            print(f"[admin-reporter] registered '{CAMERA_ID}' with admin at {ADMIN_URL}")
            return True
        except Exception as e:
            print(f"[admin-reporter] registration failed: {e}")
            return False

    # ── Heartbeat loop ────────────────────────────────────────────────────────

    def _run(self) -> None:
        # Registration + heartbeat loop — re-registers whenever admin restarts
        while not self._stop.is_set():
            # Ensure we are registered before heartbeating
            while not self._stop.is_set():
                if self._register():
                    self._registered = True
                    break
                self._stop.wait(5)

            # Heartbeat loop — exits back to registration if admin doesn't know us
            while not self._stop.is_set():
                try:
                    r = requests.post(
                        f"{ADMIN_URL}/heartbeat/{CAMERA_ID}", timeout=3
                    )
                    if r.status_code == 404:
                        # Admin restarted and lost our registration — re-register
                        print(f"[admin-reporter] heartbeat 404 — re-registering with admin")
                        self._registered = False
                        break  # break inner loop → outer loop re-registers
                except Exception:
                    pass
                self._stop.wait(HEARTBEAT_INTERVAL)

    # ── Detection reporting ───────────────────────────────────────────────────

    def report_job_summary(self, total_count: int, object_types: list, object_counts: Optional[dict] = None) -> None:
        """
        Push a detection event to Admin with all detected object counts from this job.
        Called by video_routes after every successfully processed video.
        """
        if not ADMIN_URL:
            return
        payload = {
            "camera_id": CAMERA_ID,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "detected_vehicles": total_count,
            "vehicle_types": object_types,
            "object_counts": object_counts or {},
        }
        try:
            requests.post(f"{ADMIN_URL}/camera-detection", json=payload, timeout=4)
            print(
                f"[admin-reporter] reported {total_count} objects "
                f"({len(object_types)} types) to admin"
            )
        except Exception as e:
            print(f"[admin-reporter] failed to report detection: {e}")


# Module-level singleton (only created if ADMIN_URL is set)
_reporter: Optional[AdminReporter] = None


def get_reporter() -> AdminReporter:
    global _reporter
    if _reporter is None:
        _reporter = AdminReporter()
    return _reporter
