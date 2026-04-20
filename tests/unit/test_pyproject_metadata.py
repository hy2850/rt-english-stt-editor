from __future__ import annotations

import tomllib
import unittest
from pathlib import Path


class PyprojectMetadataTests(unittest.TestCase):
    def test_pyobjc_appkit_import_uses_cocoa_distribution(self) -> None:
        pyproject = tomllib.loads(Path('pyproject.toml').read_text())
        dependencies = pyproject['project']['dependencies']
        dependency_names = {dependency.split(';', 1)[0].split('>=', 1)[0].strip() for dependency in dependencies}

        self.assertIn('pyobjc-framework-Cocoa', dependency_names)
        self.assertNotIn('pyobjc-framework-AppKit', dependency_names)

    def test_mlx_audio_runtime_dependency_is_declared_for_apple_silicon(self) -> None:
        pyproject = tomllib.loads(Path('pyproject.toml').read_text())
        dependencies = pyproject['project']['dependencies']

        self.assertTrue(any(dependency.startswith('mlx>=') for dependency in dependencies))
        self.assertTrue(any(dependency.startswith('mlx-audio==0.4.2') for dependency in dependencies))
        self.assertTrue(any("platform_machine == 'arm64'" in dependency for dependency in dependencies if dependency.startswith('mlx-audio')))


if __name__ == '__main__':
    unittest.main()
