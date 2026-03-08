"""
networking.py — Low-level TCP helpers for the socket-based coordinator protocol.

Wire format (big-endian):
    [4 bytes: frame_id][4 bytes: payload_len][payload_len bytes: data]

A frame_id of 0 is the shutdown sentinel; workers stop processing on receipt.
"""
from __future__ import annotations

import socket
import struct


def recv_exact(sock: socket.socket, n: int) -> bytes:
    """
    Read exactly *n* bytes from *sock*.

    Raises:
        ConnectionError: If the connection is closed before all bytes arrive.
    """
    buf = bytearray()
    while len(buf) < n:
        chunk = sock.recv(n - len(buf))
        if not chunk:
            raise ConnectionError(
                f"Connection closed after {len(buf)}/{n} bytes."
            )
        buf.extend(chunk)
    return bytes(buf)


def send_message(sock: socket.socket, frame_id: int, data: bytes) -> None:
    """
    Send a length-prefixed message to *sock*.

    Format: [frame_id (4B big-endian)][len(data) (4B big-endian)][data]
    """
    header = struct.pack(">II", frame_id, len(data))
    sock.sendall(header + data)


def recv_message(sock: socket.socket) -> tuple[int, bytes]:
    """
    Receive one length-prefixed message from *sock*.

    Returns:
        (frame_id, payload_bytes)

    Raises:
        ConnectionError: If the connection drops mid-read.
    """
    header = recv_exact(sock, 8)
    frame_id, payload_len = struct.unpack(">II", header)
    payload = recv_exact(sock, payload_len)
    return frame_id, payload


def send_shutdown(sock: socket.socket) -> None:
    """Send the shutdown sentinel (frame_id=0, empty payload)."""
    send_message(sock, 0, b"")
