"""
Draft a change note and procedure text for 300 synthetic release-gate
findings via the `claude` CLI (batched, `BATCH_SIZE` findings per call),
verify every sentence's citations against that finding's own fields, and
report how many of the 300 drafts were rejected for a statement no
record supported. Run:
    venv\\Scripts\\python.exe scripts\\run_change_note_benchmark.py
"""
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from change_note_drafter import findings, llm_client, verifier

N_FINDINGS = 300
BATCH_SIZE = 20
SEED = 20261119


def main():
    all_findings = findings.generate_findings(N_FINDINGS, seed=SEED)
    records = [findings.finding_record(f) for f in all_findings]

    drafts = {}
    t0 = time.time()
    n_batches = (N_FINDINGS + BATCH_SIZE - 1) // BATCH_SIZE
    for b in range(n_batches):
        lo, hi = b * BATCH_SIZE, min((b + 1) * BATCH_SIZE, N_FINDINGS)
        items = [{"id": i, "fields": records[i]} for i in range(lo, hi)]
        print(f"batch {b + 1}/{n_batches} (findings {lo}-{hi - 1})...", flush=True)
        result = llm_client.draft_batch(items)
        for r in result:
            drafts[r["id"]] = r
    elapsed = time.time() - t0

    verdicts = []
    for i in range(N_FINDINGS):
        d = drafts.get(i)
        if d is None:
            verdicts.append(verifier.DraftVerdict(i, False, [], rejection_reason="missing_from_llm_response"))
            continue
        v = verifier.verify_draft(i, d["change_note"], d["procedure_text"], records[i])
        verdicts.append(v)

    rejected = [v for v in verdicts if not v.accepted]
    reason_counts = {}
    for v in rejected:
        key = v.rejection_reason.split(":")[0]
        reason_counts[key] = reason_counts.get(key, 0) + 1

    summary = {
        "total_drafts": N_FINDINGS,
        "accepted": N_FINDINGS - len(rejected),
        "rejected": len(rejected),
        "rejection_reason_counts": reason_counts,
        "seconds": round(elapsed, 1),
        "batches": n_batches,
        "batch_size": BATCH_SIZE,
        "model": llm_client.MODEL,
    }
    print(json.dumps(summary, indent=2))

    Path("docs").mkdir(exist_ok=True)
    Path("docs/change_note_benchmark_output.json").write_text(json.dumps({
        "summary": summary,
        "rejected_ids": [v.draft_id for v in rejected],
        "rejected_examples": [
            {
                "id": v.draft_id,
                "reason": v.rejection_reason,
                "change_note": drafts.get(v.draft_id, {}).get("change_note"),
                "procedure_text": drafts.get(v.draft_id, {}).get("procedure_text"),
            }
            for v in rejected[:10]
        ],
    }, indent=2))
    Path("docs/change_note_benchmark_output.txt").write_text(
        f"{summary['accepted']}/{summary['total_drafts']} drafts accepted "
        f"({summary['rejected']}/{summary['total_drafts']} rejected for a statement "
        f"no record supported)\n"
        f"rejection reasons: {json.dumps(reason_counts)}\n"
        f"model: {summary['model']}, {summary['batches']} batches of up to "
        f"{summary['batch_size']}, {summary['seconds']}s total\n"
    )


if __name__ == "__main__":
    main()
