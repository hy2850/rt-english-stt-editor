from __future__ import annotations

from dataclasses import dataclass

from realtime_stt_writer.domain.protocols import TargetAnchorService


@dataclass(slots=True)
class HybridInjector:
    anchor_service: TargetAnchorService
    paste_injector: object
    clicker: object | None = None
    ax_injector: object | None = None

    def insert(self, text: str) -> None:
        anchor = self.anchor_service.get_active_anchor()
        if anchor is None:
            raise RuntimeError("Target is not armed")

        if self.ax_injector is not None and hasattr(self.ax_injector, "try_insert"):
            if self.ax_injector.try_insert(text, anchor):
                return

        if self.clicker is not None and hasattr(self.clicker, "click"):
            self.clicker.click(anchor.x, anchor.y)

        self.paste_injector.insert(text)
