"""
A thin wrapper around the `claude` CLI's headless print mode: the real
LLM API available on this machine (see BUILDER.md). Each call drafts a
batch of findings at once (not one call per finding) purely so a
300-finding benchmark costs tens of calls, not hundreds; the model still
drafts every individual finding's text itself, nothing is templated or
filled in after the fact.
"""
from __future__ import annotations

import json
import subprocess

MODEL = "haiku"

SYSTEM_PROMPT = (
    "You draft engineering change notes and short procedure text for a drawing-set "
    "release gate, the way a document-control engineer would write them for a real "
    "release packet: professional and specific. For each finding you are given its "
    "exact allowed fields; write 2-3 sentences for change_note and 2-3 for "
    "procedure_text. Put one or more citation tags in the form [cite:FIELD] "
    "immediately after EACH individual sentence, not only at the end of the "
    "paragraph; every sentence needs its own tag(s) right after it. Reply with "
    "ONLY a JSON array, one object per finding in the same order, each object shaped "
    "exactly {\"id\": <id>, \"change_note\": \"...\", \"procedure_text\": \"...\"}. "
    "No prose before or after the JSON."
)


def draft_batch(items: list[dict], model: str = MODEL, timeout: int = 120) -> list[dict]:
    """`items` is a list of {"id": int, "fields": {...}}. Returns the
    parsed JSON array from the model, or raises on a non-JSON reply."""
    prompt = (
        "Draft a change_note and procedure_text for each of these findings. "
        "Allowed fields per finding are exactly the keys shown; cite only those.\n\n"
        + json.dumps(items, indent=1)
    )
    result = subprocess.run(
        ["claude", "-p", prompt, "--model", model, "--output-format", "text",
         "--append-system-prompt", SYSTEM_PROMPT],
        capture_output=True, text=True, timeout=timeout, encoding="utf-8",
    )
    if result.returncode != 0:
        raise RuntimeError(f"claude CLI failed (rc={result.returncode}): {result.stderr[:500]}")
    text = result.stdout.strip()
    # Models sometimes wrap JSON in a fenced code block despite instructions; strip it.
    if text.startswith("```"):
        text = text.strip("`")
        if text.startswith("json"):
            text = text[4:]
        text = text.strip()
    return json.loads(text)
