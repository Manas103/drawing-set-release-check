from drawing_check.sheet_pdf import SheetContent, parse_sheet_pdf, render_sheet_pdf


def _sheet(revision=0, content_seed=1, revision_date="2026-01-15"):
    return SheetContent("A-101", "Floor Plan Level 1", "architectural", revision, revision_date, content_seed)


def test_title_block_fields_round_trip_exactly():
    sheet = _sheet(revision=3, content_seed=7, revision_date="2026-02-20")
    parsed = parse_sheet_pdf(render_sheet_pdf(sheet))
    assert parsed.sheet_number == "A-101"
    assert parsed.title == "Floor Plan Level 1"
    assert parsed.discipline == "architectural"
    assert parsed.revision == 3
    assert parsed.revision_date == "2026-02-20"


def test_same_content_seed_renders_identical_content_hash():
    a = parse_sheet_pdf(render_sheet_pdf(_sheet(content_seed=42)))
    b = parse_sheet_pdf(render_sheet_pdf(_sheet(content_seed=42)))
    assert a.content_hash == b.content_hash


def test_different_content_seed_renders_different_content_hash():
    a = parse_sheet_pdf(render_sheet_pdf(_sheet(content_seed=42)))
    b = parse_sheet_pdf(render_sheet_pdf(_sheet(content_seed=43)))
    assert a.content_hash != b.content_hash


def test_revision_number_change_alone_does_not_change_content_hash():
    """The whole point of splitting the sheet into a title-block region and
    a drawing region: bumping the revision number must not, by itself,
    look like a content change."""
    a = parse_sheet_pdf(render_sheet_pdf(_sheet(revision=0, content_seed=42)))
    b = parse_sheet_pdf(render_sheet_pdf(_sheet(revision=5, content_seed=42)))
    assert a.content_hash == b.content_hash
    assert a.revision != b.revision


def test_a_line_crossing_the_title_block_boundary_is_not_clipped():
    """Documents a real pdfplumber behavior discovered during development
    (see README Findings): `.crop()` selects objects that overlap the
    bbox, it does not geometrically clip them. A line that starts in the
    drawing area and crosses into the title-block strip is returned with
    its full, un-clipped coordinates, including the part outside the crop.
    This is why `render_sheet_pdf` keeps every generated line at least
    10pt clear of the boundary (`TITLE_BLOCK_HEIGHT + 10`); a real drawing
    element straddling the boundary would destabilize the content hash by
    including title-block-side geometry as if it were drawing content.
    """
    import io

    from reportlab.lib.pagesizes import letter
    from reportlab.pdfgen import canvas

    from drawing_check.sheet_pdf import TITLE_BLOCK_HEIGHT

    width, height = letter
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=letter)
    # Straddles the boundary: 50pt into the title block, 50pt into the drawing area.
    c.line(50, TITLE_BLOCK_HEIGHT - 50, 50, TITLE_BLOCK_HEIGHT + 50)
    c.showPage()
    c.save()
    data = buf.getvalue()

    import pdfplumber

    with pdfplumber.open(io.BytesIO(data)) as pdf:
        page = pdf.pages[0]
        drawing_lines = page.crop((0, 0, width, height - TITLE_BLOCK_HEIGHT)).lines
        assert len(drawing_lines) == 1
        # The full, un-clipped line is returned, including the endpoint
        # that falls inside the title-block strip (y < TITLE_BLOCK_HEIGHT
        # in reportlab's bottom-up coordinates).
        line = drawing_lines[0]
        ys = sorted([line["y0"], line["y1"]])
        # y0/y1 are PDF-native (bottom-up, matching the reportlab call
        # above directly); the un-clipped line still spans across the
        # TITLE_BLOCK_HEIGHT boundary instead of being cut off at it.
        assert ys[0] < TITLE_BLOCK_HEIGHT < ys[1]


def test_missing_title_block_field_raises():
    import io

    from reportlab.lib.pagesizes import letter
    from reportlab.pdfgen import canvas

    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=letter)
    c.drawString(20, 80, "SHEET: A-101")  # no TITLE, DISC, REV, REV DATE
    c.showPage()
    c.save()

    import pytest

    with pytest.raises(ValueError, match="missing fields"):
        parse_sheet_pdf(buf.getvalue())
