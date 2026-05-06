from __future__ import annotations

import argparse
import json
import socket
import time


def build_payload(kind: str) -> bytes:
    if kind == "ping":
        payload = {"type": "ping", "ts": time.time()}
    elif kind == "color":
        payload = {"type": "color", "r": 64, "g": 64, "b": 0, "ts": time.time()}
    else:
        payload = {
            "hex": "4B1902",
            "flight": "TEST123",
            "lat": 49.121479,
            "lon": 9.211960,
            "alt": 35000,
            "ts": time.time(),
        }
    return json.dumps(payload, separators=(",", ":")).encode("utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="10.42.0.1")
    parser.add_argument("--port", type=int, default=5005)
    parser.add_argument("--kind", choices=["ping", "color", "aircraft"], default="aircraft")
    args = parser.parse_args()

    data = build_payload(args.kind)
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.sendto(data, (args.host, args.port))
    finally:
        sock.close()
    print(f"sent {len(data)} bytes to {args.host}:{args.port}")
    print(data.decode("utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

