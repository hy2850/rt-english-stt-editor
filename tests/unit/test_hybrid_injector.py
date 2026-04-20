import unittest

from realtime_stt_writer.domain.models import TargetAnchor
from realtime_stt_writer.inject.hybrid_injector import HybridInjector
from realtime_stt_writer.inject.mac_click import MacClicker
from realtime_stt_writer.inject.mac_paste import ClipboardPreservingPasteInjector
from realtime_stt_writer.inject.mac_paste import post_command_v_events


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
    def test_restores_clipboard_after_paste_event_has_time_to_complete(self) -> None:
        clipboard = RecordingClipboard()
        actions: list[tuple[str, object | None]] = []
        injector = ClipboardPreservingPasteInjector(
            clipboard=clipboard,
            send_paste=lambda: actions.append(('paste-shortcut', None)),
            sleep_fn=lambda seconds: actions.append(('sleep', seconds)),
            paste_settle_delay_seconds=0.2,
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
        self.assertEqual(actions, [('paste-shortcut', None), ('sleep', 0.2)])

    def test_command_v_events_are_flagged_with_quartz_function(self) -> None:
        calls: list[tuple[str, object]] = []

        def create_keyboard_event(_source, keycode: int, is_down: bool) -> dict[str, object]:
            return {'keycode': keycode, 'is_down': is_down}

        post_command_v_events(
            create_keyboard_event=create_keyboard_event,
            set_flags=lambda event, flags: calls.append(('flags', event.copy(), flags)),
            post_event=lambda tap, event: calls.append(('post', tap, event.copy())),
            command_flag=1048576,
            event_tap='hid',
        )

        self.assertEqual(
            calls,
            [
                ('flags', {'keycode': 9, 'is_down': True}, 1048576),
                ('flags', {'keycode': 9, 'is_down': False}, 1048576),
                ('post', 'hid', {'keycode': 9, 'is_down': True}),
                ('post', 'hid', {'keycode': 9, 'is_down': False}),
            ],
        )


if __name__ == '__main__':
    unittest.main()
