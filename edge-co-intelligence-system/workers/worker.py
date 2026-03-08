"""
worker.py — Edge worker node entry point.

Connects to the coordinator, receives JPEG frames, runs YOLOv8 inference
via inference.py, and sends JSON results back over the TCP socket.

Usage:
    python -m workers.worker
    COORDINATOR_HOST=192.168.1.10 python -m workers.worker
"""

import json
import sys

from workers.config import COORDINATOR_HOST, COORDINATOR_PORT
from workers.inference import decode_frame, load_model, run_inference
from workers.network_client import connect, recv_frame, send_result


def main() -> None:
    model = load_model()

    try:
        sock = connect(COORDINATOR_HOST, COORDINATOR_PORT)
    except ConnectionRefusedError:
        print(
            f"[worker] Could not connect to coordinator at "
            f"{COORDINATOR_HOST}:{COORDINATOR_PORT}. Is it running?",
            flush=True,
        )
        sys.exit(1)

    try:
        while True:
            frame_id, jpeg_bytes = recv_frame(sock)

            # Shutdown sentinel
            if frame_id == 0:
                print("[worker] Received shutdown sentinel. Exiting.", flush=True)
                break

            print(f"[worker] Received frame {frame_id} ({len(jpeg_bytes)} bytes)", flush=True)

            frame = decode_frame(jpeg_bytes)
            result = run_inference(model, frame)
            result["frame_id"] = frame_id

            counts_str = (
                ", ".join(f"{k}: {v}" for k, v in result["counts"].items()) or "none"
            )
            print(f"[worker] Frame {frame_id} — objects: {counts_str}", flush=True)

            send_result(sock, frame_id, json.dumps(result).encode())

    except ConnectionError as exc:
        print(f"[worker] Connection lost: {exc}", flush=True)
    finally:
        sock.close()


if __name__ == "__main__":
    main()
