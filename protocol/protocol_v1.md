# OpenClaw ↔ Amiga Bridge Protocol (v1)

This bridge uses a **shared folder** (Directory Filesystem in WinUAE / "Shared" in Amiga Forever) as a simple,
robust message bus.

It avoids JSON on the Amiga side. Messages are plain text key/value files.

## Folder layout

Base folder (example): `Shared:openclaw/`

- `in/`  → jobs (written by Windows)
- `out/` → results (written by Amiga)
- `snap/` → screenshots (written by Windows)
- `log/` → logs (optional)

## Job file format (`*.job`)

Text file, ASCII/UTF‑8:

```
CLAWJOB 1
id=20260304_101500_ab12cd
action=run
cwd=Work:Projects/MyDemo
cmd=dir
wait_ms=0
```

### Keys

- `id` (required) : unique id, also used for result filename
- `action` (required) : `run` | `stop`
- `cwd` (optional) : directory used for the command execution (only for `run`)
- `cmd` (required for `run`) : AmigaDOS command line
- `wait_ms` (optional) : delay after completion (helps with programs that flush slowly)

## Result file format (`*.res`)

```
CLAWRES 1
id=20260304_101500_ab12cd
ok=1
rc=0
output=... (single line; long output is stored in output_file)
output_file=Shared:openclaw/out/20260304_101500_ab12cd.out
```

### Notes

- The daemon always writes an `*.out` file containing the full captured output (best-effort).
- `rc` is the AmigaDOS return code (as exposed by ARexx variable `RC`).

## Screenshot files

Windows writes PNG files to `snap/`:

`YYYYMMDD_HHMMSS_winuae.png`

OpenClaw can ingest these files as images for vision analysis.

