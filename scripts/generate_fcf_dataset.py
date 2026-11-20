"""Generates the synthetic sheet-image dataset: full-page images + YOLO
detection labels + cropped FCF images + their structured targets.

    python generate_dataset.py --n-train 2100 --n-val 450 --n-test 450
"""

import argparse
import json
import os

from PIL import Image

from fcf_extraction.fcf_image import PAGE_SIZE, render_sheet_image

CROP_MARGIN = 6


def generate_split(out_dir, split_name, start_seed, n_sheets):
    img_dir = os.path.join(out_dir, "images", split_name)
    label_dir = os.path.join(out_dir, "yolo_labels", split_name)
    crop_dir = os.path.join(out_dir, "fcf_crops", split_name)
    for d in (img_dir, label_dir, crop_dir):
        os.makedirs(d, exist_ok=True)

    targets = {}
    w, h = PAGE_SIZE
    for i in range(n_sheets):
        seed = start_seed + i
        img, ground_truth = render_sheet_image(seed=seed)
        sheet_id = f"{split_name}_{seed:06d}"
        img.save(os.path.join(img_dir, sheet_id + ".png"))

        yolo_lines = []
        for idx, fcf in enumerate(ground_truth):
            x0, y0, x1, y1 = fcf.bbox
            xc, yc = (x0 + x1) / 2 / w, (y0 + y1) / 2 / h
            bw, bh = (x1 - x0) / w, (y1 - y0) / h
            yolo_lines.append(f"0 {xc:.6f} {yc:.6f} {bw:.6f} {bh:.6f}")

            cx0, cy0 = max(0, x0 - CROP_MARGIN), max(0, y0 - CROP_MARGIN)
            cx1, cy1 = min(w, x1 + CROP_MARGIN), min(h, y1 + CROP_MARGIN)
            crop = img.crop((cx0, cy0, cx1, cy1))
            crop_id = f"{sheet_id}_{idx}"
            crop.save(os.path.join(crop_dir, crop_id + ".png"))
            targets[crop_id] = {
                "sheet_id": sheet_id,
                "type": fcf.fcf_type,
                "value": fcf.value,
                "datums": list(fcf.datums),
                "diametral": fcf.diametral,
                "grammar_string": fcf.grammar_string(),
                "bbox_in_sheet": list(fcf.bbox),
            }

        with open(os.path.join(label_dir, sheet_id + ".txt"), "w") as fh:
            fh.write("\n".join(yolo_lines))

    with open(os.path.join(out_dir, f"fcf_targets_{split_name}.json"), "w") as fh:
        json.dump(targets, fh)
    print(f"{split_name}: {n_sheets} sheets, {len(targets)} FCFs")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out-dir", default=os.path.join(os.path.dirname(__file__), "..", "data"))
    parser.add_argument("--n-train", type=int, default=2100)
    parser.add_argument("--n-val", type=int, default=450)
    parser.add_argument("--n-test", type=int, default=450)
    args = parser.parse_args()

    generate_split(args.out_dir, "train", start_seed=0, n_sheets=args.n_train)
    generate_split(args.out_dir, "val", start_seed=1_000_000, n_sheets=args.n_val)
    generate_split(args.out_dir, "test", start_seed=2_000_000, n_sheets=args.n_test)

    yolo_yaml = f"""path: {os.path.abspath(args.out_dir)}
train: images/train
val: images/val
test: images/test
names:
  0: fcf
"""
    with open(os.path.join(args.out_dir, "yolo_dataset.yaml"), "w") as fh:
        fh.write(yolo_yaml)


if __name__ == "__main__":
    main()
