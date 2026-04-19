from __future__ import annotations

import queue
import time
from dataclasses import dataclass
from dataclasses import field
from typing import Callable


StreamFactory = Callable[..., object]


@dataclass(slots=True)
class MicrophoneCapture:
    sample_rate: int
    channels: int
    blocksize: int
    device: str | None = None
    queue_maxsize: int = 32
    stream_factory: StreamFactory = field(default_factory=lambda: _build_input_stream)
    queue: queue.Queue[dict[str, object]] = field(init=False)
    _stream: object | None = field(default=None, init=False)
    _is_running: bool = field(default=False, init=False)

    def __post_init__(self) -> None:
        self.queue = queue.Queue(maxsize=self.queue_maxsize)

    @property
    def is_running(self) -> bool:
        return self._is_running

    def start(self) -> None:
        if self._is_running:
            return

        self._stream = self.stream_factory(
            samplerate=self.sample_rate,
            channels=self.channels,
            blocksize=self.blocksize,
            device=self.device,
            callback=self._on_audio_frames,
        )
        self._stream.start()
        self._is_running = True

    def stop(self) -> None:
        if self._stream is None:
            self._is_running = False
            return

        if hasattr(self._stream, 'stop'):
            self._stream.stop()
        if hasattr(self._stream, 'close'):
            self._stream.close()
        self._stream = None
        self._is_running = False

    def _on_audio_frames(self, indata, frames: int, time_info, status) -> None:
        input_time = None
        if isinstance(time_info, dict):
            input_time = time_info.get('input_buffer_adc_time')
        elif time_info is not None:
            input_time = getattr(time_info, 'inputBufferAdcTime', None)
        if input_time is None:
            input_time = time.monotonic()

        frames_payload = indata.copy() if hasattr(indata, 'copy') else indata

        chunk = {
            'frames': frames_payload,
            'frame_count': frames,
            'sample_rate': self.sample_rate,
            'input_time': input_time,
            'status': status,
        }
        try:
            self.queue.put_nowait(chunk)
        except queue.Full:
            return


def _build_input_stream(**kwargs):
    try:
        import sounddevice
    except ImportError as exc:
        raise RuntimeError('sounddevice is required for live microphone capture.') from exc

    return sounddevice.InputStream(**kwargs)
