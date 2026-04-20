from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from realtime_stt_writer.cleanup.pipeline import CleanupPipeline
from realtime_stt_writer.domain.models import FinalizedSegment
from realtime_stt_writer.domain.protocols import STTEngine
from realtime_stt_writer.domain.protocols import TextInjector
from realtime_stt_writer.inject.formatting import format_for_insert


class RuntimeLogger(Protocol):
    def write(self, message: str) -> None: ...


@dataclass(slots=True)
class AppOrchestrator:
    stt_engine: STTEngine
    cleanup_pipeline: CleanupPipeline
    injector: TextInjector
    previous_sentences: list[str] = field(default_factory=list)
    last_inserted_segment_id: str | None = None
    last_inserted_text: str | None = None
    separator: str = "\n"
    add_terminal_punctuation: bool = True
    context_window: int = 2
    logger: RuntimeLogger | None = None

    def on_finalized_segment(self, segment: FinalizedSegment) -> None:
        if segment.segment_id == self.last_inserted_segment_id:
            return

        self._log(f'[stt] transcribing {segment.segment_id} ({segment.ended_at - segment.started_at:.2f}s)')
        transcript = self.stt_engine.transcribe(
            segment.audio,
            segment.sample_rate,
            started_at=segment.started_at,
            ended_at=segment.ended_at,
            segment_id=segment.segment_id,
        )
        if not transcript.text.strip():
            self._log(f'[stt] {segment.segment_id} empty transcript; skipped')
            return
        self._log(f'[stt] {segment.segment_id} raw: {transcript.text.strip()}')

        cleaned = self.cleanup_pipeline.cleanup(
            transcript.text,
            previous_sentences=self.previous_sentences[-self.context_window :],
        )
        if not cleaned:
            self._log(f'[cleanup] {segment.segment_id} empty after cleanup; skipped')
            return
        if cleaned != transcript.text.strip():
            self._log(f'[cleanup] {segment.segment_id} cleaned: {cleaned}')

        formatted = format_for_insert(
            cleaned,
            separator=self.separator,
            add_terminal_punctuation=self.add_terminal_punctuation,
        )
        if not formatted or formatted == self.last_inserted_text:
            self._log(f'[insert] {segment.segment_id} duplicate or empty formatted text; skipped')
            return

        self.injector.insert(formatted)
        self._log(f'[insert] {segment.segment_id} inserted: {formatted.strip()}')
        self.previous_sentences.append(cleaned)
        self.previous_sentences = self.previous_sentences[-10:]
        self.last_inserted_segment_id = segment.segment_id
        self.last_inserted_text = formatted

    def _log(self, message: str) -> None:
        if self.logger is not None:
            self.logger.write(message)
