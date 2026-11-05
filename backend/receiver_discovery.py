#!/usr/bin/env python3
"""Colorlight receiver discovery - Phase 2, read-only.

Sends the same broadcast discovery frames FPP's own ColorLight-5a-75
channel output sends, and parses replies, independent of fppd so the web UI
can show this to the user on demand instead of only at channel-output
init-time in the log.

Requires raw-socket privilege (CAP_NET_RAW, plus CAP_NET_ADMIN to set
promiscuous mode on the receive socket, matching FPP's own driver). See
fpp_install.sh for how this plugin grants that narrowly via sudoers rather
than running the whole web stack as root.

Usage:
    receiver_discovery.py --iface eth1 --json
    receiver_discovery.py --iface eth1          # human-readable
"""
from __future__ import annotations

import argparse
import json
import socket
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import colorlight_protocol as clp  # noqa: E402

ETH_P_ALL = 0x0003
DISCOVERY_ETHERTYPE = 0x0805  # matches FPP's receive-socket htons(0x0805)
RECV_TIMEOUT_S = 0.3  # FPP waits up to 300ms per receiver id
MAX_RETRIES_AT_ZERO = 2  # FPP retries id 0 up to twice before giving up entirely


def discover(iface: str, max_id: int = clp.MAX_RECEIVER_ID) -> list[clp.ReceiverInfo]:
    send_sock = socket.socket(socket.AF_PACKET, socket.SOCK_RAW)
    send_sock.bind((iface, 0))

    recv_sock = socket.socket(socket.AF_PACKET, socket.SOCK_RAW, socket.htons(DISCOVERY_ETHERTYPE))
    recv_sock.bind((iface, 0))
    recv_sock.settimeout(RECV_TIMEOUT_S)

    found: list[clp.ReceiverInfo] = []
    receiver_id = 0
    retries_left = MAX_RETRIES_AT_ZERO

    try:
        while receiver_id <= max_id:
            frame = clp.build_discovery_frame(receiver_id)
            send_sock.send(frame)
            if receiver_id == 0 and retries_left == 0:
                send_sock.send(frame)
                send_sock.send(frame)

            found_this_id = False
            deadline = time.monotonic() + RECV_TIMEOUT_S
            while time.monotonic() < deadline:
                try:
                    recv_sock.settimeout(max(0.0, deadline - time.monotonic()))
                    reply = recv_sock.recv(clp.RESP_PACKET_SIZE + 64)
                except socket.timeout:
                    break
                info = clp.parse_discovery_reply(reply)
                if info is not None:
                    found.append(info)
                    found_this_id = True

            if not found_this_id and receiver_id == 0 and retries_left > 0:
                retries_left -= 1
                continue  # retry id 0 without advancing, matching FPP's loop
            if not found_this_id and receiver_id == 0 and retries_left == 0:
                # FPP stops entirely if id 0 never answers after retries.
                break

            receiver_id += 1
    finally:
        send_sock.close()
        recv_sock.close()

    return found


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--iface", required=True, help="Network interface to scan, e.g. eth1")
    parser.add_argument("--json", action="store_true", help="Emit JSON instead of a text table")
    parser.add_argument("--max-id", type=int, default=clp.MAX_RECEIVER_ID)
    args = parser.parse_args()

    try:
        receivers = discover(args.iface, args.max_id)
    except PermissionError:
        print(json.dumps({"error": "permission_denied",
                           "message": "Raw socket access denied - check the sudoers rule installed by fpp_install.sh"}),
              file=sys.stderr if not args.json else sys.stdout)
        return 1
    except OSError as e:
        payload = {"error": "socket_error", "message": str(e)}
        print(json.dumps(payload) if args.json else f"Error: {e}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps({"receivers": [r.to_dict() for r in receivers]}, indent=2))
    else:
        if not receivers:
            print("No Colorlight receivers found.")
        for r in receivers:
            print(f"Receiver {r.receiver_id}: firmware v{r.firmware_major}.{r.firmware_minor}, "
                  f"uptime {r.uptime_ms}ms, packets {r.packet_count}, mac {r.source_mac}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
