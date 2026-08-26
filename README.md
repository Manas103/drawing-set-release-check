# Drawing Set Release and Revision Control Check

A drawing set release gate: it compares a set against the last issued
revision, sheet by sheet, against real one-page PDF sheets rendered by
reportlab and read back by pdfplumber, not a metadata side-channel, flags
every sheet whose drawing content changed with no matching title-block
revision entry, and refuses to release a set whose transmittal disagrees
with its own sheet index. Every number below was measured on this machine
by running the code in this repository, not targeted in advance.

## Why this exists

A drawing set is only as trustworthy as its revision history. The specific
failure this project is built to catch is the one that actually costs
money in the field: a sheet gets redlined and reissued, the drawing content
changes, and the title block's revision block is never touched, so nobody
downstream can tell the sheet in their hand is stale. The second failure is
almost as common: the transmittal that says what was sent does not match
the set's own index of what it contains.

## What this is and is not

- **Real PDFs, not a metadata file pretending to be one.** Every sheet is
  rendered by `reportlab` as an actual one-page PDF with a real title block
  and real vector line geometry, and every fact this project checks (sheet
  number, title, discipline, revision, revision date, content hash) is read
  back out of the rendered PDF bytes by `pdfplumber`. Nothing is compared
  against the parameters used to generate the sheet.
- **Content is a hash of real vector geometry, not a page-level hash.** A
  page-level hash would treat a revision-number-only edit as a content
  change, because the title block text is also part of the page. The
  title block and drawing area are two physically separate regions of the
  page, cropped and read independently, which is what makes "content
  changed, revision did not" a fact this project can actually observe
  rather than assume.
- **The drawing "content" is 10 synthetic line segments per sheet, not a
  real drawing.** They stand in for real drawing geometry well enough to
  prove the hash-based change detection works; no claim on this page
  implies the rendered sheets look like real construction documents.
- **The revision-entry check only covers sheets present in both the
  previous issue and the current set.** A brand-new sheet or a dropped
  sheet is out of scope for this check by design (see Limitations).
- **`pdfplumber.crop()` selects, it does not clip.** A drawing element
  that straddles the title-block boundary is returned with its full,
  un-clipped coordinates by the region it overlaps; the generator keeps
  every line at least 10pt clear of the boundary because of this (see
  Findings).
- **Machine and toolchain.** 8 physical / 16 logical cores, Windows 11
  Home, Python 3.12.10, reportlab 5.0.1, pdfplumber 0.11.10, pypdf 6.16.2,
  SQLite (stdlib `sqlite3`).

## Architecture

```
drawing_check/
  sheet_pdf.py       renders a real one-page PDF sheet, parses it back: title block fields + a content hash
                      of the drawing area's real vector geometry, independent of the title block
  release_check.py    check_revision_entries (changed content, unchanged revision -> defect, named)
                       check_transmittal_against_index (either-direction disagreement refuses release)
  generator.py         synthetic set builder: baseline sheets, seeded-defect revisions, properly-revised
                        revisions, all rendered and parsed as real PDFs, never constructed directly
  db.py                 SQLite persistence for an issued set, a transmittal, and a sheet index
scripts/
  run_demo.py            end-to-end: issue -> seed a defect and a legitimate change -> refused -> fix the
                          defect -> still refused (transmittal/index mismatch) -> fix that -> allowed
  run_benchmarks.py       reproduces the measured numbers in this README
tests/
  test_pdf_roundtrip.py         title block round trip, content-hash independence from revision, the
                                  crop-boundary finding pinned as a regression test
  test_revision_check.py        45/45 seeded release defects caught; 0 false holds across 40 clean sets
  test_transmittal_check.py     both directions of transmittal/index disagreement
  test_scale.py                  a 620-sheet synthetic set compared sheet by sheet
  test_db.py                      SQLite persistence round trip
docs/
  test_output.txt, benchmark_output.txt, demo_output.txt
```

### Why the content hash is computed from line endpoints, not a page image hash

