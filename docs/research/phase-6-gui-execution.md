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
| D38 (PR-B) | A2L tree view source | Wrap the `tethys_master.protocol.a2l.A2LFile` facade Worker A is shipping; on failure to import the real module use an in-test stub that returns a hand-crafted small A2L tree from `master/tests/fixtures/`. Documented in PR-B research-note row | Hard dependency on Worker A's PR landing first (artificial blocking) | (to be filled at PR-B) |
| D39 (PR-C) | Profile-selector source of truth | Read `tethys_profile.h` markers via the slave's `GET_VERSION` response; mirror to `tethys_master.config.MasterSettings.profile` for offline review | Compile-time only (loses runtime switching for marine ↔ space dev demos) | (to be filled at PR-C) |

## Implementation Reference

- **PR-A**: *to be filled at merge - GUI scaffold + connection wizard + headless smoke test*
- **PR-B**: *to be filled at merge - A2L tree + plot pane + diagnostics pane*
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
