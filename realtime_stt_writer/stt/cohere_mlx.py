from __future__ import annotations

from dataclasses import dataclass, field

from realtime_stt_writer.domain.models import Transcript


@dataclass(slots=True)
class CohereMLXEngine:
    model_id: str = "CohereLabs/cohere-transcribe-03-2026"
    language: str = "en"
    punctuation: bool = True
    model: object | None = field(default=None, init=False)

    def warmup(self) -> None:
        try:
            from mlx_audio.stt import load  # type: ignore
            import array
        except ImportError as exc:
            raise RuntimeError(
                "mlx-audio is required for CohereMLXEngine warmup"
            ) from exc

        self.model = load(self.model_id)
        silence = array.array("f", [0.0] * 16000)
        self.model.transcribe(
            language=self.language,
            audio_arrays=[silence],
            sample_rates=[16000],
            punctuation=self.punctuation,
        )

    def transcribe(
        self,
        audio,
        sample_rate: int,
        *,
        started_at: float,
        ended_at: float,
        segment_id: str,
    ) -> Transcript:
        if self.model is None:
            raise RuntimeError("Model not loaded. Call warmup() first.")

        texts = self.model.transcribe(
            language=self.language,
            audio_arrays=[audio],
            sample_rates=[sample_rate],
            punctuation=self.punctuation,
        )
        text = texts[0].strip() if texts else ""
        return Transcript(
            text=text,
            language=self.language,
            started_at=started_at,
            ended_at=ended_at,
            segment_id=segment_id,
        )
