# Phase 6 - Master GUI (research note)

> Research note backing the Phase 6 PRs (`p6`).
> Parent plan: [`xcp_extreme-env_tool_14019278.plan.md`](../../.cursor/plans/xcp_extreme-env_tool_14019278.plan.md) §8 Phase 6.
> Sub-plan (PR-A): [`p6-gui-scaffold-60efdc4c.plan.md`](../../../../Users/wnp1cob/.cursor/plans/p6-gui-scaffold-60efdc4c.plan.md)

## Scope

Phase 6 ships the PySide6 master GUI that the existing CLI + protocol +
transport stack docks into. The work is split across three PRs so each
review surface stays small:

| PR | Title | Surface | Status |
|---|---|---|---|
| PR-A | `feat(master): GUI scaffold - QMainWindow + connection wizard + smoke test` | `gui/app.py`, `gui/main_window.py`, `gui/connection_wizard.py`, CLI subcommand, pytest-qt smoke suite, CI wiring | this PR |
| PR-B | `feat(master): A2L tree + plot pane + diagnostics pane` | A2L tree view, pyqtgraph real-time plots, diagnostics pane | next |
| PR-C | `feat(master): calibration editor + MDF4 record/playback + profile selector` | calibration editor with A2L limit-check, MDF4 panel, profile selector, flip `p6` to completed | last |

PR-A establishes the design decisions (window structure, action /
shortcut policy, dependency packaging, headless CI strategy) the
subsequent PRs build on. This note is opened by PR-A and amended by
PR-B and PR-C as their "Implementation Reference" rows fill in.

## Sources (retrieved 2026-05-15)

| # | Source | URL | Retrieval date | Relevance |
|---|---|---|---|---|
| 1 | PySide6 6.8 documentation - `QMainWindow`, `QWizard`, `QAction` | <https://doc.qt.io/qtforpython-6/PySide6/QtWidgets/QMainWindow.html> | 2026-05-15 | Top-level window pattern; menu / toolbar / status bar construction |
| 2 | PySide6 6.8 documentation - `QWizard` + `QWizardPage` | <https://doc.qt.io/qtforpython-6/PySide6/QtWidgets/QWizard.html> | 2026-05-15 | 3-page connection wizard structure; `initializePage()` semantics |
| 3 | pytest-qt 4.4 documentation | <https://pytest-qt.readthedocs.io/en/4.4.0/> | 2026-05-15 | `qtbot.addWidget`, `qtbot.waitSignal`, `qtbot.waitExposed`; headless GUI test patterns |
| 4 | Qt `offscreen` QPA platform documentation | <https://doc.qt.io/qt-6/qpa.html> | 2026-05-15 | `QT_QPA_PLATFORM=offscreen` for CI without X server; supported on Linux / Windows / macOS |
| 5 | pyqtgraph 0.13.7 release notes | <https://github.com/pyqtgraph/pyqtgraph/releases/tag/pyqtgraph-0.13.7> | 2026-05-15 | Plot widget API stability; PySide6 6.8 compatibility |
| 6 | parent plan §3.1 + §8 Phase 6 | [`xcp_extreme-env_tool_14019278.plan.md`](../../.cursor/plans/xcp_extreme-env_tool_14019278.plan.md) | local | GUI deliverables + acceptance criterion |
| 7 | ADR-0007 - Python master, MATLAB consumer | [`docs/adr/0007-python-master-not-matlab.md`](../adr/0007-python-master-not-matlab.md) | local | Confirms PySide6 (LGPL) + pyqtgraph (MIT) as the GUI stack |
| 8 | ADR-0008 - License-free toolchain | [`docs/adr/0008-license-free-toolchain.md`](../adr/0008-license-free-toolchain.md) | local | LGPL/MIT acceptable; `dependency-review.yml` deny-list covers paid licences only |
| 9 | ADR-0010 - Packet-loss tolerance budget | [`docs/adr/0010-packet-loss-tolerance-budget.md`](../adr/0010-packet-loss-tolerance-budget.md) | local | Drives the diagnostics-pane DAQ_GAP semantics (PR-B) |
| 10 | `docs/learn/xcp-101.md` §13 (typical session) | [`docs/learn/xcp-101.md`](../learn/xcp-101.md) | local | The end-to-end flow the GUI exposes: CONNECT → A2L browse → DAQ setup → measure → calibrate → DISCONNECT |

## Decisions

