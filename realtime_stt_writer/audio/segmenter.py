from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from uuid import uuid4

from realtime_stt_writer.domain.models import FinalizedSegment


@dataclass(slots=True)
class SimpleSegmenter:
    sample_rate: int = 16000
    max_segment_frames: int = 16000 * 12
    _buffer: list[float] = field(default_factory=list)

    def feed(self, samples: Iterable[float], *, started_at: float, ended_at: float) -> FinalizedSegment | None:
        chunk = list(samples)
        if not chunk:
            return None
        self._buffer.extend(chunk)
        if len(self._buffer) < self.max_segment_frames:
            return None

        audio = self._buffer[:]
        self._buffer.clear()
        return FinalizedSegment(
            audio=audio,
            sample_rate=self.sample_rate,
            started_at=started_at,
            ended_at=ended_at,
            segment_id=str(uuid4()),
        )
