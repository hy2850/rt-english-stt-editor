# Realtime STT Writer

Local macOS MVP for turning spoken English into cleaned-up text and inserting it into the editor location under your mouse.

## What it does

- Captures **English speech** from the microphone
- Detects finalized utterances with silence-based endpointing
- Transcribes finalized audio with a pluggable STT boundary, starting with **`mlx-audio` + Cohere STT**
- Cleans transcript text with deterministic rule-based cleanup
- Formats finalized utterances for editor insertion
- Inserts text into a real macOS editor using click + clipboard-preserving paste

## Current project status

This branch contains the first runnable local prototype slice:

- macOS microphone/accessibility permission checks
- automatic current-mouse target arming when the live loop starts
- persistent target state under `.omx/runtime/active_anchor.json`
- queue-based live microphone capture
- energy-based endpointing for finalized speech segments
- live capture → endpointing → STT → cleanup → insertion loop
- injector smoke tests through clipboard-preserving paste
- unit tests for the implemented behavior

The active implementation plan is tracked in:

- `docs/plans/2026-04-05-macos-injector-permissions-live-audio.md`

## Normal workflow

There is one main command for the user-facing flow:

```bash
python3 -m realtime_stt_writer.app.main start
```

Before running it:

1. Open a text editor such as **TextEdit** or **Obsidian**.
2. Move the mouse to the desired insertion point.
3. Run `start`.
4. Speak in English.
5. The app finalizes utterances, transcribes them, cleans them up, and inserts final text into the editor.

`start` performs the setup automatically: it reports required permissions, stops if any are missing, arms the current mouse target, warms the STT engine, starts microphone capture, and runs the live transcription loop.

## Diagnostic commands

These are for development and smoke testing, not the normal user flow:

```bash
python3 -m realtime_stt_writer.app.main --help
python3 -m realtime_stt_writer.app.main start-capture
python3 -m realtime_stt_writer.app.main paste-demo --text "Hello from the injector."
```

- `start-capture` opens raw microphone capture until `Ctrl-C`.
- `paste-demo` inserts fixed text into the currently stored target and is useful for checking click + paste behavior.

Setup-only steps are handled by `start` to keep the public workflow simple.

## Tech used

- **Python 3.12**
- **stdlib `unittest`**
- **`sounddevice`** for microphone capture
- **`mlx-audio`** for STT model loading and transcription
- **PyObjC / macOS frameworks**
  - `AppKit`
  - `Quartz`
  - `ApplicationServices`
  - `AVFoundation`
- **setuptools / `pyproject.toml` packaging**

## Project structure

```text
realtime_stt_writer/
├─ app/        # CLI entrypoints and app bootstrap
├─ audio/      # capture and endpointing services
├─ cleanup/    # rule-based and future LLM cleanup pipeline
├─ domain/     # shared models and protocols
├─ inject/     # target arming and text insertion
├─ services/   # live loop and orchestration
└─ stt/        # speech-to-text engine adapters
```

## How to run locally

### 1. Use Python 3.12

```bash
python3 --version
```

### 2. Create a virtual environment

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Install the package in editable mode

```bash
python3 -m pip install -e .
```

On Apple Silicon macOS this installs the MLX STT runtime (`mlx` + `mlx-audio`). If `python3 -m realtime_stt_writer.app.main start` reports `No module named 'mlx_audio'`, rerun the editable install in the active virtualenv. If pip still skips `mlx-audio`, recreate the virtualenv with an arm64 Python instead of a Rosetta/x86_64 Python.

On macOS, grant the terminal app microphone and accessibility permissions when prompted or through System Settings.

### 4. Run the live workflow

```bash
python3 -m realtime_stt_writer.app.main start
```

## How to run tests

```bash
python3 -m unittest discover -s tests/unit -v
```

Optional sanity check:

```bash
python3 -m compileall realtime_stt_writer tests
```

## Configuration

Default config lives at:

- `config/default.yaml`

Current config surface includes:

- `audio`
- `endpointing`
- `stt`
- `cleanup`
- `injection`
- `hotkeys`

## Known limitations right now

- The live loop requires macOS permissions, microphone hardware, and the configured MLX STT model locally.
- No dedicated AX direct-text injector yet; the current prototype relies on click + clipboard-preserving paste fallback.
- No hotkey runtime yet.
- No menu bar app yet.
- Manual editor and microphone smoke checks still need to be run on macOS hardware.

## Development notes

- This project is intentionally **local-first**.
- Audio callbacks stay lightweight and only push frames into a queue.
- Endpointing, STT, cleanup, and insertion run outside the audio callback.
- macOS integration details stay behind interfaces.
- The repository uses **test-first development** for behavior changes.
- Commits should follow the repo’s **Lore commit protocol**.
