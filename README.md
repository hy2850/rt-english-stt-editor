# Realtime STT Writer

Local macOS MVP for turning spoken English into cleaned-up text and inserting it into a text editor at an armed target location.

## What it does

- Captures **English speech** from the microphone
- Transcribes it with a pluggable STT boundary, starting with **`mlx-audio` + Cohere STT**
- Cleans transcript text with:
  - rule-based filler removal
  - repetition collapse
  - optional local LLM grammar correction
- Formats finalized utterances for editor insertion
- Targets a text editor location via a stored mouse/anchor concept
- Inserts only **final sentences**, not noisy partial transcripts

## Current project status

This repository currently contains the **foundation MVP scaffold**:

- domain models and protocols
- cleanup pipeline
- formatting helpers
- orchestrator with duplicate-insert guard
- STT adapter boundary for Cohere MLX
- injector and audio service scaffolding
- unit tests for the current core behavior

The next batch is planned in:

- `docs/plans/2026-04-05-macos-injector-permissions-live-audio.md`

## Planned user-facing MVP flow

1. Open a text editor such as **TextEdit** or **Obsidian**
2. Move the mouse to the desired insertion point
3. Arm that target
4. Start listening
5. Speak in English
6. Let the app finalize the sentence, clean it up, and insert it into the editor

## Features

- **Pluggable architecture**
  - STT, cleanup, segmentation, and injection are separated behind interfaces
- **Meaning-preserving cleanup**
  - prioritizes removing fillers and fixing obvious grammar without rewriting intent
- **Final-sentence insertion**
  - avoids dumping unstable partial ASR output into the editor
- **Hybrid macOS insertion direction**
  - designed around click + clipboard-preserving paste, with room for AX-based optimization later
- **Queue-oriented runtime design**
  - intended to keep audio callbacks lightweight and push heavier work to workers/services

## Tech used

### Current codebase

- **Python 3.12**
- **stdlib `unittest`**
- **setuptools / `pyproject.toml` packaging**

### Planned runtime integrations

- **`mlx-audio`** for STT model loading and transcription
- **`sounddevice`** for live microphone capture
- **PyObjC / macOS frameworks**
  - `AppKit`
  - `Quartz`
  - `ApplicationServices`
- optionally **`mlx-lm`** for local cleanup LLM behavior

## Project structure

```text
realtime_stt_writer/
├─ app/        # CLI entrypoints and app bootstrap
├─ audio/      # capture and segmentation services
├─ cleanup/    # rule-based and LLM cleanup pipeline
├─ domain/     # shared models and protocols
├─ inject/     # target arming and text insertion
├─ services/   # orchestration
└─ stt/        # speech-to-text engine adapters
```

## How to run

### 1. Use Python 3.12

```bash
python3 --version
```

### 2. (Recommended) Create a virtual environment

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Install the package in editable mode

```bash
python3 -m pip install -e .
```

### 4. Run the current CLI stub

```bash
python3 -m realtime_stt_writer.app.main --help
python3 -m realtime_stt_writer.app.main start
python3 -m realtime_stt_writer.app.main arm-target
python3 -m realtime_stt_writer.app.main retry-last
```

At the moment, the CLI is still mostly a scaffold and does not yet perform real macOS injection or live capture.

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

- No real macOS Accessibility integration yet
- No live microphone capture implementation yet
- No fully wired end-to-end STT loop yet
- No hotkey runtime yet
- No menu bar app yet

## Development notes

- This project is intentionally **local-first**
- The architecture is designed so macOS integration details stay behind interfaces
- The repository uses **test-first development** for behavior changes
- Commits should follow the repo’s **Lore commit protocol**
