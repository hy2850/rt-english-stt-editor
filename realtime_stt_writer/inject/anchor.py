from __future__ import annotations

from dataclasses import dataclass, field

from realtime_stt_writer.domain.models import TargetAnchor


@dataclass(slots=True)
class InMemoryTargetAnchorService:
    active_anchor: TargetAnchor | None = field(default=None)

    def arm_from_current_mouse_position(self) -> TargetAnchor:
        raise NotImplementedError("macOS mouse capture is not available in this environment")

    def set_active_anchor(self, anchor: TargetAnchor) -> None:
        self.active_anchor = anchor

    def get_active_anchor(self) -> TargetAnchor | None:
        return self.active_anchor
