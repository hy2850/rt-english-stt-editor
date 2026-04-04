from __future__ import annotations


class ClipboardPreservingPasteInjector:
    def insert(self, text: str) -> None:
        raise NotImplementedError("Clipboard-preserving paste requires macOS AppKit bindings")
