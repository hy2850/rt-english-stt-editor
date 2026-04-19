from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from realtime_stt_writer.audio.capture import MicrophoneCapture
from realtime_stt_writer.audio.segmenter import EndpointingSegmenter
from realtime_stt_writer.cleanup.pipeline import CleanupPipeline
from realtime_stt_writer.cleanup.rule_based import RuleBasedCleanup
from realtime_stt_writer.domain.protocols import PermissionChecker
from realtime_stt_writer.domain.protocols import TargetAnchorService
from realtime_stt_writer.domain.protocols import TextInjector
from realtime_stt_writer.inject.anchor import MacOSTargetAnchorService
from realtime_stt_writer.inject.anchor import TargetAnchorState
from realtime_stt_writer.inject.hybrid_injector import HybridInjector
from realtime_stt_writer.inject.mac_click import MacClicker
from realtime_stt_writer.inject.mac_paste import ClipboardPreservingPasteInjector
from realtime_stt_writer.inject.mac_permissions import AccessibilityPermissionChecker
from realtime_stt_writer.inject.mac_permissions import MicrophonePermissionChecker
from realtime_stt_writer.services.live_loop import LiveTranscriptionLoop
from realtime_stt_writer.services.orchestrator import AppOrchestrator
from realtime_stt_writer.stt.factory import build_stt_engine


@dataclass(slots=True)
class AppRuntime:
    permission_checkers: list[PermissionChecker]
    anchor_service: TargetAnchorService
    injector: TextInjector
    microphone_capture: MicrophoneCapture
    live_loop: LiveTranscriptionLoop


def load_config(config_path: str) -> dict[str, Any]:
    with open(config_path, 'r', encoding='utf-8') as handle:
        loaded = yaml.safe_load(handle) or {}
    if not isinstance(loaded, dict):
        raise RuntimeError(f'Config file must contain a mapping: {config_path}')
    return loaded


def build_runtime(config_path: str) -> AppRuntime:
    config = load_config(config_path)
    audio_config = config.get('audio', {})
    endpoint_config = config.get('endpointing', {})
    stt_config = config.get('stt', {})
    injection_config = config.get('injection', {})
    cleanup_config = config.get('cleanup', {})

    sample_rate = int(audio_config.get('preferred_sample_rate', 16000))
    channels = int(audio_config.get('channels', 1))
    block_ms = int(audio_config.get('block_ms', 30))
    blocksize = max(1, int(sample_rate * (block_ms / 1000)))
    queue_maxsize = int(audio_config.get('capture_queue_size', 32))
    device = audio_config.get('device')
    if device == 'default':
        device = None

    state = TargetAnchorState(storage_path=Path('.omx/runtime/active_anchor.json'))
    anchor_service = MacOSTargetAnchorService(state=state)
    injector = HybridInjector(
        anchor_service=anchor_service,
        clicker=MacClicker(),
        paste_injector=ClipboardPreservingPasteInjector(),
    )
    microphone_capture = MicrophoneCapture(
        sample_rate=sample_rate,
        channels=channels,
        blocksize=blocksize,
        device=device,
        queue_maxsize=queue_maxsize,
    )
    stt_engine = build_stt_engine(
        stt_config.get('engine', 'cohere_mlx'),
        model_id=stt_config.get('model_id'),
        language=stt_config.get('language', config.get('app', {}).get('language', 'en')),
        punctuation=bool(stt_config.get('punctuation', True)),
    )
    cleanup_pipeline = CleanupPipeline(rule_engine=RuleBasedCleanup())
    orchestrator = AppOrchestrator(
        stt_engine=stt_engine,
        cleanup_pipeline=cleanup_pipeline,
        injector=injector,
        separator=injection_config.get('separator', '\n'),
        add_terminal_punctuation=bool(injection_config.get('append_terminal_punctuation', True)),
        context_window=int(cleanup_config.get('context_size', 2)),
    )
    endpointing = EndpointingSegmenter(
        sample_rate=sample_rate,
        rms_threshold=float(endpoint_config.get('rms_threshold', 0.01)),
        min_speech_ms=int(endpoint_config.get('min_speech_ms', 250)),
        end_silence_ms=int(endpoint_config.get('end_silence_ms', 700)),
        max_segment_sec=int(audio_config.get('max_segment_sec', 12)),
        pre_roll_ms=int(audio_config.get('pre_roll_ms', 250)),
    )
    live_loop = LiveTranscriptionLoop(
        capture=microphone_capture,
        segmenter=endpointing,
        segment_handler=orchestrator,
        stt_engine=stt_engine,
    )
    return AppRuntime(
        permission_checkers=[
            AccessibilityPermissionChecker(),
            MicrophonePermissionChecker(),
        ],
        anchor_service=anchor_service,
        injector=injector,
        microphone_capture=microphone_capture,
        live_loop=live_loop,
    )
