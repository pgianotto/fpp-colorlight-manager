"""Colorlight 5A-75 Ethernet protocol - discovery frames only (Phase 2).

Ported from FPP's own channel output driver
(fpp/src/channeloutput/ColorLight-5a-75.cpp / .h), which is the only
production-proven implementation of this protocol we have. Field offsets and
sizes below are copied from there, not guessed. See docs/protocol.md in this
plugin for provenance and open questions.

Nothing in this module reads or writes receiver *configuration* - only the
discovery query/reply pair FPP already uses in production.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

# Fixed MAC pair used for all Colorlight traffic on this protocol (not a
# real registered EtherType/vendor OUI - just two addresses the stock
# firmware expects).
DEST_MAC = bytes([0x11, 0x22, 0x33, 0x44, 0x55, 0x66])
SRC_MAC = bytes([0x22, 0x22, 0x33, 0x44, 0x55, 0x66])
BROADCAST_MAC = bytes([0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF])

PACKET_TYPE_OFFSET = 12
PACKET_DATA_OFFSET = 13

DISC_PACKET_TYPE = 0x07
DISC_PACKET_SIZE = 284

RESP_PACKET_TYPE = 0x08
RESP_PACKET_SIZE = 1070
# FPP only inspects the first ~90 bytes of the 1057-byte data payload; we
# only need that much to receive a well-formed reply.
RESP_MIN_RECV_SIZE = 1000  # FPP's own driver discards anything <= 1000 bytes

# Discovery reply data[] offsets (relative to PACKET_DATA_OFFSET), copied
# from ColorLight-5a-75.cpp's GetReceiverInfo().
RESP_OFF_CARD_TYPE = 0          # 0x05 observed for "5A" cards - verified
RESP_OFF_FW_MAJOR = 2           # verified
RESP_OFF_FW_MINOR = 3           # verified
RESP_OFF_WIDTH_HI = 21          # "doesn't seem totally correct" per FPP's own comment - unknown
RESP_OFF_HEIGHT_HI = 23         # same caveat - unknown
RESP_OFF_PACKETS_HI = 38        # verified (packet counter, 4 bytes)
RESP_OFF_UPTIME_HI = 46         # verified (uptime ms, 4 bytes)
RESP_OFF_RECEIVER_ID = 85       # verified

MAX_RECEIVER_ID = 31  # FPP's GetReceiverInfo() tries ids 0..31


@dataclass
class ReceiverInfo:
    """One discovered receiver. Every field notes its provenance per
    docs/architecture.md's verified/inferred/manual/unknown model."""

    receiver_id: int                 # verified
    card_type_byte: int              # verified (raw byte; 0x05 == "5A card")
    firmware_major: int              # verified
    firmware_minor: int              # verified
    uptime_ms: int                   # verified
    packet_count: int                # verified
    source_mac: str                  # verified
    cabinet_width_unverified: int    # unknown - see docs/protocol.md
    cabinet_height_unverified: int   # unknown - see docs/protocol.md
    raw_reply: bytes                 # full reply frame, for later re-analysis

    def to_dict(self) -> dict:
        return {
            "receiverId": self.receiver_id,
            "cardTypeByte": f"0x{self.card_type_byte:02x}",
            "firmwareVersion": f"{self.firmware_major}.{self.firmware_minor}",
            "uptimeMs": self.uptime_ms,
            "packetCount": self.packet_count,
            "sourceMac": self.source_mac,
            "fields": {
                "receiverId": {"value": self.receiver_id, "source": "verified"},
                "cardTypeByte": {"value": f"0x{self.card_type_byte:02x}", "source": "verified"},
                "firmwareVersion": {"value": f"{self.firmware_major}.{self.firmware_minor}", "source": "verified"},
                "uptimeMs": {"value": self.uptime_ms, "source": "verified"},
                "packetCount": {"value": self.packet_count, "source": "verified"},
                "sourceMac": {"value": self.source_mac, "source": "verified"},
                "cabinetWidth": {"value": self.cabinet_width_unverified, "source": "unknown"},
                "cabinetHeight": {"value": self.cabinet_height_unverified, "source": "unknown"},
            },
        }


def build_discovery_frame(receiver_id: int) -> bytes:
    """Build a type-0x07 discovery query frame for one receiver id.

    Matches ColorLight5a75Output::GetReceiverInfo(): a zero-filled
    CL_DISC_PACKET_SIZE (284) byte buffer with the MAC header, packet type
    byte, and the target id written into data[3] (offset 16 from the start
    of the frame = PACKET_DATA_OFFSET(13) + 3).
    """
    if not (0 <= receiver_id <= MAX_RECEIVER_ID):
        raise ValueError(f"receiver_id must be 0..{MAX_RECEIVER_ID}, got {receiver_id}")

    frame = bytearray(DISC_PACKET_SIZE)
    frame[0:6] = DEST_MAC
    frame[6:12] = SRC_MAC
    frame[PACKET_TYPE_OFFSET] = DISC_PACKET_TYPE
    frame[PACKET_DATA_OFFSET + 3] = receiver_id
    return bytes(frame)


def is_discovery_reply(frame: bytes) -> bool:
    """Mirrors the filter FPP applies to incoming frames in GetReceiverInfo():
    must be long enough, addressed from the Colorlight source MAC, and carry
    the discovery-reply packet type.

    Note on a discrepancy in FPP's own source: the top-of-file comment in
    ColorLight-5a-75.cpp says replies have source MAC 22:22:33:44:55:66, but
    the actual (production, hardware-tested) code in GetReceiverInfo() checks
    receiveBuffer[6..11] == {0x11,0x22,0x33,0x44,0x55,0x66} - i.e. DEST_MAC,
    not SRC_MAC - at the source-address position. We follow the code, since
    it's what's actually been run against real hardware; worth confirming
    against our own capture in docs/development-plan.md Phase 3."""
    if len(frame) <= RESP_MIN_RECV_SIZE:
        return False
    if frame[6:12] != DEST_MAC:
        return False
    if frame[PACKET_TYPE_OFFSET] != RESP_PACKET_TYPE:
        return False
    return True


def parse_discovery_reply(frame: bytes) -> Optional[ReceiverInfo]:
    if not is_discovery_reply(frame):
        return None

    data = frame[PACKET_DATA_OFFSET:]

    def u32(off: int) -> int:
        return (data[off] << 24) | (data[off + 1] << 16) | (data[off + 2] << 8) | data[off + 3]

    def u16(off: int) -> int:
        return (data[off] << 8) | data[off + 1]

    src_mac = ":".join(f"{b:02x}" for b in frame[6:12])

    return ReceiverInfo(
        receiver_id=data[RESP_OFF_RECEIVER_ID],
        card_type_byte=data[RESP_OFF_CARD_TYPE],
        firmware_major=data[RESP_OFF_FW_MAJOR],
        firmware_minor=data[RESP_OFF_FW_MINOR],
        uptime_ms=u32(RESP_OFF_UPTIME_HI),
        packet_count=u32(RESP_OFF_PACKETS_HI),
        source_mac=src_mac,
        cabinet_width_unverified=u16(RESP_OFF_WIDTH_HI),
        cabinet_height_unverified=u16(RESP_OFF_HEIGHT_HI),
        raw_reply=bytes(frame),
    )
