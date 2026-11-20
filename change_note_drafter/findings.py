"""
Synthetic gate findings for the change-note drafter benchmark: real
`RevisionDefect` instances (the exact dataclass `drawing_check.
release_check.check_revision_entries` produces), built directly rather
than by running the PDF pipeline 300 times, because the drafter only
ever sees a finding's fields, never the PDF it came from.
"""
from __future__ import annotations

import hashlib
import random
from typing import List

from drawing_check.release_check import RevisionDefect

DISCIPLINES = ["Structural", "Mechanical", "Electrical", "Piping", "Architectural", "Civil"]
SHEET_SUBJECTS = [
    "Foundation Plan", "Roof Framing Plan", "HVAC Duct Layout", "Panel Schedule",
    "Piping Isometric", "Site Grading Plan", "Floor Plan Level 2", "Elevation View North",
    "Wall Section Detail", "Stair Section", "Conduit Routing Plan", "Equipment Layout",
    "Reflected Ceiling Plan", "Drainage Plan", "Structural Connection Detail",
]


def _hash(seed: str) -> str:
    return hashlib.sha256(seed.encode()).hexdigest()[:16]


def generate_findings(n: int, seed: int) -> List[RevisionDefect]:
    rng = random.Random(seed)
    findings = []
    for i in range(n):
        discipline = rng.choice(DISCIPLINES)
        subject = rng.choice(SHEET_SUBJECTS)
        sheet_number = f"{discipline[0]}-{100 + i:03d}"
        title = f"{subject}"
        revision = rng.randint(0, 6)
        previous_hash = _hash(f"prev-{i}-{seed}")
        current_hash = _hash(f"curr-{i}-{seed}")
        findings.append(RevisionDefect(
            sheet_number=sheet_number,
            title=title,
            previous_content_hash=previous_hash,
            current_content_hash=current_hash,
            revision=revision,
        ))
    return findings


def finding_record(defect: RevisionDefect) -> dict:
    """The exact, whitelisted fields a draft is allowed to cite for this
    finding; nothing else about the finding exists as far as the citation
    verifier is concerned."""
    return {
        "sheet_number": defect.sheet_number,
        "title": defect.title,
        "revision": str(defect.revision),
        "previous_content_hash": defect.previous_content_hash,
        "current_content_hash": defect.current_content_hash,
    }
