from __future__ import annotations

import argparse


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="realtime-stt-writer",
        description="Local macOS speech-to-text writer MVP",
    )
    parser.add_argument(
        "--config",
        default="config/default.yaml",
        help="Path to YAML config",
    )
    parser.add_argument(
        "command",
        choices=["start", "arm-target", "retry-last"],
        help="Command to run",
    )
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    print(f"Stub CLI command '{args.command}' using config '{args.config}'")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
