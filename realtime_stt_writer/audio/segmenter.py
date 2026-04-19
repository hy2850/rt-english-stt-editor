from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from math import sqrt
from uuid import uuid4

from realtime_stt_writer.domain.models import AudioFrame
from realtime_stt_writer.domain.models import FinalizedSegment


def compute_rms(samples: Iterable[float]) -> float:
    values = list(samples)
    if not values:
        return 0.0
    return sqrt(sum(sample * sample for sample in values) / len(values))


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


@dataclass(slots=True)
class EndpointingSegmenter:
    sample_rate: int = 16000
    rms_threshold: float = 0.01
    min_speech_ms: int = 250
    end_silence_ms: int = 700
    max_segment_sec: int = 12
    pre_roll_ms: int = 250
    _buffer: list[float] = field(default_factory=list)
    _pre_roll: list[tuple[list[float], float]] = field(default_factory=list)
    _pre_roll_samples: int = 0
    _started_at: float | None = None
    _last_ended_at: float | None = None
    _speech_samples: int = 0
    _silence_samples: int = 0

    def feed(self, frame: AudioFrame) -> list[FinalizedSegment]:
        if frame.sample_rate != self.sample_rate:
            raise ValueError(f'EndpointingSegmenter requires {self.sample_rate} Hz audio')
        samples = list(frame.samples)
        if not samples:
            return []

        chunk_end = frame.timestamp + (len(samples) / self.sample_rate)
        is_speech = compute_rms(samples) >= self.rms_threshold

        if self._started_at is None:
            if not is_speech:
                self._push_pre_roll(samples, frame.timestamp)
                return []
            self._start_segment(frame.timestamp)

        self._buffer.extend(samples)
        self._last_ended_at = chunk_end
        if is_speech:
            self._speech_samples += len(samples)
            self._silence_samples = 0
        else:
            self._silence_samples += len(samples)

        if self._duration_ms(self._silence_samples) >= self.end_silence_ms:
            segment = self._finalize()
            return [segment] if segment is not None else []
        if len(self._buffer) >= self.max_segment_sec * self.sample_rate:
            segment = self._finalize()
            return [segment] if segment is not None else []
        return []

    def flush(self) -> FinalizedSegment | None:
        return self._finalize()

    def _start_segment(self, timestamp: float) -> None:
        if self._pre_roll:
            self._started_at = self._pre_roll[0][1]
            for samples, _chunk_start in self._pre_roll:
                self._buffer.extend(samples)
        else:
            self._started_at = timestamp
        self._pre_roll = []
        self._pre_roll_samples = 0

    def _push_pre_roll(self, samples: list[float], timestamp: float) -> None:
        limit = max(0, int((self.pre_roll_ms / 1000.0) * self.sample_rate))
        if limit == 0:
            return
        self._pre_roll.append((samples[:], timestamp))
        self._pre_roll_samples += len(samples)
        while self._pre_roll and self._pre_roll_samples > limit:
            dropped, _ = self._pre_roll.pop(0)
            self._pre_roll_samples -= len(dropped)

    def _finalize(self) -> FinalizedSegment | None:
        if not self._buffer or self._started_at is None or self._last_ended_at is None:
            self._reset_active()
            return None
        if self._duration_ms(self._speech_samples) < self.min_speech_ms:
            self._reset_active()
            return None

        segment = FinalizedSegment(
            audio=self._buffer[:],
            sample_rate=self.sample_rate,
            started_at=self._started_at,
            ended_at=self._last_ended_at,
            segment_id=str(uuid4()),
        )
        self._reset_active()
        return segment

    def _duration_ms(self, samples: int) -> float:
        return (samples / self.sample_rate) * 1000.0

    def _reset_active(self) -> None:
        self._buffer = []
        self._started_at = None
        self._last_ended_at = None
        self._speech_samples = 0
        self._silence_samples = 0
