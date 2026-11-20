"""
Citation-grounding verifier: checks a drafted change_note/procedure_text
pair against exactly the finding's own allowed field values, nothing
else. Four independent ways a sentence fails, decided before the 300-
item benchmark corpus was drafted (see README Findings for the first,
too-strict version of this check and why it was replaced):

  uncited          the sentence carries no [cite:FIELD] tag at all
  unknown_field    a [cite:FIELD] tag names a field not in this
                   finding's allowed set
  speculative      the sentence contains a hedging/generalizing phrase
                   this project's field dictionary has no way to back
  wrong_value      the sentence states a concrete sheet number,
                   revision number, or content hash that does not match
                   any of this finding's own field values (a real
                   hallucination, or batch cross-contamination from a
                   different finding in the same call)

A draft is rejected the moment any one of its sentences fails any rule;
"no record supported" is the single reason reported, matching the
claim's own wording. Grounding is checked by *pattern-matching concrete
values the sentence actually states*, not by requiring every sentence to
literally restate a field's value: a sentence may legitimately refer to
"this sheet" or "the stated revision" without re-quoting the value, and
the first version of this checker rejected exactly that legitimate
phrasing as a false positive (see README Findings).
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, List

CITE_RE = re.compile(r"\[cite:([a-zA-Z0-9_]+)\]")
HASH_RE = re.compile(r"\b[0-9a-f]{16}\b", re.IGNORECASE)
REVISION_RE = re.compile(r"\brev(?:ision)?\.?\s*#?\s*(\d+)\b", re.IGNORECASE)
SHEET_NUMBER_RE = re.compile(r"\b[A-Z]{1,2}-\d{2,4}\b")

# Hedging/generalizing language a drafted sentence has no field to back up;
# fixed from the two failure examples found while prompt-testing, before the
# final 300-item corpus was drafted against it (see README Findings).
SPECULATIVE_PHRASES = [
    "usually filed under", "often filed under", "is usually", "is often",
    "typically filed", "commonly filed", "generally filed", "tend to be filed",
    "as is customary", "common practice", "usually indicates", "often indicates",
    "likely filed", "probably filed",
]


@dataclass
class SentenceCheck:
    sentence: str
    ok: bool
    reason: str = ""


@dataclass
class DraftVerdict:
    draft_id: int
    accepted: bool
    sentence_checks: List[SentenceCheck] = field(default_factory=list)
    rejection_reason: str = ""


def split_sentences(text: str) -> List[str]:
    raw = re.split(r"(?<=[.!?])\s+(?=[A-Z]|$)", text.strip())
    return [s.strip() for s in raw if s.strip()]


def check_sentence(sentence: str, allowed_fields: Dict[str, str]) -> SentenceCheck:
    tags = CITE_RE.findall(sentence)
    if not tags:
        return SentenceCheck(sentence, False, "uncited")
    for field_name in tags:
        if field_name not in allowed_fields:
            return SentenceCheck(sentence, False, f"unknown_field:{field_name}")

    stripped = CITE_RE.sub("", sentence)
    lowered = stripped.lower()

    for phrase in SPECULATIVE_PHRASES:
        if phrase in lowered:
            return SentenceCheck(sentence, False, f"ungrounded:speculative_phrase:{phrase!r}")

    real_hashes = {
        str(allowed_fields[f]).lower()
        for f in ("previous_content_hash", "current_content_hash")
        if f in allowed_fields
    }
    for token in HASH_RE.findall(lowered):
        if token.lower() not in real_hashes:
            return SentenceCheck(sentence, False, f"ungrounded:wrong_value:hash:{token}")

    if "revision" in allowed_fields:
        real_revision = str(allowed_fields["revision"])
        for stated in REVISION_RE.findall(stripped):
            if stated != real_revision:
                return SentenceCheck(sentence, False, f"ungrounded:wrong_value:revision:{stated}")

    if "sheet_number" in allowed_fields:
        real_sheet = str(allowed_fields["sheet_number"]).upper()
        for stated in SHEET_NUMBER_RE.findall(stripped.upper()):
            if stated != real_sheet:
                return SentenceCheck(sentence, False, f"ungrounded:wrong_value:sheet_number:{stated}")

    return SentenceCheck(sentence, True)


def verify_draft(draft_id: int, change_note: str, procedure_text: str,
                  allowed_fields: Dict[str, str]) -> DraftVerdict:
    checks = []
    for text in (change_note, procedure_text):
        for sentence in split_sentences(text):
            checks.append(check_sentence(sentence, allowed_fields))
    bad = [c for c in checks if not c.ok]
    if bad:
        return DraftVerdict(draft_id, False, checks, rejection_reason=bad[0].reason)
    return DraftVerdict(draft_id, True, checks)
