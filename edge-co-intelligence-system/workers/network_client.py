"""
network_client.py — TCP communication with the coordinator.

Wire protocol (big-endian, matches coordinator):
    Receive:  [4B frame_id][4B payload_len][payload_len bytes JPEG]
    Send:     [4B frame_id][4B result_len][result_len bytes JSON]
    Sentinel: frame_id == 0  →  shutdown
"""

import socket
import struct

from workers.config import COORDINATOR_HOST, COORDINATOR_PORT


def recv_exact(sock: socket.socket, n: int) -> bytes:
    """Read exactly *n* bytes; raises ConnectionError on short read."""
    buf = bytearray()
    while len(buf) < n:
        chunk = sock.recv(n - len(buf))
        if not chunk:
            raise ConnectionError(
                f"Connection closed after {len(buf)}/{n} bytes."
            )
        buf.extend(chunk)
    return bytes(buf)


def send_result(sock: socket.socket, frame_id: int, data: bytes) -> None:
    """Send a length-prefixed result message to the coordinator."""
    header = struct.pack(">II", frame_id, len(data))
    sock.sendall(header + data)


def recv_frame(sock: socket.socket) -> tuple[int, bytes]:
    """
    Receive one frame from the coordinator.

    Returns:
        (frame_id, jpeg_bytes)
        frame_id == 0 signals shutdown; jpeg_bytes will be empty.
    """
    header = recv_exact(sock, 8)
    frame_id, payload_len = struct.unpack(">II", header)
    payload = recv_exact(sock, payload_len) if payload_len > 0 else b""
    return frame_id, payload


def connect(host: str = COORDINATOR_HOST, port: int = COORDINATOR_PORT) -> socket.socket:
    """
    Open a TCP connection to the coordinator.

    Returns:
        Connected socket.

    Raises:
        ConnectionRefusedError: If the coordinator is not listening.
    """
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect((host, port))
    print(f"[network] Connected to coordinator at {host}:{port}", flush=True)
    return sock
