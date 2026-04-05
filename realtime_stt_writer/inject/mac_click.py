from __future__ import annotations

import sys
from dataclasses import dataclass, field
from typing import Callable
from typing import Iterable


MouseEventFactory = Callable[[float, float], Iterable[object]]
MouseEventPoster = Callable[[object], None]


@dataclass(slots=True)
class MacClicker:
    event_factory: MouseEventFactory = field(default_factory=lambda: _create_click_events)
    event_poster: MouseEventPoster = field(default_factory=lambda: _post_mouse_event)

    def click(self, x: float, y: float) -> None:
        for event in self.event_factory(x, y):
            self.event_poster(event)


def _create_click_events(x: float, y: float) -> list[object]:
    if sys.platform != 'darwin':
        raise RuntimeError('Synthetic click is only available on macOS.')

    try:
        from Quartz import CGEventCreateMouseEvent
        from Quartz import CGPointMake
        from Quartz import kCGEventLeftMouseDown
        from Quartz import kCGEventLeftMouseUp
        from Quartz import kCGMouseButtonLeft
    except ImportError as exc:
        raise RuntimeError('Quartz bindings are required for synthetic mouse clicks.') from exc

    point = CGPointMake(x, y)
    return [
        CGEventCreateMouseEvent(None, kCGEventLeftMouseDown, point, kCGMouseButtonLeft),
        CGEventCreateMouseEvent(None, kCGEventLeftMouseUp, point, kCGMouseButtonLeft),
    ]


def _post_mouse_event(event: object) -> None:
    if sys.platform != 'darwin':
        raise RuntimeError('Synthetic click is only available on macOS.')

    try:
        from Quartz import CGEventPost
        from Quartz import kCGHIDEventTap
    except ImportError as exc:
        raise RuntimeError('Quartz bindings are required for synthetic mouse clicks.') from exc

    CGEventPost(kCGHIDEventTap, event)
