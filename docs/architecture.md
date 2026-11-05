# fpp-colorlight-manager — Architecture (Phase 1 draft)

This is a planning document, not yet implemented. It will be revised after Phase 2
(read-only discovery prototype) is validated against real hardware.

## Relationship to FPP core

- Built as a standard FPP **plugin** (`/media/plugins/fpp-colorlight-manager`, loaded from a
  repo of the same name), following the conventions observed in the existing sibling project
  `fpp-EncoreRadio` in this workspace (real-world FPP 10 plugin, not a template guess):
  - `pluginInfo.json` at repo root (name, repoName, author, description, homeURL/srcURL/bugURL,
    `versions[]` with `minFPPVersion`/`maxFPPVersion`/`dependencies.packages`, and a `privacy`
    block disclosing any network sends / data collected / system changes).
  - `fpp_install.sh` / `fpp_uninstall.sh` at repo root (**not** `install.sh`/`uninstall.sh`).
  - `menu.inc` — PHP array of menu entries (at most one per type: status/content/output/help).
  - `www/` — PHP pages for the plugin's own UI, reached via `plugin.php?plugin=...&page=...`.
  - Flat `api.php` (or a handful of top-level PHP files) rather than a nested `api/` folder,
    matching what FPP 10 plugins actually use for this version.
  - `scripts/` for shell/python helper scripts invoked by the PHP layer or by FPP commands.
  - `commands/` + `commands/descriptions.json` if we expose FPP Command Presets.
  - `docs/` for this project's own documentation (architecture, protocol, supported-hardware,
    development plan, troubleshooting).
- **Do not modify FPP core.** We will reuse `ColorLight-5a-75.cpp`'s *behavior* (packet formats,
  discovery, raw-socket technique) but talk to the hardware from our own plugin code, independent
  of the running channel-output driver, so we never contend with or require changes to the
  existing output path. FPP's existing output plugin keeps driving pixels during normal playback;
  our plugin's management operations (discover/read/backup/program) are a separate, occasional
  raw-socket conversation on the same interface, explicitly sequenced to avoid overlapping with
  active output per the safety requirements (stop conflicting output before any write).
- Where it's useful to send actual pixel/sync/brightness frames (e.g. for Feature 7's test
  patterns), prefer driving that through FPP's existing channel-output + test-pattern mechanism
  (`SupportsTesting()`/`OverlayTestData()`) rather than re-implementing frame transmission in the
  plugin, so we don't duplicate FPP's sendmmsg-based packet pacing.

## Language/process split

- **Discovery, protocol decode/encode, backup/import file handling**: Python, mirroring the
  suggested `backend/` layout in the brief. Python is adequate here — these are low-rate,
  non-realtime operations (a handful of packets per discovery/read/write cycle, not a 1000fps
  pixel stream), so there's no performance reason to write this in C++. This also keeps the
  plugin's protocol logic independent of FPP's own build/ABI, so it can be developed, unit
  tested, and iterated without recompiling FPP.
- Raw Ethernet access from Python needs `CAP_NET_RAW` (see Privilege section below), via either
  `socket.AF_PACKET` directly or `scapy` if more convenient for repeated iteration during RE work.
  No dependency on scapy is assumed for the shipped plugin unless it proves necessary — stdlib
  `socket` is sufficient for the packet shapes already decoded (fixed-size frames, no checksums
  observed yet).
- **Web UI**: PHP pages under `www/`, consistent with the rest of FPP 10's plugin ecosystem and
  with `fpp-EncoreRadio`'s own `www/index.php` + supporting endpoint pattern (`www/save.php`,
  `www/start.php`, etc. there → here, something like `www/discover.php`, `www/read_config.php`,
  `www/backup.php`, `www/program.php`, each a thin wrapper shelling out to / invoking the Python
  backend and returning JSON for the page's JS to render).
- No case yet for C++. If profiling during Phase 5/6 shows the write-and-verify sequence needs to
  be tighter than Python's socket/process overhead allows, that's a later decision, not a Phase 1
  one — the brief itself says the implementation language may change if warranted.

## Privilege model

- Raw Ethernet packet construction/receipt requires elevated privileges. Avoid running the whole
  web stack as root:
  - Prefer granting the specific Python helper script(s) `CAP_NET_RAW` (and `CAP_NET_ADMIN` only
    if a promiscuous-mode toggle on the receive socket turns out to be required — FPP's own
    `GetReceiverInfo()` does set `IFF_PROMISC`, so plan for needing it) via `setcap`, invoked from
    a narrowly-scoped helper rather than general-purpose `www/*.php` code running as the `fpp`
    web user.
  - Alternative considered: a small long-lived privileged helper daemon that the PHP layer talks
    to over a local Unix socket (similar in spirit to how `fppd` itself is a privileged daemon
    the web UI talks to via domain socket) — revisit if `setcap` on each invocation proves
    insufficient (e.g. if discovery needs to hold the receive socket open across multiple PHP
    requests).
  - `fpp_install.sh` is where `setcap` would be applied to the installed script, and
    `fpp_uninstall.sh` should not need to reverse it beyond removing the file.

## Verified / inferred / manual / unknown — data provenance

Per the brief's Feature 2 requirement, every configuration value the plugin displays must carry
a provenance tag. Proposed representation: each decoded field in the Python backend's config
model carries a `source` enum — `"verified"` (read directly off the receiver), `"inferred"`
(derived from raw register bytes via a documented decode, not a direct 1:1 field), `"manual"`
(typed by the user in the FPP UI, never sent to or confirmed by hardware), `"unknown"` (byte
range exists but has no decode yet — displayed as hex, never interpreted). This tagging has to
exist in the data model from the first read-capable prototype, not bolted on later, since it's
core to the safety requirements (never present inferred/unknown data as verified).

## Planned directory layout

Matches the brief's suggested structure; adjusted only where the `fpp-EncoreRadio` precedent in
this workspace shows the real FPP 10 convention differs (install script names, flat `api.php`
vs `api/`):

```
fpp-colorlight-manager/
├── README.md
├── LICENSE
├── pluginInfo.json
├── fpp_install.sh
├── fpp_uninstall.sh
├── menu.inc
├── icon.png
├── www/
│   ├── index.php              # Dashboard
│   ├── discover.php
│   ├── read_config.php
│   ├── backup.php
│   ├── import.php
│   ├── configure.php
│   ├── program.php
│   ├── css/colorlight.css
│   └── js/colorlight.js
├── backend/
│   ├── receiver_discovery.py
│   ├── colorlight_protocol.py   # shared frame encode/decode, ported from FPP's own + our capture findings
│   ├── configuration_reader.py
│   ├── configuration_decoder.py
│   ├── configuration_writer.py
│   ├── backup_manager.py
│   └── receiver_manager.py
├── configs/panel_profiles/
├── docs/
│   ├── architecture.md
│   ├── protocol.md
│   ├── supported-hardware.md
│   ├── development-plan.md
│   └── troubleshooting.md
└── tests/
    ├── test_discovery.py
    ├── test_protocol.py
    ├── test_configuration.py
    └── test_backups.py
```

Not yet created beyond `docs/` — code starts in Phase 2, scoped to discovery only (see
`development-plan.md`).
