import tempfile
import unittest
from pathlib import Path

from realtime_stt_writer.domain.models import TargetAnchor
from realtime_stt_writer.inject.anchor import MacOSTargetAnchorService
from realtime_stt_writer.inject.anchor import _ax_copy_attribute
from realtime_stt_writer.inject.anchor import _ax_copy_parameterized_attribute
from realtime_stt_writer.inject.anchor import TargetAnchorState


class AccessibilityHelperTests(unittest.TestCase):
    def test_ax_copy_attribute_supports_two_argument_pyobjc_shape(self) -> None:
        calls: list[tuple[object, object]] = []

        def copy_attribute(element, attribute):
            calls.append((element, attribute))
            return (0, 'value')

        self.assertEqual(_ax_copy_attribute(copy_attribute, 'element', 'attribute'), 'value')
        self.assertEqual(calls, [('element', 'attribute')])

    def test_ax_copy_parameterized_attribute_supports_two_argument_pyobjc_shape(self) -> None:
        calls: list[tuple[object, object, object]] = []

        def copy_parameterized(element, attribute, parameter):
            calls.append((element, attribute, parameter))
            return (0, {'x': 1, 'y': 2, 'width': 3, 'height': 4})

        value = _ax_copy_parameterized_attribute(copy_parameterized, 'element', 'bounds', 'range')

        self.assertEqual(value, {'x': 1, 'y': 2, 'width': 3, 'height': 4})
        self.assertEqual(calls, [('element', 'bounds', 'range')])


class TargetAnchorStateTests(unittest.TestCase):
    def test_setting_and_getting_active_anchor(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            state = TargetAnchorState(storage_path=Path(temp_dir) / 'anchor.json')
            anchor = TargetAnchor(x=12.5, y=34.5, pid=42, bundle_id='com.example.Editor', app_name='Editor')

            state.set_active_anchor(anchor)

            self.assertEqual(state.get_active_anchor(), anchor)


class MacOSTargetAnchorServiceTests(unittest.TestCase):
    def test_arms_from_pointer_and_platform_response(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            state = TargetAnchorState(storage_path=Path(temp_dir) / 'anchor.json')
            service = MacOSTargetAnchorService(
                state=state,
                pointer_provider=lambda: (100.0, 200.0),
                target_resolver=lambda x, y: {
                    'pid': 501,
                    'bundle_id': 'com.apple.TextEdit',
                    'app_name': 'TextEdit',
                },
            )

            anchor = service.arm_from_current_mouse_position()

            self.assertEqual(
                anchor,
                TargetAnchor(
                    x=100.0,
                    y=200.0,
                    pid=501,
                    bundle_id='com.apple.TextEdit',
                    app_name='TextEdit',
                ),
            )
            self.assertEqual(service.get_active_anchor(), anchor)


    def test_prefers_focused_text_cursor_over_mouse_pointer(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            state = TargetAnchorState(storage_path=Path(temp_dir) / 'anchor.json')
            pointer_calls: list[str] = []
            service = MacOSTargetAnchorService(
                state=state,
                pointer_provider=lambda: pointer_calls.append('pointer') or (100.0, 200.0),
                target_resolver=lambda x, y: {
                    'pid': 501,
                    'bundle_id': 'com.apple.TextEdit',
                    'app_name': 'TextEdit',
                },
                insertion_cursor_provider=lambda: {
                    'x': 300.0,
                    'y': 400.0,
                    'pid': 777,
                    'bundle_id': 'md.obsidian',
                    'app_name': 'Obsidian',
                },
            )

            anchor = service.arm_from_current_mouse_position()

            self.assertEqual(
                anchor,
                TargetAnchor(
                    x=300.0,
                    y=400.0,
                    pid=777,
                    bundle_id='md.obsidian',
                    app_name='Obsidian',
                ),
            )
            self.assertEqual(pointer_calls, [])

    def test_falls_back_to_mouse_pointer_when_text_cursor_is_unavailable(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            state = TargetAnchorState(storage_path=Path(temp_dir) / 'anchor.json')
            service = MacOSTargetAnchorService(
                state=state,
                pointer_provider=lambda: (100.0, 200.0),
                target_resolver=lambda x, y: {
                    'pid': 501,
                    'bundle_id': 'com.apple.TextEdit',
                    'app_name': 'TextEdit',
                },
                insertion_cursor_provider=lambda: None,
            )

            anchor = service.arm_from_current_mouse_position()

            self.assertEqual(anchor.x, 100.0)
            self.assertEqual(anchor.y, 200.0)
            self.assertEqual(anchor.app_name, 'TextEdit')

    def test_refuses_to_arm_when_target_cannot_be_resolved(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            state = TargetAnchorState(storage_path=Path(temp_dir) / 'anchor.json')
            service = MacOSTargetAnchorService(
                state=state,
                pointer_provider=lambda: (100.0, 200.0),
                target_resolver=lambda x, y: None,
            )

            with self.assertRaisesRegex(RuntimeError, 'resolve'):
                service.arm_from_current_mouse_position()

            self.assertIsNone(service.get_active_anchor())


if __name__ == '__main__':
    unittest.main()
