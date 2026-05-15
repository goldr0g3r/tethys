"""atheris-based fuzz harness for Tethys's A2L parser facade.

Module:    tests.fuzz.a2l_parser
Profiles:  all (marine, space, dev bench)
Standards: ASAM MCD-2 MC v1.7 (A2L file format); DO-178C §6.4.4.1
           (robustness testing); ECSS-E-ST-40C Rev.1 §5.5 (verification).
Trace:     docs/traceability.csv rows TETHYS-REQ-VER-002 + TETHYS-DES-0011.

What it does
------------
atheris (Google's Python binding for libFuzzer) mutates random byte
sequences and calls ``TestOneInput(data)`` for each one. The harness
decodes the bytes as UTF-8 text (errors=replace) and feeds the string
into ``tethys_master.protocol.a2l.A2LFile.loads()``. The parser must:

1. Never raise anything other than :class:`A2LParseError` (a controlled
   ``ValueError`` subclass). Any other exception type is a finding.
2. Never crash the Python interpreter (atheris detects native-code
   crashes when the parser eventually swaps in Sauci/pya2l's C extension
   per ADR-0007).
3. Run in bounded time. The harness clamps input size to 64 KiB so a
   pathological input cannot block the fuzz loop indefinitely.

Run locally
-----------
.. code-block:: bash

    pip install atheris
    cd master
    PYTHONPATH=src python ../slave/fuzz/fuzz_a2l_parser.py \\
        ../slave/fuzz/corpus/a2l/ -atheris_runs=100000

The harness is a no-op when ``atheris`` is not importable (CI without
atheris installed prints a notice and exits 0). atheris is available on
Linux + macOS; Windows wheels are limited per
https://github.com/google/atheris (retrieved 2026-05-15).

Copyright (c) 2026 Tethys contributors. SPDX-License-Identifier: MIT.
"""

from __future__ import annotations

import sys

# Bounded input size so any single mutation runs in deterministic time.
_MAX_INPUT_BYTES = 64 * 1024  # 64 KiB


def _emit_skip_notice(reason: str) -> int:
    sys.stderr.write(
        f"fuzz_a2l_parser: skipping (no fuzz performed) - {reason}\n"
        f"  Install atheris (pip install atheris) and tethys-master to enable.\n"
    )
    return 0


def main() -> int:
    """Entrypoint. Wraps the atheris setup so the import failure is benign."""
    try:
        import atheris  # type: ignore[import-not-found]
    except ImportError:
        return _emit_skip_notice("atheris not importable")

    try:
        from tethys_master.protocol.a2l import (  # type: ignore[import-not-found]
            A2LFile,
            A2LParseError,
        )
    except ImportError as exc:
        return _emit_skip_notice(
            f"tethys_master.protocol.a2l not importable ({exc!s}); "
            f"ensure PYTHONPATH points at master/src or pip install -e master/"
        )

    def test_one_input(data: bytes) -> None:
        """Mutated input → A2L parser. Allowed exceptions: A2LParseError only."""
        if len(data) > _MAX_INPUT_BYTES:
            data = data[:_MAX_INPUT_BYTES]
        try:
            text = data.decode("utf-8", errors="replace")
        except (UnicodeDecodeError, ValueError):
            # Defensive: errors='replace' should never raise, but keep this
            # as belt-and-braces so the fuzz harness can't ever surface as
            # a "the harness crashed" finding.
            return
        try:
            A2LFile.loads(text)
        except A2LParseError:
            # Expected and controlled. Not a finding.
            return
        # Any other exception type propagates → atheris flags as a finding.

    atheris.Setup(sys.argv, test_one_input, enable_python_coverage=True)
    atheris.Fuzz()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
