from __future__ import annotations

import os
import subprocess
import sys
from dataclasses import dataclass, field
from typing import Callable

from realtime_stt_writer.domain.protocols import PermissionStatus


@dataclass(slots=True)
class AccessibilityPermissionChecker:
    probe: Callable[[], bool] = field(default_factory=lambda: _probe_accessibility_permission)
    prompt_requester: Callable[[], None] = field(default_factory=lambda: _request_accessibility_prompt)
    process_identity: Callable[[], str] = field(default_factory=lambda: _describe_current_process)
    platform: str = field(default_factory=lambda: sys.platform)

    def check(self) -> PermissionStatus:
        if self.platform != 'darwin':
            return _status('accessibility', False, 'Accessibility permission checks are only available on macOS.')

        try:
            granted = bool(self.probe())
        except RuntimeError as exc:
            return _status(
                'accessibility',
                False,
                f'Unable to check Accessibility permission: {exc}. Verify PyObjC macOS framework dependencies are installed.',
            )

        if granted:
            return _status('accessibility', True, 'Accessibility granted.')

        self.prompt_requester()
        return _status(
            'accessibility',
            False,
            'Accessibility missing. macOS may show a permission prompt; grant Accessibility for your terminal app, then fully quit/restart that terminal app and rerun this command. '
            'If it still reports missing, also add the Python executable shown below via System Settings > Privacy & Security > Accessibility. '
            f'Permission identity: {self.process_identity()}',
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
    ax_is_process_trusted, _ = _load_accessibility_api()
    return bool(ax_is_process_trusted())


def _request_accessibility_prompt() -> None:
    _, ax_is_process_trusted_with_options = _load_accessibility_api()
    if ax_is_process_trusted_with_options is None:
        return
    try:
        from ApplicationServices import kAXTrustedCheckOptionPrompt
    except ImportError:
        try:
            from Quartz import kAXTrustedCheckOptionPrompt
        except ImportError:
            return

    ax_is_process_trusted_with_options({kAXTrustedCheckOptionPrompt: True})


def _load_accessibility_api():
    import_errors: list[str] = []
    for module_name in ('ApplicationServices', 'Quartz'):
        try:
            module = __import__(module_name, fromlist=['AXIsProcessTrusted'])
        except ImportError as exc:
            import_errors.append(f'{module_name}: {exc}')
            continue
        ax_is_process_trusted = getattr(module, 'AXIsProcessTrusted', None)
        if ax_is_process_trusted is None:
            import_errors.append(f'{module_name}: AXIsProcessTrusted missing')
            continue
        return ax_is_process_trusted, getattr(module, 'AXIsProcessTrustedWithOptions', None)
    raise RuntimeError('; '.join(import_errors) or 'AXIsProcessTrusted unavailable')


def _describe_current_process() -> str:
    parts = [f'python executable: {sys.executable}']
    try:
        from AppKit import NSRunningApplication

        app = NSRunningApplication.currentApplication()
        app_name = app.localizedName() if app is not None else None
        bundle_id = app.bundleIdentifier() if app is not None else None
        if app_name or bundle_id:
            parts.insert(0, f'current app: {app_name or "unknown"} ({bundle_id or "no bundle id"})')
    except ImportError:
        pass

    parent = _parent_process_name()
    if parent:
        parts.append(f'parent process: {parent}')
    return '; '.join(parts)


def _parent_process_name() -> str:
    try:
        completed = subprocess.run(
            ['ps', '-p', str(os.getppid()), '-o', 'comm='],
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError:
        return ''
    return completed.stdout.strip()


def _probe_microphone_permission() -> bool:
    try:
        from AVFoundation import AVAuthorizationStatusAuthorized
        from AVFoundation import AVCaptureDevice
        from AVFoundation import AVMediaTypeAudio
    except ImportError:
        return False

    status = AVCaptureDevice.authorizationStatusForMediaType_(AVMediaTypeAudio)
    return bool(status == AVAuthorizationStatusAuthorized)
