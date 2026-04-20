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
LiveRunner = Callable[[object, TextIO], None]


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
    paste_demo = subparsers.add_parser('paste-demo', help='Inject demo text into the armed target')
    paste_demo.add_argument('--text', required=True, help='Text to insert into the armed target')
    subparsers.add_parser('start-capture', help='Start raw microphone capture until interrupted')
    subparsers.add_parser('start', help='Start live English speech transcription and insertion')
    subparsers.add_parser('retry-last', help='Reserved for retrying the last insert')
    return parser


def main(
    argv: Sequence[str] | None = None,
    *,
    stdout: TextIO | None = None,
    bootstrap_factory=build_runtime,
    capture_runner: CaptureRunner | None = None,
    live_runner: LiveRunner | None = None,
) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    out = stdout or sys.stdout
    runtime = bootstrap_factory(args.config, stdout=out)


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

    if args.command == 'start':
        statuses = [checker.check() for checker in runtime.permission_checkers]
        out.write(_render_permission_statuses(statuses))
        if any(not status['granted'] for status in statuses):
            out.write('Cannot start until missing permissions are granted.\n')
            return 1

        out.write('Pointer target will be resolved for each insertion; keep the mouse over the desired editor insertion point.\n')
        try:
            runtime.live_loop.start()
        except RuntimeError as exc:
            out.write(f'Cannot start live transcription: {exc}\n')
            return 1
        out.write('Listening for English speech. Press Ctrl-C to stop.\n')
        runner = live_runner or _run_live_session
        runner(runtime.live_loop, out)
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

    if anchor.app_name:
        label = anchor.app_name
    elif anchor.bundle_id:
        label = anchor.bundle_id
    elif anchor.pid is not None:
        label = f'pid={anchor.pid}'
    else:
        label = 'unknown app'
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


def _run_live_session(loop: object, stdout: TextIO) -> None:
    try:
        if hasattr(loop, 'run_until_interrupted'):
            loop.run_until_interrupted()
        else:
            while getattr(loop, 'is_running', False):
                time.sleep(0.25)
    except KeyboardInterrupt:
        pass
    finally:
        if getattr(loop, 'is_running', False) and hasattr(loop, 'stop'):
            loop.stop()
        stdout.write('Live transcription stopped.\n')


if __name__ == '__main__':
    raise SystemExit(main())
