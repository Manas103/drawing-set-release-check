"""An ASME Y14.5-shaped grammar gate for feature control frame text.

Not the real ASME Y14.5 standard (that grammar is far larger: material
condition modifiers, composite frames, projected tolerance zones, and
more). This is a small, genuinely enforced subset of its structure,
matching exactly what `fcf_image.py` renders: a type code, a tolerance
value with an optional diameter modifier, and zero or more datum letters,
with two real cross-field rules (flatness never has a datum; position and
concentricity always carry the diameter modifier) that a prediction can
violate independently of getting any single field "look right" in
isolation.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

VALID_TYPE_CODES = {"POS": "position", "FLT": "flatness", "PERP": "perpendicularity",
                     "PAR": "parallelism", "CONC": "concentricity", "PROF": "profile"}
DIAMETRAL_CODES = {"POS", "CONC"}
VALID_DATUM_LETTERS = set("ABCD")
_FIELD_RE = re.compile(r"^(?P<code>[A-Z]+)\|(?P<dia>⌀?)(?P<value>\d+\.\d+)\|(?P<datums>[A-Z]*)$")


@dataclass(frozen=True)
class FCFRecord:
    fcf_type: str
    value: float
    datums: tuple
    diametral: bool


class GrammarError(ValueError):
    pass


def parse_fcf_string(raw: str) -> FCFRecord:
    """Parses `raw` (the canonical "CODE|value|DATUMS" layout) into an
    FCFRecord, raising GrammarError for anything that does not fit the
    grammar OR violates one of its two cross-field rules. Nothing here
    ever returns a record for input it rejects."""
    m = _FIELD_RE.match(raw.strip())
    if not m:
        raise GrammarError(f"does not match the CODE|value|DATUMS layout: {raw!r}")

    code = m.group("code")
    if code not in VALID_TYPE_CODES:
        raise GrammarError(f"unknown type code: {code!r}")
    fcf_type = VALID_TYPE_CODES[code]

    diametral = bool(m.group("dia"))
    if diametral != (code in DIAMETRAL_CODES):
        raise GrammarError(
            f"{code} {'must' if code in DIAMETRAL_CODES else 'must not'} carry the diameter modifier"
        )

    value = float(m.group("value"))
    if not (0.0 < value < 10.0):
        raise GrammarError(f"tolerance value out of plausible range: {value}")

    datums = tuple(m.group("datums"))
    if len(set(datums)) != len(datums):
        raise GrammarError(f"duplicate datum letters: {datums}")
    if not all(d in VALID_DATUM_LETTERS for d in datums):
        raise GrammarError(f"datum letters outside the allowed set: {datums}")

    if fcf_type == "flatness" and datums:
        raise GrammarError("flatness is a form tolerance and must not carry a datum reference")
    if fcf_type != "flatness" and not (1 <= len(datums) <= 3):
        raise GrammarError(f"{fcf_type} must carry 1 to 3 datum references, got {len(datums)}")

    return FCFRecord(fcf_type=fcf_type, value=value, datums=datums, diametral=diametral)


def try_parse_fcf_string(raw: str):
    """Returns an FCFRecord, or None if `raw` fails the grammar gate."""
    try:
        return parse_fcf_string(raw)
    except GrammarError:
        return None
