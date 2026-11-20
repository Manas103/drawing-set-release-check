"""OCR + regular-expression baseline: reads an FCF crop with EasyOCR (a
real, pretrained scene-text OCR engine, not a stub), concatenates the
recognized text left to right, and regex-extracts a type code, a
tolerance value and datum letters from it. No document understanding, no
fine-tuning; whatever EasyOCR reads is what the regex gets."""

from __future__ import annotations

import re

_TYPE_PATTERN = re.compile(r"\b(POS|FLT|PERP|PAR|CONC|PROF)\b", re.IGNORECASE)
# the diameter-modifier prefix is deliberately [ØO] only, not "0": a
# leading "0" is indistinguishable from the value's own leading zero
# (every tolerance in this dataset is under 1.0, so "0.05" always starts
# with "0"), and treating it as a modifier would false-positive on every
# single value. Only a stray capital O or the real Ø glyph is unambiguous.
_VALUE_PATTERN = re.compile(r"(?:[ØO]\s*)?(\d+\.\d+)")
_DATUM_PATTERN = re.compile(r"\b([A-D])\b")


def extract_fields_from_text(raw_text: str) -> dict:
    """Returns a (type_code, value, datums, diametral) best-effort guess
    from already-recognized text, or None for a field the regex could not
    find. Unlike grammar.parse_fcf_string, this never raises and never
    enforces the cross-field rules; it is the un-gated baseline. Split out
    from OcrRegexBaseline so the regex logic is unit-testable without
    loading an OCR model."""
    type_match = _TYPE_PATTERN.search(raw_text)
    value_match = _VALUE_PATTERN.search(raw_text)
    datum_matches = _DATUM_PATTERN.findall(raw_text)

    type_code = type_match.group(1).upper() if type_match else None
    value = float(value_match.group(1)) if value_match else None
    # the real "⌀" glyph is frequently misread by OCR as a stray O or Ø
    # immediately before the number; _VALUE_PATTERN's own optional group
    # already swallows that character into the match, so the check is
    # against the full match text, not whatever precedes it.
    diametral = bool(value_match and re.match(r"[ØO]", value_match.group(0)))
    datums = tuple(sorted(set(datum_matches)))
    return {
        "raw_text": raw_text,
        "type_code": type_code,
        "value": value,
        "datums": datums,
        "diametral": diametral,
    }


class OcrRegexBaseline:
    def __init__(self, gpu: bool = False):
        import easyocr

        self.reader = easyocr.Reader(["en"], gpu=gpu, verbose=False)

    def read_crop(self, image_path: str) -> str:
        results = self.reader.readtext(image_path, detail=1)
        # sort left to right, the same order the FCF's own cells are drawn in
        results.sort(key=lambda r: r[0][0][0])
        return " ".join(text for _, text, _ in results)

    def extract(self, image_path: str) -> dict:
        return extract_fields_from_text(self.read_crop(image_path))
