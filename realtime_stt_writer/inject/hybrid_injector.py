from __future__ import annotations

import time
from dataclasses import dataclass
from dataclasses import field
from typing import Callable

from realtime_stt_writer.domain.protocols import TargetAnchorService


@dataclass(slots=True)
class HybridInjector:
    anchor_service: TargetAnchorService
    paste_injector: object
    clicker: object | None = None
    ax_injector: object | None = None
    post_click_delay_seconds: float = 0.05
    sleep_fn: Callable[[float], None] = field(default_factory=lambda: time.sleep)

    def insert(self, text: str) -> None:
        anchor = self.anchor_service.arm_from_current_mouse_position()

        if self.ax_injector is not None and hasattr(self.ax_injector, 'try_insert'):
            if self.ax_injector.try_insert(text, anchor):
                return

        if self.clicker is not None and hasattr(self.clicker, 'click'):
            self.clicker.click(anchor.x, anchor.y)
            self.sleep_fn(self.post_click_delay_seconds)

        self.paste_injector.insert(text)
