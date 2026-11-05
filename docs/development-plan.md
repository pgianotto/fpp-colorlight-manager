# Initial Development Plan

## Phase 1 — Research and Feasibility (this document + protocol.md + supported-hardware.md + architecture.md)

Status: **complete**, pending your review. Findings summarized in the chat response that
accompanies this commit of docs. No code written yet, per the brief's instruction not to begin
writes — or really any implementation — before this review.

## Phase 2 — Read-Only Receiver Discovery (recommended next step, smallest practical slice)

Goal: a working prototype, independent of FPP's channel-output driver, that:

1. Lets the user pick the Ethernet interface (reuse FPP's existing interface list).
2. Sends the `0x07` discovery broadcast and parses `0x08` replies — id, firmware major/minor,
   uptime, packet counter, source MAC, and the two still-fuzzy width/height-like fields (Data[21-24])
   tagged `"unknown"` per the provenance model until we confirm their meaning against our own
   hardware.
3. Displays results in a minimal `www/index.php` page (table: receiver id, firmware, uptime, MAC).
4. Logs every sent/received frame (hex) to a plugin log file for debugging and for reuse as
   evidence when we write `protocol.md` updates later.

This is deliberately almost a re-implementation of FPP's own `GetReceiverInfo()` in Python,
exposed through the plugin's own UI instead of being buried in channel-output init-time logging —
because today a user has no way to see this information without reading `fppd` logs. It's useful
on its own (answers "is my receiver even talking to me") and it's the lowest-risk possible piece:
read-only, broadcast-only, uses only packet types FPP's shipping code already proves correct.

**Test plan for Phase 2:** run against the real 5A-75B V7.0 on the Pi 5 + built-in Ethernet setup
described in the brief; compare output against `fppd`'s own discovery log for the same hardware
at the same moment (should match exactly, since it's the same protocol).

## Phase 3 update (2026-11-02): partially unblocked without hardware

See `protocol.md`'s "BREAKTHROUGH" section - LEDVision's **"Net Card" sending mode** streams its
full config-write packet sequence without any receiver attached, which got us real payloads for
every previously-mystery packet type (`0x10`, `0x18`, `0x1F`, `0x76`, plus new ones `0x03`,
`0x05`, `0x17`, `0x1B`). The capture-dependency below is still real for *confirming reads work
at all* and for the *write-and-verify* round trip, but isolating what each byte in the
config-write packets means can now proceed via controlled diffs in LEDVision alone (change one
setting, re-capture, diff) - no card required for that part. Hardware is still needed to confirm
anything actually gets read back correctly and that a write persists/survives a restart.

## Phase 3 (original) — Configuration Reading — needs packet captures

Per `protocol.md`, no read command for stored receiver configuration has been identified in any
source reviewed. Before any code for this phase, we need the capture sessions below, run by you
against your actual hardware (we can't drive LEDVision on your Windows PC from here).

### Required captures (adapted from the brief's plan, trimmed to what Phase 3 actually needs)

All captures: Wireshark on the Windows PC, PC's NIC connected directly to the 5A-75B receiver
(the same connection you'd normally make to bypass FPP). Load `fpp/docs/ColorLight_Wireshark.lua`
into Wireshark first (`Analyze → Reload Lua Plugins` after copying it into Wireshark's plugin
folder) — it already decodes the known types and labels `0x10/0x18/0x1F/0x26/0x31/0x32/0x76` as
"Unparsed ColorLight Packet" so they're easy to spot in the capture.

- **Capture A — Discovery** (sanity check / confirms our Phase 2 decode against your exact
  firmware): start Wireshark, launch LEDVision, let it detect the receiver, stop capture, save
  as `capture-a-discovery.pcapng`.
- **Capture B — Read existing configuration**: start a new capture, open the receiver's settings
  in LEDVision, use whatever LEDVision command reads current config *off* the hardware (not from
  a local file) — this is the capture most likely to contain the still-unknown read command, if
  one exists. Save as `capture-b-read-config.pcapng`.
- **Capture C — Export a config file**: with the same panel open in LEDVision, export/save its
  configuration to a file (whatever extension LEDVision actually offers — do **not** assume
  `.rcfg`/`.rcfgx`, those are NovaStar's; note the real extension you see). Keep both the pcap
  (in case exporting itself talks to the receiver) and the exported file — the file itself may
  turn out to be more useful for decoding format than the capture.
- **Capture D — Program a known config**: start a new capture, load a known-working configuration
  in LEDVision (ideally the exact one already running on your panels, to minimize risk of writing
  something wrong to real hardware), send it to the receiver. Save as `capture-d-write-config.pcapng`.
- **Capture E — Save-to-receiver / persist**: start a new capture, execute LEDVision's explicit
  "save to receiver" / persist-to-flash action if it's a separate step from Capture D. Save as
  `capture-e-persist.pcapng`.

Captures B and D/E are the ones expected to contain the `0x10/0x11/0x18/0x1F/0x26/0x31/0x32/0x76`
traffic. Capture A should contain only already-decoded types and is mainly a format sanity check.

**Safety for these captures:** B and A are read-only by construction (LEDVision reading state,
not writing it) — no risk. C writes a file only. D and E are the ones that touch receiver state;
do them only after a successful full backup (manual, via LEDVision's own backup feature, since
our plugin can't do this yet) and ideally on a panel you can tolerate re-flashing if something
goes wrong, consistent with the brief's own "use passive capture and read-only experiments before
testing configuration writes" rule.

Once captures exist, Phase 3's actual work is: decode the new packet types field-by-field against
the capture, cross-check multiple captures with deliberately different settings (e.g. change one
field in LEDVision, re-export/re-send, diff the packets) to isolate which bytes correspond to
which UI setting, then implement `configuration_reader.py`/`configuration_decoder.py` against the
confirmed decode — carrying the verified/inferred/unknown provenance tags from day one.

If a capture-based read command isn't found (e.g. LEDVision always reads from its own local
project file, never from the receiver), we report that honestly rather than inventing one, and
Feature 3 (backup) degrades to "export whatever a raw register dump (if any undocumented read-
back exists) contains, labeled as an unverified blob" or "no hardware-side backup possible for
this firmware" — not a fabricated feature.

## Phase 4 — Import and Validation (after Phase 3, and only once we know the real export format)

## Phase 5 — Receiver Programming (after Phase 3/4, write-side protocol confirmed and round-trip tested)

## Phase 6 — Intelligent Configuration Wizard (long-term, per brief — not before Phase 5 ships)

## Immediate recommendation

Build **Phase 2 only** next (read-only discovery UI), and in parallel, you run the Capture
A–E sessions above on your Windows PC against the real 5A-75B V7.0. Phase 2 needs no captures
and gives an immediately useful, safe, demoable piece; the captures are the hard dependency for
everything else in the brief (Features 2–7) and only you can produce them, since they require
your LEDVision + hardware setup. We should not start Phase 3+ code until at least Capture B
exists and we've looked at it together.
