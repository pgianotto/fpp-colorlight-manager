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

### What's still open

- Module size (192W×16H), scan mode (16), driver IC (DP5125), decode IC (138 Decoding), refresh
  rate (1920 - found once at decompressed offset 24111, far from the other confirmed fields, so
  likely a different, separate sub-section of the blob), gray level (16384), and most other
  visible fields are not yet mapped to specific offsets.
- The write path (sending a changed config back, and the "Save to Receivers" persist step) has
  not been captured yet - only the read path. If whoever ran this capture can also click
  **Send** and **Save to Receivers** after changing something, that's the next capture to get.
- The two unknown-value header fields in the first `0x09` frame's 36-byte header are still a
  mystery (possibly a request-id, CRC, or session token - 14 bytes of it looked hash-like).

## What this means for scope

- Packet types `0x01/0x07/0x08/0x0A/0x55` (discovery + output) are **safe to build on now** —
  FPP's own driver proves them correct in production.
  - **Risk even in “safe” territory:** FPP never *sends* `0x02` and its own comment admits the
    `0x08` discovery-reply width/height-like fields (Data[21-24]) don't arithmetically match
    cabinet offsets the way expected. Treat anything derived from those fields as unverified
    until confirmed against our own hardware, even though the bytes themselves are read, not guessed.
- Everything required for Features 2, 3 (meaningfully — see below), 4, 5, 6, 7 requires
  decoding packet types `0x10/0x11/0x18/0x1F/0x26/0x31/0x32/0x76`, which is **undocumented
  anywhere we can find**. This must come from our own Wireshark captures of LEDVision talking
  to the actual 5A-75B V7.0 hardware (see `development-plan.md` Phase 1 capture plan).
- Feature 3 (backup) has a fallback that doesn't require decoding: a **raw register/EEPROM dump**
  if we find a read-back command, even undecoded, can still be stored as a binary blob backup —
  but per the brief's own safety rule, it must **not** be presented as a verified, restorable
  configuration until the write path is understood well enough to confirm round-trip fidelity.
