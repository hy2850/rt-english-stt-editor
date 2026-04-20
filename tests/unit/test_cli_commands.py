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
        self.start_error: Exception | None = None

    @property
    def is_running(self) -> bool:
        return self.started and not self.stopped

    def start(self) -> None:
        if self.start_error is not None:
            raise self.start_error
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


def main_help_text() -> str:
    from realtime_stt_writer.app.main import build_parser

    return build_parser().format_help()


class CLICommandTests(unittest.TestCase):
    def setUp(self) -> None:
        self.anchor = TargetAnchor(
            x=100.0,
            y=200.0,
            pid=501,
            bundle_id='com.apple.TextEdit',
            app_name='Dock',
        )
        self.runtime = FakeRuntime(
            permission_checkers=[
                FakePermissionChecker('accessibility', True, 'Accessibility granted'),
                FakePermissionChecker('microphone', True, 'Microphone granted'),
            ],
            anchor_service=FakeAnchorService(self.anchor),
            injector=FakeInjector(),
            microphone_capture=FakeCapture(),
            live_loop=FakeLiveLoop(),
        )


    def test_removed_setup_commands_are_not_public_cli_commands(self) -> None:
        help_text = main_help_text()

        self.assertNotIn('check-permissions', help_text)
        self.assertNotIn('arm-target', help_text)

    def test_paste_demo_command_injects_requested_text(self) -> None:
        stdout = io.StringIO()

        exit_code = main(
            ['paste-demo', '--text', 'Hello from the injector.'],
            stdout=stdout,
            bootstrap_factory=lambda _config_path, **_kwargs: self.runtime,
        )

        self.assertEqual(exit_code, 0)
        self.assertEqual(self.runtime.injector.inserted, ['Hello from the injector.'])
        self.assertIn('inserted', stdout.getvalue().lower())

    def test_start_capture_command_starts_capture_service(self) -> None:
        stdout = io.StringIO()

        exit_code = main(
            ['start-capture'],
            stdout=stdout,
            bootstrap_factory=lambda _config_path, **_kwargs: self.runtime,
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
            bootstrap_factory=lambda _config_path, **_kwargs: self.runtime,
            live_runner=lambda loop, _stdout: loop.stop(),
        )

        self.assertEqual(exit_code, 0)
        output = stdout.getvalue().lower()
        self.assertEqual(self.runtime.anchor_service.arm_calls, 1)
        self.assertTrue(self.runtime.live_loop.started)
        self.assertTrue(self.runtime.live_loop.stopped)
        self.assertIn('accessibility: granted', output)
        self.assertIn('microphone: granted', output)
        self.assertIn('armed target', output)
        self.assertIn('warning: target appears to be dock', output)
        self.assertIn('listening for english speech', output)

    def test_start_exits_before_arming_when_permissions_are_missing(self) -> None:
        stdout = io.StringIO()
        self.runtime.permission_checkers = [
            FakePermissionChecker('accessibility', False, 'Accessibility missing'),
            FakePermissionChecker('microphone', True, 'Microphone granted'),
        ]

        exit_code = main(
            ['start'],
            stdout=stdout,
            bootstrap_factory=lambda _config_path, **_kwargs: self.runtime,
            live_runner=lambda loop, _stdout: loop.stop(),
        )

        self.assertEqual(exit_code, 1)
        self.assertEqual(self.runtime.anchor_service.arm_calls, 0)
        self.assertFalse(self.runtime.live_loop.started)
        self.assertIn('cannot start until missing permissions', stdout.getvalue().lower())

    def test_start_reports_live_loop_start_errors_without_traceback(self) -> None:
        stdout = io.StringIO()
        self.runtime.live_loop.start_error = RuntimeError('mlx-audio is required; run python3 -m pip install -e .')

        exit_code = main(
            ['start'],
            stdout=stdout,
            bootstrap_factory=lambda _config_path, **_kwargs: self.runtime,
            live_runner=lambda loop, _stdout: loop.stop(),
        )

        self.assertEqual(exit_code, 1)
        self.assertIn('cannot start live transcription', stdout.getvalue().lower())
        self.assertIn('mlx-audio is required', stdout.getvalue().lower())


if __name__ == '__main__':
    unittest.main()
