from fcf_extraction.fcf_image import FCF_TYPES, render_sheet_image
from fcf_extraction.grammar import parse_fcf_string


def test_render_sheet_image_returns_requested_number_of_fcfs():
    img, ground_truth = render_sheet_image(seed=42, n_fcf=2)
    assert len(ground_truth) == 2
    assert img.size[0] > 0 and img.size[1] > 0


def test_every_rendered_fcf_bbox_is_within_the_page():
    img, ground_truth = render_sheet_image(seed=7, n_fcf=3)
    for fcf in ground_truth:
        x0, y0, x1, y1 = fcf.bbox
        assert 0 <= x0 < x1 <= img.size[0]
        assert 0 <= y0 < y1 <= img.size[1]


def test_rendered_fcf_bboxes_do_not_overlap():
    img, ground_truth = render_sheet_image(seed=123, n_fcf=3)
    boxes = [fcf.bbox for fcf in ground_truth]
    for i in range(len(boxes)):
        for j in range(i + 1, len(boxes)):
            ax0, ay0, ax1, ay1 = boxes[i]
            bx0, by0, bx1, by1 = boxes[j]
            separated = ax1 < bx0 or bx1 < ax0 or ay1 < by0 or by1 < ay0
            assert separated, f"boxes {boxes[i]} and {boxes[j]} overlap"


def test_flatness_frames_never_render_a_datum():
    seen_flatness = False
    for seed in range(50):
        _, ground_truth = render_sheet_image(seed=seed, n_fcf=3)
        for fcf in ground_truth:
            if fcf.fcf_type == "flatness":
                seen_flatness = True
                assert fcf.datums == ()
    assert seen_flatness, "no flatness frame generated across 50 seeds; widen the seed range"


def test_every_generated_grammar_string_round_trips_through_the_parser():
    for seed in range(30):
        _, ground_truth = render_sheet_image(seed=seed, n_fcf=3)
        for fcf in ground_truth:
            rec = parse_fcf_string(fcf.grammar_string())
            assert rec.fcf_type == fcf.fcf_type
            assert rec.value == fcf.value
            assert rec.datums == fcf.datums
            assert rec.diametral == fcf.diametral


def test_all_six_types_appear_across_enough_seeds():
    seen = set()
    for seed in range(200):
        _, ground_truth = render_sheet_image(seed=seed, n_fcf=3)
        seen.update(fcf.fcf_type for fcf in ground_truth)
    assert seen == set(FCF_TYPES)
