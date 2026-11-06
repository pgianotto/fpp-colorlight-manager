# Colorlight 5A-75B Ethernet Protocol — Research Notes

Status: **Phase 1 research only.** Nothing below has been validated against hardware
by this project yet; it is a synthesis of FPP's existing driver source and public
third-party research. Confidence is marked per item.

## Transport

- Raw Ethernet frames (`AF_PACKET`/`SOCK_RAW`), no IP/UDP layer. FPP opens the socket
  with `IPPROTO_RAW` and binds it to a specific interface via `SO_BINDTODEVICE`.
  **Confidence: verified** (FPP source, `ColorLight-5a-75.cpp`).
- Fixed MAC pair for all traffic:
  - Host → receiver: dst `11:22:33:44:55:66`, src `22:22:33:44:55:66` (src is sent but FPP's
    comment notes it doesn't appear to be checked).
  - Receiver → host (discovery reply): broadcast, src `22:22:33:44:55:66`, dst `FF:FF:FF:FF:FF:FF`.
  **Confidence: verified** (FPP source + matches hkubota's independent capture).
- "Packet type" is a single byte that FPP stores in the Ethernet header's EtherType field
  (`CL_PACKET_TYPE_OFFSET = 12`), i.e. the protocol does not use a real registered EtherType —
  it reuses that field as a command id. Data follows immediately after it (`CL_PACKET_DATA_OFFSET = 13`).
  **Confidence: verified.**

## Packet types FPP implements today (output path — verified by shipping code)

| Type | Name | Size | Purpose |
|------|------|------|---------|
| `0x01` | Sync / Display Frame | 112 bytes | Tells receiver(s) to latch/display the frame buffer just written. Carries brightness bytes at Data[22,25,26,27]. Sent twice on FW ≥ v13. |
| `0x02` | Write receiver layout | variable (3 + 64×20 bytes data) | Configures up to 64 receivers' width/height/offset/total-canvas-size in a multi-receiver chain. **FPP does not send this today** — decoded from LEDVision capture notes in FPP's own source comment, not implemented in code. |
| `0x07` | Discover | 284 bytes | Broadcast query, one receiver ID per request (Data[3] = id, tried 0–31). |
| `0x08` | Discover reply | 1070 bytes | Receiver's response: card type (`0x05` = "5A"), firmware major/minor (Data[2],[3]), packet counter (Data[38-41]), uptime ms (Data[46-49]), receiver id (Data[85]), and at least one width/height-like field (Data[21-24]) whose exact semantics FPP's own comment says are **not fully understood** ("doesn't seem to match... some other math going on"). |
| `0x0A` | Brightness | 77 bytes | Global RGB brightness (Data[0-3]). Sent twice on FW ≥ v13. Reportedly ineffective on v2.x/v3.x firmware. |
| `0x55` | Pixel row data | header 8 bytes + up to 1491 bytes payload (497 px × 3) | One packet per (row, chunk). Row number (Data[0-1]), pixel offset (Data[2-3]), pixel count (Data[4-5]), two unexplained bytes (Data[6-7] = `0x08 0x88`), then RGB bytes in the panel's configured color order. |

Everything above is **output-path only**: FPP can discover a receiver's identity/uptime/counters
and can drive pixels, but implements no read of panel configuration (resolution, scan, driver IC,
HUB75 mapping, port assignment, etc.) and no write of configuration beyond the ad-hoc layout
packet it recognizes but never sends.

## Packet types seen but NOT decoded (config-write path — this is Features 2–7's blocker)

FPP's own source comment (`ColorLight-5a-75.cpp` top-of-file) lists these as observed "when
sending config to receiver" in a LEDVision capture, with no field-level decode:

| Type | Observed size | Notes |
|------|------|-------|
| `0x10` | 1026 bytes | Unknown. |
| `0x11` | 1283 bytes | Possibly "save config" — Data[3] looks like a receiver index, same convention as `0x02`/`0x07`. Unconfirmed. |
| `0x18` | unspecified | Unknown. |
| `0x1F` | 1034 bytes | Unknown. |
| `0x26` | 264 bytes | Unknown. |
| `0x31` | unspecified | "Some kind of table, 2 bytes per entry" per FPP's comment — possibly a register map or pixel-mapping table. |
| `0x32` | unspecified | Unknown. |
| `0x76` | unspecified | "Some kind of table, 3 bytes per entry" per FPP's comment — possibly a 3-byte-per-entry mapping (RGB order table? pin map?). |

**None of these have published, field-level decodes anywhere we found** (FPP's own comment,
hkubota's writeup, or the chubby75 project). This is the actual gap between "FPP today" and
Features 2 (read config), 4 (import config), 6 (write config) in the request.

## Public third-party research reviewed

- **FPP's own `ColorLight-5a-75.cpp` header comment** — most complete existing writeup;
  covers the output path and discovery, and lists (without decoding) the config-write types above.
  Cites `docs/ColorLight_Wireshark.lua`, a Wireshark dissector already in this FPP checkout that
  decodes types `0x01,0x02,0x07,0x08,0x0A,0x11,0x55` and stubs `0x10/0x18/0x1F/0x26/0x31/0x32/0x76`
  as "unparsed." **This dissector is directly reusable for our own packet captures.**
- **hkubota, "Winter project: Colorlight 5A-75B protocol" (2022)** — independently reverse-engineered
  the same output/discovery packets (calls them Display Frame, Set Brightness, Pixel Data, Receiver
  Detection). Confirms FPP's packet layout. Explicitly states configuration read/write was **not**
  investigated and LEDVision's config protocol is undocumented. Source:
  https://hkubota.wordpress.com/2022/01/31/winter-project-colorlight-5a-75b-protocol/
- **q3k/chubby75** (https://github.com/q3k/chubby75) — reverse-engineers the 5A-75B/5A-75E/RV901T
  *hardware* (ECP5/Spartan6 FPGA pinouts, SPI config PROM, JTAG) to write **replacement gateware**.
  It is not about talking to the stock firmware's network protocol and gives no register-level
  decode of LEDVision's config commands. Useful later only if we ever need to understand the board
  at the silicon level (e.g., confirming the config PROM is where nonvolatile settings live); not
  useful for Phase 1–4.
- **dgym/receiver75** — a replacement gateware for the 5A-75B v8 board that defines *its own*
  UDP-based config-register protocol. Relevant only as prior art for designing our own protocol
  *if* we ever replace firmware (explicitly out of scope — "No firmware flashing in the initial
  release"). Not applicable to talking to stock Colorlight firmware.
- **`.rcfg` / `.rcfgx` file extensions** — **these are NovaStar formats, not Colorlight.**
  (NovaStar "Receiving Card Configuration" files for its own SmartLCT/VX series.) We found no
  evidence Colorlight's LEDSetting/LEDVision tools use these extensions at all. This is a
  correction to an assumption in the original project brief: Feature 4 (import existing
  configurations) should target whatever file format Colorlight's own LEDSetting/LEDVision
  software actually exports — which we have not yet observed, since we don't have a sample file.
  **Action for Phase 2/3: export or locate a real LEDSetting config file for the connected panels
  before building any importer.**

## Config file format — found via static analysis of LEDVision's own installer (2026-11-02)

Rather than guessing, we statically extracted the real LEDVISION 9.7 Windows installer
(`LEDVISION_Setup_x64_9.7.52113.exe`, an NSIS package — unpacked with 7-Zip, nothing executed)
and found it ships **thousands of vendor-supplied panel/receiver profiles** under
`config_files/`. The real extensions are:

- **`.rcvp`** — "Receiver Profile" (plain variant)
- **`.rcvbp`** — "Receiver Backup Profile"(?) — binary, larger, seen far more often (2013 of
  them vs. 72 `.rcvp`). Likely what LEDVision's own backup/import feature actually reads/writes.

**This confirms the `.rcfg`/`.rcfgx` assumption in the original brief was wrong** (those are
NovaStar's), and gives us real sample files instead of a guess. A handful are copied into
`samples/rcvp/` in this repo for reference (all vendor-shipped generic module profiles bundled
with the installer, not anything extracted from your hardware).

**Decoded so far, by diffing same-size-family samples byte-for-byte** (e.g. `P5-64×32-16S.rcvp`
vs `P5-32×32-16S.rcvp` vs `P5-32×32-8S-A5.rcvp`):

| Offset | Field | Confidence |
|---|---|---|
| `0x18` | Panel width in pixels (`64` vs `32` confirmed) | **High** — isolated via diff, consistent across 2 comparisons |
| `0x38` | Scan rate (`16` vs `8` confirmed) | **High** — isolated via diff |
| `0x00-0x0F` | 16 bytes, high entropy, constant-length — possibly a checksum/hash or encrypted/signed header | Unknown |
| everything else | Not yet isolated (panel height wasn't distinguishable in this sample set since all 3 compared files share height 32; driver IC, RGB order, HUB75 mapping, timing are all still unknown) | Unknown |

This is a `.rcvp`/`.rcvbp` **file format** decode, not a **wire protocol** decode — it tells us
nothing yet about how LEDVision reads/writes this data to/from the receiver over Ethernet (still
blocked on the `0x10/0x11/0x18/0x1F/0x26/0x31/0x32/0x76` packet types). But it's a real, concrete
head start on Feature 4 (import) once we have enough samples to fully map the format, and it's
reusable immediately for recognizing/validating an uploaded file's basic shape (magic/size
sanity checks) before we can decode it fully.

**Next step for this thread:** diff more same-family samples (we have hundreds available in the
installer) to isolate height, driver IC, RGB order, and the 16-byte header; cross-reference
against a `.rcvp`/`.rcvbp` file *actually exported from your card* (Capture C in
`development-plan.md`) once you've run that capture, since vendor-generic profiles may not
exercise every field your specific receiver cares about.

## Software architecture clues from LEDVision's own binaries (2026-11-02, static only)

Since we don't currently have the receiver card physically available, we went one level deeper
into the same installer: extracted the actual program `.exe`/`.dll` files (still nothing
executed) and pulled readable symbol names out of them with `strings`-style scanning. This is
static analysis of binaries, not running them, and not a substitute for a real packet capture -
but it tells us where the protocol logic actually lives and confirms some structure:

- **`CLTNic.dll`** - the raw-Ethernet transport layer. Exports `Nic_Read`/`Nic_Write`/
  `Nic_SendScreenPicture`/`Nic_SetBrightness`/etc., and explicitly checks for WinPcap
  (`Nic_DetectIsInstallWinpCap`). Confirms LEDVision talks to receivers the same way FPP does -
  raw frames via a packet-capture-style driver (WinPcap/Npcap on Windows, `AF_PACKET` on Linux) -
  just a generic send/receive primitive, not where packet *contents* are decided.
- **`LedAdmin.dll`** (14.5MB, the largest non-redistributable binary in the install) - this is
  where it gets interesting. Exported/internal symbols include:
  - `CRcvParamFileManager` - a class literally named "Receiver Parameter File Manager." Almost
    certainly the code that reads/writes `.rcvp`/`.rcvbp` files and prepares what gets sent to
    the card.
  - `GetRcvParamBufForSPIFlash` / `GetRcvGammaTableBufForSPIFlash` - **confirms configuration and
    gamma data are stored in the receiver's SPI flash**, not some other mechanism. This matches
    chubby75's hardware teardown noting a 25Q16 SPI flash chip on the 5A-75B board (previously we
    only knew that flash held the FPGA bitstream; this suggests it - or another flash region -
    also holds user config).
  - `SaveBpToBuffer` / `SaveToBpFile` - ties directly to the `.rcvbp` ("backup profile") file
    extension found earlier; the "Bp" naming is confirmed, not a guess.
  - `SaveToCmdFile` / `LoadFromCmdFile` - LEDVision apparently has a concept of a serialized
    "command file" distinct from the parameter file. This could plausibly be the literal
    byte-for-byte command sequence sent to the receiver - if so, decompiling the function that
    *writes* a CmdFile would hand us the wire protocol directly, without needing a live capture
    at all. We have not gone further than symbol-name discovery here; actually extracting that
    logic needs real disassembly (Ghidra/IDA), which is a bigger step than string-scanning and
    hasn't been attempted yet.
  - `ChipSetting.dll` and the per-chip `ChipData/<vendor>/.../configDLLxxxx.dll` files (e.g.
    `configDLL6619.dll`, matching the ICN6619 HUB75 driver IC) hold driver-IC-specific register
    knowledge - relevant later for decoding the rest of the `.rcvp`/`.rcvbp` fields (driver IC
    selection, timing) but not the Ethernet wire protocol itself.

**What this is good for right now:** confirms the overall architecture (generic raw-Ethernet
transport + a receiver-parameter manager that serializes to SPI-flash-shaped buffers) and gives
a precise target (`CRcvParamFileManager` in `LedAdmin.dll`) for anyone willing to do a full
disassembly pass later. **It does not give us decoded packet bytes yet** - that still needs
either (a) a real capture against hardware, or (b) someone sitting down with Ghidra against this
specific DLL and class, which is a distinct, larger task from what's been done so far.

## BREAKTHROUGH: real config-write packets captured, no receiver hardware required (2026-11-02)

We found a way to get LEDVision to send its full config-write stream without the card physically
present at all. Key discovery: LEDVision's receiving-card config tool has a **"Select Sending
Device"** option with three modes — **Net Card**, **Sender**, **Play Box**. "Sender"/"Play Box"
expect a separate physical Colorlight hardware box; **"Net Card" makes the PC's own NIC act as
the sender**, exactly like FPP does. In this mode, LEDVision proactively streams its *entire*
config sequence as soon as a screen is defined - it doesn't wait for a receiver to answer. We
captured this with Wireshark on a direct NIC (no switch, no card attached) using **LEDVision
7.0** (9.7 was tried first and only sent ordinary IP traffic in its "Sender" mode - see below).

Raw captures are in `samples/net-card-detect-no-receiver.pcapng` (73MB, not committed to git -
local only) with one representative frame per type extracted to `samples/decoded_frames/*.txt`.

### Every previously-unknown FPP packet type, now with real payloads

| Type | FPP's prior knowledge | What we captured | Confidence |
|---|---|---|---|
| `0x10` | "sent when sending config, Data Length: 1026" | 1040-byte frame, **entirely zero-filled** payload in this no-panel-configured state | Size confirmed; content only seen in a trivial/empty case |
| `0x1F` | "sent when sending config, Data Length: 1034" | 1048-byte frame, **entirely zero-filled** | Same as above |
| `0x76` | "some kind of table, 3 bytes per entry" | 1171-byte frame, confirmed **3-bytes-per-entry incrementing table** (`10 01 00`, `20 02 00`, `30 03 00`, ... pattern climbing through ~380 entries, non-trivial internal structure, repeats twice more later in the same frame) - FPP's guess was exactly right | Table structure confirmed; per-entry meaning (gamma LUT? pixel address map?) still unknown |
| `0x18` | "sent when sending config" (no size given) | 1040 bytes, **entirely zero-filled**, same size as `0x10` | New: size now known |
| `0x11` | "Save Config??" | not seen in this capture (no card ever "detected," so LEDVision may never reach the save step without a successful discovery reply first) | Still unconfirmed |
| `0x31`, `0x32` | mentioned, no detail | not seen in this capture | Still unknown |

### Brand new packet types FPP's source never mentioned at all

| Type | Size | What we saw | Notes |
|---|---|---|---|
| **`0x1B`** | 282 bytes | `data[0..17] = 00 ff ff 00 00 00 00 41 00 00 00 05 01 00 ff ff ff 00`, rest zero | Sent **continuously, repeatedly** (~every 2.3ms, hundreds of times) the moment you click "Detect Receiver Cards" with nothing connected - this looks like the actual continuous discovery/retry probe LEDVision 7.0 uses (distinct from, and sent *in addition to*, the classic `0x07` discovery FPP already implements) |
| **`0x05`** | 272 bytes | Structured, non-zero: identity-like byte ramps (`10 11 12 ... 1f`, `00 01 02 ... 0f`), four `2b` bytes (ASCII `++++`), and a UTF-16LE text string decoding to `"3b9a1e18"` (looks like a software-generated session/device id, not anything read from hardware) | Sent once per session setup, not repeated |
| **`0x03`** | 784 bytes | Highly regular enumeration table: repeating triplets where byte0 cycles 0-7, byte1 increments every 8th entry, byte2 stays 0 - classic (sub-channel, group) coordinate table shape | Strong candidate for a HUB75 port/data-group assignment table (Feature 5/6 territory) but unconfirmed |
| **`0x17`** | 785 bytes | Structured for the first ~190 bytes (repeating 8-byte-ish records with small values 0-3 and 0x10/0x20/0x30), then zero-padded to end | Shape resembles a receiver/output layout table; unconfirmed |

### Known types - cross-checked, with corrections to FPP's own comment

- **`0x01` (Sync)**: confirms FPP's documented brightness byte positions (data[22]=0xFF, data[23]=0x05
  exactly as FPP's comment says for "PC/Netcard"). **Correction**: data[0] was `0x04` here, not
  FPP's documented `0x00` (S2 Sender) or `0x07` (PC/Netcard) - LEDVision 7.0's Net Card mode uses
  a third value FPP's comment didn't anticipate. Worth checking if this is firmware/version-dependent.
- **`0x0A` (Brightness)**: matches FPP's documented format exactly (`FF FF FF FF`).
- **`0x07` (Discovery)**: FPP's own driver iterates receiver ids 0-31 in `data[3]`. LEDVision 7.0
  instead sent `data[2..4] = FF FF FF` - looks like a broadcast/wildcard "any receiver" query
  rather than FPP's per-id enumeration. Both are presumably valid; FPP's approach just gets
  per-receiver answers back one at a time.

### What this means for Phase 3

This is a huge head start on Features 2/5/6 (reading and writing panel configuration) **without
needing the physical card** - we now have real byte-for-byte examples of every packet type in
the config-write sequence, just not yet correlated to specific user-visible settings (panel
width/height/scan/driver IC/etc.), because this capture was taken with LEDVision's *default*,
unconfigured screen. The next concrete step is controlled diffing, the same technique that
worked for the `.rcvp` file format: change one setting at a time in LEDVision's **Screen
Configuration** (e.g. set resolution to match your real panels, pick scan 16, pick driver IC),
re-run the capture, and diff against this baseline to isolate exactly which bytes in `0x10`,
`0x18`, `0x1F`, `0x03`, `0x17` change. This can all be done **without the card attached**, at
your own pace, no hardware required - a major change from the original plan, which assumed we
needed hardware captures for all of this.

## MAJOR BREAKTHROUGH: the actual read-config protocol, decoded against real hardware (2026-11-05)

Someone with physical access to a real 5A-75B (firmware **5A 10.16** - same firmware as the
card documented earlier in this file) ran captures for us using LEDVision 7.0's **Net Card**
mode, including clicking **"Read"** on the Receiver Parameters tab, which pulled real settings
off the card: Module 192W×16H, 16-scan, driver IC **DP5125**, decode IC **138 Decoding**,
cabinet 192×64, DCLK 25.0MHz, Minimum OE 24.0ns, Gamma 2.8, Gray Level 16384, and more (full
values in the screenshot this was captured from - ask the user if needed). Two capture files:
`Capture_LEDVision_Start.pcapng` and `Capture 01.pcapng` (both large, not committed to git -
local only, same as the other raw captures).

### The actual read-config wire protocol

After the standard `0x07` discovery query, a real receiver replies with:

1. One **`0x08`** frame - the already-known identify reply (firmware, uptime, etc.) FPP already
   parses.
2. A **sequence of `0x09` frames** - a packet type that exists nowhere in any prior
   documentation, including FPP's own source. **FPP's `GetReceiverInfo()` silently discards
   these** because it filters strictly on `CL_RESP_PACKET_TYPE == 0x08`.

The `0x09` frames, concatenated and decompressed, contain the receiver's **entire parameter
block as a raw-deflate-compressed blob** - this is the actual "read configuration off the card"
data. Full reassembly/decompression logic (verified working) is in
`backend/decode_config_stream.py`. Key points:

- Every `0x09` frame is exactly 1070 bytes (same size as the `0x08` reply), data starts with a
  constant 2-byte prefix (`01 01`).
- The *first* `0x09` frame has a 36-byte header after that prefix (unknown fields, plus what
  look like compressed/uncompressed length fields: 6711/30432 bytes in this capture - the real
  stream ran slightly past the stated compressed length, so treat those as approximate, not
  exact, until confirmed against another capture) - then the zlib stream starts (`78 9c`).
- Every *subsequent* `0x09` frame in the same sequence is pure continuation: strip the `01 01`
  prefix and the rest is more compressed bytes, no new header.
- The reassembled stream decompresses cleanly as **raw deflate** (strip the 2-byte zlib header,
  inflate with `wbits=-15`, ignore the trailing checksum - it doesn't reliably validate,
  probably because trailing frames carry padding past the real end). This was captured once with
  7 `0x09` frames producing a 31171-byte decompressed blob (close to, but not exactly, the
  30432 the header implied).
- This capture showed groups of `0x09` frames repeating periodically (a group of 7 right after
  discovery, then smaller groups of 1-3 roughly every 0.3-0.5s afterward) - looks like LEDVision
  keeps the Receiver Parameters window live-synced rather than reading once.

### Confirmed fields inside the decompressed parameter blob

Found by searching the decompressed bytes for the exact values visible in LEDVision's own UI
for this card:

| Offset (decompressed blob) | Type | Field | Confirmed value |
|---|---|---|---|
| 32 | float32 LE | Gamma Value | 2.8 |
| 178 | float32 LE | Minimum OE (ns) | 24.0 |
| 196 | uint16 LE | Cabinet Width (px) | 192 |
| 198 | uint16 LE | Cabinet Height (px) | 64 (immediately adjacent to width - same field pair as the `.rcvp` file format's layout) |

The blob also contains large, clearly-structured regions matching the `.rcvp` file format we
decoded earlier from LEDVision's installer: identity byte ramps (`00 01 02 ... 0f`,
`10 11 12 ... 1f`), full printable-ASCII ranges, and a `2b 2b 2b 2b` ("++++") marker - strong
evidence that **the live wire-protocol parameter blob and the `.rcvp` file format are the same
underlying structure**, just one travels compressed over the wire and the other is saved
uncompressed to disk. That means everything we eventually decode from either source transfers
to the other.

### What's still open (as of the read-path capture)

- Module size (192W×16H), scan mode (16), driver IC (DP5125), decode IC (138 Decoding), refresh
  rate (1920 - found once at decompressed offset 24111, far from the other confirmed fields, so
  likely a different, separate sub-section of the blob), gray level (16384), and most other
  visible fields are not yet mapped to specific offsets.
- The two unknown-value header fields in the first `0x09` frame's 36-byte header are still a
  mystery (possibly a request-id, CRC, or session token - 14 bytes of it looked hash-like).

## THE WRITE PATH, captured and partially decoded (2026-11-06)

Same person, same real 5A-75B (fw 10.16), ran a third capture: clicked **Send**, then
**Save to Receivers** in LEDVision's Receiver Parameters tab. File:
`Capture_LEDVision_With_SendAndSave.pcapng` (1.7GB, local only, not in git).

### The write sequence, in order

Both the "Send" and "Save to Receivers" clicks produced the **same burst of packet types, in
the same order**, back to back in two clearly separated time windows (~8s apart in this
capture):

```
0x05 (272B) x2   -- dimensions / session block (see below)
0x10 (1040B) x2  -- still all-zero, even now (see note below)
0x03 (784B) x24  -- per-row/output index table (content now DIFFERENT from the
                    no-card baseline capture - see below)
0x1F (1048B) x12 -- still all-zero, even now
0x76 (1171B) x2  -- gamma/brightness lookup table (content now a real nonlinear
                    curve, not the linear ramp seen in the no-card baseline)
0x10 (1040B) x4  -- all-zero again
0x1B (282B) x24  -- the continuous retry/probe type, already known
```

**Important finding: "Send" and "Save to Receivers" produced byte-for-byte identical `0x05`
frames** (diffed the two captures' worth, zero differences). Best guess right now: there may not
be a separate "write to RAM" vs. "persist to flash" distinction in this protocol at all - the
receiver might treat any complete config-write sequence as automatically persistent. This needs
one more targeted capture to confirm (watch power-cycle survival), but it simplifies Feature 6
considerably if true: there may be no separate "commit" step to implement.

### Confirmed: `0x05` (272 bytes) carries panel dimensions, cross-validated two ways

Decoded against the real card's actual values (cabinet 192x64):

- `data[8]` = `0xC0` = **192** (width)
- `data[10]` = `0x10` = **16** (scan, or possibly module-related - appears alongside width)
- `data[15]` = `0xC0` = **192**, `data[17]` = `0xC0` = **192** (width repeated - likely appears
  in more than one sub-field: module width, cabinet width, total canvas width)
- Later in the packet: `c0 00 40` = **192, 0, 64** - width immediately followed by height,
  **same adjacent width/height pairing pattern found in the decompressed `0x09` read-path blob**
  (there at offset 196/198). Strong independent confirmation this is a real, consistent
  width-then-height field pair used throughout the protocol, not a coincidence.
- The `2b 2b 2b 2b` ("++++") marker and the `00 01 02...0f` / `10 11 12...1f` identity ramps are
  present at the same relative positions as the earlier no-card baseline capture of this same
  packet type - confirmed as fixed/constant content, not per-config data.

### Confirmed: `0x76` (1171 bytes) is a gamma/brightness lookup table

Unlike the no-card baseline (a simple linear ramp - `10 01 00`, `20 02 00`, `30 03 00`...), this
real-card capture's `0x76` content is a **non-linear, steadily-accelerating curve** (3-byte
entries climbing from near-zero up through large values in a classic gamma-curve shape), repeated
three times within the single frame. This strongly confirms `0x76` is the gamma/brightness LUT
(matches the UI's "Gamma Value: 2.8" setting) rather than some other generic table.

### Revised: `0x03` (784 bytes) is a per-row/output index table, content varies with your panel

The no-card baseline's `0x03` content cycled through groups of 8 (byte0: 0-7, byte1 incrementing
every 8th entry) - that was LEDVision's *default*, multi-output test layout. This real capture
(single 192x64 cabinet, one receiver) instead shows a **simple linear sequence**: `(0,0,0),
(1,0,0), (2,0,0), (3,0,0)...` climbing past 100 - i.e., the table's shape depends on your actual
panel/output configuration, confirming it's a real per-config mapping table (most likely
per-scanline or per-module row index) rather than a fixed constant.

### Still zero: `0x10` and `0x1F`

Even during a real write to real hardware, these two packet types remained **entirely
zero-filled** - same as the no-card baseline. Current best guess: these are reserved for
optional features not exercised by this simple single-cabinet setup (possibly calibration data,
pixel-by-pixel correction, or multi-cabinet cascade info - all things this particular capture's
panel didn't use). Not yet confirmed.

### New type found: `0x26` (278 bytes) — correction, see below

Matches FPP's own source comment size guess almost exactly ("Data Length: 264" vs. our measured
265 data bytes). Appeared ~372 times across the whole capture (not just during the write burst),
suggesting a continuous periodic status packet rather than one-time config data - not yet decoded
in detail.

**Correction (2026-11-07):** filtering by frame length alone is not reliable - a later capture
showed 278-byte frames are actually a *mix* of two different packet types: `0x26` and `0x06`
(the same "heartbeat" type seen elsewhere at 140 bytes, apparently also capable of a larger
278-byte variant with real content, not just a fixed poll). In one capture, the periodic status
packet ran as `0x26` for the first ~86 occurrences, then **permanently switched to `0x06`
partway through the session** (no burst or other visible event at that moment) and stayed `0x06`
for the rest of the capture. Cause unknown. Takeaway: always verify the actual type byte
(frame offset 12), never group packets by length alone.

## First controlled single-variable diff: Brightness Level isolated (2026-11-06)

Same person, same card, changed **only the "Brightness Level" dropdown (8 → 5)** in LEDVision
and clicked Send, capturing again (`Brightness_8to5.pcapng`, local only). This is exactly the
one-variable-at-a-time methodology recommended earlier, and it worked cleanly:

- **`0x03` and `0x76` were byte-for-byte unchanged** - cleanly rules brightness out of those two
  packet types.
- **`0x05` changed in exactly two places** (both in lock-step, same value in both spots -
  confirms this protocol stores some fields redundantly at multiple offsets, consistent with
  width/192 also appearing more than once earlier):
  - data offset **24** (frame byte 0x25): `0x03` → `0x02`
  - data offset **156** (frame byte 0xA9): `0x03` → `0x02`
  - **Mapping is not yet 1:1 obvious**: UI level 8→wire value 3, UI level 5→wire value 2. Not a
    direct linear encoding of the displayed number - more data points (try level 1, level 4,
    level 8 individually) needed to nail the exact function. But the *offset* is now solid.
- **Bonus find**: the **last 4 bytes of the `0x05` packet changed completely** (`24 a9 14 58` →
  `35 1b de 7b`) even though only 2 content bytes changed. This is almost certainly a
  **checksum/CRC covering the packet body** - worth checking if other packet types end the same
  way, and whether it's a standard CRC32 (if so, writing a valid config packet requires computing
  this correctly, which is solvable once we identify the exact algorithm/seed).

This single clean diff is worth more than hours of guessing - same technique should be repeated
for scan mode, driver IC, decode IC, and the other visible fields next.

## What this means for scope (current, 2026-11-06)

- Packet types `0x01/0x07/0x08/0x0A/0x55` (discovery + output) remain **safe to build on** —
  FPP's own driver proves them correct in production.
- **Read path (Feature 2/3) is now substantially understood**: `0x08` identify + a sequence of
  `0x09` frames carrying a raw-deflate-compressed parameter blob. Reassembly/decompression is
  implemented and working in `backend/decode_config_stream.py`. Several fields are mapped to
  exact offsets (gamma, minimum OE, cabinet width/height); most are not yet.
- **Write path (Feature 5/6) is now substantially understood** too: a fixed-order burst of
  `0x05` (dimensions), `0x10` (unused in simple configs), `0x03` (per-row/output table, shape
  depends on panel layout), `0x1F` (unused in simple configs), `0x76` (gamma LUT), `0x10` again,
  `0x1B` (retry/probe). "Send" and "Save to Receivers" appear to send the identical sequence -
  there may be no separate RAM-vs-flash commit step in this protocol.
- **Still open**: exact offsets for most individual settings (module size, scan mode, driver IC,
  decode IC, refresh rate, data group count, etc.) within `0x05`/`0x03`/`0x76`; what `0x10` and
  `0x1F` are actually for (they've been zero in every capture so far); whether Send vs. Save
  really are wire-identical or whether persistence happens some other way; the `0x11`
  ("Save Config??" per FPP's old comment), `0x31`, `0x32` types still haven't appeared in any
  capture at all.
- Feature 3 (backup)'s fallback plan (raw undecoded blob, clearly labeled unverified) is now less
  necessary than originally thought - the `0x09` stream decompresses into something we can
  already partially interpret, so a "backup" can be a real, growing-in-fidelity decode rather
  than an opaque blob, as more fields get mapped.
- **Next most valuable capture**: change exactly ONE visible setting (e.g. just brightness, or
  just scan mode) in LEDVision, Send, and capture again - diffing against this capture's `0x05`/
  `0x03`/`0x76` content the same way we isolated width/scan in the `.rcvp` file format. That's
  the fastest remaining path to mapping the rest of the fields.

## Mystery solved: why "Segments x16 → x32" never showed up on the wire (2026-11-06)

Three separate capture attempts (`Brightness_8to5.zip`/`Anotherone.zip` and now a third, narrated
one, `Capture_01.pcapng`) all tried to isolate a Segments x16→x32 change and all three showed
**zero difference anywhere in the write-burst traffic**. The third attempt included screenshots
of the actual LEDVision session, which explain why:

1. Before: `Segment x 16`, `Refresh Rate 1920`, `Width 192` (module is 192×16, cabinet 192×64,
   `<=381` shown as the width limit at x16 segments).
2. After selecting `Segment x 32` in the dropdown: `Refresh Rate` auto-updated to `3840`, but the
   `Width` field's limit shown next to it dropped to **`<=191`** - and the field turned red with a
   warning icon, because the panel's actual width (192) now *exceeds* the max width Segment x32
   allows (191, i.e. roughly half of the x16 limit, as expected since 32 segments only has half
   the addressable width per segment vs 16).
3. Clicking **Send** with that invalid combination pops a LEDVISION dialog: *"Current parameter
   have the following problems: 1. Receiver card width is not proper (it may not be an integer
   multiple of the width of the module or exceeding the max width)! Continue to Send?"*
   (Yes/No).

The capture itself (160s, 1.86M frames) contains exactly **one** write burst, at t=155.83s:
2× `0x05` (272B), ~a dozen `0x03` (784B each), and `0x1B` (282B) - no `0x76` gamma LUT this time
(unchanged, so apparently not resent). Byte-for-byte diff of all of them against the established
x16-segment baseline (`samples/decoded_frames/write_type05_dimensions.txt` /
`write_type03_row_table.txt`) shows **every single byte identical, including the trailing
checksum** (`24 a9 14 58`). So whatever happened at the dialog (Yes or No), **the data that
actually went out on the wire still describes the old Segment x16 / Refresh 1920 configuration,
not x32** - LEDVision never transmits the requested change when the width/segment combination is
invalid for this panel.

**Conclusion**: this was never a capture-methodology problem. `192×16, Segment x16` is simply not
compatible with `Segment x32` on this panel (the effective max width halves and 192 > 191), so
LEDVision silently keeps/reverts to the last valid values instead of sending the edited ones. To
actually observe a Segments x32 write on the wire we'd need either a panel/width combination where
x32 is valid (e.g. temporarily set width to something ≤191, like 96 or 128, *then* switch to
Segment x32 and Send), or to abandon this field and pick a different, unconstrained one (scan
mode, driver IC, decode IC, gray level, DCLK, data group count are all good next candidates and
don't have this kind of cross-field validation as far as we've seen).

## Audit: have we exhausted the captures we already have? (2026-11-06)

Before asking for yet another capture, re-mined all 6 captures collected so far
(`Capture_LEDVision_Start`, `Capture 01`, `Capture_LEDVision_With_SendAndSave`, `Brightness_8to5`,
`Anotherone`, `Capture_01`/`Wireshark_01`) for anything not yet squeezed out of them:

- **Brute-forced known Receiver-Parameters values** (Refresh Rate 1920, Gray Level 16384, DCLK
  25.0, etc.) against the already-decompressed `0x09` config blob at every plausible
  uint8/16/32/float32 offset. Only one interesting hit: `1920` as `<H` at offset 24111 - but
  cross-checking against a second capture's blob at that same offset showed it's part of an
  incrementing index/ID table (`...00 80 09|0a 00 80 0c 00 80 07 06 ae 00 06 af...`), not a
  settings field - a coincidental byte match, not real. Ruled out rather than reported as a find.
- **Decoded the read-path (`0x09`) blob from every capture that has one** (`start`, `cap01`,
  `sendsave`, `Brightness_8to5`) and diffed each against the original baseline blob. Three of the
  four are **byte-for-byte identical** to the original baseline (31171 bytes, zero diffs) - strong
  evidence the decompression/reassembly is fully deterministic when the underlying settings
  haven't changed. `Brightness_8to5`'s blob differs only in a small receiver-ID/index table late
  in the blob (session-specific, not a setting) - expected, since **no capture we have ever reads
  the config a second time after changing something**; every `0x09` sequence we've captured
  reflects the exact same pre-change baseline state.
- **Re-checked every `0x05` write burst across all captures** against the established baseline -
  all are either byte-identical (no change sent) or already-mapped (Brightness Level, offsets 24
  and 156).

**Conclusion: the existing logs are now fully mined.** There is no free diff left sitting unused -
every remaining field mapping (scan mode, driver IC, decode IC, data group, display mode, etc.)
needs a genuinely new, controlled single-variable capture. Two useful variants for the next ask:
1. A **write-path** capture (as before): change exactly one field with no cross-field validation
   (Blanking Value, Calibration Mode, Display Mode, Gray Mode, No Signal Action, Data/OE Polarity
   Reverse, Enable Gradual are all simple toggles unlikely to hit a "value not proper" wall like
   Segments did), Send, capture just that burst.
2. A **read-path** capture we don't have any version of yet: click **Read** *before* changing
   anything, change one field and Send, then click **Read** again (pulling the value back off the
   card) in the *same* capture - this is the only way to get a controlled before/after diff of the
   `0x09` config blob itself, independent of the `0x05`/`0x03`/`0x76` write packets.

**Update, same day**: "fully mined" turned out to only be true of *captures*. LEDVision's own
*installation* on disk is a second, much bigger source of ground truth - see next section.

## A second data source we'd been ignoring: LEDVision's own bundled profile library (2026-11-06)

`C:\Program Files (x86)\ColorLight\LEDVISION\` (wherever LEDVision is actually installed) ships
**856 example receiver-profile files** (`.rcvbp`) under `config_files\`, one per
manufacturer/module combination Colorlight has ever published a preset for - covering 25+ driver
ICs (DP5125, DP5020, DP7268, FM5020/6124/6126/6153/6253, ICN2019 through ICN2163, MBI5124,
SM16159/16169/16207/16259/5266, etc.) and ~10 decode ICs. These are plain binary files, no
protocol or hardware needed to read them - a goldmine sitting on disk the whole time. There's also
a `ChipSetting.dll` in the same install that almost certainly contains the authoritative
driver/decode IC tables and packing logic in native code, not yet examined.

### Isolating fields directly from the file library (no capture needed)

Parsed all 856 filenames (`<panel>-<driverIC>+<decodeIC>-<X.XX>.rcvbp`) and grouped them to find
sets that hold everything but one token constant - the same single-variable-diff technique used
on captures, just applied to a static library instead:

- **Decode IC is a clean single byte at file offset 104.** Verified across 23+ samples spanning
  different driver ICs, panel sizes, and scan modes - always the same value for the same decode
  name: `0="138 Decoding"`, `1="5166"`, `9="5266"`, `17="2013"`.
- **Driver IC is not a single byte** - diffing three otherwise-identical presets (same panel, same
  decode, same gamma, only driver IC differs: 16169 vs 16259 vs 2053) shows ~25-40 bytes change,
  in clusters (offsets 78, 132-144, 222-250, plus the trailing checksum). Makes sense: different
  driver chips need genuinely different current/timing parameters, not just a label. Practical
  conclusion: identifying the driver IC on a connected card is better solved as **fingerprint
  matching** against this 856-file library than as a single enum field.
- The gamma value we'd already found at wire-blob offset 32 turns out to live at **file offset
  52** in `.rcvbp` - confirmed by an exact value match (2.8 both places), not just inference.

### The big find: `.rcvbp` and the wire read-blob share the same struct layout, 20 bytes apart

Lined up a real `.rcvbp` file against `samples/decoded_frames/receiver_params_decompressed.bin`
(our one live read-config capture) byte-for-byte and found they are **the same underlying
structure**, just with a constant 20-byte offset: `wire_offset = rcvbp_offset - 20`. Verified two
ways:
- **`gamma_value`**: exact value match, not just position - `33 33 33 40` (2.8 as float32 LE) sits
  at rcvbp offset 52 and wire offset 32, exactly 20 apart.
- **The 16-byte incrementing marker** `bytes(range(0x10, 0x20))` (part of a placeholder/calibration
  table both formats carry) - `rc.find(marker) == 146`, `wire.find(marker) == 126`. Also exactly
  20 apart.
- Beyond those two anchors, the ~100 bytes between them line up byte-for-byte structurally in both
  files: identical constant bytes in the same relative positions (`ff ff ff 03 02 01 00 01`,
  `32 14`, `00 70 42`), and a 3x-repeated 2-byte pattern (probably an R/G/B-channel calibration
  triplet) at the same relative offset in both, with different-but-structurally-parallel values
  (`00 fc` x3 in the wire blob vs `cf 39` x3 in this particular `.rcvbp` - different cards, same
  slot).

This means **every field position documented in either format now transfers to the other** -
we've effectively doubled our reference data overnight, and can keep mining the `.rcvbp` library
(856 static files, zero captures needed) to find more wire-blob field offsets going forward.

**One open mismatch, not yet resolved**: translating the `.rcvbp` decode-IC slot (offset 104)
through the delta lands on wire offset 84. Our one real card (LEDVision shows "138 Decoding" for
it) reads back `wire[84] == 1`, but per the `.rcvbp` enum table `1` means "5166", not the expected
`0` ("138 Decoding"). Given how precisely everything else lines up at this delta, this looks less
like an offset error and more like **the GUI's own preset-authoring enum and the firmware's actual
wire-level enum are two independently assigned code spaces** for the same physical chip - they
just happen to share the same struct slot because both formats clearly derive from the same
underlying receiver memory layout. Confirming this (and getting a real decode-IC lookup table)
needs one more real read-config capture, ideally from a receiver with a **different, known** Decode
IC, to diff against this one the same way Brightness Level was isolated.

Implemented in [`backend/decode_config_stream.py`](../backend/decode_config_stream.py) as
`RCVBP_TO_WIRE_OFFSET_DELTA` with the candidate (unconfirmed) decode IC offset documented inline.
