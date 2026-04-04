from __future__ import annotations

from dataclasses import dataclass, field

from realtime_stt_writer.cleanup.pipeline import CleanupPipeline
from realtime_stt_writer.domain.models import FinalizedSegment
from realtime_stt_writer.domain.protocols import STTEngine
from realtime_stt_writer.domain.protocols import TextInjector
from realtime_stt_writer.inject.formatting import format_for_insert


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

    def on_finalized_segment(self, segment: FinalizedSegment) -> None:
        if segment.segment_id == self.last_inserted_segment_id:
            return

        transcript = self.stt_engine.transcribe(
            segment.audio,
            segment.sample_rate,
            started_at=segment.started_at,
            ended_at=segment.ended_at,
            segment_id=segment.segment_id,
        )
        if not transcript.text.strip():
            return

        cleaned = self.cleanup_pipeline.cleanup(
            transcript.text,
            previous_sentences=self.previous_sentences[-self.context_window :],
        )
        if not cleaned:
            return

        formatted = format_for_insert(
            cleaned,
            separator=self.separator,
            add_terminal_punctuation=self.add_terminal_punctuation,
        )
        if not formatted or formatted == self.last_inserted_text:
            return

        self.injector.insert(formatted)
        self.previous_sentences.append(cleaned)
        self.previous_sentences = self.previous_sentences[-10:]
        self.last_inserted_segment_id = segment.segment_id
        self.last_inserted_text = formatted
