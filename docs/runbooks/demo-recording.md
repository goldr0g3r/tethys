# Runbook - Demo recording

> Audience: project owner producing the two end-to-end demo videos (marine +
> space) for README + docs site + case-study PDF.
> Goal: from "HIL bench is functional (see hil-bench-setup.md)" to
> "two ~3-minute polished demo videos published in the GitHub Release, plus
> embedded thumbnails in README". Wall-clock target: **3 hours per demo** the
> first pass, **<1 hour for re-records**.
> Style: pre-production checklist, shot list per demo, post-production
> recipe, publishing checklist.
>
> Implements parent plan §11 (public deliverables) and §9 (Phase 9 HIL).
> Companion to [`hil-bench-setup.md`](hil-bench-setup.md) and
> [`release-process.md`](release-process.md).

## Table of contents

1. [Equipment](#1-equipment)
2. [Pre-production checklist](#2-pre-production-checklist)
3. [Shot list - marine demo](#3-shot-list---marine-demo)
4. [Shot list - space demo](#4-shot-list---space-demo)
5. [Recording](#5-recording)
6. [Post-production](#6-post-production)
7. [Publishing](#7-publishing)
8. [Cross-references](#8-cross-references)

---

## 1. Equipment

| Item | USD | Use |
| --- | --- | --- |
| OBS Studio (free) | 0 | Screen + webcam + audio capture |
| USB condenser mic (Blue Snowball or similar) | ~50 | Voice-over |
| Plain backdrop (paper or wall) | 0 | Webcam aesthetic |
| Ring light (5500 K LED) | ~25 | Webcam lighting |
| Phone tripod | ~15 | Bench photo |
| HIL bench (per hil-bench-setup.md) | ~150 | The actual demo |
| **Total** | **~240** | |

Software:

- OBS Studio 30+ (<https://obsproject.com/>) - free
- DaVinci Resolve (free tier) (<https://www.blackmagicdesign.com/products/davinciresolve/>) - editing
- Audacity (<https://www.audacityteam.org/>) - audio cleanup (optional)
- ffmpeg - any version - final transcode

## 2. Pre-production checklist

- [ ] HIL bench fully working (smoke per `hil-bench-setup.md` §5).
- [ ] Master tool window arranged (terminal + GUI side-by-side).
- [ ] Wallpaper / desktop free of personal info.
- [ ] Notifications off (PowerShell: `Get-Process Teams,Slack,Discord |
      Stop-Process`).
- [ ] Mic gain set; test recording 30 seconds; verify no clipping in Audacity.
- [ ] OBS Studio profile loaded with scenes:
      1. "Title card" - text overlay only.
      2. "Bench wide" - webcam centered.
      3. "Master tool" - screen capture.
      4. "Master + bench PIP" - screen + small webcam corner.
      5. "Slack mode close-up" - zoom on key terminal area.
- [ ] Recording target FPS: 30; resolution: 1920x1080; bitrate: 8 Mbps;
      output: MKV (transcode to MP4 in post).
- [ ] Script printed or on a second monitor.

## 3. Shot list - marine demo

Target length: **3:00** final cut.

| # | Section | Time | Notes |
| - | --- | --- | --- |
| 1 | Title card | 0:00-0:05 | "Tethys - marine common-rail injector calibration" |
| 2 | Bench wide shot | 0:05-0:15 | "Here's the bench: Nucleo F767ZI + CANable 2.0 + 1 m Ethernet cable" |
| 3 | Cost callout | 0:15-0:25 | Overlay: "Total bench cost: ~$109. Vector CANape: ~$5,000." |
| 4 | Boot master tool | 0:25-0:40 | `tethys-master connect --profile marine --transport udp --a2l marine-demo.a2l` |
| 5 | A2L tree zoom | 0:40-0:55 | Show 123 measurements + 45 calibrations in the GUI |
| 6 | Start DAQ | 0:55-1:15 | `tethys-master daq start --rate 1000 --list cylinder_pressure,injector_pulse_us,fuel_temp_c` |
| 7 | Show pyqtgraph plot | 1:15-1:40 | Real-time signals scrolling; callout the rate (1 kHz) |
| 8 | Open Simulink | 1:40-1:55 | Plant model running; "external mode connected" |
| 9 | Calibrate injector pulse | 1:55-2:25 | Live tweak via XCP CAL; show pressure response in pyqtgraph + Simulink scope |
| 10 | Stop DAQ + open MDF4 | 2:25-2:45 | `tethys-master daq stop`; open `marine-demo.mdf4` in asammdf viewer; show signals |
| 11 | Standards callout | 2:45-2:55 | Overlay: "IACS UR E22 Rev.3 + IEC 61508 SIL 2 traceability rows: <N>" |
| 12 | Outro | 2:55-3:00 | "github.com/goldr0g3r/tethys" |

## 4. Shot list - space demo

Target length: **3:00** final cut.

| # | Section | Time | Notes |
| - | --- | --- | --- |
| 1 | Title card | 0:00-0:05 | "Tethys - satellite reaction wheel torque calibration" |
| 2 | Bench wide shot | 0:05-0:15 | "Bench: Nucleo H753ZI (ECC RAM) + FT232RL UART + plant model" |
| 3 | Cost callout | 0:15-0:25 | Overlay: "Total bench cost: ~$74. Real space-grade kit: ~$3,000+." |
| 4 | Boot master tool with auth | 0:25-0:50 | `tethys-master connect --profile space --transport sxi --auth-key-file space-test.key`; show the AES-128 seed-and-key handshake in the log |
| 5 | Show A2L space-profile tree | 0:50-1:05 | Reaction-wheel housekeeping + torque setpoint |
| 6 | Start DAQ + plant | 1:05-1:25 | 1 kHz DAQ; Simulink plant running |
| 7 | Calibrate torque setpoint | 1:25-1:50 | Show closed-loop response; emphasise deterministic ODT scheduling |
| 8 | Fault injection | 1:50-2:25 | `tethys-master fault inject --kind bit-flip --target cal_page_0 --offset 16`; show EDAC catch + recovery; watchdog still kicking |
| 9 | MC/DC coverage callout | 2:25-2:45 | Overlay: "MC/DC coverage on protocol core: 96% (>95% target)" |
| 10 | Standards callout | 2:45-2:55 | Overlay: "ECSS-E-ST-40C Rev.1 + NPR 7150.2D + DO-178C DAL-B trace rows: <N>" |
| 11 | Outro | 2:55-3:00 | "github.com/goldr0g3r/tethys" |

## 5. Recording

### 5.1 OBS setup

```text
Settings -> Output:
  Mode: Advanced
  Recording Path: ~/tethys-recordings
  Recording Format: MKV
  Encoder: x264
  Rate Control: CBR
  Bitrate: 8000 Kbps

Settings -> Video:
  Base Resolution: 1920x1080
  Output Resolution: 1920x1080
  FPS: 30

Settings -> Audio:
  Mic: Blue Snowball (or your mic)
  Sample Rate: 48 kHz
```

### 5.2 Recording session

1. Start recording.
2. Read the script section by section, doing the actual demo actions.
3. Take 2-3 takes per section; pick the best in editing.
4. Stop recording.

### 5.3 Backup raw footage

```bash
rsync -av ~/tethys-recordings/ /external-backup/tethys-recordings-$(date +%Y%m%d)/
```

```powershell
robocopy "$env:USERPROFILE\tethys-recordings" "E:\backup\tethys-recordings-$(Get-Date -Format yyyyMMdd)" /MIR
```

## 6. Post-production

### 6.1 Edit in DaVinci Resolve

1. Import MKV; sync to mic audio if separate.
2. Cut into shot-list segments.
3. Add 1-frame fade between sections.
4. Add overlay text per shot list.
5. Add intro / outro card (1 second each, plain text).
6. Add captions (SRT export for accessibility).

### 6.2 Audio cleanup (optional in Audacity)

- Noise reduction profile from a 1-second silent segment.
- Compressor: ratio 3:1, threshold -18 dB.
- Normalise to -3 dBFS peak.

### 6.3 Export

```text
DaVinci Resolve -> Deliver:
  Format: MP4
  Codec: H.264
  Resolution: 1920x1080
  Frame Rate: 30
  Quality: Best (CRF 18)
  Audio: AAC 192 kbps stereo
```

Target file size: **<50 MB** for embed in README; **<150 MB** for GitHub
Release attach.

### 6.4 Verify

```bash
ffprobe marine-demo.mp4 2>&1 | grep -E "Duration|Stream"
```

Expected: ~3:00 duration; one H.264 video stream + one AAC audio stream.

## 7. Publishing

### 7.1 Add to GitHub Release

```powershell
gh release upload v0.7.0 marine-demo.mp4 marine-demo.srt --clobber
gh release upload v0.8.0 space-demo.mp4 space-demo.srt --clobber
```

```bash
gh release upload v0.7.0 marine-demo.mp4 marine-demo.srt --clobber
gh release upload v0.8.0 space-demo.mp4 space-demo.srt --clobber
```

### 7.2 Embed in README

Add to `README.md` (Phase 11 finalises the README format):

```markdown
## Demos

### Marine - common-rail injector calibration
<!-- Embed via GitHub markdown video tag -->
[Watch marine demo (3:00)](https://github.com/goldr0g3r/tethys/releases/download/v0.7.0/marine-demo.mp4)

### Space - reaction-wheel torque calibration with fault injection
[Watch space demo (3:00)](https://github.com/goldr0g3r/tethys/releases/download/v0.8.0/space-demo.mp4)
```

### 7.3 Add to docs site

Sphinx + GitHub Pages (Phase 11) - `docs/architecture/demos.rst`:

```rst
Demos
=====

.. raw:: html

   <video controls width="100%">
     <source src="../_static/marine-demo.mp4" type="video/mp4">
   </video>
```

### 7.4 YouTube upload (optional)

If the project owner wants broader reach:

- Channel: personal or project-dedicated.
- Title: "Tethys - <marine|space> demo - license-free XCP calibration".
- Description: link to repo + brief tech stack summary.
- Tags: `XCP`, `marine`, `space`, `ECSS`, `MISRA`, `STM32`, `calibration`.
- Visibility: Unlisted initially; switch to Public after Phase 11 launch.

### 7.5 Case study PDF

`docs/case-study.pdf` (Phase 11) embeds three stills + one screenshot per demo.
Export stills:

```bash
ffmpeg -i marine-demo.mp4 -vf "select=eq(n\,150)+eq(n\,1500)+eq(n\,4000)" -vsync vfr -q:v 2 marine-still-%d.jpg
```

```powershell
ffmpeg -i marine-demo.mp4 -vf "select=eq(n\,150)+eq(n\,1500)+eq(n\,4000)" -vsync vfr -q:v 2 marine-still-%d.jpg
```

## 8. Cross-references

- Parent plan section 9 (Phase 9 HIL demos source the recording).
- Parent plan section 11 (public deliverables - the demo videos + README
  embed).
- [Runbook: hil-bench-setup.md](hil-bench-setup.md) - the bench you record.
- [Runbook: release-process.md](release-process.md) §7-8 - attaching the
  videos to the release.
- [OBS Studio docs](https://obsproject.com/wiki/).
- [DaVinci Resolve free download](https://www.blackmagicdesign.com/products/davinciresolve/).
- [GitHub release uploads](https://cli.github.com/manual/gh_release_upload).
