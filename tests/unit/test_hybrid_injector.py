import unittest

from realtime_stt_writer.domain.models import TargetAnchor
from realtime_stt_writer.inject.hybrid_injector import HybridInjector
from realtime_stt_writer.inject.mac_click import MacClicker
from realtime_stt_writer.inject.mac_click import build_click_events
from realtime_stt_writer.inject.mac_paste import ClipboardPreservingPasteInjector
from realtime_stt_writer.inject.mac_paste import post_command_v_events
from realtime_stt_writer.inject.mac_paste import write_text_to_pasteboard


class FakeAnchorService:
    def __init__(self, anchor: TargetAnchor | None, *, arm_results: list[TargetAnchor | None] | None = None) -> None:
        self._anchor = anchor
        self.arm_results = list(arm_results or [])
        self.arm_calls = 0

    def arm_from_current_mouse_position(self) -> TargetAnchor:
        self.arm_calls += 1
        if self.arm_results:
            next_anchor = self.arm_results.pop(0)
            if next_anchor is None:
                self._anchor = None
                raise RuntimeError('Target is not armed')
            self._anchor = next_anchor
            return next_anchor
        if self._anchor is None:
            raise RuntimeError('Target is not armed')
        return self._anchor

    def set_active_anchor(self, anchor: TargetAnchor) -> None:
        self._anchor = anchor

    def get_active_anchor(self) -> TargetAnchor | None:
        return self._anchor


class RecordingLogger:
    def __init__(self) -> None:
        self.lines: list[str] = []

    def write(self, message: str) -> None:
        self.lines.append(message)


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

    def read_text(self) -> str:
        return next((value for action, value in reversed(self.actions) if action == 'write_text'), '')

    def restore(self, snapshot: object) -> None:
        self.actions.append(('restore', snapshot))


class FakePasteboard:
    def __init__(self, *, set_result: bool = True, stored_text: str | None = None) -> None:
        self.set_result = set_result
        self.stored_text = stored_text
        self.calls: list[tuple[str, object]] = []

    def clearContents(self) -> None:
        self.calls.append(('clearContents', None))

    def declareTypes_owner_(self, types, owner) -> None:
        self.calls.append(('declareTypes_owner_', list(types)))

    def setString_forType_(self, text: str, pasteboard_type: str) -> bool:
        self.calls.append(('setString_forType_', (text, pasteboard_type)))
        if self.set_result:
            self.stored_text = text
        return self.set_result

    def stringForType_(self, pasteboard_type: str) -> str | None:
        self.calls.append(('stringForType_', pasteboard_type))
        return self.stored_text


