from __future__ import annotations

from typing import Protocol
from typing import TypedDict

from realtime_stt_writer.domain.models import FinalizedSegment
from realtime_stt_writer.domain.models import TargetAnchor
from realtime_stt_writer.domain.models import Transcript


class STTEngine(Protocol):
    def warmup(self) -> None: ...

    def transcribe(
        self,
        audio,
        sample_rate: int,
        *,
        started_at: float,
        ended_at: float,
        segment_id: str,
    ) -> Transcript: ...


class CleanupEngine(Protocol):
    def cleanup(self, text: str, *, previous_sentences: list[str] | None = None) -> str: ...


class TextInjector(Protocol):
    def insert(self, text: str) -> None: ...


class PermissionStatus(TypedDict):
    name: str
    granted: bool
    detail: str


class PermissionChecker(Protocol):
    def check(self) -> PermissionStatus: ...


class TargetAnchorService(Protocol):
    def arm_from_current_mouse_position(self) -> TargetAnchor: ...

    def set_active_anchor(self, anchor: TargetAnchor) -> None: ...

    def get_active_anchor(self) -> TargetAnchor | None: ...


class VADAdapter(Protocol):
    def is_speech(self, audio_frame: bytes, sample_rate: int) -> bool: ...


class SegmentHandler(Protocol):
    def on_finalized_segment(self, segment: FinalizedSegment) -> None: ...
