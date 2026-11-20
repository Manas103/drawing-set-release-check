"""Field-level exact match: a prediction is correct only if its type,
value (to 2 decimals) and datum set all match the ground truth. A
tolerance with the right value and the wrong datum is wrong.

Every extraction method (the grammar-gated fine-tuned model, the OCR+regex
baseline, the zero-shot Donut baseline) is normalized to the same plain
dict shape before comparison, so the metric itself cannot favor one
method's internal representation over another's.
"""

from __future__ import annotations


def normalize(type_name, value, datums, diametral) -> dict:
    return {
        "type": type_name,
        "value": round(value, 2) if value is not None else None,
        "datums": frozenset(datums) if datums is not None else None,
        "diametral": diametral,
    }


def exact_match(predicted: dict | None, truth: dict) -> bool:
    if predicted is None or predicted["type"] is None:
        return False
    return (
        predicted["type"] == truth["type"]
        and predicted["value"] == round(truth["value"], 2)
        and predicted["datums"] == frozenset(truth["datums"])
        and predicted["diametral"] == truth["diametral"]
    )


def field_level_exact_match_rate(predictions: list, truths: list) -> float:
    assert len(predictions) == len(truths)
    if not predictions:
        return float("nan")
    return sum(exact_match(p, t) for p, t in zip(predictions, truths)) / len(predictions)