class HybridInjectorTests(unittest.TestCase):
    def test_raises_when_no_target_is_armed(self) -> None:
        injector = HybridInjector(
            anchor_service=FakeAnchorService(None),
            paste_injector=RecordingPasteInjector(),
            clicker=RecordingClicker(),
        )

        with self.assertRaisesRegex(RuntimeError, 'armed'):
            injector.insert('Hello')

    def test_rearms_from_current_mouse_position_for_each_insert(self) -> None:
        first = TargetAnchor(x=10.0, y=20.0)
        second = TargetAnchor(x=30.0, y=40.0)
        anchor_service = FakeAnchorService(None, arm_results=[first, second])
        clicker = RecordingClicker()
        paste = RecordingPasteInjector()
        logger = RecordingLogger()
        injector = HybridInjector(
            anchor_service=anchor_service,
            paste_injector=paste,
            clicker=clicker,
            sleep_fn=lambda _seconds: None,
            logger=logger,
        )

        injector.insert('First')
        injector.insert('Second')

        self.assertEqual(anchor_service.arm_calls, 2)
        self.assertEqual(clicker.actions, [('click', (10.0, 20.0)), ('click', (30.0, 40.0))])
        self.assertEqual(paste.actions, [('paste', 'First'), ('paste', 'Second')])
        self.assertIn('[target] current pointer target: unknown app at (10.0, 20.0)', logger.lines)
        self.assertIn('[target] current pointer target: unknown app at (30.0, 40.0)', logger.lines)

    def test_manual_target_override_is_used_until_updated(self) -> None:
        first = TargetAnchor(x=10.0, y=20.0)
        second = TargetAnchor(x=30.0, y=40.0)
        anchor_service = FakeAnchorService(None, arm_results=[TargetAnchor(x=99.0, y=99.0)])
        clicker = RecordingClicker()
        paste = RecordingPasteInjector()
        injector = HybridInjector(
            anchor_service=anchor_service,
            paste_injector=paste,
            clicker=clicker,
            sleep_fn=lambda _seconds: None,
        )

        injector.set_target_override(first)
        injector.insert('First')
        injector.set_target_override(second)
        injector.insert('Second')

        self.assertEqual(anchor_service.arm_calls, 0)
        self.assertEqual(clicker.actions, [('click', (10.0, 20.0)), ('click', (30.0, 40.0))])
        self.assertEqual(paste.actions, [('paste', 'First'), ('paste', 'Second')])

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
        self.assertEqual(sleep_calls, [0.2])

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
    def test_build_click_events_moves_then_marks_down_and_up_as_a_click(self) -> None:
        flag_calls: list[tuple[object, object, object]] = []

        def create_mouse_event(_source, event_type, point, button):
            return {'event_type': event_type, 'point': point, 'button': button}

        events = build_click_events(
            10.0,
            20.0,
            point_factory=lambda x, y: (x, y),
            create_mouse_event=create_mouse_event,
            set_integer_field=lambda event, field, value: flag_calls.append((event.copy(), field, value)),
            event_types={'move': 'move', 'down': 'down', 'up': 'up'},
            button='left',
            click_state_field='click-state',
        )

        self.assertEqual(
            events,
            [
                {'event_type': 'move', 'point': (10.0, 20.0), 'button': 'left'},
                {'event_type': 'down', 'point': (10.0, 20.0), 'button': 'left'},
                {'event_type': 'up', 'point': (10.0, 20.0), 'button': 'left'},
            ],
        )
        self.assertEqual(
            flag_calls,
            [
                ({'event_type': 'down', 'point': (10.0, 20.0), 'button': 'left'}, 'click-state', 1),
                ({'event_type': 'up', 'point': (10.0, 20.0), 'button': 'left'}, 'click-state', 1),
            ],
        )

    def test_posts_all_generated_mouse_events(self) -> None:
        posted: list[str] = []
        clicker = MacClicker(
            event_factory=lambda x, y: ['mouse-down', 'mouse-up'],
            event_poster=posted.append,
        )

        clicker.click(10.0, 20.0)

        self.assertEqual(posted, ['mouse-down', 'mouse-up'])


class ClipboardPreservingPasteInjectorTests(unittest.TestCase):
    def test_write_text_to_pasteboard_declares_string_type_and_verifies_readback(self) -> None:
        pasteboard = FakePasteboard()

        write_text_to_pasteboard(pasteboard, 'new transcript', pasteboard_type='public.utf8-plain-text')

        self.assertEqual(
            pasteboard.calls,
            [
                ('clearContents', None),
                ('declareTypes_owner_', ['public.utf8-plain-text']),
                ('setString_forType_', ('new transcript', 'public.utf8-plain-text')),
                ('stringForType_', 'public.utf8-plain-text'),
            ],
        )

    def test_write_text_to_pasteboard_raises_when_text_cannot_be_verified(self) -> None:
        pasteboard = FakePasteboard(set_result=False, stored_text='old content')

        with self.assertRaisesRegex(RuntimeError, 'Failed to write text to clipboard'):
            write_text_to_pasteboard(pasteboard, 'new transcript', pasteboard_type='public.utf8-plain-text')

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

    def test_restores_clipboard_when_write_text_fails(self) -> None:
        class FailingClipboard(RecordingClipboard):
            def write_text(self, text: str) -> None:
                self.actions.append(('write_text', text))
                raise RuntimeError('write failed')

        clipboard = FailingClipboard()
        injector = ClipboardPreservingPasteInjector(
            clipboard=clipboard,
            send_paste=lambda: None,
            sleep_fn=lambda _seconds: None,
        )

        with self.assertRaisesRegex(RuntimeError, 'write failed'):
            injector.insert('Hello')

        self.assertEqual(
            clipboard.actions,
            [
                ('snapshot', None),
                ('write_text', 'Hello'),
                ('restore', {'value': 'before'}),
            ],
        )

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
