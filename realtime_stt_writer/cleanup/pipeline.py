from __future__ import annotations

from dataclasses import dataclass

from realtime_stt_writer.domain.protocols import CleanupEngine


@dataclass(slots=True)
class CleanupPipeline:
    rule_engine: CleanupEngine
    llm_engine: CleanupEngine | None = None

    def cleanup(self, text: str, *, previous_sentences: list[str] | None = None) -> str:
        cleaned = self.rule_engine.cleanup(text, previous_sentences=previous_sentences)
        if not cleaned:
            return ""

        if self.llm_engine is None:
            return cleaned

        try:
            llm_cleaned = self.llm_engine.cleanup(
                cleaned,
                previous_sentences=previous_sentences,
            )
        except Exception:
            return cleaned

        return llm_cleaned.strip() or cleaned
