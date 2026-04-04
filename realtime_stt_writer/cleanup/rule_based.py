from __future__ import annotations

import re

from realtime_stt_writer.domain.protocols import CleanupEngine

_FILLER_PATTERN = re.compile(r"\b(?:um|uh|erm|ah|hmm)\b", flags=re.IGNORECASE)
_REPEATED_WORD_PATTERN = re.compile(r"\b(\w+)\s+\1\b", flags=re.IGNORECASE)
_SPACE_BEFORE_PUNCTUATION_PATTERN = re.compile(r"\s+([,.?!])")


class RuleBasedCleanup(CleanupEngine):
    """Deterministic cleanup that preserves meaning over polish."""

    def cleanup(self, text: str, *, previous_sentences: list[str] | None = None) -> str:
        del previous_sentences
        cleaned = text.strip()
        cleaned = _FILLER_PATTERN.sub(" ", cleaned)

        previous = None
        while previous != cleaned:
            previous = cleaned
            cleaned = _REPEATED_WORD_PATTERN.sub(r"\1", cleaned)

        cleaned = re.sub(r"\s+", " ", cleaned).strip()
        cleaned = _SPACE_BEFORE_PUNCTUATION_PATTERN.sub(r"\1", cleaned)
        return cleaned
