import io
import unittest
from dataclasses import dataclass

from realtime_stt_writer.app.main import main


@dataclass(slots=True)
class FakeRuntime:
    permission_checkers: list[object]


class FakePermissionChecker:
    def __init__(self, name: str, granted: bool, detail: str) -> None:
        self._status = {'name': name, 'granted': granted, 'detail': detail}

    def check(self) -> dict[str, object]:
        return dict(self._status)


class CLICommandTests(unittest.TestCase):
    def test_check_permissions_command_reports_both_permissions(self) -> None:
        stdout = io.StringIO()
        runtime = FakeRuntime(
            permission_checkers=[
                FakePermissionChecker('accessibility', True, 'Accessibility granted'),
                FakePermissionChecker('microphone', False, 'Microphone missing'),
            ]
        )

        exit_code = main(
            ['check-permissions'],
            stdout=stdout,
            bootstrap_factory=lambda _config_path: runtime,
        )

        output = stdout.getvalue()
        self.assertEqual(exit_code, 0)
        self.assertIn('accessibility: granted', output.lower())
        self.assertIn('microphone: missing', output.lower())


if __name__ == '__main__':
    unittest.main()
