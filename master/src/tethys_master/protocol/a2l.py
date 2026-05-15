"""Minimal A2L parser facade (ASAM MCD-2 MC v1.6 subset).

Tethys needs A2L parsing for two things in Phase 2:

1. The master GUI / CLI can look up a signal name in the A2L and resolve it
   to (address, datatype) tuples for SHORT_UPLOAD / DOWNLOAD calls.
2. The differential test against pyxcp (PR-31) uses the same A2L fixture
   on both sides to exercise the protocol against identical signal sets.

Scope choice (decision D19 in
``docs/research/phase-2-xcp-protocol-core-execution.md``):

- Sauci/pya2l (BSD-3) is the long-term parsing engine of choice per
  ADR-0007. However its current release is a 64 MB wheel that pulls in
  gRPC and grpcio-tools, which is a heavy dependency for Phase 2's needs
  (MEASUREMENT + CHARACTERISTIC lookup only).
- For Phase 2 we ship this **minimal hand-rolled reader** that parses the
  ~10 % of A2L grammar Tethys actually consumes today. It is correct for
  the subset, fast, dependency-free, and has no Windows/macOS gRPC
  install pain.
- A later phase (likely Phase 6 GUI when richer COMPU_METHOD / IF_DATA
  features are needed) will swap the engine for Sauci/pya2l behind the
  same :class:`A2LFile` facade. Tethys callers should depend on the
  facade, never on the parser internals.

Supported grammar (Phase 2):

.. code-block:: text

    /begin PROJECT name "long_identifier"
      /begin MODULE name "long_identifier"
        /begin MEASUREMENT
          name
          "long_identifier"
          datatype
          conversion
          resolution
          accuracy
          lower_limit
          upper_limit
          [ECU_ADDRESS hex_int]
        /end MEASUREMENT

        /begin CHARACTERISTIC
          name
          "long_identifier"
          type           ; one of VALUE | CURVE | MAP | ASCII | VAL_BLK
          address        ; hex int
          record_layout
          maxdiff
          conversion
          lower_limit
          upper_limit
        /end CHARACTERISTIC
      /end MODULE
    /end PROJECT

Unsupported (silently skipped):

- COMPU_METHOD, COMPU_VTAB, RECORD_LAYOUT, AXIS_DESCR, IF_DATA, ...
- Comments (``//`` and ``/* ... */`` are stripped before tokenising)

Cite: ASAM MCD-2 MC v1.6 §4.4.1 PROJECT
Cite: ASAM MCD-2 MC v1.6 §4.4.2 MODULE
Cite: ASAM MCD-2 MC v1.6 §4.4.18 MEASUREMENT
Cite: ASAM MCD-2 MC v1.6 §4.4.10 CHARACTERISTIC
Cite: ADR-0007 (Python master tool, MATLAB is consumer not driver)
Trace: docs/traceability.csv row TETHYS-DES-0011 (lands at PR-10)
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path


class A2LParseError(ValueError):
    """Raised when an A2L file cannot be parsed at the supported subset."""


class A2LDatatype(str, Enum):
    """A2L primitive datatypes (ASAM MCD-2 MC v1.6 §3.13.2 Table 2)."""

    UBYTE = "UBYTE"
    SBYTE = "SBYTE"
    UWORD = "UWORD"
    SWORD = "SWORD"
    ULONG = "ULONG"
    SLONG = "SLONG"
    A_UINT64 = "A_UINT64"
    A_INT64 = "A_INT64"
    FLOAT32_IEEE = "FLOAT32_IEEE"
    FLOAT64_IEEE = "FLOAT64_IEEE"


class CharacteristicType(str, Enum):
    """A2L CHARACTERISTIC sub-types (ASAM MCD-2 MC v1.6 §4.4.10)."""

    VALUE = "VALUE"
    CURVE = "CURVE"
    MAP = "MAP"
    ASCII = "ASCII"
    VAL_BLK = "VAL_BLK"


@dataclass(frozen=True, slots=True)
class Measurement:
    """A2L MEASUREMENT block.

    Field order matches the canonical positional layout the A2L grammar
    mandates (name, long_identifier, datatype, conversion, resolution,
    accuracy, lower_limit, upper_limit). ``address`` and
    ``address_extension`` come from the optional ECU_ADDRESS sub-block.
    """

    name: str
    long_identifier: str
    datatype: A2LDatatype
    conversion: str
    resolution: int
    accuracy: float
    lower_limit: float
    upper_limit: float
    address: int = 0
    address_extension: int = 0


@dataclass(frozen=True, slots=True)
class Characteristic:
    """A2L CHARACTERISTIC block."""

    name: str
    long_identifier: str
    characteristic_type: CharacteristicType
    address: int
    record_layout: str
    maxdiff: float
    conversion: str
    lower_limit: float
    upper_limit: float
    address_extension: int = 0


@dataclass(slots=True)
class A2LFile:
    """In-memory representation of the supported A2L subset.

    Use :py:meth:`load` to parse a file or :py:meth:`loads` to parse a
    string. Look up measurements and characteristics by name via the
    eponymous dicts.
    """

    project_name: str
    project_long_identifier: str
    module_name: str
    module_long_identifier: str
    measurements: dict[str, Measurement] = field(default_factory=dict)
    characteristics: dict[str, Characteristic] = field(default_factory=dict)

    @classmethod
    def load(cls, path: str | Path) -> A2LFile:
        """Read an A2L file from disk."""
        text = Path(path).read_text(encoding="utf-8", errors="replace")
        return cls.loads(text)

    @classmethod
    def loads(cls, text: str) -> A2LFile:
        """Parse an A2L string into an :class:`A2LFile` instance."""
        tokens = _tokenise(text)
        return _build_from_tokens(tokens)


# ---- Tokeniser -------------------------------------------------------


_COMMENT_BLOCK = re.compile(r"/\*.*?\*/", re.DOTALL)
_COMMENT_LINE = re.compile(r"//[^\n]*")
_TOKEN_PATTERN = re.compile(r'"(?:[^"\\]|\\.)*"|\S+')


def _tokenise(text: str) -> list[str]:
    """Split A2L text into bare tokens (whitespace-separated, quoted strings preserved)."""
    no_block_comments = _COMMENT_BLOCK.sub(" ", text)
    no_comments = _COMMENT_LINE.sub(" ", no_block_comments)
    return _TOKEN_PATTERN.findall(no_comments)


# ---- Block walker ----------------------------------------------------


def _unquote(token: str) -> str:
    if len(token) >= 2 and token[0] == '"' and token[-1] == '"':
        return token[1:-1].encode("utf-8").decode("unicode_escape")
    return token


def _parse_int(token: str) -> int:
    if token.lower().startswith("0x"):
        return int(token, 16)
    return int(token, 10)


def _parse_float(token: str) -> float:
    return float(token)


def _build_from_tokens(tokens: list[str]) -> A2LFile:
    project_name = ""
    project_long_identifier = ""
    module_name = ""
    module_long_identifier = ""
    measurements: dict[str, Measurement] = {}
    characteristics: dict[str, Characteristic] = {}

    i = 0
    n = len(tokens)
    while i < n:
        head = tokens[i]
        if head == "/begin" and i + 1 < n:
            block = tokens[i + 1]
            if block == "PROJECT":
                if i + 3 >= n:
                    msg = "PROJECT block too short"
                    raise A2LParseError(msg)
                project_name = tokens[i + 2]
                project_long_identifier = _unquote(tokens[i + 3])
                i += 4
                continue
            if block == "MODULE":
                if i + 3 >= n:
                    msg = "MODULE block too short"
                    raise A2LParseError(msg)
                module_name = tokens[i + 2]
                module_long_identifier = _unquote(tokens[i + 3])
                i += 4
                continue
            if block == "MEASUREMENT":
                measurement, advance = _parse_measurement(tokens, i + 2)
                measurements[measurement.name] = measurement
                i = advance
                continue
            if block == "CHARACTERISTIC":
                characteristic, advance = _parse_characteristic(tokens, i + 2)
                characteristics[characteristic.name] = characteristic
                i = advance
                continue
            # Unknown / unsupported block: skip to its matching /end <block>.
            i = _skip_block(tokens, i + 1, block)
            continue
        i += 1

    if not project_name:
        msg = "A2L file missing /begin PROJECT block"
        raise A2LParseError(msg)
    if not module_name:
        msg = "A2L file missing /begin MODULE block"
        raise A2LParseError(msg)
    return A2LFile(
        project_name=project_name,
        project_long_identifier=project_long_identifier,
        module_name=module_name,
        module_long_identifier=module_long_identifier,
        measurements=measurements,
        characteristics=characteristics,
    )


def _skip_block(tokens: list[str], start: int, block_name: str) -> int:
    depth = 1
    i = start + 1
    n = len(tokens)
    while i < n and depth > 0:
        if tokens[i] == "/begin" and i + 1 < n and tokens[i + 1] == block_name:
            depth += 1
            i += 2
            continue
        if tokens[i] == "/end" and i + 1 < n and tokens[i + 1] == block_name:
            depth -= 1
            i += 2
            continue
        i += 1
    return i


def _parse_measurement(tokens: list[str], start: int) -> tuple[Measurement, int]:
    """Parse the positional fields of a MEASUREMENT block, returning the next read index."""
    end_index = _find_end(tokens, start, "MEASUREMENT")
    body = tokens[start:end_index]
    if len(body) < 8:
        msg = f"MEASUREMENT block too short (got {len(body)} tokens, expected >=8)"
        raise A2LParseError(msg)
    name = body[0]
    long_identifier = _unquote(body[1])
    try:
        datatype = A2LDatatype(body[2])
    except ValueError as exc:
        msg = f"MEASUREMENT '{name}': unknown datatype '{body[2]}'"
        raise A2LParseError(msg) from exc
    conversion = body[3]
    resolution = _parse_int(body[4])
    accuracy = _parse_float(body[5])
    lower_limit = _parse_float(body[6])
    upper_limit = _parse_float(body[7])
    address = 0
    address_extension = 0
    j = 8
    while j < len(body):
        if body[j] == "ECU_ADDRESS" and j + 1 < len(body):
            address = _parse_int(body[j + 1])
            j += 2
            continue
        if body[j] == "ECU_ADDRESS_EXTENSION" and j + 1 < len(body):
            address_extension = _parse_int(body[j + 1])
            j += 2
            continue
        j += 1
    return (
        Measurement(
            name=name,
            long_identifier=long_identifier,
            datatype=datatype,
            conversion=conversion,
            resolution=resolution,
            accuracy=accuracy,
            lower_limit=lower_limit,
            upper_limit=upper_limit,
            address=address,
            address_extension=address_extension,
        ),
        end_index + 2,  # consume "/end MEASUREMENT"
    )


def _parse_characteristic(tokens: list[str], start: int) -> tuple[Characteristic, int]:
    end_index = _find_end(tokens, start, "CHARACTERISTIC")
    body = tokens[start:end_index]
    if len(body) < 9:
        msg = f"CHARACTERISTIC block too short (got {len(body)} tokens, expected >=9)"
        raise A2LParseError(msg)
    name = body[0]
    long_identifier = _unquote(body[1])
    try:
        char_type = CharacteristicType(body[2])
    except ValueError as exc:
        msg = f"CHARACTERISTIC '{name}': unknown type '{body[2]}'"
        raise A2LParseError(msg) from exc
    address = _parse_int(body[3])
    record_layout = body[4]
    maxdiff = _parse_float(body[5])
    conversion = body[6]
    lower_limit = _parse_float(body[7])
    upper_limit = _parse_float(body[8])
    address_extension = 0
    j = 9
    while j < len(body):
        if body[j] == "ECU_ADDRESS_EXTENSION" and j + 1 < len(body):
            address_extension = _parse_int(body[j + 1])
            j += 2
            continue
        j += 1
    return (
        Characteristic(
            name=name,
            long_identifier=long_identifier,
            characteristic_type=char_type,
            address=address,
            record_layout=record_layout,
            maxdiff=maxdiff,
            conversion=conversion,
            lower_limit=lower_limit,
            upper_limit=upper_limit,
            address_extension=address_extension,
        ),
        end_index + 2,  # consume "/end CHARACTERISTIC"
    )


def _find_end(tokens: list[str], start: int, block_name: str) -> int:
    """Return the index of the matching ``/end <block_name>`` token pair."""
    depth = 1
    i = start
    n = len(tokens)
    while i < n:
        if tokens[i] == "/begin" and i + 1 < n and tokens[i + 1] == block_name:
            depth += 1
            i += 2
            continue
        if tokens[i] == "/end" and i + 1 < n and tokens[i + 1] == block_name:
            depth -= 1
            if depth == 0:
                return i
            i += 2
            continue
        i += 1
    msg = f"Unterminated /begin {block_name} block"
    raise A2LParseError(msg)


# ---- Emitter ---------------------------------------------------------


def to_a2l_string(file: A2LFile) -> str:
    """Re-serialise an :class:`A2LFile` to A2L source.

    The output is canonical (sorted keys, fixed formatting) so a parse →
    emit → parse round-trip produces equal :class:`A2LFile` instances even
    when whitespace and comments in the input differ from this output.
    """
    lines: list[str] = []
    lines.append(f'/begin PROJECT {file.project_name} "{file.project_long_identifier}"')
    lines.append(f'  /begin MODULE {file.module_name} "{file.module_long_identifier}"')
    for name in sorted(file.measurements):
        m = file.measurements[name]
        lines.append("    /begin MEASUREMENT")
        lines.append(f"      {m.name}")
        lines.append(f'      "{m.long_identifier}"')
        lines.append(f"      {m.datatype.value}")
        lines.append(f"      {m.conversion}")
        lines.append(f"      {m.resolution}")
        lines.append(f"      {m.accuracy}")
        lines.append(f"      {m.lower_limit}")
        lines.append(f"      {m.upper_limit}")
        if m.address:
            lines.append(f"      ECU_ADDRESS 0x{m.address:X}")
        if m.address_extension:
            lines.append(f"      ECU_ADDRESS_EXTENSION {m.address_extension}")
        lines.append("    /end MEASUREMENT")
    for name in sorted(file.characteristics):
        c = file.characteristics[name]
        lines.append("    /begin CHARACTERISTIC")
        lines.append(f"      {c.name}")
        lines.append(f'      "{c.long_identifier}"')
        lines.append(f"      {c.characteristic_type.value}")
        lines.append(f"      0x{c.address:X}")
        lines.append(f"      {c.record_layout}")
        lines.append(f"      {c.maxdiff}")
        lines.append(f"      {c.conversion}")
        lines.append(f"      {c.lower_limit}")
        lines.append(f"      {c.upper_limit}")
        if c.address_extension:
            lines.append(f"      ECU_ADDRESS_EXTENSION {c.address_extension}")
        lines.append("    /end CHARACTERISTIC")
    lines.append("  /end MODULE")
    lines.append("/end PROJECT")
    lines.append("")
    return "\n".join(lines)
