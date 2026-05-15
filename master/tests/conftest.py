"""Shared pytest fixtures and Qt env setup for the Tethys master test suite.

Setting ``QT_QPA_PLATFORM=offscreen`` before any ``PySide6`` import is
the recommended pattern for pytest-qt CI runs across Linux / Windows /
macOS (it removes the X server / display dependency entirely). We do it
unconditionally here so the GUI tests run identically on every OS in
the master matrix.

The actual ``PySide6`` import is performed by individual test modules
behind a :func:`pytest.importorskip` guard, so the headless tests
remain runnable in an environment where the optional ``[gui]`` extras
are not installed (e.g. local checkout without ``--all-extras``).
"""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
