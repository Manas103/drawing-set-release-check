"""Synthetic drawing set generator. Every sheet is a real rendered and
parsed PDF (see `sheet_pdf.py`); nothing here fakes a `ParsedSheet` by
constructing it directly. Labeled synthetic throughout: no claim implies a
real 600-sheet issued set.
"""
from __future__ import annotations

import random

from .sheet_pdf import ParsedSheet, SheetContent, parse_sheet_pdf, render_sheet_pdf

_DISCIPLINE_PREFIXES = {"A": "architectural", "S": "structural", "M": "mep"}
_TITLES = [
    "Floor Plan",
    "Reflected Ceiling Plan",
    "Roof Plan",
    "Building Section",
    "Wall Section",
    "Foundation Plan",
    "Framing Plan",
    "Duct Layout",
    "Piping Layout",
    "Electrical Riser",
]


def sheet_numbers(count: int) -> list:
    """`count` sheet numbers spread evenly across architectural,
    structural and MEP prefixes, e.g. A-101, S-201, M-301, ..."""
    prefixes = list(_DISCIPLINE_PREFIXES)
    return [f"{prefixes[i % len(prefixes)]}-{100 * (i % len(prefixes) + 1) + i // len(prefixes)}" for i in range(count)]


def build_sheet_content(sheet_number: str, revision: int, revision_date: str, content_seed: int, rng: random.Random) -> SheetContent:
    discipline = _DISCIPLINE_PREFIXES[sheet_number[0]]
    title = rng.choice(_TITLES)
    return SheetContent(sheet_number, title, discipline, revision, revision_date, content_seed)


def render_and_parse(sheet: SheetContent) -> ParsedSheet:
    return parse_sheet_pdf(render_sheet_pdf(sheet))


def build_baseline_set(rng: random.Random, count: int, issued_date: str = "2026-01-15") -> tuple:
    """Builds `count` sheets at revision 0. Returns
    (sheet_contents: {sheet_number: SheetContent}, parsed: {sheet_number: ParsedSheet})."""
    contents = {}
    parsed = {}
    for i, number in enumerate(sheet_numbers(count)):
        content = build_sheet_content(number, revision=0, revision_date=issued_date, content_seed=i, rng=rng)
        contents[number] = content
        parsed[number] = render_and_parse(content)
    return contents, parsed


def revise_sheet(previous: SheetContent, bump_revision: bool, change_content: bool, new_date: str, seed_offset: int) -> SheetContent:
    return SheetContent(
        sheet_number=previous.sheet_number,
        title=previous.title,
        discipline=previous.discipline,
        revision=previous.revision + 1 if bump_revision else previous.revision,
        revision_date=new_date if bump_revision else previous.revision_date,
        content_seed=previous.content_seed + seed_offset if change_content else previous.content_seed,
    )


def build_next_set(
    rng: random.Random,
    baseline_contents: dict,
    seeded_defect_sheets: list,
    properly_revised_sheets: list,
    new_date: str = "2026-03-01",
) -> dict:
    """Builds the "current" set to check for release: `seeded_defect_sheets`
    get new drawing content with no revision bump (a real release defect);
    `properly_revised_sheets` get new content and a revision bump (a
    legitimate, correctly documented change); every other sheet is carried
    over unchanged. Returns {sheet_number: ParsedSheet}."""
    current = {}
    for number, content in baseline_contents.items():
        if number in seeded_defect_sheets:
            new_content = revise_sheet(content, bump_revision=False, change_content=True, new_date=new_date, seed_offset=10_000)
        elif number in properly_revised_sheets:
            new_content = revise_sheet(content, bump_revision=True, change_content=True, new_date=new_date, seed_offset=10_000)
        else:
            new_content = content
        current[number] = render_and_parse(new_content)
    return current
