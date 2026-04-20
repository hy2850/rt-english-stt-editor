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
InsertionCursorProvider = Callable[[], Mapping[str, object] | None]


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
    insertion_cursor_provider: InsertionCursorProvider = field(default_factory=lambda: _resolve_focused_text_cursor)

    def arm_from_current_mouse_position(self) -> TargetAnchor:
        cursor_target = self.insertion_cursor_provider()
        if cursor_target is None:
            raise RuntimeError('Unable to resolve the focused text cursor. Click into a text editor first.')

        anchor = _anchor_from_mapping(cursor_target)
        self.state.set_active_anchor(anchor)
        return anchor

    def set_active_anchor(self, anchor: TargetAnchor) -> None:
        self.state.set_active_anchor(anchor)

    def get_active_anchor(self) -> TargetAnchor | None:
        return self.state.get_active_anchor()


def _anchor_from_mapping(payload: Mapping[str, object]) -> TargetAnchor:
    return TargetAnchor(
        x=float(payload['x']),
        y=float(payload['y']),
        pid=int(payload['pid']) if payload.get('pid') is not None else None,
        bundle_id=str(payload['bundle_id']) if payload.get('bundle_id') is not None else None,
        app_name=str(payload['app_name']) if payload.get('app_name') is not None else None,
    )


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


def _resolve_focused_text_cursor() -> Mapping[str, object] | None:
    if sys.platform != 'darwin':
        return None

    try:
        from ApplicationServices import AXUIElementCopyAttributeValue
        from ApplicationServices import AXUIElementCopyParameterizedAttributeValue
        from ApplicationServices import AXUIElementCreateSystemWide
        from ApplicationServices import AXUIElementGetPid
        from ApplicationServices import kAXBoundsForRangeParameterizedAttribute
        from ApplicationServices import kAXFocusedApplicationAttribute
        from ApplicationServices import kAXFocusedUIElementAttribute
        from ApplicationServices import kAXSelectedTextRangeAttribute
        from AppKit import NSRunningApplication
    except ImportError:
        return None

    system_wide = AXUIElementCreateSystemWide()
    focused_app = _ax_copy_attribute(AXUIElementCopyAttributeValue, system_wide, kAXFocusedApplicationAttribute)
    if focused_app is None:
        return None
    focused_element = _ax_copy_attribute(AXUIElementCopyAttributeValue, focused_app, kAXFocusedUIElementAttribute)
    if focused_element is None:
        return None
    selected_range = _ax_copy_attribute(AXUIElementCopyAttributeValue, focused_element, kAXSelectedTextRangeAttribute)
    if selected_range is None:
        return None
    bounds = _ax_copy_parameterized_attribute(
        AXUIElementCopyParameterizedAttributeValue,
        focused_element,
        kAXBoundsForRangeParameterizedAttribute,
        selected_range,
    )
    point = _rect_midpoint(bounds)
    if point is None:
        return None

    pid = _ax_pid(AXUIElementGetPid, focused_app)
    app = NSRunningApplication.runningApplicationWithProcessIdentifier_(pid) if pid is not None else None
    return {
        'x': point[0],
        'y': point[1],
        'pid': pid,
        'bundle_id': app.bundleIdentifier() if app is not None else None,
        'app_name': app.localizedName() if app is not None else None,
    }


def _ax_copy_attribute(copy_attribute, element, attribute):
    try:
        result = copy_attribute(element, attribute, None)
    except TypeError:
        result = copy_attribute(element, attribute)
    if isinstance(result, tuple):
        if len(result) >= 2 and result[0] == 0:
            return result[1]
        return None
    return result


def _ax_copy_parameterized_attribute(copy_parameterized_attribute, element, attribute, parameter):
    try:
        result = copy_parameterized_attribute(element, attribute, parameter, None)
    except TypeError:
        result = copy_parameterized_attribute(element, attribute, parameter)
    if isinstance(result, tuple):
        if len(result) >= 2 and result[0] == 0:
            return result[1]
        return None
    return result


def _ax_pid(get_pid, element) -> int | None:
    try:
        result = get_pid(element, None)
    except TypeError:
        try:
            return int(get_pid(element))
        except Exception:
            return None
    if isinstance(result, tuple):
        if len(result) >= 2 and result[0] == 0:
            return int(result[1])
        return None
    if result is None:
        return None
    return int(result)


def _rect_midpoint(rect) -> tuple[float, float] | None:
    if rect is None:
        return None
    origin = getattr(rect, 'origin', None)
    size = getattr(rect, 'size', None)
    if origin is not None and size is not None:
        return float(origin.x) + (float(size.width) / 2.0), float(origin.y) + (float(size.height) / 2.0)
    if isinstance(rect, Mapping):
        x = float(rect.get('x', rect.get('X', 0.0)))
        y = float(rect.get('y', rect.get('Y', 0.0)))
        width = float(rect.get('width', rect.get('Width', 0.0)))
        height = float(rect.get('height', rect.get('Height', 0.0)))
        return x + (width / 2.0), y + (height / 2.0)
    return None


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
