"""Detector -> extractor -> grammar-gate end to end on the test split, for
all three extraction methods (fine-tuned Donut, zero-shot Donut, OCR+regex),
all three fed the SAME YOLO-detected crops so detector noise is shared
rather than favoring any one method. Also calibrates and applies the
abstention band for the fine-tuned model. Writes benchmark_report.json.

    python run_end_to_end_eval.py --limit 0
"""

import argparse
import json
import os
import time

from PIL import Image
from ultralytics import YOLO

from fcf_extraction.donut_infer import DonutExtractor
from fcf_extraction.evaluate import exact_match, field_level_exact_match_rate, normalize
from fcf_extraction.grammar import try_parse_fcf_string
from fcf_extraction.ocr_regex_baseline import OcrRegexBaseline, extract_fields_from_text

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
YOLO_WEIGHTS = os.path.join(os.path.dirname(__file__), "..", "runs", "fcf_detect", "weights", "best.pt")
FINETUNED_DONUT = os.path.join(os.path.dirname(__file__), "..", "models", "donut_finetuned")
CROP_MARGIN = 6


def iou(a, b):
    ax0, ay0, ax1, ay1 = a
    bx0, by0, bx1, by1 = b
    ix0, iy0 = max(ax0, bx0), max(ay0, by0)
    ix1, iy1 = min(ax1, bx1), min(ay1, by1)
    inter = max(0, ix1 - ix0) * max(0, iy1 - iy0)
    area_a = (ax1 - ax0) * (ay1 - ay0)
    area_b = (bx1 - bx0) * (by1 - by0)
    union = area_a + area_b - inter
    return inter / union if union > 0 else 0.0


def match_detections_to_truth(detections, truths, iou_threshold=0.5):
    """Greedy best-IoU matching; returns [(detection_box, truth_record)]."""
    pairs = []
    used_truth = set()
    for det_box in detections:
        best_iou, best_idx = 0.0, None
        for i, t in enumerate(truths):
            if i in used_truth:
                continue
            score = iou(det_box, tuple(t["bbox_in_sheet"]))
            if score > best_iou:
                best_iou, best_idx = score, i
        if best_idx is not None and best_iou >= iou_threshold:
            pairs.append((det_box, truths[best_idx]))
            used_truth.add(best_idx)
    return pairs


