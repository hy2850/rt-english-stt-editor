import unittest

from realtime_stt_writer.domain.models import TargetAnchor
from realtime_stt_writer.inject.hybrid_injector import HybridInjector
from realtime_stt_writer.inject.mac_click import MacClicker
from realtime_stt_writer.inject.mac_paste import ClipboardPreservingPasteInjector


class FakeAnchorService:
    def __init__(self, anchor: TargetAnchor | None) -> None:
        self._anchor = anchor

    def arm_from_current_mouse_position(self) -> TargetAnchor:
        raise NotImplementedError

    def set_active_anchor(self, anchor: TargetAnchor) -> None:
        self._anchor = anchor

    def get_active_anchor(self) -> TargetAnchor | None:
        return self._anchor


class RecordingClicker:
    def __init__(self) -> None:
        self.actions: list[tuple[str, object]] = []

    def click(self, x: float, y: float) -> None:
        self.actions.append(('click', (x, y)))


class RecordingPasteInjector:
    def __init__(self) -> None:
        self.actions: list[tuple[str, object]] = []

    def insert(self, text: str) -> None:
        self.actions.append(('paste', text))


class RecordingAXInjector:
    def __init__(self, result: bool) -> None:
        self.result = result
        self.calls: list[tuple[str, TargetAnchor]] = []

    def try_insert(self, text: str, anchor: TargetAnchor) -> bool:
        self.calls.append((text, anchor))
        return self.result


class RecordingClipboard:
    def __init__(self) -> None:
        self.actions: list[tuple[str, object | None]] = []

    def snapshot(self) -> object:
        self.actions.append(('snapshot', None))
        return {'value': 'before'}

    def write_text(self, text: str) -> None:
        self.actions.append(('write_text', text))

    def restore(self, snapshot: object) -> None:
        self.actions.append(('restore', snapshot))


class HybridInjectorTests(unittest.TestCase):
    def test_raises_when_no_target_is_armed(self) -> None:
        injector = HybridInjector(
            anchor_service=FakeAnchorService(None),
            paste_injector=RecordingPasteInjector(),
            clicker=RecordingClicker(),
        )

        with self.assertRaisesRegex(RuntimeError, 'armed'):
            injector.insert('Hello')

    def test_clicks_before_paste_when_anchor_exists(self) -> None:
        actions: list[tuple[str, object]] = []
        clicker = RecordingClicker()
        paste = RecordingPasteInjector()
        sleep_calls: list[float] = []
        anchor = TargetAnchor(x=10.0, y=20.0)
        injector = HybridInjector(
            anchor_service=FakeAnchorService(anchor),
            paste_injector=paste,
            clicker=clicker,
            sleep_fn=lambda seconds: sleep_calls.append(seconds),
        )

        injector.insert('Hello')
        actions.extend(clicker.actions)
        actions.extend(paste.actions)

        self.assertEqual(actions, [('click', (10.0, 20.0)), ('paste', 'Hello')])
        self.assertEqual(sleep_calls, [0.05])

    def test_uses_ax_direct_insert_only_when_it_succeeds(self) -> None:
        clicker = RecordingClicker()
        paste = RecordingPasteInjector()
        ax_injector = RecordingAXInjector(True)
        anchor = TargetAnchor(x=10.0, y=20.0)
        injector = HybridInjector(
            anchor_service=FakeAnchorService(anchor),
            paste_injector=paste,
            clicker=clicker,
            ax_injector=ax_injector,
        )

        injector.insert('Hello')

        self.assertEqual(ax_injector.calls, [('Hello', anchor)])
        self.assertEqual(clicker.actions, [])
        self.assertEqual(paste.actions, [])

    def test_falls_back_to_click_and_paste_when_ax_insert_returns_false(self) -> None:
        clicker = RecordingClicker()
        paste = RecordingPasteInjector()
        ax_injector = RecordingAXInjector(False)
        anchor = TargetAnchor(x=10.0, y=20.0)
        injector = HybridInjector(
            anchor_service=FakeAnchorService(anchor),
            paste_injector=paste,
            clicker=clicker,
            ax_injector=ax_injector,
            sleep_fn=lambda _seconds: None,
        )

        injector.insert('Hello')

        self.assertEqual(ax_injector.calls, [('Hello', anchor)])
        self.assertEqual(clicker.actions, [('click', (10.0, 20.0))])
        self.assertEqual(paste.actions, [('paste', 'Hello')])


class MacClickerTests(unittest.TestCase):
    def test_posts_all_generated_mouse_events(self) -> None:
        posted: list[str] = []
        clicker = MacClicker(
            event_factory=lambda x, y: ['mouse-down', 'mouse-up'],
            event_poster=posted.append,
        )

        clicker.click(10.0, 20.0)

        self.assertEqual(posted, ['mouse-down', 'mouse-up'])


class ClipboardPreservingPasteInjectorTests(unittest.TestCase):
    def test_restores_clipboard_after_paste(self) -> None:
        clipboard = RecordingClipboard()
        send_paste_calls: list[str] = []
        injector = ClipboardPreservingPasteInjector(
            clipboard=clipboard,
            send_paste=lambda: send_paste_calls.append('paste-shortcut'),
        )

        injector.insert('Hello')

        self.assertEqual(
            clipboard.actions,
            [
                ('snapshot', None),
                ('write_text', 'Hello'),
                ('restore', {'value': 'before'}),
            ],
        )
        self.assertEqual(send_paste_calls, ['paste-shortcut'])


if __name__ == '__main__':
    unittest.main()
