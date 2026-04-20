from __future__ import annotations

import sys
from dataclasses import dataclass, field
from typing import Callable

from realtime_stt_writer.domain.protocols import PermissionStatus


@dataclass(slots=True)
class AccessibilityPermissionChecker:
    probe: Callable[[], bool] = field(default_factory=lambda: _probe_accessibility_permission)
    prompt_requester: Callable[[], None] = field(default_factory=lambda: _request_accessibility_prompt)
    platform: str = field(default_factory=lambda: sys.platform)

    def check(self) -> PermissionStatus:
        if self.platform != 'darwin':
            return _status('accessibility', False, 'Accessibility permission checks are only available on macOS.')

        granted = bool(self.probe())
        if granted:
            return _status('accessibility', True, 'Accessibility granted.')

        self.prompt_requester()
        return _status(
            'accessibility',
            False,
            'Accessibility missing. macOS may show a permission prompt; grant Accessibility for your terminal app, then rerun this command. If no prompt appears, open System Settings > Privacy & Security > Accessibility and enable Terminal/iTerm/VS Code/Cursor for the shell running this app.',
        )


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


def _request_accessibility_prompt() -> None:
    try:
        from Quartz import AXIsProcessTrustedWithOptions
        from Quartz import kAXTrustedCheckOptionPrompt
    except ImportError:
        return

    AXIsProcessTrustedWithOptions({kAXTrustedCheckOptionPrompt: True})


def _probe_microphone_permission() -> bool:
    try:
        from AVFoundation import AVAuthorizationStatusAuthorized
        from AVFoundation import AVCaptureDevice
        from AVFoundation import AVMediaTypeAudio
    except ImportError:
        return False

    status = AVCaptureDevice.authorizationStatusForMediaType_(AVMediaTypeAudio)
    return bool(status == AVAuthorizationStatusAuthorized)
