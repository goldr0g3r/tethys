"""A2L parse → emit → parse round-trip verifier.

Invoked by the ``a2l-roundtrip.yml`` GitHub Actions workflow on every PR
that touches ``slave/tests/fixtures/**/*.a2l`` or
``master/src/tethys_master/protocol/a2l*``. Exits non-zero if the
re-serialised AST does not match the original.

Usage::

    python -m tethys_master.protocol.a2l_roundtrip <fixture.a2l>

Cite: parent plan §6.7 (a2l-roundtrip CI gate)
"""

from __future__ import annotations

import sys
from pathlib import Path

from tethys_master.protocol.a2l import A2LFile, to_a2l_string


def roundtrip(path: Path) -> int:
    """Round-trip an A2L file. Returns 0 on success, non-zero on drift."""
    original = A2LFile.load(path)
    emitted = to_a2l_string(original)
    re_parsed = A2LFile.loads(emitted)
    if original != re_parsed:
        sys.stderr.write(f"A2L round-trip drift detected for {path}\n")
        return 1
    sys.stdout.write(f"OK: {path}\n")
    return 0


def main(argv: list[str] | None = None) -> int:
    args = argv if argv is not None else sys.argv[1:]
    if len(args) != 1:
        sys.stderr.write("usage: python -m tethys_master.protocol.a2l_roundtrip <file.a2l>\n")
        return 2
    return roundtrip(Path(args[0]))


if __name__ == "__main__":
    raise SystemExit(main())
