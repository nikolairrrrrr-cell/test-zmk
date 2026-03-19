from __future__ import annotations

import re
from pathlib import Path
from typing import Iterable

from PIL import Image


def slugify_filename(stem: str) -> str:
    s = stem.strip().lower()
    s = re.sub(r"[^a-z0-9а-яё]+", "_", s, flags=re.IGNORECASE)
    s = s.strip("_")
    return s or "input"


def preprocess_table_image(
    input_path: Path,
    output_dir: Path = Path("data/recognition"),
    left_frac: float = 0.52,
    top_frac: float = 0.52,
    right_frac: float = 0.98,
    bottom_frac: float = 0.96,
    scale: float = 4.0,
) -> Path:
    """
    Always-preprocess pipeline for image scan:
    1) crop table area
    2) upscale crop
    3) save artifact used for recognition step
    """
    image = Image.open(input_path)
    width, height = image.size

    # 1) Try adaptive detection of table bounds.
    detected = _detect_table_bbox(image)
    if detected is None:
        # 2) Fallback to wide static crop if detection fails.
        left = int(width * left_frac)
        top = int(height * top_frac)
        right = int(width * right_frac)
        bottom = int(height * bottom_frac)
    else:
        left, top, right, bottom = detected

    crop = image.crop((left, top, right, bottom))
    upscaled = crop.resize(
        (max(1, int(crop.width * scale)), max(1, int(crop.height * scale))),
        Image.LANCZOS,
    )
    if upscaled.mode not in ("RGB", "L"):
        upscaled = upscaled.convert("RGB")

    output_dir.mkdir(parents=True, exist_ok=True)
    slug = slugify_filename(input_path.stem)
    out_path = output_dir / f"{slug}.table_x4.jpg"
    upscaled.save(out_path, quality=95)
    return out_path


def _moving_average(values: Iterable[float], window: int = 9) -> list[float]:
    seq = list(values)
    if not seq:
        return []
    w = max(1, window)
    out: list[float] = []
    prefix = [0.0]
    for v in seq:
        prefix.append(prefix[-1] + v)
    for i in range(len(seq)):
        l = max(0, i - w // 2)
        r = min(len(seq), i + w // 2 + 1)
        out.append((prefix[r] - prefix[l]) / max(1, (r - l)))
    return out


def _first_last_over_threshold(values: list[float], threshold: float) -> tuple[int, int] | None:
    idx = [i for i, v in enumerate(values) if v >= threshold]
    if not idx:
        return None
    return idx[0], idx[-1]


def _detect_table_bbox(image: Image.Image) -> tuple[int, int, int, int] | None:
    """
    Detect table-like block using dark-pixel projections in lower sheet area.
    Works better than fixed fractions when the table shifts left/right.
    """
    gray = image.convert("L")
    width, height = gray.size

    # Analyze only likely area where title block/table usually resides.
    scan_left = int(width * 0.05)
    scan_top = int(height * 0.20)
    scan_right = int(width * 0.99)
    scan_bottom = int(height * 0.99)
    roi = gray.crop((scan_left, scan_top, scan_right, scan_bottom))
    rw, rh = roi.size
    if rw < 50 or rh < 50:
        return None

    # Downscale analysis image for speed/stability.
    max_w = 900
    if rw > max_w:
        ratio = max_w / rw
        arw = max_w
        arh = max(1, int(rh * ratio))
        analysis = roi.resize((arw, arh), Image.BILINEAR)
    else:
        analysis = roi
        arw, arh = rw, rh

    px = analysis.load()
    dark_threshold = 185

    row_scores: list[float] = []
    col_scores: list[float] = [0.0] * arw
    for y in range(arh):
        dark = 0
        for x in range(arw):
            if px[x, y] < dark_threshold:
                dark += 1
                col_scores[x] += 1.0
        row_scores.append(dark / arw)
    col_scores = [v / arh for v in col_scores]

    row_smooth = _moving_average(row_scores, window=11)
    col_smooth = _moving_average(col_scores, window=11)

    row_bounds = _first_last_over_threshold(row_smooth, threshold=0.04)
    col_bounds = _first_last_over_threshold(col_smooth, threshold=0.02)
    if row_bounds is None or col_bounds is None:
        return None

    y0, y1 = row_bounds
    x0, x1 = col_bounds

    # Convert back to original ROI coordinates.
    sx = rw / arw
    sy = rh / arh
    left = int(scan_left + max(0, x0 * sx - 20))
    top = int(scan_top + max(0, y0 * sy - 20))
    right = int(scan_left + min(rw, x1 * sx + 20))
    bottom = int(scan_top + min(rh, y1 * sy + 20))

    # Safety clamps.
    left = max(0, min(left, width - 1))
    top = max(0, min(top, height - 1))
    right = max(left + 1, min(right, width))
    bottom = max(top + 1, min(bottom, height))
    return left, top, right, bottom

