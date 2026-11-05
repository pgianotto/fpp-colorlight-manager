"""Unit tests for backend/colorlight_protocol.py.

These test only the pure encode/decode logic against synthetic frames built
to match the byte layout documented in docs/protocol.md (itself taken from
FPP's shipping ColorLight-5a-75.cpp). No socket, no hardware required.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))
import colorlight_protocol as clp  # noqa: E402


def test_build_discovery_frame_basic():
    frame = clp.build_discovery_frame(5)
    assert len(frame) == clp.DISC_PACKET_SIZE
    assert frame[0:6] == clp.DEST_MAC
    assert frame[6:12] == clp.SRC_MAC
    assert frame[clp.PACKET_TYPE_OFFSET] == clp.DISC_PACKET_TYPE
    assert frame[clp.PACKET_DATA_OFFSET + 3] == 5


@pytest.mark.parametrize("bad_id", [-1, 32, 1000])
def test_build_discovery_frame_rejects_out_of_range(bad_id):
    with pytest.raises(ValueError):
        clp.build_discovery_frame(bad_id)


def _make_reply_frame(receiver_id=3, fw_major=7, fw_minor=0,
                       uptime_ms=123456, packet_count=9999,
                       cabinet_w=32, cabinet_h=16,
                       # Matches FPP's actual (code, not comment) check -
                       # see the note in colorlight_protocol.is_discovery_reply.
                       src_mac=bytes([0x11, 0x22, 0x33, 0x44, 0x55, 0x66])):
    frame = bytearray(clp.RESP_PACKET_SIZE)
    frame[0:6] = bytes([0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF])  # broadcast dest
    frame[6:12] = src_mac
    frame[clp.PACKET_TYPE_OFFSET] = clp.RESP_PACKET_TYPE

    data_start = clp.PACKET_DATA_OFFSET
    frame[data_start + clp.RESP_OFF_CARD_TYPE] = 0x05
    frame[data_start + clp.RESP_OFF_FW_MAJOR] = fw_major
    frame[data_start + clp.RESP_OFF_FW_MINOR] = fw_minor
    frame[data_start + clp.RESP_OFF_WIDTH_HI] = (cabinet_w >> 8) & 0xFF
    frame[data_start + clp.RESP_OFF_WIDTH_HI + 1] = cabinet_w & 0xFF
    frame[data_start + clp.RESP_OFF_HEIGHT_HI] = (cabinet_h >> 8) & 0xFF
    frame[data_start + clp.RESP_OFF_HEIGHT_HI + 1] = cabinet_h & 0xFF

    for i in range(4):
        frame[data_start + clp.RESP_OFF_PACKETS_HI + i] = (packet_count >> (24 - 8 * i)) & 0xFF
        frame[data_start + clp.RESP_OFF_UPTIME_HI + i] = (uptime_ms >> (24 - 8 * i)) & 0xFF

    frame[data_start + clp.RESP_OFF_RECEIVER_ID] = receiver_id
    return bytes(frame)


def test_parse_discovery_reply_roundtrip():
    frame = _make_reply_frame(receiver_id=2, fw_major=7, fw_minor=0,
                               uptime_ms=5000, packet_count=42,
                               cabinet_w=32, cabinet_h=16)
    info = clp.parse_discovery_reply(frame)

    assert info is not None
    assert info.receiver_id == 2
    assert info.firmware_major == 7
    assert info.firmware_minor == 0
    assert info.uptime_ms == 5000
    assert info.packet_count == 42
    assert info.cabinet_width_unverified == 32
    assert info.cabinet_height_unverified == 16
    assert info.source_mac == "11:22:33:44:55:66"


def test_parse_discovery_reply_rejects_wrong_type():
    frame = bytearray(_make_reply_frame())
    frame[clp.PACKET_TYPE_OFFSET] = 0x55  # pixel data type, not a disco reply
    assert clp.parse_discovery_reply(bytes(frame)) is None


def test_parse_discovery_reply_rejects_wrong_source_mac():
    frame = bytearray(_make_reply_frame(src_mac=bytes([1, 2, 3, 4, 5, 6])))
    assert clp.parse_discovery_reply(bytes(frame)) is None


def test_parse_discovery_reply_rejects_short_frame():
    assert clp.parse_discovery_reply(b"\x00" * 50) is None


def test_to_dict_tags_unknown_fields():
    frame = _make_reply_frame()
    info = clp.parse_discovery_reply(frame)
    d = info.to_dict()

    assert d["fields"]["receiverId"]["source"] == "verified"
    assert d["fields"]["firmwareVersion"]["source"] == "verified"
    assert d["fields"]["cabinetWidth"]["source"] == "unknown"
    assert d["fields"]["cabinetHeight"]["source"] == "unknown"
