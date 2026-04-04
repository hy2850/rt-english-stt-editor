# macOS Injector, Permissions, and Live Audio Capture Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add the next end-to-end MVP slice: real macOS target arming and paste injection, startup permission checks, and non-blocking live microphone capture.

**Architecture:** Keep the current boundary-first design. Implement macOS-specific behavior behind the existing injector and anchor interfaces, add a dedicated audio capture module that only pushes frames/events, and wire everything through the CLI without letting OS/audio details leak into the orchestrator. Follow @superpowers:test-driven-development for every behavior change.

**Tech Stack:** Python 3.12, stdlib `unittest`, `sounddevice`, PyObjC (`AppKit`, `Quartz`, `ApplicationServices`), existing package layout in `realtime_stt_writer/`

---

## Batch objective

This batch should end with a manually runnable local prototype that can:

1. verify microphone + accessibility permissions,
2. arm a target from the current mouse position on macOS,
3. click and paste a provided sentence into a real editor,
4. start live microphone capture without blocking the main thread,
5. expose the above through CLI commands that are useful for manual testing.

Do **not** expand scope into hotkeys, full STT live streaming, menu bar UI, or remote services in this batch.

---

### Task 1: Add permission checks as a first-class service

**Files:**
- Create: `realtime_stt_writer/inject/mac_permissions.py`
- Modify: `realtime_stt_writer/domain/protocols.py`
- Modify: `realtime_stt_writer/app/main.py`
- Modify: `tests/unit/test_cli_commands.py`
- Create: `tests/unit/test_permissions.py`

**Step 1: Write the failing permission tests**

Add tests that assert:
- accessibility permission state is reported as `granted` / `missing`
- microphone permission check can be represented without crashing on non-macOS test runners
- CLI status output surfaces both permissions before starting live features

**Step 2: Run the targeted tests to verify they fail**

Run:

```bash
python3 -m unittest tests.unit.test_permissions tests.unit.test_cli_commands -v
```

Expected: import errors or assertion failures because no permission service exists yet.

**Step 3: Write the minimal implementation**

Implement a small macOS permission module with:
- `AccessibilityPermissionChecker`
- `MicrophonePermissionChecker`
- a normalized result shape like `{"name": "...", "granted": bool, "detail": str}`

Keep platform-specific imports inside functions/methods so unit tests still run on non-macOS/Linux environments.

**Step 4: Wire permission reporting into the CLI**

Extend `realtime_stt_writer/app/main.py` to add a `check-permissions` command and shared formatting for permission status output.

**Step 5: Run the tests again**

Run:

```bash
python3 -m unittest tests.unit.test_permissions tests.unit.test_cli_commands -v
```

Expected: PASS

**Step 6: Commit**

```bash
git add realtime_stt_writer/inject/mac_permissions.py realtime_stt_writer/domain/protocols.py realtime_stt_writer/app/main.py tests/unit/test_permissions.py tests/unit/test_cli_commands.py
git commit -m "Surface macOS runtime permission checks"
```

---

### Task 2: Replace the in-memory anchor stub with a real macOS anchor service

**Files:**
- Modify: `realtime_stt_writer/inject/anchor.py`
- Modify: `realtime_stt_writer/domain/models.py`
- Modify: `realtime_stt_writer/domain/protocols.py`
- Create: `tests/unit/test_anchor_service.py`

**Step 1: Write the failing anchor tests**

Add tests for:
- setting and retrieving the active anchor
- converting a low-level platform response into `TargetAnchor`
- refusing to arm when the current pointer target cannot be resolved

**Step 2: Run the targeted tests to verify they fail**

Run:

```bash
python3 -m unittest tests.unit.test_anchor_service -v
```

Expected: FAIL because `arm_from_current_mouse_position()` is still unimplemented.

**Step 3: Write the minimal implementation**

Refactor `realtime_stt_writer/inject/anchor.py` into:
- a reusable state holder for the active anchor
- a macOS-backed service that reads current mouse coordinates
- optional metadata capture (`pid`, `bundle_id`, `app_name`) if the AX element lookup succeeds

Keep the low-level pointer and AX calls in private helpers so they can be stubbed in tests.

**Step 4: Run the tests again**

Run:

```bash
python3 -m unittest tests.unit.test_anchor_service -v
```

Expected: PASS

**Step 5: Commit**

```bash
git add realtime_stt_writer/inject/anchor.py realtime_stt_writer/domain/models.py realtime_stt_writer/domain/protocols.py tests/unit/test_anchor_service.py
git commit -m "Implement macOS target arming from mouse position"
```

---

### Task 3: Implement real click + clipboard-preserving paste injection

**Files:**
- Modify: `realtime_stt_writer/inject/mac_click.py`
- Modify: `realtime_stt_writer/inject/mac_paste.py`
- Modify: `realtime_stt_writer/inject/hybrid_injector.py`
- Create: `tests/unit/test_hybrid_injector.py`

**Step 1: Write the failing injector tests**

Add tests that verify:
- injector raises if no target is armed
- injector clicks before paste when anchor exists
- injector uses AX direct insert only when it returns success
- injector falls back to paste when AX direct insert returns false

**Step 2: Run the targeted tests to verify they fail**

Run:

```bash
python3 -m unittest tests.unit.test_hybrid_injector -v
```

Expected: FAIL because the current implementation does not fully define the behavior contract.

**Step 3: Write the minimal implementation**

Implement:
- real synthetic left-click in `mac_click.py`
- clipboard snapshot / temporary replacement / restore in `mac_paste.py`
- a small wait/order guarantee in `hybrid_injector.py` so click happens before paste