| # | Decision | Choice | Rejected | Cite / Trace |
|---|---|---|---|---|
| D30 (PR-A) | GUI deps packaging | `[project.optional-dependencies] gui` group with `PySide6==6.8.0.2` + `pyqtgraph==0.13.7`; pulled in by `pip install 'tethys-master[gui]'` or `uv sync --all-extras` | Make PySide6 a runtime dep (forces every CLI / Python-API user to download ~150 MB they don't need) | ADR-0007; ADR-0008 |
| D31 (PR-A) | GUI CLI entry point | Two equivalent invocations: (a) `tethys-master gui` click subcommand that lazy-imports `gui.app:main`; (b) standalone `tethys-master-gui` `[project.scripts]` entry point. Both invoke the same function; `pyproject [project.scripts]` cannot expose a multi-word name so we ship both forms | Single entry point only (loses either ergonomic discoverability or PATH-binary convenience) | parent §8 Phase 6 |
| D32 (PR-A) | Headless test strategy | `QT_QPA_PLATFORM=offscreen` set in `master/tests/conftest.py` + the CI `env:` block; auto-detected on CI via `_ensure_offscreen_on_ci()` in `gui.app`; no `xvfb` required on Linux | `xvfb-run` only on Linux (works but adds a Linux-only step; the offscreen platform works on every OS in the matrix) | parent §8 Phase 6 acceptance; pytest-qt 4.4 README |
| D33 (PR-A) | Keyboard-only navigation policy | Every critical `QAction` (`action_connect`, `action_disconnect`, `action_start_daq`, `action_stop_daq`, `action_record`, `action_about`, `action_quit`) has a non-empty `QKeySequence`; menu / toolbar / shortcut all wired to the same `triggered` signal; `test_gui_keyboard_nav.py` parametrises a coverage assertion | Per-widget Tab-order overrides (Qt's automatic focus chain visits widgets in construction order which is already correct here) | parent §8 Phase 6 acceptance |
| D34 (PR-A) | Connection-wizard target shape | Emits a `dict` on `connect_requested` with one of three schemas: `{transport, host, port}` (UDP/TCP), `{transport, interface}` (CAN), `{transport, device, baud}` (UART). Keeps the wire-protocol layer (Worker B's transports) free to evolve its constructor signatures independently of the GUI | Pass a typed dataclass (couples GUI to transport classes; cyclic import risk) | ADR-0004 (transport abstraction layer) |
| D35 (PR-A) | Central-widget for PR-A | Placeholder `QTextEdit` with onboarding copy; replaced by PR-B's dock area holding A2L tree + plot pane + diagnostics pane | Empty `QWidget` (poor first-run UX); jump straight to PR-B layout (out of PR-A scope) | parent §8 Phase 6 |
| D36 (PR-A) | PySide6 + pyqtgraph + pytest-qt version pinning | `PySide6==6.8.0.2` (Oct 2024 LGPL release), `pyqtgraph==0.13.7` (Jul 2024 MIT), `pytest-qt==4.4.0` (Apr 2024 MIT). Each pinned exactly per `.cursor/rules/version-pinning.mdc`; Renovate proposes upgrades via PR | Use floating `>=` ranges (banned by the rule) | `version-pinning.mdc`; ADR-0008 |
| D37 (PR-A) | Windows-portable Quit shortcut | Bind `Ctrl+Q` explicitly instead of `QKeySequence.StandardKey.Quit` (Qt resolves the latter to an empty sequence on Windows where Alt+F4 is the OS-level close idiom). Keeps the keyboard-nav acceptance test green on every matrix leg | `QKeySequence.StandardKey.Quit` (passes on Linux/macOS, fails on Windows) | parent §8 Phase 6 acceptance |
| D38 (PR-B) | A2L tree view source | Wrap Worker A's `tethys_master.protocol.a2l.A2LFile` facade (landed PR #38); module-private `_StubA2LFile` (empty measurements / characteristics dicts) is the fallback when the facade is unimportable. Lazy import inside `_load_a2l` so the GUI keeps booting in degraded checkouts | Hard dependency on Worker A's PR landing first (creates artificial blocking) | parent §8 Phase 6; ASAM MCD-2 MC v1.7 §4.4.10 + §4.4.18 |
| D40 (PR-B) | Dock layout | `QMainWindow` with `PlotPane` central, `QDockWidget` for the A2L tree (left) and diagnostics pane (bottom); each dock's `toggleViewAction()` is wired into View menu (`Ctrl+Shift+A` / `Ctrl+Shift+D`) so keyboard-only navigation reaches every pane | Single resizable splitter (loses persisted layout state on dock close / show) | parent §8 Phase 6 acceptance |
| D41 (PR-B) | Plot rolling window | Default 60 s rolling window per trace; pyqtgraph `setDownsampling(auto=True, mode="peak")` + `setClipToView(True)` for cheap rendering at high sample counts | Unbounded retention (memory grows without bound for hour-long sessions) | parent §3.1; pyqtgraph 0.13.7 docs |
| D42 (PR-B) | DAQ_GAP marker style | Semi-transparent dashed vertical line (vermilion ARGB 204/102/0/90) per gap event; counts surfaced in plot status bar + status-bar `Gaps:` label + diagnostics-pane counter (all three stay in sync via `MainWindow.record_daq_gap()`) | Shaded region (visually heavier; hides the trace at the gap point) | ADR-0010 (packet-loss tolerance budget) |
| D43 (PR-B) | Diagnostics event log | Bounded FIFO with capacity 100 (`QListWidget` + `takeItem(0)` once over the limit); latency stats rendered as text (p50 / p99 / max) over a 1000-sample sliding window — full histogram deferred to a Phase 11 polish PR | Unbounded log (UI freezes in long sessions); histogram plot (extra widget for marginal value in PR-B) | docs/research/phase-0-system-requirements.md §4.2 + §7 |
| D44 (PR-B) | pyqtgraph mypy stance | `# type: ignore[import-untyped]` on the `pyqtgraph` import (the package doesn't ship `py.typed`). Tracked as a follow-up: contribute a `pyqtgraph-stubs` PEP-561 stubs package — out-of-scope for Phase 6 | Fork pyqtgraph to add stubs (huge maintenance burden); silence mypy globally (loses the rest of the strict-mode safety net) | parent §5 (toolchain); pyqtgraph 0.13.7 docs |
| D45 (PR-C) | Profile-selector UX | Radio-button group inside a `QGroupBox`; descriptive label updates per-profile to remind operators of the constraint differences (e.g. space = AES-128 service-mode unlock required before CAL writes). Live profile from slave is wired in a post-Phase-6 PR | Combo-box (collapses both options behind a click; loses at-a-glance reminder) | parent §3.3; ADR-0001; marine-profile-invariants.mdc + space-profile-invariants.mdc |
| D46 (PR-C) | Calibration editor row layout | `QAbstractTableModel` over A2L `CHARACTERISTIC` list, 6 columns (Name / Value / Units / Min / Max / Status). Edits go to a per-row `pending_value` slot; Commit emits a dict + promotes pending to current. Out-of-range pending edits paint the Value cell red and disable Commit | Live-write on every keystroke (drops the atomic-commit guarantee Phase 4 specifies); two separate widgets (loses inline limit feedback) | parent §8 Phase 4 + Phase 6; XCP 1.4 §1.3.4.1 DOWNLOAD + §1.5.1 BUILD_CHECKSUM |
| D47 (PR-C) | MDF4 file format | PR-C ships a self-describing binary stub format (`b"TETHYSMDF4STUB"` + version byte + repeating little-endian `<I H f f>` records) so the smoke tests stay hermetic on CI runners without asammdf wheels. asammdf is wired in the post-Phase-6 plumbing PR; the panel's public API (`start_recording` / `append_sample` / `stop_recording` / `load_playback`) is the swap point | Require asammdf at every test run (bloats CI install; pytest-qt smoke would skip on minimal checkouts) | parent §3.1; ASAM MDF v4 |
| D48 (PR-C) | Right-side dock tabification | Calibration + MDF4 + Profile share the right dock area, tabified via `tabifyDockWidget`. Calibration is raised by default. Each dock keeps its own `toggleViewAction` in View menu (Ctrl+Shift+C / M / I) so keyboard nav still reaches every one independently | Three separate visible docks (cramps the plot area to nothing on 1080p screens) | parent §8 Phase 6 acceptance |
| D49 (PR-C) | Parent-plan p6 flip | Set `p6.status = completed` in the parent-plan YAML frontmatter (this PR — the Phase 6 acceptance criterion holds: keyboard-only nav passes, all critical actions reachable, pytest-qt smoke runs headlessly in CI). README progress + traceability bookkeeping land in the closeout PR | Defer the flip until after the post-Phase-6 plumbing PR (delays the parent-plan signal that Phase 6 the *deliverable* is in) | parent §6.8 status-sync workflow |

## Implementation Reference

- **PR-A**: #39 (merged 2026-05-15) — GUI scaffold + connection wizard + headless smoke test
- **PR-B**: #42 (open at PR-C time) — A2L tree + plot pane + diagnostics pane
- **PR-C**: *to be filled at merge - calibration editor + MDF4 record/playback + profile selector + p6 → completed*

## Open follow-ups

- Tooltips + icon-set polish (deferred to a post-Phase-6 cleanup PR; the
  Phase 6 acceptance is functional, not visual).
- Translations / i18n: not in scope for v1.0; PySide6 supports `tr()` so
  enabling later is purely additive.
- PyInstaller packaging of the GUI binary is Phase 11 (parent §8).
- Worker-A coordination: when `master.protocol.a2l` lands on main, PR-B
  drops its stub fallback.
- Worker-B coordination: when transport implementations land, PR-B / PR-C
  swap the wizard's emitted-dict consumer to actually open the chosen
  transport via `XcpClient`.
