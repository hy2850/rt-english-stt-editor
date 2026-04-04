from __future__ import annotations

from realtime_stt_writer.stt.cohere_mlx import CohereMLXEngine


def build_stt_engine(name: str = "cohere_mlx") -> object:
    if name != "cohere_mlx":
        raise ValueError(f"Unsupported STT engine: {name}")
    return CohereMLXEngine()
