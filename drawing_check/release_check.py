"""The release gate: sheet-by-sheet comparison against the last issued
revision, plus a transmittal-versus-sheet-index consistency check. Both are
independent reasons a set is refused.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .sheet_pdf import ParsedSheet


@dataclass(frozen=True)
class RevisionDefect:
    sheet_number: str
    title: str
    previous_content_hash: str
    current_content_hash: str
    revision: int

    def describe(self) -> str:
        return (
            f"sheet {self.sheet_number} ({self.title}): drawing content changed "
            f"but title block still reads REV {self.revision}, no new revision entry"
        )


@dataclass(frozen=True)
class ReleaseCheckResult:
    changed_without_revision: tuple = field(default_factory=tuple)
    transmittal_only: tuple = field(default_factory=tuple)  # on transmittal, not in the sheet index
    index_only: tuple = field(default_factory=tuple)  # in the sheet index, not on the transmittal

    @property
    def releasable(self) -> bool:
        return not self.changed_without_revision and not self.transmittal_only and not self.index_only

    def describe(self) -> str:
        if self.releasable:
            return "release allowed: every changed sheet carries a new revision entry, transmittal matches the sheet index"
        lines = [d.describe() for d in self.changed_without_revision]
        if self.transmittal_only:
            lines.append(f"transmittal lists sheets not in the sheet index: {sorted(self.transmittal_only)}")
        if self.index_only:
            lines.append(f"sheet index lists sheets not on the transmittal: {sorted(self.index_only)}")
        return "release refused: " + "; ".join(lines)


def check_revision_entries(previous: dict, current: dict) -> tuple:
    """Compares every sheet present in both `previous` and `current`
    (both `{sheet_number: ParsedSheet}`). A sheet whose `content_hash`
    changed but whose `revision` did not is a defect: real drawing content
    changed with no title-block revision entry to show for it. Sheets new
    to `current` and sheets dropped from `current` are out of scope for
    this check by design; see the README."""
    defects = []
    for sheet_number, current_sheet in current.items():
        previous_sheet = previous.get(sheet_number)
        if previous_sheet is None:
            continue
        content_changed = current_sheet.content_hash != previous_sheet.content_hash
        revision_bumped = current_sheet.revision != previous_sheet.revision
        if content_changed and not revision_bumped:
            defects.append(
                RevisionDefect(
                    sheet_number=sheet_number,
                    title=current_sheet.title,
                    previous_content_hash=previous_sheet.content_hash,
                    current_content_hash=current_sheet.content_hash,
                    revision=current_sheet.revision,
                )
            )
    return tuple(defects)


def check_transmittal_against_index(transmittal: set, sheet_index: set) -> tuple:
    """A real transmittal has to name exactly the sheets in the set's own
    index, no more and no fewer; either direction of disagreement refuses
    the release."""
    return tuple(sorted(transmittal - sheet_index)), tuple(sorted(sheet_index - transmittal))


def check_release(previous: dict, current: dict, transmittal: set, sheet_index: set) -> ReleaseCheckResult:
    defects = check_revision_entries(previous, current)
    transmittal_only, index_only = check_transmittal_against_index(transmittal, sheet_index)
    return ReleaseCheckResult(
        changed_without_revision=defects, transmittal_only=transmittal_only, index_only=index_only
    )
