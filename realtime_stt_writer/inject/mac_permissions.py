from __future__ import annotations

import sys
from dataclasses import dataclass, field
from typing import Callable

from realtime_stt_writer.domain.protocols import PermissionStatus


@dataclass(slots=True)
class AccessibilityPermissionChecker:
    probe: Callable[[], bool] = field(default_factory=lambda: _probe_accessibility_permission)
    platform: str = field(default_factory=lambda: sys.platform)

    def check(self) -> PermissionStatus:
        if self.platform != 'darwin':
            return _status('accessibility', False, 'Accessibility permission checks are only available on macOS.')

        granted = bool(self.probe())
        detail = 'Accessibility granted.' if granted else 'Accessibility missing. Enable it in System Settings > Privacy & Security > Accessibility.'
        return _status('accessibility', granted, detail)


@dataclass(slots=True)
class MicrophonePermissionChecker:
    probe: Callable[[], bool] = field(default_factory=lambda: _probe_microphone_permission)
    platform: str = field(default_factory=lambda: sys.platform)

    def check(self) -> PermissionStatus:
        if self.platform != 'darwin':
            return _status('microphone', False, 'Microphone permission checks are only available on macOS.')

        granted = bool(self.probe())
        detail = 'Microphone granted.' if granted else 'Microphone missing. Enable it in System Settings > Privacy & Security > Microphone.'
        return _status('microphone', granted, detail)


def _status(name: str, granted: bool, detail: str) -> PermissionStatus:
    return {'name': name, 'granted': granted, 'detail': detail}


def _probe_accessibility_permission() -> bool:
    try:
        from Quartz import AXIsProcessTrusted
    except ImportError:
        return False

    return bool(AXIsProcessTrusted())


def _probe_microphone_permission() -> bool:
    try:
        from AVFoundation import AVAuthorizationStatusAuthorized
        from AVFoundation import AVCaptureDevice
        from AVFoundation import AVMediaTypeAudio
    except ImportError:
        return False

    status = AVCaptureDevice.authorizationStatusForMediaType_(AVMediaTypeAudio)
    return bool(status == AVAuthorizationStatusAuthorized)
