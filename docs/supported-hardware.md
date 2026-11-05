# Supported Operation Matrix — Phase 1 Assessment

Target hardware for initial development: Colorlight 5A-75B, firmware V7.0, driven by FPP 10 on
a Raspberry Pi 5, built-in Ethernet port direct to the receiver.

Legend: ✅ supported today (in FPP or via decoded public protocol) · 🟡 feasible, protocol
partially understood, needs verification/capture · 🔴 not currently feasible — protocol unknown,
needs new reverse engineering (packet capture) before any code can be written.

| Capability | Status | Basis |
|---|---|---|
| Select Ethernet interface | ✅ | FPP already does this (`m_ifName` config, link/speed checks) — reusable as-is. |
| Discover connected receiver(s) | ✅ | FPP's `GetReceiverInfo()` already implements broadcast discovery (type `0x07`/`0x08`) and parses id, firmware major/minor, uptime, packet counter. |
| Identify exact model (e.g. "5A-75B" vs "5A-75E") | 🟡 | Discover reply Data[0] = `0x05` ("5A card") is the only model byte FPP decodes; it does not distinguish 75B vs 75E vs other 5A-series boards. May require either a longer reply field FPP currently ignores (packet is 1070 bytes; FPP only reads the first ~90) or capture analysis. Must report "unknown sub-model" rather than guess per the brief's own rule. |
| Firmware version | ✅ | Discover reply Data[2]/Data[3], already decoded by FPP. |
| MAC address of receiver | 🟡 | Not currently captured by FPP (it discards the raw frame after parsing `data[]`); the source MAC is present in every reply frame and trivially extractable — low-risk addition, not yet implemented. |
| Network interface used | ✅ | Known locally (it's the configured FPP interface), not something that needs to come from the receiver. |
| Capabilities (ports, resolution limits, etc.) | 🔴 | No discovery field decodes this. Would need either spec-sheet lookup keyed off model/firmware (static table) or new protocol RE. |
| Multiple receivers | 🟡 | FPP's discovery loop already tries receiver ids 0–31 and stores one `ColorLightReceiver` per id found — the data structure exists. Not exposed anywhere in FPP's UI/API today; a thin wrapper can read it. |
| Read panel resolution / scan rate / driver IC / RGB order / HUB75 mapping / port config / panel mapping / data groups / timing / PWM | 🔴 | None of these are read by stock discovery. They live in the undecoded `0x10/0x11/0x18/0x1F/0x26/0x31/0x32/0x76` config-write packets (see `protocol.md`) — and even those are the *write* path; no *read* command for stored config has been identified at all yet, from FPP, hkubota's research, or chubby75. **This is the single biggest open question** and gates Features 2, 5 (prefill from hardware), 6, 7. |
| Backup (raw bytes) | 🟡 | Possible only once/if a read-back command is found. Until then, nothing exists to back up beyond what the panel-layout JSON the *user* already configured in FPP (not the receiver's own state). |
| Backup (validated, restorable) | 🔴 | Requires both read and write paths to be understood and round-trip-tested. |
| Import `.rcfg`/`.rcfgx` | 🔴 (wrong premise) | These extensions belong to NovaStar, not Colorlight — see `protocol.md`. Colorlight's own LEDSetting/LEDVision export format is currently unknown to us; we have no sample file yet. |
| Manual panel configuration UI (local, FPP-side layout only — width/height/scan/driver IC/RGB order/etc. as *FPP's own* channel-output settings, not written to the receiver) | ✅ | Already exists via `ColorLight-5a-75.cpp`'s `Init()` JSON config (`panelWidth`, `panelHeight`, `colorOrder`, `panels[]`, `invertedData`, etc.) and FPP's web UI for this output type. This configures how *FPP* maps pixels to the wire protocol — it does not touch anything stored on the receiver card itself. |
| Write configuration to receiver | 🔴 | Blocked on decoding `0x10/0x11/0x18/0x1F/0x26/0x31/0x32/0x76`. |
| Persist config to nonvolatile storage on receiver | 🔴 | Type `0x11` is suspected ("Save Config??" per FPP's own comment) but unconfirmed. |
| Test patterns | ✅ | FPP already implements `OverlayTestData()` / `SupportsTesting()` for this output type — reusable. |
| Intelligent/guided setup wizard | 🔴 | Explicitly depends on write support existing first; brief itself defers this to Phase 6. |

## Net assessment

FPP's existing Colorlight driver gives us, for free: interface selection/link checks, raw-socket
plumbing, MAC framing, discovery (id/firmware/uptime/counter), pixel/brightness/sync output, and
test-pattern overlay. That covers this project's **Feature 1 (discovery)** almost completely and
is a solid foundation to build the plugin's read-only dashboard on in Phase 2.

Every other requested feature (2, 3 fully, 4, 5's hardware-prefill half, 6, 7) is blocked on the
same unanswered question: **how does LEDVision read and write a receiver's stored panel
configuration?** No existing source — FPP's own code, hkubota's independent writeup, or the
chubby75 hardware-RE project — has published that. It has to come from our own packet captures
per `development-plan.md`'s Phase 1 capture plan, using the Wireshark dissector already present
at `fpp/docs/ColorLight_Wireshark.lua` as a starting point (it already frames types
`0x10/0x18/0x1F/0x26/0x31/0x32/0x76` as "unparsed" placeholders ready to be filled in).
