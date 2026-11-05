# Colorlight Protocol Capture — Step by Step

Send this to whoever is running the capture. Two scenarios are covered: **with** a real
Colorlight receiver card connected (better, do this if at all possible), and **without** one
(still useful, and what we've been doing so far). Follow the "with a card" path if you have one;
otherwise skip to "without a card."

## 1. One-time setup

1. Install **Wireshark** (includes Npcap) if not already installed: https://www.wireshark.org/download.html
2. Install **LEDVision** (Colorlight's config software). Version matters: **use LEDVision 7.0**,
   not the current 9.7 — 9.7 had problems talking to Ethernet-connected cards in our testing.
   Official download: https://en.colorlightinside.com/service/download/?cat=3559 (look for "LEDVISION V7.0").
   (The site blocks scripted downloads — this link only works from a normal browser click, not
   curl/wget/etc.)
3. Copy this Lua dissector file into Wireshark's plugin folder so captured Colorlight packets
   show up decoded instead of as raw bytes: `fpp/docs/ColorLight_Wireshark.lua` from the FPP
   source tree (ask if you need this file sent separately). Wireshark's plugin folder location:
   **Help → About Wireshark → Folders → Personal Lua Plugins**. Restart Wireshark after copying
   it in (or **Analyze → Reload Lua Plugins**).

## 2. Identify the right network adapter

In Windows, open PowerShell and run:
```powershell
Get-NetAdapter | Select-Object Name,InterfaceDescription,Status,LinkSpeed
```
You want the **real physical Ethernet port** — usually just named "Ethernet" with a
description like "Realtek..." or "Intel... Gigabit..." and `Status: Up`. Ignore anything named
Wi-Fi, VPN, Tailscale, WireGuard, VirtualBox, Hyper-V, or VMware — those are virtual and will
just add noise.

## 3. Physical connection

- **With a card**: connect that NIC directly to the Colorlight receiver with an Ethernet cable
  (no switch in between if avoidable — we saw a report that some switches interfere with this
  protocol). Power on the receiver and its LED panels if convenient.
- **Without a card**: nothing to connect — just leave that NIC as-is (it doesn't even need a
  cable plugged in, though having one plugged into a quiet network is cleaner).

## 4. Start the capture

1. Open Wireshark, select the adapter identified in step 2.
2. Click the blue shark-fin **Start** button. **Start this before opening LEDVision** so we
   don't miss the first packets.

## 5. Open LEDVision's receiving-card tool

1. Open **LEDVISION 7.0**.
2. Click into **Control → Led Screen Settings** (or similar — look for a screen/device settings
   option).
3. If prompted for a password, use **`168`** (try **`777`** if that doesn't work). This is a
   known default, not a real security measure.
4. You should land on a window with tabs: **Sending Device / Receiver Parameters / Receiver
   Mapping**.

## 6. Switch to "Net Card" mode

1. On the **Sending Device** tab, under "Select Sending Device," click **Net Card** (not
   "Sender" or "Play Box" — those expect separate physical hardware and won't produce the
   traffic we need).
2. A network adapter selection should appear — pick the **same adapter** you're capturing on.

## 7. Run the captures

Do each of these as a **separate** Wireshark capture (Stop, Save As, Start again for the next
one) so each scenario is isolated. Name the files exactly as shown.

### If you have a real receiver card connected:

| # | Action in LEDVision | Save capture as |
|---|---|---|
| 1 | Click **"Detect Receiver Cards"** and let it finish | `01-discover-with-card.pcapng` |
| 2 | Go to **Receiver Parameters** tab, use whatever button **reads the current settings off the card** (not from a file) | `02-read-config-with-card.pcapng` |
| 3 | Set the parameters to match the real panel (ask whoever has the panel specs: pixel pitch/model, width×height, scan rate, driver IC) and **send/apply** them to the card | `03-write-config-with-card.pcapng` |
| 4 | If there's a separate **"Save"** / "write to flash" / persist action (distinct from step 3's apply), do it now | `04-save-persist-with-card.pcapng` |

**Important**: before step 3, back up the card's current working config first if LEDVision
offers a backup/export option — we don't want to lose a known-good configuration.

### If you do NOT have a card connected:

| # | Action in LEDVision | Save capture as |
|---|---|---|
| 1 | Click **"Detect Receiver Cards"** (it'll find nothing, that's fine) | `01-detect-no-card.pcapng` |
| 2 | Go to **Receiver Parameters** / **Screen Configuration**. Set up a screen matching a real P5 panel: **64×32 pixels, scan 16**. Apply/send it. | `02-configure-p5-64x32-16s-no-card.pcapng` |
| 3 | Change **only the scan rate** to 8 (leave everything else the same) and re-send | `03-scan8-no-card.pcapng` |
| 4 | Change it back to scan 16, then change **only the width** to 32 and re-send | `04-width32-no-card.pcapng` |
| 5 | Set width back to 64, then change **only the height** to 16 and re-send | `05-height16-no-card.pcapng` |

Changing exactly one setting at a time between captures is the important part — that's what
lets us isolate which bytes in the packets correspond to which setting.

## 8. Send the files back

Send all the `.pcapng` files. If they're too large for whatever you're using to send them,
7-Zip/zip them first — they should compress well. Also mention:
- The receiver card's exact model/firmware if you have a card (our own card reported firmware
  **10.16** — if theirs reports something very different, that's useful to know).
- Whether anything in LEDVision errored, grayed out, or behaved unexpectedly at any step.
