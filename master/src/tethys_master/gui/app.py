"""QApplication bootstrap + ``tethys-master gui`` entry point.

Lazy-imports PySide6 so the rest of :mod:`tethys_master` (CLI, protocol,
transport) can be used without the ~150 MB Qt install. Sets up the
``offscreen`` Qt platform on CI runners (detected via ``CI=true``) so
GUI tests run headlessly on every OS in the matrix without xvfb.

Cite: parent plan §3.1 (PySide6 GUI) + §8 Phase 6
Cite: ADR-0007 (Python master tool stack)
"""

from __future__ import annotations

import os
import sys
from typing import TYPE_CHECKING

from tethys_master.logging_setup import configure_logging, get_logger

if TYPE_CHECKING:
    from collections.abc import Sequence

_PYSIDE6_MISSING_HINT = (
    "PySide6 is not installed. The Tethys master GUI requires the optional\n"
    "[gui] extras. Install them with:\n"
    "    pip install 'tethys-master[gui]'\n"
    "    (or, in this repo: uv sync --all-extras)\n"
)

_EXIT_PYSIDE6_MISSING = 2

logger = get_logger(__name__)


def _ensure_offscreen_on_ci() -> None:
    """Default to the ``offscreen`` Qt platform on headless CI runners.

    GitHub Actions sets ``CI=true``; if the caller has not already chosen
    a platform plugin we pick ``offscreen`` so pytest-qt + the GUI smoke
    tests run on every OS in the master matrix without an X server. The
    same behaviour is convenient for any unattended automation.
    """
    if "QT_QPA_PLATFORM" not in os.environ and os.environ.get("CI"):
        os.environ["QT_QPA_PLATFORM"] = "offscreen"


def main(argv: Sequence[str] | None = None) -> int:
    """Launch the Tethys master GUI.

    Args:
        argv: argv passed to ``QApplication``. ``None`` means use
            ``sys.argv`` (the normal interactive case).

    Returns:
        The Qt event-loop exit code (0 on clean shutdown) or
        :data:`_EXIT_PYSIDE6_MISSING` when PySide6 is not installed.
    """
    _ensure_offscreen_on_ci()
    configure_logging("INFO", "plain")

    try:
        from PySide6.QtWidgets import QApplication
    except ImportError as exc:
        sys.stderr.write(_PYSIDE6_MISSING_HINT)
        sys.stderr.write(f"Underlying error: {exc}\n")
        return _EXIT_PYSIDE6_MISSING

    from tethys_master.gui.main_window import MainWindow

    args = list(argv) if argv is not None else list(sys.argv)
    app = QApplication.instance() or QApplication(args)
    # ``setApplicationName`` / ``setOrganizationName`` are static on
    # QCoreApplication; ``setApplicationDisplayName`` lives on
    # QGuiApplication. Calling them through the class (not the instance)
    # keeps mypy happy when the instance is typed as the base class.
    QApplication.setApplicationName("tethys-master")
    QApplication.setOrganizationName("Tethys")
    QApplication.setApplicationDisplayName("Tethys master")

    window = MainWindow()
    window.show()
    logger.info("gui.started", platform=os.environ.get("QT_QPA_PLATFORM", "default"))

    exit_code = int(app.exec())
    logger.info("gui.exited", exit_code=exit_code)
    return exit_code


def main_cli() -> int:
    """``[project.scripts]`` shim — no-arg wrapper around :func:`main`."""
    return main()


if __name__ == "__main__":  # pragma: no cover - exercised by the entry-point
    sys.exit(main())
