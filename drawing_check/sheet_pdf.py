"""Renders and parses real one-page PDF drawing sheets.

Each sheet has two physically separate regions, the way a real drawing
sheet does: a title block strip along the bottom (sheet number, title,
discipline, revision, revision date) and a drawing area above it. Both
regions are read back from the rendered PDF bytes with `pdfplumber`, not
from the parameters used to generate them, so a content change and a
title-block change are two independently observable facts, exactly as they
would be from a real drawing set with no metadata side-channel.
"""
from __future__ import annotations

import hashlib
import io
import random
from dataclasses import dataclass

from pdfplumber import open as pdfplumber_open
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

TITLE_BLOCK_HEIGHT = 100.0  # points, measured up from the bottom of the page


@dataclass(frozen=True)
class SheetContent:
    """One version of one sheet: what its title block says, and what its
    drawing content actually is. `content_seed` fully determines the
    drawing geometry; two `SheetContent` with the same seed render
    byte-identical drawing areas."""

    sheet_number: str
    title: str
    discipline: str
    revision: int
    revision_date: str
    content_seed: int


def render_sheet_pdf(sheet: SheetContent) -> bytes:
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=letter)
    width, height = letter
    rng = random.Random(sheet.content_seed)

    # Drawing area: everything above the title block strip. Line count and
    # endpoints are the only thing `content_seed` controls; this stands in
    # for a real drawing's geometry. Endpoints stay at least 10pt clear of
    # TITLE_BLOCK_HEIGHT on purpose: pdfplumber's `.crop()` selects objects
    # that overlap a bbox, it does not clip their geometry (see
    # tests/test_pdf_roundtrip.py::test_a_line_crossing_the_title_block_boundary_is_not_clipped),
    # so a line straddling the boundary would be read back with its full,
    # un-clipped coordinates and could destabilize the content hash.
    for _ in range(10):
        x1, y1 = rng.uniform(20, width - 20), rng.uniform(TITLE_BLOCK_HEIGHT + 10, height - 20)
        x2, y2 = rng.uniform(20, width - 20), rng.uniform(TITLE_BLOCK_HEIGHT + 10, height - 20)
        c.line(x1, y1, x2, y2)

    # Title block strip.
    c.rect(10, 10, width - 20, TITLE_BLOCK_HEIGHT - 10, stroke=1, fill=0)
    c.setFont("Helvetica", 10)
    c.drawString(20, 80, f"SHEET: {sheet.sheet_number}")
    c.drawString(20, 65, f"TITLE: {sheet.title}")
    c.drawString(20, 50, f"DISC: {sheet.discipline}")
    c.drawString(20, 35, f"REV: {sheet.revision}")
    c.drawString(20, 20, f"REV DATE: {sheet.revision_date}")

    c.showPage()
    c.save()
    return buf.getvalue()


@dataclass(frozen=True)
class ParsedSheet:
    """What was actually read back out of a rendered PDF. `content_hash`
    is a SHA-256 over the drawing area's real vector geometry (line
    endpoints, rounded to 0.1pt to absorb float round-trip noise), read
    from the PDF itself via `pdfplumber`, never from `SheetContent`."""

    sheet_number: str
    title: str
    discipline: str
    revision: int
    revision_date: str
    content_hash: str


def parse_sheet_pdf(pdf_bytes: bytes) -> ParsedSheet:
    with pdfplumber_open(io.BytesIO(pdf_bytes)) as pdf:
        page = pdf.pages[0]
        width, height = page.width, page.height

        title_block_text = page.crop((0, height - TITLE_BLOCK_HEIGHT, width, height)).extract_text() or ""
        fields = _parse_title_block(title_block_text)

        drawing_area = page.crop((0, 0, width, height - TITLE_BLOCK_HEIGHT))
        endpoints = sorted(
            (round(line["x0"], 1), round(line["y0"], 1), round(line["x1"], 1), round(line["y1"], 1))
            for line in drawing_area.lines
        )
        content_hash = hashlib.sha256(repr(endpoints).encode()).hexdigest()

    return ParsedSheet(
        sheet_number=fields["SHEET"],
        title=fields["TITLE"],
        discipline=fields["DISC"],
        revision=int(fields["REV"]),
        revision_date=fields["REV DATE"],
        content_hash=content_hash,
    )


def _parse_title_block(text: str) -> dict:
    fields: dict = {}
    for line in text.splitlines():
        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        fields[key.strip()] = value.strip()
    required = {"SHEET", "TITLE", "DISC", "REV", "REV DATE"}
    missing = required - fields.keys()
    if missing:
        raise ValueError(f"title block missing fields: {sorted(missing)}")
    return fields
