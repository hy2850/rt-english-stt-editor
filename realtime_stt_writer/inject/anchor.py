from __future__ import annotations

import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable
from typing import Mapping

from realtime_stt_writer.domain.models import TargetAnchor


PointerProvider = Callable[[], tuple[float, float]]
TargetResolver = Callable[[float, float], Mapping[str, object] | None]


@dataclass(slots=True)
class TargetAnchorState:
    storage_path: Path
    active_anchor: TargetAnchor | None = field(default=None, init=False)

    def __post_init__(self) -> None:
        if self.storage_path.exists():
            self.active_anchor = TargetAnchor.from_dict(json.loads(self.storage_path.read_text()))

    def set_active_anchor(self, anchor: TargetAnchor) -> None:
        self.active_anchor = anchor
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        self.storage_path.write_text(json.dumps(anchor.to_dict(), indent=2))

    def get_active_anchor(self) -> TargetAnchor | None:
        return self.active_anchor


@dataclass(slots=True)
class MacOSTargetAnchorService:
    state: TargetAnchorState
    pointer_provider: PointerProvider = field(default_factory=lambda: _read_pointer_position)
    target_resolver: TargetResolver = field(default_factory=lambda: _resolve_target_at_point)

    def arm_from_current_mouse_position(self) -> TargetAnchor:
        x, y = self.pointer_provider()
        target = self.target_resolver(x, y)
        if target is None:
            raise RuntimeError('Unable to resolve a target under the current mouse position.')

        anchor = TargetAnchor(
            x=x,
            y=y,
            pid=int(target['pid']) if target.get('pid') is not None else None,
            bundle_id=str(target['bundle_id']) if target.get('bundle_id') is not None else None,
            app_name=str(target['app_name']) if target.get('app_name') is not None else None,
        )
        self.state.set_active_anchor(anchor)
        return anchor

    def set_active_anchor(self, anchor: TargetAnchor) -> None:
        self.state.set_active_anchor(anchor)

    def get_active_anchor(self) -> TargetAnchor | None:
        return self.state.get_active_anchor()


def _read_pointer_position() -> tuple[float, float]:
    if sys.platform != 'darwin':
        raise RuntimeError('Pointer inspection is only available on macOS.')

    try:
        from Quartz import CGEventCreate
        from Quartz import CGEventGetLocation
    except ImportError as exc:
        raise RuntimeError('Quartz bindings are required to read the current mouse position.') from exc

    event = CGEventCreate(None)
    location = CGEventGetLocation(event)
    return float(location.x), float(location.y)


def _resolve_target_at_point(x: float, y: float) -> Mapping[str, object] | None:
    if sys.platform != 'darwin':
        raise RuntimeError('Target resolution is only available on macOS.')

    try:
        from AppKit import NSRunningApplication
        from Quartz import CGWindowListCopyWindowInfo
        from Quartz import kCGNullWindowID
        from Quartz import kCGWindowListOptionOnScreenOnly
        from Quartz import kCGWindowListOptionIncludingWindow
    except ImportError as exc:
        raise RuntimeError('Quartz/AppKit bindings are required to resolve the mouse target.') from exc

    windows = CGWindowListCopyWindowInfo(
        kCGWindowListOptionOnScreenOnly | kCGWindowListOptionIncludingWindow,
        kCGNullWindowID,
    ) or []
    for window in windows:
        bounds = window.get('kCGWindowBounds') or {}
        left = float(bounds.get('X', 0.0))
        top = float(bounds.get('Y', 0.0))
        width = float(bounds.get('Width', 0.0))
        height = float(bounds.get('Height', 0.0))
        if left <= x <= left + width and top <= y <= top + height:
            pid = window.get('kCGWindowOwnerPID')
            app = NSRunningApplication.runningApplicationWithProcessIdentifier_(pid) if pid is not None else None
            bundle_id = app.bundleIdentifier() if app is not None else None
            app_name = window.get('kCGWindowOwnerName') or (app.localizedName() if app is not None else None)
            return {
                'pid': pid,
                'bundle_id': bundle_id,
                'app_name': app_name,
            }
    return None
