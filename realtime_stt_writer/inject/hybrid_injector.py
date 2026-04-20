from __future__ import annotations

import time
from dataclasses import dataclass
from dataclasses import field
from typing import Callable
from typing import Protocol

from realtime_stt_writer.domain.protocols import TargetAnchorService


class RuntimeLogger(Protocol):
    def write(self, message: str) -> None: ...


@dataclass(slots=True)
class HybridInjector:
    anchor_service: TargetAnchorService
    paste_injector: object
    clicker: object | None = None
    ax_injector: object | None = None
    post_click_delay_seconds: float = 0.2
    sleep_fn: Callable[[float], None] = field(default_factory=lambda: time.sleep)
    logger: RuntimeLogger | None = None
    pointer_line_step_px: float = 24.0

    def insert(self, text: str) -> None:
        anchor = self.anchor_service.arm_from_current_mouse_position()
        self._log(f'[target] current pointer target: {_describe_anchor(anchor)}')

        if self.ax_injector is not None and hasattr(self.ax_injector, 'try_insert'):
            if self.ax_injector.try_insert(text, anchor):
                self._advance_pointer(anchor)
                return

        if self.clicker is not None and hasattr(self.clicker, 'click'):
            self.clicker.click(anchor.x, anchor.y)
            self.sleep_fn(self.post_click_delay_seconds)

        self.paste_injector.insert(text)
        self._advance_pointer(anchor)

    def _advance_pointer(self, anchor) -> None:
        if self.clicker is not None and hasattr(self.clicker, 'move'):
            next_y = anchor.y + self.pointer_line_step_px
            self.clicker.move(anchor.x, next_y)
            self._log(f'[target] advanced pointer to next line at ({anchor.x:.1f}, {next_y:.1f})')

    def _log(self, message: str) -> None:
        if self.logger is not None:
            self.logger.write(message)


def _describe_anchor(anchor) -> str:
    if anchor.app_name:
        label = anchor.app_name
    elif anchor.bundle_id:
        label = anchor.bundle_id
    elif anchor.pid is not None:
        label = f'pid={anchor.pid}'
    else:
        label = 'unknown app'
    return f'{label} at ({anchor.x:.1f}, {anchor.y:.1f})'
