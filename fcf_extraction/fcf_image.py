"""Synthetic drawing-sheet images carrying feature control frames (FCFs).

Separate from drawing_check/sheet_pdf.py (which renders PDFs for the
release-check side of this repo): the detector and document model need
raster images, so sheets here are drawn directly with Pillow rather than
round-tripped through a PDF. Every FCF's ground truth (type, tolerance
value, datum references, pixel bounding box) is returned alongside the
image; nothing about the image is inferred after the fact.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field

from PIL import Image, ImageDraw, ImageFont

PAGE_SIZE = (850, 1100)  # roughly a letter page at 100dpi
MARGIN = 40

FCF_TYPES = ["position", "flatness", "perpendicularity", "parallelism", "concentricity", "profile"]
TYPE_CODE = {
    "position": "POS",
    "flatness": "FLT",
    "perpendicularity": "PERP",
    "parallelism": "PAR",
    "concentricity": "CONC",
    "profile": "PROF",
}
# ASME Y14.5-shaped rules this dataset actually encodes:
#   - flatness is a form tolerance: it never carries a datum reference.
#   - every other type carries 1 to 3 datum letters.
#   - position and concentricity are diametral tolerance zones: the value
#     always carries the diameter modifier; the others never do.
DIAMETRAL_TYPES = {"position", "concentricity"}
DATUM_LETTERS = ["A", "B", "C", "D"]


@dataclass(frozen=True)
class FCFGroundTruth:
    fcf_type: str
    value: float
    datums: tuple
    diametral: bool
    bbox: tuple  # (x0, y0, x1, y1) in pixels, the detector's target

    def grammar_string(self) -> str:
        """The exact text this FCF renders as, which is also the target
        string the document model is trained to reproduce."""
        value_str = f"{'⌀' if self.diametral else ''}{self.value:.2f}"
        datum_str = "".join(self.datums)
        return f"{TYPE_CODE[self.fcf_type]}|{value_str}|{datum_str}"


def _font(size: int) -> ImageFont.ImageFont:
    try:
        return ImageFont.truetype("DejaVuSans.ttf", size)
    except OSError:
        return ImageFont.load_default()


def _random_fcf(rng: random.Random, fcf_type: str | None = None) -> tuple:
    fcf_type = fcf_type or rng.choice(FCF_TYPES)
    value = round(rng.uniform(0.01, 0.50), 2)
    diametral = fcf_type in DIAMETRAL_TYPES
    if fcf_type == "flatness":
        datums = ()
    else:
        n_datums = rng.randint(1, 3)
        datums = tuple(sorted(rng.sample(DATUM_LETTERS, n_datums)))
    return fcf_type, value, datums, diametral


def _draw_fcf(draw: ImageDraw.ImageDraw, x: int, y: int, fcf_type: str, value: float, datums: tuple,
              diametral: bool, font) -> tuple:
    """Draws a compartmented FCF box (symbol | value | datum cells) with a
    real border, and returns its pixel bounding box."""
    cells = [TYPE_CODE[fcf_type], f"{'⌀' if diametral else ''}{value:.2f}"] + list(datums)
    cell_w, cell_h = 55, 26
    total_w = cell_w * len(cells)
    draw.rectangle([x, y, x + total_w, y + cell_h], outline="black", width=1)
    for i in range(1, len(cells)):
        draw.line([x + i * cell_w, y, x + i * cell_w, y + cell_h], fill="black", width=1)
    for i, text in enumerate(cells):
        draw.text((x + i * cell_w + 6, y + 5), text, fill="black", font=font)
    return (x, y, x + total_w, y + cell_h)


def render_sheet_image(seed: int, n_fcf: int | None = None) -> tuple:
    """Returns (PIL.Image, [FCFGroundTruth]). `n_fcf` defaults to a random
    1-3 if not given."""
    rng = random.Random(seed)
    img = Image.new("L", PAGE_SIZE, "white")
    draw = ImageDraw.Draw(img)
    font = _font(14)

    # Background drawing geometry: stand-in line work, the same role the
    # 10 synthetic lines play in sheet_pdf.render_sheet_pdf.
    for _ in range(12):
        x1, y1 = rng.uniform(MARGIN, PAGE_SIZE[0] - MARGIN), rng.uniform(MARGIN, PAGE_SIZE[1] - 150)
        x2, y2 = rng.uniform(MARGIN, PAGE_SIZE[0] - MARGIN), rng.uniform(MARGIN, PAGE_SIZE[1] - 150)
        draw.line([x1, y1, x2, y2], fill="black", width=1)

    n_fcf = n_fcf if n_fcf is not None else rng.randint(1, 3)
    ground_truth = []
    placed_boxes = []
    attempts = 0
    while len(ground_truth) < n_fcf and attempts < n_fcf * 20:
        attempts += 1
        fcf_type, value, datums, diametral = _random_fcf(rng)
        x = rng.randint(MARGIN, PAGE_SIZE[0] - 260)
        y = rng.randint(MARGIN, PAGE_SIZE[1] - 200)
        n_cells = 2 + len(datums)
        candidate_box = (x, y, x + 55 * n_cells, y + 26)
        if any(_overlaps(candidate_box, b) for b in placed_boxes):
            continue
        bbox = _draw_fcf(draw, x, y, fcf_type, value, datums, diametral, font)
        placed_boxes.append(bbox)
        ground_truth.append(FCFGroundTruth(fcf_type, value, datums, diametral, bbox))

    return img, ground_truth


def _overlaps(a: tuple, b: tuple, pad: int = 8) -> bool:
    ax0, ay0, ax1, ay1 = a
    bx0, by0, bx1, by1 = b
    return not (ax1 + pad < bx0 or bx1 + pad < ax0 or ay1 + pad < by0 or by1 + pad < ay0)
