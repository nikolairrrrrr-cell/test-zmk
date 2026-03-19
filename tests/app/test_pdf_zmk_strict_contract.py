from __future__ import annotations

import pytest

from app.use_cases.pdf_zmk import build_pdf_zmk_values_from_payload


def test_build_pdf_zmk_values_fails_on_empty_items() -> None:
    with pytest.raises(ValueError):
        build_pdf_zmk_values_from_payload({"drawing_name": "X", "items": []})

