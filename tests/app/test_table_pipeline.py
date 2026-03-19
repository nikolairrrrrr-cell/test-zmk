from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

from app.recognizers.table_pipeline import preprocess_table_image


def _dark_bbox(img: Image.Image, threshold: int = 180) -> tuple[int, int, int, int] | None:
    gray = img.convert("L")
    w, h = gray.size
    px = gray.load()
    xs: list[int] = []
    ys: list[int] = []
    for y in range(h):
        for x in range(w):
            if px[x, y] < threshold:
                xs.append(x)
                ys.append(y)
    if not xs:
        return None
    return min(xs), min(ys), max(xs), max(ys)


def _make_table_image(path: Path, rect: tuple[int, int, int, int]) -> None:
    img = Image.new("RGB", (1200, 900), "white")
    dr = ImageDraw.Draw(img)
    x0, y0, x1, y1 = rect
    dr.rectangle(rect, outline="black", width=4)
    # draw internal grid lines
    for t in range(1, 5):
        yy = y0 + (y1 - y0) * t // 5
        dr.line([(x0, yy), (x1, yy)], fill="black", width=2)
    for t in range(1, 4):
        xx = x0 + (x1 - x0) * t // 4
        dr.line([(xx, y0), (xx, y1)], fill="black", width=2)
    img.save(path)


def test_preprocess_table_image_detects_shifted_left_table(tmp_path: Path) -> None:
    src = tmp_path / "left.jpg"
    _make_table_image(src, (140, 360, 760, 820))
    out = preprocess_table_image(src, output_dir=tmp_path)
    crop = Image.open(out)
    bbox = _dark_bbox(crop)
    assert bbox is not None
    x0, _y0, x1, _y1 = bbox
    assert (x1 - x0) > 1400  # after x4 upscale, table should be wide and not clipped


def test_preprocess_table_image_detects_shifted_right_table(tmp_path: Path) -> None:
    src = tmp_path / "right.jpg"
    _make_table_image(src, (420, 340, 1120, 840))
    out = preprocess_table_image(src, output_dir=tmp_path)
    crop = Image.open(out)
    bbox = _dark_bbox(crop)
    assert bbox is not None
    x0, _y0, x1, _y1 = bbox
    assert (x1 - x0) > 1600

