import io
import unittest
from dataclasses import dataclass

from realtime_stt_writer.app.main import main
from realtime_stt_writer.domain.models import TargetAnchor


class FakePermissionChecker:
    def __init__(self, name: str, granted: bool, detail: str) -> None:
        self._status = {'name': name, 'granted': granted, 'detail': detail}

    def check(self) -> dict[str, object]:
        return dict(self._status)


class FakeAnchorService:
    def __init__(self, anchor: TargetAnchor) -> None:
        self.anchor = anchor
        self.arm_calls = 0

    def arm_from_current_mouse_position(self) -> TargetAnchor:
        self.arm_calls += 1
        return self.anchor

    def set_active_anchor(self, anchor: TargetAnchor) -> None:
        self.anchor = anchor

    def get_active_anchor(self) -> TargetAnchor:
        return self.anchor


class FakeInjector:
    def __init__(self) -> None:
        self.inserted: list[str] = []

    def insert(self, text: str) -> None:
        self.inserted.append(text)


class FakeLiveLoop:
    def __init__(self) -> None:
        self.started = False
        self.stopped = False

    @property
    def is_running(self) -> bool:
        return self.started and not self.stopped

    def start(self) -> None:
        self.started = True

    def stop(self) -> None:
        self.stopped = True


class FakeCapture:
    def __init__(self) -> None:
        self.started = False
        self.stopped = False

    @property
    def is_running(self) -> bool:
        return self.started and not self.stopped

    def start(self) -> None:
        self.started = True

    def stop(self) -> None:
        self.stopped = True


@dataclass(slots=True)
class FakeRuntime:
    permission_checkers: list[object]
    anchor_service: object
    injector: object
    microphone_capture: object
    live_loop: object


class CLICommandTests(unittest.TestCase):
    def setUp(self) -> None:
        self.anchor = TargetAnchor(
            x=100.0,
            y=200.0,
            pid=501,
            bundle_id='com.apple.TextEdit',
            app_name='TextEdit',
        )
        self.runtime = FakeRuntime(
            permission_checkers=[
                FakePermissionChecker('accessibility', True, 'Accessibility granted'),
                FakePermissionChecker('microphone', False, 'Microphone missing'),
            ],
            anchor_service=FakeAnchorService(self.anchor),
            injector=FakeInjector(),
            microphone_capture=FakeCapture(),
            live_loop=FakeLiveLoop(),
        )

    def test_check_permissions_command_reports_both_permissions(self) -> None:
        stdout = io.StringIO()

        exit_code = main(
            ['check-permissions'],
            stdout=stdout,
            bootstrap_factory=lambda _config_path: self.runtime,
        )

        output = stdout.getvalue().lower()
        self.assertEqual(exit_code, 0)
        self.assertIn('accessibility: granted', output)
        self.assertIn('microphone: missing', output)

    def test_arm_target_command_uses_anchor_service(self) -> None:
        stdout = io.StringIO()

        exit_code = main(
            ['arm-target'],
            stdout=stdout,
            bootstrap_factory=lambda _config_path: self.runtime,
        )

        self.assertEqual(exit_code, 0)
        self.assertEqual(self.runtime.anchor_service.arm_calls, 1)
        self.assertIn('textedit', stdout.getvalue().lower())

    def test_paste_demo_command_injects_requested_text(self) -> None:
        stdout = io.StringIO()

        exit_code = main(
            ['paste-demo', '--text', 'Hello from the injector.'],
            stdout=stdout,
            bootstrap_factory=lambda _config_path: self.runtime,
        )

        self.assertEqual(exit_code, 0)
        self.assertEqual(self.runtime.injector.inserted, ['Hello from the injector.'])
        self.assertIn('inserted', stdout.getvalue().lower())

    def test_start_capture_command_starts_capture_service(self) -> None:
        stdout = io.StringIO()

        exit_code = main(
            ['start-capture'],
            stdout=stdout,
            bootstrap_factory=lambda _config_path: self.runtime,
            capture_runner=lambda capture, _stdout: capture.stop(),
        )

        self.assertEqual(exit_code, 0)
        self.assertTrue(self.runtime.microphone_capture.started)
        self.assertTrue(self.runtime.microphone_capture.stopped)
        self.assertIn('capture started', stdout.getvalue().lower())

    def test_start_command_starts_live_transcription_loop(self) -> None:
        stdout = io.StringIO()

        exit_code = main(
            ['start'],
            stdout=stdout,
            bootstrap_factory=lambda _config_path: self.runtime,
            live_runner=lambda loop, _stdout: loop.stop(),
        )

        self.assertEqual(exit_code, 0)
        self.assertTrue(self.runtime.live_loop.started)
        self.assertTrue(self.runtime.live_loop.stopped)
        self.assertIn('listening for english speech', stdout.getvalue().lower())


if __name__ == '__main__':
    unittest.main()
