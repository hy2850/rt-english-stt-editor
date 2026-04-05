from __future__ import annotations

import argparse
import sys
import time
from typing import Callable
from typing import Sequence
from typing import TextIO

from realtime_stt_writer.app.bootstrap import build_runtime
from realtime_stt_writer.domain.models import TargetAnchor


CaptureRunner = Callable[[object, TextIO], None]


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
    subparsers = parser.add_subparsers(dest='command', required=True)
    subparsers.add_parser('check-permissions', help='Report live macOS permission status')
    subparsers.add_parser('arm-target', help='Arm the current mouse target for later paste injection')
    paste_demo = subparsers.add_parser('paste-demo', help='Inject demo text into the armed target')
    paste_demo.add_argument('--text', required=True, help='Text to insert into the armed target')
    subparsers.add_parser('start-capture', help='Start live microphone capture until interrupted')
    subparsers.add_parser('start', help='Reserved for the full runtime loop')
    subparsers.add_parser('retry-last', help='Reserved for retrying the last insert')
    return parser


def main(
    argv: Sequence[str] | None = None,
    *,
    stdout: TextIO | None = None,
    bootstrap_factory=build_runtime,
    capture_runner: CaptureRunner | None = None,
) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    out = stdout or sys.stdout
    runtime = bootstrap_factory(args.config)

    if args.command == 'check-permissions':
        statuses = [checker.check() for checker in runtime.permission_checkers]
        out.write(_render_permission_statuses(statuses))
        return 0

    if args.command == 'arm-target':
        anchor = runtime.anchor_service.arm_from_current_mouse_position()
        out.write(f'Armed target: {_describe_anchor(anchor)}\n')
        return 0

    if args.command == 'paste-demo':
        runtime.injector.insert(args.text)
        out.write(f'Inserted demo text into {_describe_anchor(runtime.anchor_service.get_active_anchor())}.\n')
        return 0

    if args.command == 'start-capture':
        runtime.microphone_capture.start()
        out.write('Capture started. Press Ctrl-C to stop.\n')
        runner = capture_runner or _run_capture_session
        runner(runtime.microphone_capture, out)
        return 0

    out.write(f"Command '{args.command}' is not wired yet.\n")
    return 0


def _render_permission_statuses(statuses: Sequence[dict[str, object]]) -> str:
    lines = []
    for status in statuses:
        state = 'granted' if status['granted'] else 'missing'
        lines.append(f"{status['name']}: {state} - {status['detail']}")
    return '\n'.join(lines) + ('\n' if lines else '')


def _describe_anchor(anchor: TargetAnchor | None) -> str:
    if anchor is None:
        return 'unarmed target'

    label = anchor.app_name or anchor.bundle_id or f'pid={anchor.pid}' if anchor.pid is not None else 'unknown app'
    return f'{label} at ({anchor.x:.1f}, {anchor.y:.1f})'


def _run_capture_session(capture: object, stdout: TextIO) -> None:
    try:
        while getattr(capture, 'is_running', False):
            time.sleep(0.25)
    except KeyboardInterrupt:
        stdout.write('Stopping capture...\n')
    finally:
        if hasattr(capture, 'stop'):
            capture.stop()
        stdout.write('Capture stopped.\n')


if __name__ == '__main__':
    raise SystemExit(main())
