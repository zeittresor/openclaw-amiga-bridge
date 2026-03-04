# openclaw-amiga-bridge

A experimental shared-folder bridge between **OpenClaw (Windows/WSL2)** and an **Amiga system running in WinUAE**.

It consists of:

- **Windows Bridge** (`windows/`): Python CLI + Tkinter GUI
  - Sends jobs (`*.job`) into a shared folder
  - Waits for results (`*.res` + `*.out`)
  - Captures **WinUAE window screenshots** into `snap/` (PNG)
- **Amiga Listener** (`amiga/clawd.rexx`): ARexx daemon
  - Polls `in/` for jobs
  - Executes AmigaDOS commands
  - Captures output into `out/`

This design avoids pixel-fragile RPA. **Vision screenshots are optional**, used for “what’s on screen?” verification.

---

## 1) Requirements

### Windows
- Windows 10/11
- Python 3.10+ (recommended)
- WinUAE or Amiga Forever (Cloanto)
- A shared folder mapped into the Amiga as a volume (Directory Filesystem / “Shared”)

### Amiga (emulated)
- AmigaOS 2.x / 3.x
- `RexxMast` running (standard on most setups)

---

## 2) Folder layout (shared)

Pick (or create) a Windows folder, e.g.:

`C:\Amiga\Shared\openclaw`

Inside it the bridge will create:

- `in/`  (jobs)
- `out/` (results)
- `snap/` (screenshots)
- `log/` (logs)

On the Amiga side, the same folder should be visible as:

`Shared:openclaw/`

---

## 3) Amiga setup

1. Copy `amiga/clawd.rexx` somewhere reachable from the Amiga (e.g. inside `Shared:openclaw/amiga/`).

2. Start it in background:

```
Run >NIL: RX Shared:openclaw/amiga/clawd.rexx Shared:openclaw
```

To stop, use the Windows CLI command `stop` (see below).

---

## 4) Windows setup

Open a terminal in `windows/` and run:

- `install_windows.bat`

Then run:

- `run_gui.bat`

Or use the CLI:

```
python clawbridge.py send --base "C:\Amiga\Shared\openclaw" --cmd "version" --wait
python clawbridge.py snap --base "C:\Amiga\Shared\openclaw" --window "WinUAE" --open
```

---

## 5) Using with OpenClaw (WSL2)

OpenClaw runs in WSL2 on Windows. From WSL you can call Windows programs, e.g.:

```
cmd.exe /c C:\path\to\openclaw-amiga-bridge\windows\run_cli_examples.bat
```

For an OpenClaw skill, see: `openclaw_skill/amiga_bridge/SKILL.md`

---

## 6) Security / Safety

`clawd.rexx` executes AmigaDOS commands coming from the shared folder.
Treat it like SSH on a LAN:
- Only use a shared folder that is not writable by untrusted users/processes.
- Consider adding a whitelist inside `clawd.rexx` if you want to restrict allowed commands.

---

## 7) Troubleshooting

### “TIMEOUT waiting for .res”
- Listener not running on Amiga
- Wrong shared folder mapping (Windows base path != Amiga `Shared:` volume)
- `RexxMast` not running

### Screenshot captures full screen
- Window title substring not found. Set `--window` to match your WinUAE title (e.g. `"WinUAE - A500"`).

---

## 8) Protocol details

See `protocol/protocol_v1.md`.