def crop_from_box(img, box, margin=CROP_MARGIN):
    x0, y0, x1, y1 = box
    w, h = img.size
    return img.crop((max(0, x0 - margin), max(0, y0 - margin), min(w, x1 + margin), min(h, y1 + margin)))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=0, help="0 means use every test sheet")
    parser.add_argument("--out", default=os.path.join(os.path.dirname(__file__), "benchmark_report.json"))
    args = parser.parse_args()

    yolo = YOLO(YOLO_WEIGHTS)
    donut_ft = DonutExtractor(FINETUNED_DONUT, task_token="<fcf>")
    donut_zs = DonutExtractor("naver-clova-ix/donut-base", task_token="<s_synthdog>")
    ocr = OcrRegexBaseline(gpu=True)

    targets = json.load(open(os.path.join(DATA_DIR, "fcf_targets_test.json")))
    by_sheet = {}
    for crop_id, t in targets.items():
        by_sheet.setdefault(t["sheet_id"], []).append(t)
    sheet_ids = sorted(by_sheet)
    if args.limit:
        sheet_ids = sheet_ids[: args.limit]

    truths, ft_preds, ft_confs, zs_preds, ocr_preds = [], [], [], [], []
    t0 = time.time()
    for n, sheet_id in enumerate(sheet_ids):
        img_path = os.path.join(DATA_DIR, "images", "test", sheet_id + ".png")
        img = Image.open(img_path).convert("RGB")
        results = yolo.predict(img_path, verbose=False)[0]
        det_boxes = [tuple(b.tolist()) for b in results.boxes.xyxy]

        pairs = match_detections_to_truth(det_boxes, by_sheet[sheet_id])
        for det_box, truth in pairs:
            crop = crop_from_box(img, det_box)
            tmp_path = "/tmp/_eval_crop.png"
            crop.save(tmp_path)

            ft_text, ft_conf = donut_ft.read_crop(tmp_path, with_confidence=True)
            ft_record = try_parse_fcf_string(ft_text)
            ft_norm = normalize(ft_record.fcf_type, ft_record.value, ft_record.datums, ft_record.diametral) \
                if ft_record else None

            zs_text = donut_zs.read_crop(tmp_path)
            zs_fields = extract_fields_from_text(zs_text)
            type_name = {"POS": "position", "FLT": "flatness", "PERP": "perpendicularity", "PAR": "parallelism",
                         "CONC": "concentricity", "PROF": "profile"}.get(zs_fields["type_code"])
            zs_norm = normalize(type_name, zs_fields["value"], zs_fields["datums"], zs_fields["diametral"]) \
                if type_name and zs_fields["value"] is not None else None

            ocr_fields = ocr.extract(tmp_path)
            ocr_type = {"POS": "position", "FLT": "flatness", "PERP": "perpendicularity", "PAR": "parallelism",
                        "CONC": "concentricity", "PROF": "profile"}.get(ocr_fields["type_code"])
            ocr_norm = normalize(ocr_type, ocr_fields["value"], ocr_fields["datums"], ocr_fields["diametral"]) \
                if ocr_type and ocr_fields["value"] is not None else None

            truths.append(truth)
            ft_preds.append(ft_norm)
            ft_confs.append(ft_conf)
            zs_preds.append(zs_norm)
            ocr_preds.append(ocr_norm)

        if (n + 1) % 50 == 0:
            print(f"  {n + 1}/{len(sheet_ids)} sheets, {len(truths)} matched FCFs, {time.time() - t0:.1f}s")

    report = {
        "n_sheets": len(sheet_ids),
        "n_matched_fcfs": len(truths),
        "finetuned_donut": {
            "field_level_exact_match": field_level_exact_match_rate(ft_preds, truths),
        },
        "zero_shot_donut": {
            "field_level_exact_match": field_level_exact_match_rate(zs_preds, truths),
        },
        "ocr_regex_baseline": {
            "field_level_exact_match": field_level_exact_match_rate(ocr_preds, truths),
        },
        "elapsed_s": time.time() - t0,
    }

    # abstention band: calibrate threshold on a held-out half, apply on the other half
    half = len(truths) // 2
    calib_conf, calib_correct = ft_confs[:half], [exact_match(p, t) for p, t in zip(ft_preds[:half], truths[:half])]
    apply_conf = ft_confs[half:]
    apply_correct = [exact_match(p, t) for p, t in zip(ft_preds[half:], truths[half:])]

    order = sorted(range(len(calib_conf)), key=lambda i: -calib_conf[i])
    best_threshold, best_accept_rate = 1.0, 0.0
    cum_correct, cum_count = 0, 0
    for i in order:
        cum_correct += calib_correct[i]
        cum_count += 1
        precision = cum_correct / cum_count
        if precision >= 0.99:
            best_threshold = calib_conf[i]
            best_accept_rate = cum_count / len(order)

    accepted = [c >= best_threshold for c in apply_conf]
    n_accept = sum(accepted)
    precision_applied = (
        sum(corr for corr, acc in zip(apply_correct, accepted) if acc) / n_accept if n_accept else float("nan")
    )
    report["abstention_band"] = {
        "threshold": best_threshold,
        "calibration_accept_rate": best_accept_rate,
        "applied_accept_rate": n_accept / len(apply_conf) if apply_conf else float("nan"),
        "applied_precision": precision_applied,
        "n_calibration": len(calib_conf),
        "n_applied": len(apply_conf),
    }

    with open(args.out, "w") as fh:
        json.dump(report, fh, indent=2, default=float)
    print(json.dumps(report, indent=2, default=float))


if __name__ == "__main__":
    main()
