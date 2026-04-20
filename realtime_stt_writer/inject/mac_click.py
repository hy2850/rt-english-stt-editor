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
        from Quartz import CGEventSetIntegerValueField
        from Quartz import CGPointMake
        from Quartz import kCGEventLeftMouseDown
        from Quartz import kCGEventLeftMouseUp
        from Quartz import kCGEventMouseMoved
        from Quartz import kCGMouseButtonLeft
        from Quartz import kCGMouseEventClickState
    except ImportError as exc:
        raise RuntimeError('Quartz bindings are required for synthetic mouse clicks.') from exc

    return build_click_events(
        x,
        y,
        point_factory=CGPointMake,
        create_mouse_event=CGEventCreateMouseEvent,
        set_integer_field=CGEventSetIntegerValueField,
        event_types={
            'move': kCGEventMouseMoved,
            'down': kCGEventLeftMouseDown,
            'up': kCGEventLeftMouseUp,
        },
        button=kCGMouseButtonLeft,
        click_state_field=kCGMouseEventClickState,
    )


def build_click_events(
    x: float,
    y: float,
    *,
    point_factory,
    create_mouse_event,
    set_integer_field,
    event_types,
    button,
    click_state_field,
) -> list[object]:
    point = point_factory(x, y)
    move = create_mouse_event(None, event_types['move'], point, button)
    down = create_mouse_event(None, event_types['down'], point, button)
    up = create_mouse_event(None, event_types['up'], point, button)
    set_integer_field(down, click_state_field, 1)
    set_integer_field(up, click_state_field, 1)
    return [move, down, up]


def _post_mouse_event(event: object) -> None:
    if sys.platform != 'darwin':
        raise RuntimeError('Synthetic click is only available on macOS.')

    try:
        from Quartz import CGEventPost
        from Quartz import kCGHIDEventTap
    except ImportError as exc:
        raise RuntimeError('Quartz bindings are required for synthetic mouse clicks.') from exc

    CGEventPost(kCGHIDEventTap, event)