Hide PyObjC imports behind runtime guards and return actionable errors when running off macOS.

**Step 4: Run the tests again**

Run:

```bash
python3 -m unittest tests.unit.test_hybrid_injector -v
```

Expected: PASS

**Step 5: Perform a manual smoke check**

Run:

```bash
python3 -m realtime_stt_writer.app.main arm-target
python3 -m realtime_stt_writer.app.main paste-demo --text "This is a test."
```

Expected: with a real editor open on macOS, the text is inserted at the armed location.

**Step 6: Commit**

```bash
git add realtime_stt_writer/inject/mac_click.py realtime_stt_writer/inject/mac_paste.py realtime_stt_writer/inject/hybrid_injector.py tests/unit/test_hybrid_injector.py
git commit -m "Add real macOS click and paste injection"
```

---

### Task 4: Add non-blocking live microphone capture

**Files:**
- Create: `realtime_stt_writer/audio/capture.py`
- Modify: `realtime_stt_writer/audio/__init__.py`
- Create: `tests/unit/test_audio_capture.py`
- Modify: `config/default.yaml`

**Step 1: Write the failing audio capture tests**

Add tests for:
- callback pushes frames into a queue without doing heavy work
- capture service starts and stops cleanly
- sample-rate and channel config are carried into the stream builder

Use fakes instead of real microphone devices in unit tests.

**Step 2: Run the targeted tests to verify they fail**

Run:

```bash
python3 -m unittest tests.unit.test_audio_capture -v
```

Expected: FAIL because no capture module exists yet.

**Step 3: Write the minimal implementation**

Create a `MicrophoneCapture` service that:
- wraps `sounddevice.InputStream`
- writes frames to a queue
- exposes `start()`, `stop()`, and `is_running`
- performs no STT, cleanup, or injection work in the callback

Keep dependency imports guarded so the module fails with a clear message if `sounddevice` is not installed.

**Step 4: Run the tests again**

Run:

```bash
python3 -m unittest tests.unit.test_audio_capture -v
```

Expected: PASS

**Step 5: Commit**

```bash
git add realtime_stt_writer/audio/capture.py realtime_stt_writer/audio/__init__.py config/default.yaml tests/unit/test_audio_capture.py
git commit -m "Add queue-based live microphone capture"
```

---

### Task 5: Wire CLI commands for manual end-to-end batch verification

**Files:**
- Modify: `realtime_stt_writer/app/main.py`
- Create: `realtime_stt_writer/app/bootstrap.py`
- Modify: `realtime_stt_writer/inject/anchor.py`
- Modify: `realtime_stt_writer/audio/capture.py`
- Modify: `tests/unit/test_cli_commands.py`

**Step 1: Write the failing CLI workflow tests**

Add tests for:
- `check-permissions`
- `arm-target`
- `listen-once` or `start-capture`
- `paste-demo --text ...`

The tests should verify command dispatch and service wiring, not real OS effects.

**Step 2: Run the targeted tests to verify they fail**

Run:

```bash
python3 -m unittest tests.unit.test_cli_commands -v
```

Expected: FAIL because the current CLI only prints a stub message.

**Step 3: Write the minimal implementation**

Create a small bootstrap module that assembles:
- permission checkers
- anchor service
- paste injector
- microphone capture service

Update `main.py` so commands trigger real behavior and produce human-readable output for manual testing.

**Step 4: Run the tests again**

Run:

```bash
python3 -m unittest tests.unit.test_cli_commands -v
```

Expected: PASS

**Step 5: Manual verification on macOS**

Run:

```bash
python3 -m realtime_stt_writer.app.main check-permissions
python3 -m realtime_stt_writer.app.main arm-target
python3 -m realtime_stt_writer.app.main paste-demo --text "Hello from the injector."
python3 -m realtime_stt_writer.app.main start-capture
```

Expected:
- permission report is readable,
- anchor command stores a real mouse target,
- paste demo inserts into TextEdit and Obsidian,
- capture starts without blocking or crashing.

**Step 6: Commit**

```bash
git add realtime_stt_writer/app/main.py realtime_stt_writer/app/bootstrap.py realtime_stt_writer/inject/anchor.py realtime_stt_writer/audio/capture.py tests/unit/test_cli_commands.py
git commit -m "Expose injector and audio services through the CLI"
```

---

### Task 6: Full regression pass and batch closeout

**Files:**
- Modify: `README.md`
- Modify: `docs/plans/2026-04-05-macos-injector-permissions-live-audio.md`

**Step 1: Run the full automated test suite**

Run:

```bash
python3 -m unittest discover -s tests/unit -v
```

Expected: PASS

**Step 2: Run bytecode compilation**

Run:

```bash
python3 -m compileall realtime_stt_writer tests
```

Expected: PASS

**Step 3: Perform manual acceptance checks**

Verify on macOS:
- TextEdit insertion works
- Obsidian insertion works
- clipboard contents are restored after paste
- denied permissions produce actionable output
- starting/stopping capture leaves no hung audio stream

**Step 4: Document any deviations**

If the implemented shape differs from this plan, update this plan file and `README.md` to match reality before final handoff.

**Step 5: Commit**

```bash
git add README.md docs/plans/2026-04-05-macos-injector-permissions-live-audio.md
git commit -m "Document macOS injector and live capture workflow"
```

---

## Notes for the implementer

- Stay local-only; do not add remote APIs in this batch.
- Do not build hotkeys yet; the CLI is enough for manual validation.
- Keep heavy work out of callbacks and away from low-level macOS event helpers.
- Prefer explicit runtime errors over silent no-ops when permissions or macOS-only dependencies are missing.
- Keep commits small and Lore-compliant.
