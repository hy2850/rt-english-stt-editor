from __future__ import annotations

from dataclasses import asdict
from dataclasses import dataclass
from typing import Any
from typing import Mapping


@dataclass(slots=True)
class AudioFrame:
    samples: list[float]
    sample_rate: int
    timestamp: float
    status: object | None = None


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

    def to_dict(self) -> dict[str, float | int | str | None]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: Mapping[str, object]) -> 'TargetAnchor':
        return cls(
            x=float(payload['x']),
            y=float(payload['y']),
            pid=int(payload['pid']) if payload.get('pid') is not None else None,
            bundle_id=str(payload['bundle_id']) if payload.get('bundle_id') is not None else None,
            app_name=str(payload['app_name']) if payload.get('app_name') is not None else None,
        )
