#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ClawBridge (Windows)
- Sends jobs to an Amiga-side listener via a shared folder
- Waits for results
- Captures WinUAE window screenshots into the same shared folder

Usage:
  python clawbridge.py send --base "C:\...\openclaw" --cmd "dir" [--cwd "Work:"] [--wait]
  python clawbridge.py snap --base "C:\...\openclaw" [--window "WinUAE"] [--open]

Designed to be callable from OpenClaw (via cmd.exe / PowerShell, also from WSL2).
"""

from __future__ import annotations

import argparse
import ctypes
import ctypes.wintypes as wt
import os
import sys
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Tuple, List

try:
    from PIL import ImageGrab
except Exception as e:
    ImageGrab = None  # type: ignore


MAGIC_JOB = "CLAWJOB 1"
MAGIC_RES = "CLAWRES 1"


def _now_id() -> str:
    # deterministic-ish but unique enough
    return time.strftime("%Y%m%d_%H%M%S") + "_" + uuid.uuid4().hex[:6]


def atomic_write_text(path: Path, text: str) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8", newline="\n")
    # On Windows, replace is atomic-ish on same filesystem
    tmp.replace(path)


def ensure_layout(base: Path) -> dict:
    base.mkdir(parents=True, exist_ok=True)
    d = {}
    for name in ["in", "out", "snap", "log"]:
        p = base / name
        p.mkdir(parents=True, exist_ok=True)
        d[name] = p
    return d


def parse_kv_file(path: Path) -> dict:
    data = {}
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    # first line magic
    for ln in lines[1:]:
        ln = ln.strip()
        if not ln or ln.startswith("#") or ln.startswith(";"):
            continue
        if "=" in ln:
            k, v = ln.split("=", 1)
            data[k.strip()] = v.strip()
    return data


def wait_for_result(out_dir: Path, job_id: str, timeout_s: float = 60.0, poll_s: float = 0.2) -> Tuple[Optional[Path], Optional[Path]]:
    res = out_dir / f"{job_id}.res"
    out = out_dir / f"{job_id}.out"
    t0 = time.time()
    while True:
        if res.exists():
            return res, out if out.exists() else None
        if time.time() - t0 > timeout_s:
            return None, out if out.exists() else None
        time.sleep(poll_s)


# ----------------- Win32 window helpers (no pywin32 needed) -----------------

user32 = ctypes.WinDLL("user32", use_last_error=True)

EnumWindowsProc = ctypes.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM)

user32.EnumWindows.argtypes = [EnumWindowsProc, wt.LPARAM]
user32.EnumWindows.restype = wt.BOOL

user32.GetWindowTextLengthW.argtypes = [wt.HWND]
user32.GetWindowTextLengthW.restype = ctypes.c_int

user32.GetWindowTextW.argtypes = [wt.HWND, wt.LPWSTR, ctypes.c_int]
user32.GetWindowTextW.restype = ctypes.c_int

user32.IsWindowVisible.argtypes = [wt.HWND]
user32.IsWindowVisible.restype = wt.BOOL

user32.GetWindowRect.argtypes = [wt.HWND, ctypes.POINTER(wt.RECT)]
user32.GetWindowRect.restype = wt.BOOL


def list_top_windows() -> List[Tuple[int, str]]:
    out: List[Tuple[int, str]] = []

    @EnumWindowsProc
    def cb(hwnd, lparam):
        if not user32.IsWindowVisible(hwnd):
            return True
        length = user32.GetWindowTextLengthW(hwnd)
        if length <= 0:
            return True
        buf = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, buf, length + 1)
        title = buf.value
        if title:
            out.append((int(hwnd), title))
        return True

    user32.EnumWindows(cb, 0)
    return out


def find_window_by_substring(needle: str) -> Optional[int]:
    needle_l = needle.lower()
    for hwnd, title in list_top_windows():
        if needle_l in title.lower():
            return hwnd
    return None


def get_window_rect(hwnd: int) -> Optional[Tuple[int, int, int, int]]:
    rect = wt.RECT()
    if not user32.GetWindowRect(wt.HWND(hwnd), ctypes.byref(rect)):
        return None
    left, top, right, bottom = rect.left, rect.top, rect.right, rect.bottom
    if right <= left or bottom <= top:
        return None
    return left, top, right, bottom


def capture_window_png(hwnd: Optional[int], outfile: Path) -> Path:
    if ImageGrab is None:
        raise RuntimeError("Pillow ImageGrab not available. Install requirements.txt.")
    if hwnd is None:
        # Full screen capture
        img = ImageGrab.grab(all_screens=True)
    else:
        box = get_window_rect(hwnd)
        if not box:
            img = ImageGrab.grab(all_screens=True)
        else:
            img = ImageGrab.grab(bbox=box)
    outfile.parent.mkdir(parents=True, exist_ok=True)
    img.save(outfile, "PNG")
    return outfile


def open_file_in_default_app(path: Path) -> None:
    os.startfile(str(path))  # noqa


# ----------------- Commands -----------------

def cmd_send(args: argparse.Namespace) -> int:
    base = Path(args.base).expanduser()
    layout = ensure_layout(base)
    job_id = args.id or _now_id()

    job_lines = [
        MAGIC_JOB,
        f"id={job_id}",
        "action=run",
    ]
    if args.cwd:
        job_lines.append(f"cwd={args.cwd}")
    job_lines.append(f"cmd={args.cmd}")
    if args.wait_ms is not None:
        job_lines.append(f"wait_ms={int(args.wait_ms)}")

    job_text = "\n".join(job_lines) + "\n"
    job_path = layout["in"] / f"{job_id}.job"
    atomic_write_text(job_path, job_text)

    if not args.wait:
        print(job_id)
        return 0

    res_path, out_path = wait_for_result(layout["out"], job_id, timeout_s=float(args.timeout))
    if res_path is None:
        print(f"TIMEOUT waiting for {job_id}.res after {args.timeout}s", file=sys.stderr)
        if out_path and out_path.exists():
            print(out_path.read_text(encoding="utf-8", errors="replace"))
        return 2

    data = parse_kv_file(res_path)
    ok = data.get("ok", "0") == "1"
    rc = data.get("rc", "")
    output_file = data.get("output_file", "")
    # Print output (prefer .out file)
    if out_path and out_path.exists():
        print(out_path.read_text(encoding="utf-8", errors="replace"))
    elif output_file:
        # Might be an Amiga path; try only if it's a local file path
        try:
            pf = Path(output_file)
            if pf.exists():
                print(pf.read_text(encoding="utf-8", errors="replace"))
        except Exception:
            pass

    if not ok:
        print(f"[amiga] command failed rc={rc}", file=sys.stderr)
        return 1
    return 0


def cmd_stop(args: argparse.Namespace) -> int:
    base = Path(args.base).expanduser()
    layout = ensure_layout(base)
    job_id = args.id or _now_id()
    job_text = "\n".join([MAGIC_JOB, f"id={job_id}", "action=stop"]) + "\n"
    job_path = layout["in"] / f"{job_id}.job"
    atomic_write_text(job_path, job_text)
    print(job_id)
    return 0


def cmd_snap(args: argparse.Namespace) -> int:
    base = Path(args.base).expanduser()
    layout = ensure_layout(base)

    ts = time.strftime("%Y%m%d_%H%M%S")
    out = layout["snap"] / f"{ts}_winuae.png"

    hwnd = None
    if args.window:
        hwnd = find_window_by_substring(args.window)
        if hwnd is None:
            print(f'Window containing "{args.window}" not found; capturing full screen.', file=sys.stderr)

    capture_window_png(hwnd, out)
    print(str(out))
    if args.open:
        open_file_in_default_app(out)
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="clawbridge", description="OpenClaw ↔ Amiga bridge (shared folder).")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("send", help="Send an AmigaDOS command as a job file.")
    s.add_argument("--base", required=True, help=r'Base shared folder, e.g. C:\Amiga\Shared\openclaw')
    s.add_argument("--cmd", required=True, help='AmigaDOS command, e.g. "dir SYS:"')
    s.add_argument("--cwd", default="", help='Optional working directory on Amiga, e.g. "Work:"')
    s.add_argument("--id", default="", help="Optional job id. Default: auto-generated.")
    s.add_argument("--wait", action="store_true", help="Wait for result and print output.")
    s.add_argument("--timeout", default="60", help="Seconds to wait when --wait is used (default: 60).")
    s.add_argument("--wait-ms", default=None, help="Optional delay after command execution (ms).")
    s.set_defaults(func=cmd_send)

    st = sub.add_parser("stop", help="Ask the Amiga listener to stop.")
    st.add_argument("--base", required=True)
    st.add_argument("--id", default="")
    st.set_defaults(func=cmd_stop)

    sn = sub.add_parser("snap", help="Capture a screenshot of the WinUAE window (best-effort).")
    sn.add_argument("--base", required=True)
    sn.add_argument("--window", default="WinUAE", help='Substring of emulator window title (default: "WinUAE")')
    sn.add_argument("--open", action="store_true", help="Open the PNG after capturing.")
    sn.set_defaults(func=cmd_snap)

    return p


def main(argv: Optional[list] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