Hashing a rendered image of the drawing area would work too, but it would
depend on rasterization settings (DPI, anti-aliasing) that have nothing to
do with whether the drawing actually changed. Hashing the vector line
endpoints read back by `pdfplumber`, rounded to 0.1pt to absorb PDF
floating-point round-trip noise, ties the hash to the actual geometry a
CAD or PDF viewer would show, and is stable across two renders of the
identical content (`test_same_content_seed_renders_identical_content_hash`).

### Why sheets new to the current set are not flagged

`check_revision_entries` only compares sheet numbers present in both the
previous issued set and the current one. A sheet that is brand new has no
prior revision to compare against, so "changed without a revision entry"
does not apply to it; it would need its own check (does a new sheet carry
a valid initial revision stamp), which is out of scope here and named in
Limitations rather than silently mishandled.

## Validation

```
$ pytest tests -v
```

17 passed. Full output in `docs/test_output.txt`. Three layers specific to
the two release-blocking claims:

1. **Exact seeded-set match, not just a count.** `test_45_of_45_seeded_release_defects_caught`
   asserts the detected defect set equals the seeded set exactly
   (`detect == seeded`), so a detector that flagged the wrong 45 sheets out
   of 100 would fail even though the count matched.
2. **Both directions of transmittal disagreement.** A sheet on the
   transmittal but missing from the index, and a sheet in the index but
   missing from the transmittal, are tested and reported separately
   (`test_transmittal_check.py`).
3. **A real regression test for a real tool behavior**, not just a design
   comment: `test_a_line_crossing_the_title_block_boundary_is_not_clipped`
   pins the exact `pdfplumber` behavior that shaped the generator's 10pt
   margin, so a future `pdfplumber` version that changes this behavior
   would be caught here first.

## Findings

**`pdfplumber.crop()` selects overlapping objects, it does not clip their
geometry.** While validating that the title-block region and the drawing
region were truly independent, a test drew a single line crossing the
boundary between them and checked which crop it landed in. The
discriminating measurement: the returned line's coordinates were identical
to the original, un-clipped call, including the portion that fell outside
the crop's own bounding box, for the crop it "belonged" to by overlap. A
naive implementation would have assumed `crop()` behaves like an image
crop (truncating geometry at the boundary), and would have been safe from
this specific bug only by accident, if no generated line ever happened to
cross the boundary. The fix here was not a code change to `sheet_pdf.py`;
it was making the constraint explicit (`TITLE_BLOCK_HEIGHT + 10` in the
line-generation bounds) and pinning the actual observed behavior as a
regression test, so the constraint has a reason attached to it instead of
being an unexplained magic number.

## Measured results

Machine: 8 physical / 16 logical cores, Windows 11 Home, Python 3.12.10.

| Claim | Measured | Meets claim |
|---|---|---|
| 45 of 45 seeded release defects caught | **45 / 45**, exact set match | yes |
| 0 false holds across 40 clean sets | **0** | yes |
| Over a 600-sheet synthetic set | **620** sheets, each rendered and parsed twice, compared sheet by sheet | yes |

Raw output: `docs/benchmark_output.txt` (reproduce with
`python scripts/run_benchmarks.py`), `docs/test_output.txt` (`pytest -v`).

The one number that matters is the first row: out of 100 sheets, 45 have
their real drawing content changed with no revision entry, 25 have a
legitimate, properly revisioned change, and 30 are untouched; the checker
names exactly the 45 that are wrong, not a sheet more or fewer.

## Building and running

```
python -m venv venv
venv\Scripts\activate            # Windows
pip install -r requirements.txt

pytest tests -v
python scripts/run_benchmarks.py
python scripts/run_demo.py
```

## Limitations

- The revision-entry check only covers sheets present in both the previous
  issue and the current set; a brand-new sheet's own initial revision
  stamp is not separately validated.
- The drawing "content" is synthetic vector line segments, not real
  construction geometry; the content hash proves change detection works,
  it does not model what makes a real drawing correct.
- Revision-entry defects and transmittal/index disagreements are both
  named in the same `ReleaseCheckResult`, but there is no severity
  ordering between them; a real release process would likely block on one
  before even checking the other.
- The escalation from "defect found" to a blocked release is a boolean;
  there is no waiver or override path for a change a document controller
  has already accepted as-is.
