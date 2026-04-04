from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class EnergyThresholdVAD:
    threshold: float = 0.01

    def is_speech(self, audio_frame: bytes, sample_rate: int) -> bool:
        del sample_rate
        if not audio_frame:
            return False
        amplitude = max(abs(sample) for sample in audio_frame)
        return amplitude / 255.0 >= self.threshold
