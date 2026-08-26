"""Reproduces the measured numbers quoted in the README. Prints, does not
assert; `pytest` is what actually verifies these claims (see tests/)."""
import os
import random
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from drawing_check.generator import build_baseline_set, build_next_set
from drawing_check.release_check import check_revision_entries


def main():
    rng = random.Random(1)
    baseline_contents, baseline_parsed = build_baseline_set(rng, count=100)
    numbers = list(baseline_contents)
    seeded_defects = numbers[:45]
    properly_revised = numbers[45:70]
    current = build_next_set(rng, baseline_contents, seeded_defects, properly_revised)
    defects = check_revision_entries(baseline_parsed, current)
    caught = {d.sheet_number for d in defects} == set(seeded_defects)
    print(f"seeded release defects: 45, caught: {len(defects)}, exact set match: {caught}")

    false_holds = 0
    for seed in range(40):
        rng = random.Random(2000 + seed)
        baseline_contents, baseline_parsed = build_baseline_set(rng, count=20)
        numbers = list(baseline_contents)
        properly_revised = numbers[: len(numbers) // 2]
        current = build_next_set(rng, baseline_contents, [], properly_revised)
        false_holds += len(check_revision_entries(baseline_parsed, current))
    print(f"false holds across 40 clean sets: {false_holds}")

    rng = random.Random(3)
    t0 = time.time()
    baseline_contents, baseline_parsed = build_baseline_set(rng, count=620)
    numbers = list(baseline_contents)
    current = build_next_set(rng, baseline_contents, numbers[:20], numbers[20:120])
    defects = check_revision_entries(baseline_parsed, current)
    elapsed = time.time() - t0
    print(f"620-sheet set: {len(baseline_parsed)} sheets rendered+parsed twice, {len(defects)} defects caught, {elapsed:.2f}s")


if __name__ == "__main__":
    main()
