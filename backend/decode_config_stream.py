#!/usr/bin/env python3
"""Reassemble and decompress a Colorlight receiver's 0x09 config-stream reply.

Confirmed against a real 5A-75B (firmware 10.16) capture on 2026-11-05: after a
0x07 discovery query, the receiver replies with one 0x08 identify frame
(already handled by colorlight_protocol.py) followed by a *sequence* of 0x09
frames that together hold a raw-deflate-compressed blob of the receiver's
actual parameter data (module size, scan mode, driver/decode IC, gamma,
timing, calibration tables, etc. - the same fields shown in LEDVision's
"Receiver Parameters" tab).

Frame layout (all 0x09 frames are exactly CL_RESP_PACKET_SIZE=1070 bytes,
same as the 0x08 reply):
  - Every 0x09 frame's data[] starts with a constant 2-byte prefix (0x01 0x01).
  - The FIRST 0x09 frame in a sequence additionally has a 36-byte header right
    after that prefix (data[2:38]) before the compressed stream starts:
      data[2:4]   uint16 LE - unknown (seen 0x1a5b)
      data[4:6]   uint16 LE - unknown (seen 0x0000)
      data[6:8]   uint16 LE - unknown (seen 0x2020)
      data[8:22]  14 bytes  - unknown, possibly a hash/session id
      data[22:26] uint32 LE - unknown (seen 4)
      data[26:30] uint32 LE - compressed length (seen 0x1a37 = 6711, but real
                              captures overrun this - treat as approximate)
      data[30:34] uint32 LE - uncompressed length (seen 0x76e0 = 30432,
                              likewise approximate)
      data[34:38] 4 bytes   - zero padding
      data[38:]   zlib stream (starts with the 2-byte zlib header 0x78 0x9c)
  - Every SUBSEQUENT 0x09 frame in the same sequence is pure continuation:
    just skip its 2-byte (0x01 0x01) prefix and append the rest.
  - The reassembled stream decompresses as RAW DEFLATE (not plain zlib -
    the trailing Adler32 checksum does not reliably validate, likely because
    trailing frames are padded past the real end; skip the 2-byte zlib header
    and inflate with wbits=-15, which stops cleanly at the deflate end-of-block
    marker and ignores any trailing garbage).

Confirmed decoded fields so far (byte offsets into the DECOMPRESSED blob):
  - offset 32,  float32 LE: Gamma Value          (confirmed: 2.8)
  - offset 178, float32 LE: Minimum OE (ns)       (confirmed: 24.0)
  - offset 196, uint16 LE:  Cabinet Width (px)     (confirmed: 192)
  - offset 198, uint16 LE:  Cabinet Height (px)    (confirmed: 64)
Everything else in the blob is still unmapped - see docs/protocol.md.
"""
from __future__ import annotations

import struct
import sys
import zlib
from pathlib import Path

PACKET_TYPE_OFFSET = 12
PACKET_DATA_OFFSET = 13
CONFIG_STREAM_TYPE = 0x09
FIRST_FRAME_HEADER_LEN = 38  # 2-byte prefix + 36-byte header, before zlib data
CONTINUATION_PREFIX_LEN = 2  # just the 2-byte (0x01 0x01) prefix


def reassemble_and_decompress(frames: list[bytes]) -> bytes:
    """frames: raw Ethernet frames (full bytes, MAC header included), in the
    order captured, all of type CONFIG_STREAM_TYPE."""
    if not frames:
        raise ValueError("no frames given")

    stream = bytearray()
    first_data = frames[0][PACKET_DATA_OFFSET:]
    stream.extend(first_data[FIRST_FRAME_HEADER_LEN:])

    for frame in frames[1:]:
        data = frame[PACKET_DATA_OFFSET:]
        stream.extend(data[CONTINUATION_PREFIX_LEN:])

    if stream[:2] != b"\x78\x9c":
        raise ValueError(f"expected zlib header 78 9c at stream start, got {stream[:2].hex()}")

    dobj = zlib.decompressobj(-15)  # raw deflate, skip the 2-byte zlib header ourselves
    out = dobj.decompress(bytes(stream[2:]))
    out += dobj.flush()
    if not dobj.eof:
        raise ValueError("decompression did not reach a clean end-of-stream")
    return out


KNOWN_FIELDS = {
    "gamma_value": (32, "<f"),
    "minimum_oe_ns": (178, "<f"),
    "cabinet_width_px": (196, "<H"),
    "cabinet_height_px": (198, "<H"),
}


def decode_known_fields(blob: bytes) -> dict:
    result = {}
    for name, (offset, fmt) in KNOWN_FIELDS.items():
        result[name] = struct.unpack_from(fmt, blob, offset)[0]
    return result


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: decode_config_stream.py <dir-of-raw-frame-dumps>", file=sys.stderr)
        sys.exit(1)

    frame_dir = Path(sys.argv[1])
    frame_files = sorted(frame_dir.glob("*.bin"))
    frames = [f.read_bytes() for f in frame_files]
    blob = reassemble_and_decompress(frames)
    print(f"Decompressed {len(blob)} bytes from {len(frames)} frames")
    for name, value in decode_known_fields(blob).items():
        print(f"  {name}: {value}")
