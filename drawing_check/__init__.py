"""Drawing set release and revision control check.

Compares a drawing set against the last issued revision, sheet by sheet,
against real PDF sheets rendered by reportlab and parsed back by
pdfplumber, not a side-channel metadata file. Flags every sheet whose
drawing content changed without a matching title-block revision entry, and
refuses to release a set whose transmittal disagrees with its own sheet
index.
"""
