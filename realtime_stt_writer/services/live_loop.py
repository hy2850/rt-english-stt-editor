from __future__ import annotations

import queue
import threading
import time
from dataclasses import dataclass
from dataclasses import field
from typing import Callable
from typing import Iterable
from typing import Protocol

from realtime_stt_writer.domain.models import AudioFrame
from realtime_stt_writer.domain.protocols import SegmentHandler
from realtime_stt_writer.domain.protocols import STTEngine


WorkerFactory = Callable[[Callable[[], None]], threading.Thread | None]


class RuntimeLogger(Protocol):
    def write(self, message: str) -> None: ...


@dataclass(slots=True)
class LiveTranscriptionLoop:
    capture: object
    segmenter: object
    segment_handler: SegmentHandler
    stt_engine: STTEngine
    poll_timeout_seconds: float = 0.2
    worker_factory: WorkerFactory = field(default_factory=lambda: _default_worker_factory)
    logger: RuntimeLogger | None = None
    _worker: threading.Thread | None = field(default=None, init=False)
    _running: bool = field(default=False, init=False)

    @property
    def is_running(self) -> bool:
        return self._running

    def start(self) -> None:
        if self._running:
            return
        self._log('[startup] warming STT engine')
        self.stt_engine.warmup()
        self._log('[startup] starting microphone capture')
        self.capture.start()
        self._running = True
        self._worker = self.worker_factory(self._worker_loop)
        if self._worker is not None:
            self._worker.start()
        self._log('[ready] listening for speech')

    def stop(self) -> None:
        if hasattr(self.capture, 'stop'):
            self.capture.stop()
        self._running = False
        if self._worker is not None and self._worker.is_alive():
            self._worker.join(timeout=2.0)
        final_segment = self.segmenter.flush()
        if final_segment is not None:
            self._log_segment(final_segment)
            self.segment_handler.on_finalized_segment(final_segment)

    def process_next_chunk(self, *, block: bool = True) -> bool:
        try:
            chunk = self.capture.queue.get(block=block, timeout=self.poll_timeout_seconds if block else 0)
        except queue.Empty:
            return False
        frame = audio_frame_from_capture_chunk(chunk)
        for segment in self.segmenter.feed(frame):
            self._log_segment(segment)
            self.segment_handler.on_finalized_segment(segment)
        return True

    def run_until_interrupted(self) -> None:
        try:
            while self.is_running:
                time.sleep(0.25)
        except KeyboardInterrupt:
            pass
        finally:
            self.stop()

    def _worker_loop(self) -> None:
        while self._running or getattr(self.capture, 'is_running', False):
            self.process_next_chunk(block=True)

    def _log_segment(self, segment) -> None:
        self._log(f'[audio] finalized segment {segment.segment_id} ({segment.ended_at - segment.started_at:.2f}s)')

    def _log(self, message: str) -> None:
        if self.logger is not None:
            self.logger.write(message)


def _default_worker_factory(target: Callable[[], None]) -> threading.Thread:
    return threading.Thread(target=target, name='live-transcription-worker', daemon=True)


def audio_frame_from_capture_chunk(chunk: dict[str, object]) -> AudioFrame:
    sample_rate = int(chunk.get('sample_rate') or 16000)
    timestamp = chunk.get('input_time')
    if timestamp is None:
        timestamp = time.monotonic()
    return AudioFrame(
        samples=_flatten_audio_samples(chunk.get('frames')),
        sample_rate=sample_rate,
        timestamp=float(timestamp),
        status=chunk.get('status'),
    )


def _flatten_audio_samples(frames: object) -> list[float]:
    if frames is None:
        return []
    if hasattr(frames, 'tolist'):
        frames = frames.tolist()
    if isinstance(frames, (bytes, bytearray)):
        return [((sample - 128) / 128.0) for sample in frames]
    if isinstance(frames, Iterable) and not isinstance(frames, (str, bytes, bytearray)):
        values = []
        for item in frames:
            if isinstance(item, Iterable) and not isinstance(item, (str, bytes, bytearray)):
                nested = list(item)
                if nested:
                    values.append(float(sum(float(value) for value in nested) / len(nested)))
            else:
                values.append(float(item))
        return values
    return [float(frames)]
