# GUI

> **Audience:** engineer using `tethys-master gui` (the PySide6 desktop
> application) for calibration / measurement work.
> **Scope:** the seven panes that make up the Phase 6 UI, keyboard
> navigation, headless CI smoke.
> **Length budget:** 2 pages.
>
> Implementation: [`master/src/tethys_master/gui/`](../src/tethys_master/gui/).

## 1. Launching the GUI

```bash
uv pip install 'tethys-master[gui]'
tethys-master gui
```

For headless / CI runs (Qt's offscreen platform plugin):

```bash
QT_QPA_PLATFORM=offscreen tethys-master gui
```

The CI workflows
([`.github/workflows/ci.yml`](../../.github/workflows/ci.yml)) set this
automatically on every OS.

## 2. Panes (parent plan section 8 Phase 6 acceptance)

| # | Pane | Source file | Role |
| --- | --- | --- | --- |
| 1 | Connection wizard | [`gui/connection_wizard.py`](../src/tethys_master/gui/connection_wizard.py) | Pick transport, target, profile; issue CONNECT. |
| 2 | A2L tree view | [`gui/a2l_tree.py`](../src/tethys_master/gui/a2l_tree.py) | Tree of MEASUREMENTs + CHARACTERISTICs loaded from an A2L file. |
| 3 | Real-time plot pane | [`gui/plot_pane.py`](../src/tethys_master/gui/plot_pane.py) | pyqtgraph multi-series plotter. |
| 4 | Calibration editor | [`gui/calibration_editor.py`](../src/tethys_master/gui/calibration_editor.py) | Edit CHARACTERISTIC values; A2L-driven limit checks. |
| 5 | Profile selector | [`gui/profile_selector.py`](../src/tethys_master/gui/profile_selector.py) | Marine / space radio group; drives invariants. |
| 6 | MDF4 record / playback | [`gui/mdf4_panel.py`](../src/tethys_master/gui/mdf4_panel.py) | Start / stop logging; open a recording. |
| 7 | Diagnostics | [`gui/diagnostics_pane.py`](../src/tethys_master/gui/diagnostics_pane.py) | Log feed, transport stats, MISRA / coverage badges. |

The orchestrator is [`gui/main_window.py`](../src/tethys_master/gui/main_window.py).

## 3. Keyboard navigation

Parent plan section 8 Phase 6 acceptance criterion is **keyboard-only
navigation passes**. Every interactive control has:

- An accelerator key (`&Marine` -> `Alt+M`, `&Connect` -> `Alt+C`).
- A `setAccessibleName(...)` string for screen readers.
- A logical tab order (`QWidget.setTabOrder(...)`).

Smoke test: [`master/tests/test_gui_keyboard_nav.py`](../tests/test_gui_keyboard_nav.py).

## 4. Profile-aware behaviour

The profile selector (pane 5) drives feature gates across the other
panes:

| Pane | Marine | Space |
| --- | --- | --- |
| Calibration editor | All CHARACTERISTICs writable. | Writable only after AES-128 service-mode unlock; CRC-checked. |
| MDF4 record | Full record always allowed. | Budgeted ring buffer (per `space-profile-invariants.mdc`). |
| Diagnostics | Shows MISRA mandatory + required status. | Adds advisory deviations + ECC counters + watchdog kick counter. |

Source: [`profiles.md`](profiles.md) (master-side) +
[`.cursor/rules/marine-profile-invariants.mdc`](../../.cursor/rules/marine-profile-invariants.mdc) /
[`.cursor/rules/space-profile-invariants.mdc`](../../.cursor/rules/space-profile-invariants.mdc).

## 5. Headless smoke test

`master/tests/test_gui_*.py` exercises every pane under
[`pytest-qt`](https://pytest-qt.readthedocs.io). The suite runs in CI
on Linux, Windows, and macOS via the Qt offscreen platform plugin (see
`gui/app.py::_ensure_offscreen_on_ci`).

Run locally:

```bash
cd master
QT_QPA_PLATFORM=offscreen uv run pytest tests/test_gui_*.py
```

## 6. Screenshots

Screenshots are deferred to Phase 11 (parent plan section 11). Until then,
the panes are documented by their accessibility tree + the structure
in this file.

## Cross-references

- [`api.md`](api.md).
- [`profiles.md`](profiles.md).
- Parent plan section 8 (Phase 6).
- [pyqtgraph docs](https://pyqtgraph.readthedocs.io/).
- [PySide6 docs](https://doc.qt.io/qtforpython-6/).
- [pytest-qt docs](https://pytest-qt.readthedocs.io).
