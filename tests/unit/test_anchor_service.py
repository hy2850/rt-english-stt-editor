import tempfile
import unittest
from pathlib import Path

from realtime_stt_writer.domain.models import TargetAnchor
from realtime_stt_writer.inject.anchor import MacOSTargetAnchorService
from realtime_stt_writer.inject.anchor import TargetAnchorState


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
