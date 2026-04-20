from __future__ import annotations

from realtime_stt_writer.stt.cohere_mlx import CohereMLXEngine


def build_stt_engine(
    name: str = 'cohere_mlx',
    *,
    model_id: str | None = None,
    language: str = 'en',
    punctuation: bool = True,
) -> object:
    if name != 'cohere_mlx':
        raise ValueError(f'Unsupported STT engine: {name}')
    kwargs: dict[str, object] = {
        'language': language,
        'punctuation': punctuation,
    }
    if model_id is not None:
        kwargs['model_id'] = model_id
    return CohereMLXEngine(**kwargs)
