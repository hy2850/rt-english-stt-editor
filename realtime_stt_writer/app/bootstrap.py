from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from realtime_stt_writer.audio.capture import MicrophoneCapture
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


@dataclass(slots=True)
class AppRuntime:
    permission_checkers: list[PermissionChecker]
    anchor_service: TargetAnchorService
    injector: TextInjector
    microphone_capture: MicrophoneCapture


def load_config(config_path: str) -> dict[str, Any]:
    with open(config_path, 'r', encoding='utf-8') as handle:
        loaded = yaml.safe_load(handle) or {}
    if not isinstance(loaded, dict):
        raise RuntimeError(f'Config file must contain a mapping: {config_path}')
    return loaded


def build_runtime(config_path: str) -> AppRuntime:
    config = load_config(config_path)
    audio_config = config.get('audio', {})
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
    return AppRuntime(
        permission_checkers=[
            AccessibilityPermissionChecker(),
            MicrophonePermissionChecker(),
        ],
        anchor_service=anchor_service,
        injector=injector,
        microphone_capture=microphone_capture,
    )
