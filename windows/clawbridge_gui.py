#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Minimal GUI for ClawBridge using Tkinter (no extra dependencies beyond Pillow for screenshots).
"""

from __future__ import annotations

import os
import threading
import time
from pathlib import Path
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

from clawbridge import cmd_send, cmd_snap, build_parser  # reuse CLI logic
from clawbridge import ensure_layout, wait_for_result, parse_kv_file


try:
    from PIL import Image, ImageTk
except Exception:
    Image = None  # type: ignore
    ImageTk = None  # type: ignore


class App(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("OpenClaw ↔ Amiga Bridge (WinUAE)")

        self.base_var = tk.StringVar(value=str(Path.home() / "Amiga" / "Shared" / "openclaw"))
        self.cmd_var = tk.StringVar(value="version")
        self.cwd_var = tk.StringVar(value="")
        self.window_var = tk.StringVar(value="WinUAE")

        self._img_label = None
        self._img_obj = None

        self._build()

    def _build(self) -> None:
        pad = {"padx": 8, "pady": 6}

        frm = ttk.Frame(self)
        frm.grid(row=0, column=0, sticky="nsew", **pad)
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)

        # Base folder
        row = 0
        ttk.Label(frm, text="Shared base folder (Windows path):").grid(row=row, column=0, sticky="w")
        ttk.Entry(frm, textvariable=self.base_var, width=60).grid(row=row, column=1, sticky="ew")
        ttk.Button(frm, text="Browse…", command=self._browse_base).grid(row=row, column=2, sticky="ew")
        frm.columnconfigure(1, weight=1)

        # Command
        row += 1
        ttk.Label(frm, text="AmigaDOS command:").grid(row=row, column=0, sticky="w")
        ttk.Entry(frm, textvariable=self.cmd_var).grid(row=row, column=1, sticky="ew")
        ttk.Button(frm, text="Send", command=self._send).grid(row=row, column=2, sticky="ew")

        # CWD
        row += 1
        ttk.Label(frm, text="CWD (optional):").grid(row=row, column=0, sticky="w")
        ttk.Entry(frm, textvariable=self.cwd_var).grid(row=row, column=1, sticky="ew")
        ttk.Button(frm, text="Screenshot", command=self._snap).grid(row=row, column=2, sticky="ew")

        # Window title
        row += 1
        ttk.Label(frm, text="Emulator window title contains:").grid(row=row, column=0, sticky="w")
        ttk.Entry(frm, textvariable=self.window_var).grid(row=row, column=1, sticky="ew")
        ttk.Button(frm, text="Open base folder", command=self._open_base).grid(row=row, column=2, sticky="ew")

        # Output box
        row += 1
        ttk.Label(frm, text="Output:").grid(row=row, column=0, sticky="nw")
        self.txt = tk.Text(frm, height=16, width=90)
        self.txt.grid(row=row, column=1, columnspan=2, sticky="nsew")
        frm.rowconfigure(row, weight=1)

        # Screenshot preview
        row += 1
        ttk.Label(frm, text="Last screenshot preview:").grid(row=row, column=0, sticky="nw")
        self._img_label = ttk.Label(frm)
        self._img_label.grid(row=row, column=1, columnspan=2, sticky="w")

    def _browse_base(self) -> None:
        p = filedialog.askdirectory(title="Select shared base folder")
        if p:
            self.base_var.set(p)

    def _open_base(self) -> None:
        p = Path(self.base_var.get())
        if p.exists():
            os.startfile(str(p))  # noqa
        else:
            messagebox.showerror("Not found", "Base folder does not exist yet.")

    def _append(self, s: str) -> None:
        self.txt.insert("end", s + "\n")
        self.txt.see("end")

    def _send(self) -> None:
        base = self.base_var.get().strip()
        cmd = self.cmd_var.get().strip()
        cwd = self.cwd_var.get().strip()

        if not base or not cmd:
            return

        def worker():
            try:
                layout = ensure_layout(Path(base))
                # Make job id
                import time, uuid
                job_id = time.strftime("%Y%m%d_%H%M%S") + "_" + uuid.uuid4().hex[:6]
                # write job
                job_lines = ["CLAWJOB 1", f"id={job_id}", "action=run"]
                if cwd:
                    job_lines.append(f"cwd={cwd}")
                job_lines.append(f"cmd={cmd}")
                job_text = "\n".join(job_lines) + "\n"
                job_path = layout["in"] / f"{job_id}.job"
                from clawbridge import atomic_write_text
                atomic_write_text(job_path, job_text)

                # wait
                res_path, out_path = wait_for_result(layout["out"], job_id, timeout_s=60.0)
                if res_path is None:
                    self.after(0, lambda: self._append(f"TIMEOUT waiting for {job_id}.res"))
                    return
                data = parse_kv_file(res_path)
                ok = data.get("ok", "0") == "1"
                rc = data.get("rc", "")
                out_txt = ""
                if out_path and out_path.exists():
                    out_txt = out_path.read_text(encoding="utf-8", errors="replace")
                else:
                    out_txt = data.get("output", "")
                self.after(0, lambda: self._append(out_txt.rstrip()))
                if not ok:
                    self.after(0, lambda: self._append(f"[FAILED rc={rc}]"))
            except Exception as e:
                self.after(0, lambda: self._append(f"[ERROR] {e!r}"))

        threading.Thread(target=worker, daemon=True).start()

    def _snap(self) -> None:
        base = self.base_var.get().strip()
        if not base:
            return

        def worker():
            try:
                from argparse import Namespace
                ns = Namespace(base=base, window=self.window_var.get().strip() or "WinUAE", open=False)
                # capture via CLI function
                from clawbridge import cmd_snap
                # cmd_snap prints to stdout; we want the path
                # So just call internal capture path
                from clawbridge import ensure_layout, find_window_by_substring, capture_window_png
                layout = ensure_layout(Path(base))
                ts = time.strftime("%Y%m%d_%H%M%S")
                out = layout["snap"] / f"{ts}_winuae.png"
                hwnd = find_window_by_substring(ns.window)
                capture_window_png(hwnd, out)
                self.after(0, lambda: self._append(f"[screenshot] {out}"))
                self.after(0, lambda: self._load_preview(out))
            except Exception as e:
                self.after(0, lambda: self._append(f"[ERROR] {e!r}"))

        threading.Thread(target=worker, daemon=True).start()

    def _load_preview(self, path: Path) -> None:
        if Image is None or ImageTk is None or self._img_label is None:
            return
        try:
            img = Image.open(path)
            img.thumbnail((640, 360))
            self._img_obj = ImageTk.PhotoImage(img)
            self._img_label.configure(image=self._img_obj)
        except Exception:
            pass


def main():
    app = App()
    app.mainloop()


if __name__ == "__main__":
    main()
