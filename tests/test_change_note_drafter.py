import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from change_note_drafter import findings, llm_client, verifier

REC = {
    "sheet_number": "A-140", "title": "Floor Plan Level 2", "revision": "5",
    "previous_content_hash": "165b6cfdb862eeb0", "current_content_hash": "8f8f321636616b8a",
}


def test_generate_findings_is_deterministic_and_the_right_count():
    a = findings.generate_findings(300, seed=1)
    b = findings.generate_findings(300, seed=1)
    assert len(a) == 300
    assert [f.sheet_number for f in a] == [f.sheet_number for f in b]
    assert [f.current_content_hash for f in a] == [f.current_content_hash for f in b]


def test_finding_record_has_exactly_the_allowed_fields():
    f = findings.generate_findings(1, seed=1)[0]
    rec = findings.finding_record(f)
    assert set(rec) == {"sheet_number", "title", "revision",
                         "previous_content_hash", "current_content_hash"}


def test_accepted_real_example():
    cn = ("Sheet A-140 (Floor Plan Level 2) is revised to Rev 5 and must be reissued "
          "with the updated revision entry [cite:sheet_number][cite:title][cite:revision]. "
          "The content hash changed from 165b6cfdb862eeb0 to 8f8f321636616b8a, which "
          "indicates a substantive change to the sheet content since the prior issued "
          "revision [cite:previous_content_hash][cite:current_content_hash]. The revision "
          "entry for this sheet must be carried onto the transmittal so it reconciles "
          "with the sheet index before release [cite:sheet_number][cite:revision].")
    pt = "Confirm this sheet number appears on the transmittal at the stated revision. [cite:sheet_number][cite:revision]"
    v = verifier.verify_draft(0, cn, pt, REC)
    assert v.accepted


def test_uncited_sentence_is_rejected():
    v = verifier.verify_draft(0, "The content changed since the prior issue.", "ok [cite:revision]", REC)
    assert not v.accepted
    assert v.rejection_reason == "uncited"


def test_unknown_field_citation_is_rejected():
    v = verifier.verify_draft(0, "Sheet A-140 changed. [cite:supplier_code]", "ok [cite:revision]", REC)
    assert not v.accepted
    assert v.rejection_reason.startswith("unknown_field")


def test_speculative_phrase_is_rejected_even_with_a_valid_citation():
    sentence = "This sheet is usually filed under structural review. [cite:sheet_number]"
    v = verifier.verify_draft(0, sentence, "ok [cite:revision]", REC)
    assert not v.accepted
    assert "speculative_phrase" in v.rejection_reason


def test_wrong_revision_value_is_rejected():
    sentence = "Sheet A-140 is now at Revision 9. [cite:sheet_number][cite:revision]"
    v = verifier.verify_draft(0, sentence, "ok [cite:revision]", REC)
    assert not v.accepted
    assert v.rejection_reason == "ungrounded:wrong_value:revision:9"


def test_wrong_hash_value_is_rejected():
    sentence = "The current hash is deadbeefdeadbeef. [cite:current_content_hash]"
    v = verifier.verify_draft(0, sentence, "ok [cite:revision]", REC)
    assert not v.accepted
    assert "wrong_value:hash" in v.rejection_reason


def test_wrong_sheet_number_value_is_rejected():
    sentence = "Sheet B-999 changed content. [cite:sheet_number]"
    v = verifier.verify_draft(0, sentence, "ok [cite:revision]", REC)
    assert not v.accepted
    assert "wrong_value:sheet_number" in v.rejection_reason


def test_a_real_hash_belonging_to_a_different_field_does_not_false_trigger():
    # citing current_content_hash but stating the *previous* hash value is a
    # legitimate "before/after" sentence, not a hallucination: both values
    # are real values of this same finding.
    sentence = "The hash moved from 165b6cfdb862eeb0 to 8f8f321636616b8a. [cite:current_content_hash]"
    v = verifier.verify_draft(0, sentence, "ok [cite:revision]", REC)
    assert v.accepted


def test_draft_batch_parses_a_fenced_json_response(monkeypatch):
    fake_payload = [{"id": 0, "change_note": "x [cite:sheet_number]", "procedure_text": "y [cite:revision]"}]

    def fake_run(*args, **kwargs):
        return subprocess.CompletedProcess(
            args=args, returncode=0, stdout="```json\n" + json.dumps(fake_payload) + "\n```", stderr="",
        )

    monkeypatch.setattr(subprocess, "run", fake_run)
    result = llm_client.draft_batch([{"id": 0, "fields": REC}])
    assert result == fake_payload


def test_draft_batch_raises_on_nonzero_exit(monkeypatch):
    def fake_run(*args, **kwargs):
        return subprocess.CompletedProcess(args=args, returncode=1, stdout="", stderr="boom")

    monkeypatch.setattr(subprocess, "run", fake_run)
    try:
        llm_client.draft_batch([{"id": 0, "fields": REC}])
        assert False, "expected RuntimeError"
    except RuntimeError as e:
        assert "boom" in str(e)
