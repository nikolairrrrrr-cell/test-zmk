from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol


class RecognitionError(RuntimeError):
    pass


@dataclass
class PendingCrop:
    """One crop image that needs agent-side reading."""
    source_file: Path
    crop_path: Path
    expected_payload: Path


class AgentReadRequired(RuntimeError):
    """
    Raised when crop+upscale is done but JSON payloads are missing.
    The agent MUST read every crop listed in `pending`, write the JSON,
    then re-run the pipeline.
    """
    pending: list[PendingCrop] = field(default_factory=list)

    def __init__(self, pending: list[PendingCrop]) -> None:
        self.pending = pending
        files = "\n".join(
            f"  crop: {p.crop_path}  ->  write: {p.expected_payload}"
            for p in pending
        )
        super().__init__(
            f"AGENT_READ_REQUIRED — {len(pending)} crop(s) have no JSON payload.\n"
            "The agent must read each crop image and write the payload JSON.\n"
            f"{files}"
        )


class Recognizer(Protocol):
    def recognize_pdf_zmk(self, input_path: Path) -> dict:
        ...

    def recognize_pdf_zmk2(self, input_path: Path) -> dict:
        ...

