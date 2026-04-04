from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(slots=True)
class FinalizedSegment:
    audio: Any
    sample_rate: int
    started_at: float
    ended_at: float
    segment_id: str


@dataclass(slots=True)
class Transcript:
    text: str
    language: str
    started_at: float
    ended_at: float
    segment_id: str


@dataclass(slots=True)
class TargetAnchor:
    x: float
    y: float
    pid: int | None = None
    bundle_id: str | None = None
    app_name: str | None = None
