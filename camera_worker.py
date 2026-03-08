"""
camera_worker.py — run this on each Camera Laptop.

It captures webcam frames, runs YOLOv8 vehicle detection, registers itself
with the Admin backend, streams detection events to Admin, and periodically
prints a live summary of ALL cameras (fetched from Admin /analytics).

Usage:
    python3 camera_worker.py \
        --admin-url http://<ADMIN_IP>:8001 \
        --camera-id cam1 \
        --camera-name "Camera Laptop 1" \
        --source 0          # 0 = built-in webcam, 1 = external, or /path/to/video.mp4

Requirements:
    pip install ultralytics opencv-python requests
"""

import argparse
import socket
import sys
import time
import threading
from datetime import datetime, timezone

import cv2
import requests
from ultralytics import YOLO

# ── Vehicle class names YOLOv8 COCO uses ──────────────────────────────────────
VEHICLE_CLASSES = {2: "car", 3: "motorcycle", 5: "bus", 7: "truck"}

# ── How often to send heartbeat / poll analytics (seconds) ────────────────────
HEARTBEAT_INTERVAL = 10
ANALYTICS_INTERVAL = 5


def get_local_ip() -> str:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


def register(admin_url: str, camera_id: str, camera_name: str) -> bool:
    payload = {
        "camera_id": camera_id,
        "hostname": camera_name,
        "ip_address": get_local_ip(),
    }
    try:
        r = requests.post(f"{admin_url}/register-camera", json=payload, timeout=5)
        r.raise_for_status()
        print(f"[INFO] Registered as '{camera_id}' with admin at {admin_url}")
        return True
    except Exception as e:
        print(f"[ERROR] Could not register with admin: {e}")
        return False


def send_heartbeat(admin_url: str, camera_id: str) -> None:
    try:
        requests.post(f"{admin_url}/heartbeat/{camera_id}", timeout=3)
    except Exception:
        pass  # silently retry next cycle


def send_detection(admin_url: str, camera_id: str, count: int, types: list[str]) -> None:
    payload = {
        "camera_id": camera_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "detected_vehicles": count,
        "vehicle_types": types,
    }
    try:
        requests.post(f"{admin_url}/camera-detection", json=payload, timeout=3)
    except Exception:
        pass  # network blip; frame result is best-effort


def fetch_and_print_analytics(admin_url: str, camera_id: str) -> None:
    try:
        r = requests.get(f"{admin_url}/analytics", timeout=3)
        data = r.json()
        total = data.get("total_vehicles", 0)
        per_cam = data.get("per_camera", {})

        print("\n┌─ NETWORK SUMMARY ──────────────────────────────")
        print(f"│  Total vehicles (all cameras): {total}")
        for cid, cnt in per_cam.items():
            marker = " ← YOU" if cid == camera_id else ""
            print(f"│  {cid}: {cnt} vehicles{marker}")
        types = data.get("type_distribution", {})
        if types:
            type_str = "  ".join(f"{k}:{v}" for k, v in types.items())
            print(f"│  Types: {type_str}")
        print("└────────────────────────────────────────────────\n")
    except Exception:
        pass


def heartbeat_loop(admin_url: str, camera_id: str, stop_event: threading.Event) -> None:
    while not stop_event.is_set():
        send_heartbeat(admin_url, camera_id)
        stop_event.wait(HEARTBEAT_INTERVAL)


def analytics_loop(admin_url: str, camera_id: str, stop_event: threading.Event) -> None:
    while not stop_event.is_set():
        fetch_and_print_analytics(admin_url, camera_id)
        stop_event.wait(ANALYTICS_INTERVAL)


def run(admin_url: str, camera_id: str, camera_name: str, source: str | int) -> None:
    # ── Try registering; retry until admin is reachable ───────────────────────
    while not register(admin_url, camera_id, camera_name):
        print("[INFO] Retrying registration in 5 seconds...")
        time.sleep(5)

    # ── Background threads ────────────────────────────────────────────────────
    stop_event = threading.Event()
    threading.Thread(
        target=heartbeat_loop, args=(admin_url, camera_id, stop_event), daemon=True
    ).start()
    threading.Thread(
        target=analytics_loop, args=(admin_url, camera_id, stop_event), daemon=True
    ).start()

    # ── Load model ────────────────────────────────────────────────────────────
    print("[INFO] Loading YOLOv8n model...")
    model = YOLO("yolov8n.pt")
    print("[INFO] Model loaded. Starting capture...")

    cap = cv2.VideoCapture(int(source) if str(source).isdigit() else source)
    if not cap.isOpened():
        print(f"[ERROR] Cannot open video source: {source}")
        stop_event.set()
        sys.exit(1)

    fps_target = 5          # run inference at ~5 fps to keep CPU reasonable
    frame_delay = 1.0 / fps_target
    last_send = 0.0

    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                print("[INFO] Stream ended or frame read failed.")
                break

            t_start = time.time()

            # ── Run detection ─────────────────────────────────────────────────
            results = model(frame, verbose=False)[0]
            vehicle_types: list[str] = []
            annotated = frame.copy()

            for box in results.boxes:
                cls_id = int(box.cls[0])
                conf = float(box.conf[0])
                if cls_id in VEHICLE_CLASSES and conf >= 0.4:
                    label = VEHICLE_CLASSES[cls_id]
                    vehicle_types.append(label)
                    x1, y1, x2, y2 = map(int, box.xyxy[0])
                    cv2.rectangle(annotated, (x1, y1), (x2, y2), (0, 200, 0), 2)
                    cv2.putText(
                        annotated, f"{label} {conf:.2f}",
                        (x1, y1 - 8), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 200, 0), 1
                    )

            count = len(vehicle_types)

            # ── Send to admin (throttled to fps_target) ───────────────────────
            now = time.time()
            if now - last_send >= frame_delay:
                send_detection(admin_url, camera_id, count, vehicle_types)
                last_send = now

            # ── Show local window ─────────────────────────────────────────────
            overlay = f"{camera_name}  |  vehicles: {count}"
            cv2.putText(annotated, overlay, (10, 28),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)
            cv2.imshow(f"Camera: {camera_id}", annotated)

            if cv2.waitKey(1) & 0xFF == ord("q"):
                print("[INFO] 'q' pressed — stopping.")
                break

            # ── Pace loop to ~fps_target ──────────────────────────────────────
            elapsed = time.time() - t_start
            if elapsed < frame_delay:
                time.sleep(frame_delay - elapsed)

    except KeyboardInterrupt:
        print("\n[INFO] Interrupted.")
    finally:
        stop_event.set()
        cap.release()
        cv2.destroyAllWindows()
        print("[INFO] Camera worker stopped.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Edge AI Camera Worker")
    parser.add_argument(
        "--admin-url",
        required=True,
        help="Admin backend URL, e.g. http://192.168.1.10:8001",
    )
    parser.add_argument(
        "--camera-id",
        required=True,
        help="Unique ID for this camera, e.g. cam1",
    )
    parser.add_argument(
        "--camera-name",
        default=None,
        help="Display name, e.g. 'Camera Laptop 1' (defaults to camera-id)",
    )
    parser.add_argument(
        "--source",
        default="0",
        help="Video source: 0 for webcam, 1 for USB cam, or path to video file",
    )
    args = parser.parse_args()

    run(
        admin_url=args.admin_url.rstrip("/"),
        camera_id=args.camera_id,
        camera_name=args.camera_name or args.camera_id,
        source=args.source,
    )
