from __future__ import annotations

import argparse
import sys
from types import SimpleNamespace
from typing import Sequence
from typing import TextIO

from realtime_stt_writer.inject.mac_permissions import AccessibilityPermissionChecker
from realtime_stt_writer.inject.mac_permissions import MicrophonePermissionChecker


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog='realtime-stt-writer',
        description='Local macOS speech-to-text writer MVP',
    )
    parser.add_argument(
        '--config',
        default='config/default.yaml',
        help='Path to YAML config',
    )
    parser.add_argument(
        'command',
        choices=['start', 'arm-target', 'retry-last', 'check-permissions'],
        help='Command to run',
    )
    return parser


def main(
    argv: Sequence[str] | None = None,
    *,
    stdout: TextIO | None = None,
    bootstrap_factory=None,
) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    out = stdout or sys.stdout
    factory = bootstrap_factory or _build_runtime
    runtime = factory(args.config)

    if args.command == 'check-permissions':
        statuses = [checker.check() for checker in runtime.permission_checkers]
        out.write(_render_permission_statuses(statuses))
        return 0

    out.write(f"Stub CLI command '{args.command}' using config '{args.config}'\n")
    return 0


def _build_runtime(_config_path: str):
    return SimpleNamespace(
        permission_checkers=[
            AccessibilityPermissionChecker(),
            MicrophonePermissionChecker(),
        ]
    )


def _render_permission_statuses(statuses: Sequence[dict[str, object]]) -> str:
    lines = []
    for status in statuses:
        state = 'granted' if status['granted'] else 'missing'
        lines.append(f"{status['name']}: {state} - {status['detail']}")
    return '\n'.join(lines) + ('\n' if lines else '')


if __name__ == '__main__':
    raise SystemExit(main())
