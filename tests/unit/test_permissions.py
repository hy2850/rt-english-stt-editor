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
        checker = AccessibilityPermissionChecker(probe=lambda: False, platform='darwin')

        status = checker.check()

        self.assertFalse(status['granted'])
        self.assertIn('missing', status['detail'].lower())

    def test_microphone_checker_is_safe_on_non_macos(self) -> None:
        checker = MicrophonePermissionChecker(platform='linux')

        status = checker.check()

        self.assertEqual(status['name'], 'microphone')
        self.assertFalse(status['granted'])
        self.assertIn('macos', status['detail'].lower())


if __name__ == '__main__':
    unittest.main()
