import unittest

from realtime_stt_writer.inject.mac_permissions import AccessibilityPermissionChecker
from realtime_stt_writer.inject.mac_permissions import MicrophonePermissionChecker


class PermissionCheckerTests(unittest.TestCase):
    def test_accessibility_checker_reports_granted_state(self) -> None:
        checker = AccessibilityPermissionChecker(probe=lambda: True, platform='darwin')

        status = checker.check()

        self.assertEqual(status['name'], 'accessibility')
        self.assertTrue(status['granted'])
        self.assertIn('granted', status['detail'].lower())

    def test_accessibility_checker_reports_missing_state(self) -> None:
        checker = AccessibilityPermissionChecker(
            probe=lambda: False,
            prompt_requester=lambda: None,
            process_identity=lambda: 'current app: Python (/tmp/.venv/bin/python3); parent process: Terminal',
            platform='darwin',
        )

        status = checker.check()

        detail = status['detail'].lower()
        self.assertFalse(status['granted'])
        self.assertIn('missing', detail)
        self.assertIn('restart', detail)
        self.assertIn('current app: python', detail)
        self.assertIn('parent process: terminal', detail)

    def test_accessibility_checker_requests_prompt_when_missing(self) -> None:
        prompts: list[bool] = []
        checker = AccessibilityPermissionChecker(
            probe=lambda: False,
            prompt_requester=lambda: prompts.append(True),
            platform='darwin',
        )

        status = checker.check()

        self.assertFalse(status['granted'])
        self.assertEqual(prompts, [True])
        self.assertIn('terminal app', status['detail'].lower())
        self.assertIn('rerun', status['detail'].lower())

    def test_accessibility_checker_reports_binding_errors_separately(self) -> None:
        checker = AccessibilityPermissionChecker(
            probe=lambda: (_ for _ in ()).throw(RuntimeError('AX API unavailable')),
            platform='darwin',
        )

        status = checker.check()

        self.assertFalse(status['granted'])
        self.assertIn('unable to check accessibility', status['detail'].lower())
        self.assertIn('ax api unavailable', status['detail'].lower())

    def test_microphone_checker_is_safe_on_non_macos(self) -> None:
        checker = MicrophonePermissionChecker(platform='linux')

        status = checker.check()

        self.assertEqual(status['name'], 'microphone')
        self.assertFalse(status['granted'])
        self.assertIn('macos', status['detail'].lower())


if __name__ == '__main__':
    unittest.main()
