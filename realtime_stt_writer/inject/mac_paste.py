from __future__ import annotations

import sys
from dataclasses import dataclass, field
from typing import Callable


@dataclass(slots=True)
class ClipboardPreservingPasteInjector:
    clipboard: object = field(default_factory=lambda: MacClipboard())
    send_paste: Callable[[], None] = field(default_factory=lambda: _send_command_v)

    def insert(self, text: str) -> None:
        snapshot = self.clipboard.snapshot()
        self.clipboard.write_text(text)
        try:
            self.send_paste()
        finally:
            self.clipboard.restore(snapshot)


class MacClipboard:
    def snapshot(self) -> list[dict[str, bytes]]:
        pasteboard = _general_pasteboard()
        items = pasteboard.pasteboardItems() or []
        snapshot: list[dict[str, bytes]] = []
        for item in items:
            entry: dict[str, bytes] = {}
            for data_type in item.types() or []:
                data = item.dataForType_(data_type)
                if data is not None:
                    entry[str(data_type)] = bytes(data)
            snapshot.append(entry)
        return snapshot

    def write_text(self, text: str) -> None:
        pasteboard = _general_pasteboard()
        pasteboard.clearContents()
        pasteboard.setString_forType_(text, 'public.utf8-plain-text')

    def restore(self, snapshot: list[dict[str, bytes]]) -> None:
        pasteboard = _general_pasteboard()
        pasteboard.clearContents()
        if not snapshot:
            return

        try:
            from AppKit import NSData
            from AppKit import NSPasteboardItem
        except ImportError as exc:
            raise RuntimeError('AppKit bindings are required to restore clipboard contents.') from exc

        items = []
        for entry in snapshot:
            item = NSPasteboardItem.alloc().init()
            for data_type, payload in entry.items():
                item.setData_forType_(NSData.dataWithBytes_length_(payload, len(payload)), data_type)
            items.append(item)
        pasteboard.writeObjects_(items)


def _general_pasteboard():
    if sys.platform != 'darwin':
        raise RuntimeError('Clipboard-preserving paste is only available on macOS.')

    try:
        from AppKit import NSPasteboard
    except ImportError as exc:
        raise RuntimeError('AppKit bindings are required for clipboard-preserving paste.') from exc

    return NSPasteboard.generalPasteboard()


def _send_command_v() -> None:
    if sys.platform != 'darwin':
        raise RuntimeError('Clipboard-preserving paste is only available on macOS.')

    try:
        from Quartz import CGEventCreateKeyboardEvent
        from Quartz import CGEventPost
        from Quartz import kCGEventFlagMaskCommand
        from Quartz import kCGHIDEventTap
    except ImportError as exc:
        raise RuntimeError('Quartz bindings are required to send the paste shortcut.') from exc

    keycode_v = 9
    key_down = CGEventCreateKeyboardEvent(None, keycode_v, True)
    key_up = CGEventCreateKeyboardEvent(None, keycode_v, False)
    key_down.setFlags_(kCGEventFlagMaskCommand)
    key_up.setFlags_(kCGEventFlagMaskCommand)
    CGEventPost(kCGHIDEventTap, key_down)
    CGEventPost(kCGHIDEventTap, key_up)
