# fpp-colorlight-manager

An FPP 10 plugin to manage Colorlight LED receiving cards (starting with the 5A-75B) from the
FPP web UI, without disconnecting Ethernet to use Colorlight's Windows-only LEDVision software.

**Current status: Phase 2 — read-only discovery only.** This plugin currently does one thing:
it sends Colorlight's broadcast discovery query on an interface you pick and shows what
receivers reply with (id, firmware version, uptime, packet count, source MAC). It does **not**
read, back up, import, or write any receiver configuration yet — see `docs/development-plan.md`
for why (short version: nobody has publicly reverse-engineered that part of the protocol yet,
including FPP's own driver, and it needs real packet captures against hardware before any of
that code can be written safely).

See `docs/` for the full research behind this:

- `docs/protocol.md` — what's been verified vs. is still unknown about the wire protocol, with
  references to FPP's own driver and public reverse-engineering sources.
- `docs/supported-hardware.md` — feature-by-feature status against the original project goals.
- `docs/architecture.md` — plugin layout and design decisions.
- `docs/development-plan.md` — phased plan, including the Wireshark capture sessions needed
  before configuration read/write can be attempted.

## Installing

Install like any other FPP 10 plugin: clone this repo into FPP's plugin directory (or add it
via FPP's Plugin Manager once published), which runs `fpp_install.sh`. That script installs a
narrowly-scoped sudoers rule (see `pluginInfo.json`'s `privacy.systemChanges`) so the web UI can
invoke `backend/receiver_discovery.py` with the raw-socket privilege it needs, without running
the whole web stack as root.

## Using it

Open **Status → Colorlight Manager** in the FPP web UI, pick the Ethernet interface your
Colorlight receiver is connected to, and click **Scan for Receivers**.

## Running the tests

```bash
pip install pytest
pytest tests/
```

Tests cover the protocol encode/decode logic (`backend/colorlight_protocol.py`) against
synthetic frames; no hardware or raw-socket access is required to run them.

## Safety

This plugin only sends broadcast discovery frames and parses replies — it cannot affect how any
receiver is currently displaying content. Nothing here writes to a receiver. See the safety
requirements in `docs/development-plan.md` for the ground rules this project follows as later
phases (reading, backing up, writing configuration) are built.

## License

MIT — see `LICENSE`.
