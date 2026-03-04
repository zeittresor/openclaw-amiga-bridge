---
name: amiga_bridge
description: Send AmigaDOS commands to a WinUAE/Amiga system via shared-folder job queue and fetch screenshots.
tools:
  - bash
---

# Amiga Bridge Skill

This skill assumes you have **ClawBridge** installed on Windows and the Amiga-side listener **clawd.rexx** running.

## Commands (Windows-side)

- Send an AmigaDOS command:
  - `python clawbridge.py send --base "<WINDOWS_SHARED_BASE>\openclaw" --cmd "dir SYS:" --wait`

- Capture a screenshot of WinUAE:
  - `python clawbridge.py snap --base "<WINDOWS_SHARED_BASE>\openclaw" --window "WinUAE"`

## If running OpenClaw in WSL2

WSL can call Windows executables directly. Example:

- `cmd.exe /c C:\path\to\openclaw-amiga-bridge\windows\run_cli_examples.bat`

For production, point OpenClaw to the actual `python.exe` inside the bridge venv or bundle it into an `.exe`.
