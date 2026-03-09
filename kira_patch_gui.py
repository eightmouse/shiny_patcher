#!/usr/bin/env python3
from __future__ import annotations

import contextlib
import io
import sys
import threading
from pathlib import Path
from queue import Empty, Queue

import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from shiny_patcher import patch_rom


ODDS_PRESETS = (
    "8192",
    "4096",
    "2048",
    "1024",
    "512",
    "256",
    "128",
    "64",
    "32",
    "16",
    "Custom",
)


def resource_path(name: str) -> Path:
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    return base / name


class KiraPatchApp:
    def __init__(self, root: tk.Tk, startup_paths: list[Path]) -> None:
        self.root = root
        self.root.title("KiraPatch")
        self.root.minsize(760, 520)
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(1, weight=1)
        self._set_icon()

        self.paths: list[Path] = []
        self.worker: threading.Thread | None = None
        self.log_queue: Queue[tuple[str, object]] = Queue()

        self.odds_choice = tk.StringVar(value="256")
        self.custom_odds = tk.StringVar(value="256")
        self.status_text = tk.StringVar(value="Uses auto mode for canonical shiny generation.")

        self._build_header()
        self._build_body()
        self._build_footer()

        if startup_paths:
            self.add_paths(startup_paths)

        self._sync_custom_odds_state()
        self.root.after(100, self._poll_log_queue)

    def _set_icon(self) -> None:
        icon_path = resource_path("logo.ico")
        if icon_path.exists():
            try:
                self.root.iconbitmap(default=str(icon_path))
            except tk.TclError:
                pass

    def _build_header(self) -> None:
        frame = ttk.Frame(self.root, padding=(14, 14, 14, 10))
        frame.grid(row=0, column=0, sticky="ew")
        frame.columnconfigure(0, weight=1)

        title = ttk.Label(frame, text="KiraPatch", font=("Segoe UI", 16, "bold"))
        title.grid(row=0, column=0, sticky="w")

        subtitle = ttk.Label(
            frame,
            text="Standalone Gen 3 shiny patcher. Select ROMs, choose odds, patch.",
        )
        subtitle.grid(row=1, column=0, sticky="w", pady=(4, 0))

    def _build_body(self) -> None:
        body = ttk.Frame(self.root, padding=(14, 0, 14, 10))
        body.grid(row=1, column=0, sticky="nsew")
        body.columnconfigure(0, weight=3)
        body.columnconfigure(1, weight=2)
        body.rowconfigure(1, weight=1)

        files_label = ttk.Label(body, text="ROM files")
        files_label.grid(row=0, column=0, sticky="w")

        options_label = ttk.Label(body, text="Patch settings")
        options_label.grid(row=0, column=1, sticky="w", padx=(14, 0))

        files_frame = ttk.Frame(body)
        files_frame.grid(row=1, column=0, sticky="nsew")
        files_frame.columnconfigure(0, weight=1)
        files_frame.rowconfigure(0, weight=1)

        self.file_list = tk.Listbox(files_frame, selectmode=tk.EXTENDED, height=12)
        self.file_list.grid(row=0, column=0, sticky="nsew")

        file_scroll = ttk.Scrollbar(files_frame, orient="vertical", command=self.file_list.yview)
        file_scroll.grid(row=0, column=1, sticky="ns")
        self.file_list.configure(yscrollcommand=file_scroll.set)

        file_button_row = ttk.Frame(files_frame)
        file_button_row.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(10, 0))
        for idx in range(3):
            file_button_row.columnconfigure(idx, weight=1)

        ttk.Button(file_button_row, text="Add ROMs", command=self.choose_files).grid(
            row=0, column=0, sticky="ew"
        )
        ttk.Button(
            file_button_row, text="Remove Selected", command=self.remove_selected
        ).grid(row=0, column=1, sticky="ew", padx=8)
        ttk.Button(file_button_row, text="Clear List", command=self.clear_files).grid(
            row=0, column=2, sticky="ew"
        )

        options = ttk.Frame(body, padding=(14, 0, 0, 0))
        options.grid(row=1, column=1, sticky="nsew")
        options.columnconfigure(1, weight=1)

        ttk.Label(options, text="Odds (1 in N)").grid(row=0, column=0, sticky="w")
        self.odds_combo = ttk.Combobox(
            options,
            textvariable=self.odds_choice,
            values=ODDS_PRESETS,
            state="readonly",
        )
        self.odds_combo.grid(row=0, column=1, sticky="ew")
        self.odds_combo.bind("<<ComboboxSelected>>", self._on_odds_selected)

        ttk.Label(options, text="Custom N").grid(row=1, column=0, sticky="w", pady=(10, 0))
        self.custom_entry = ttk.Entry(options, textvariable=self.custom_odds)
        self.custom_entry.grid(row=1, column=1, sticky="ew", pady=(10, 0))

        ttk.Label(options, text="Mode").grid(row=2, column=0, sticky="w", pady=(10, 0))
        ttk.Label(options, text="auto (canonical, recommended)").grid(
            row=2, column=1, sticky="w", pady=(10, 0)
        )

        note = (
            "Higher rates work, but 1/16 can pause for a bit while the game rerolls.\n"
            "1/128 or 1/256 are smoother for normal play."
        )
        ttk.Label(options, text=note, justify="left", wraplength=260).grid(
            row=3, column=0, columnspan=2, sticky="w", pady=(14, 0)
        )

        self.patch_button = ttk.Button(options, text="Patch Selected ROMs", command=self.start_patch)
        self.patch_button.grid(row=4, column=0, columnspan=2, sticky="ew", pady=(18, 0))

        log_label = ttk.Label(body, text="Patch log")
        log_label.grid(row=2, column=0, columnspan=2, sticky="w", pady=(12, 4))

        log_frame = ttk.Frame(body)
        log_frame.grid(row=3, column=0, columnspan=2, sticky="nsew")
        log_frame.columnconfigure(0, weight=1)
        log_frame.rowconfigure(0, weight=1)
        body.rowconfigure(3, weight=1)

        self.log_text = tk.Text(log_frame, height=14, wrap="word", state="disabled")
        self.log_text.grid(row=0, column=0, sticky="nsew")

        log_scroll = ttk.Scrollbar(log_frame, orient="vertical", command=self.log_text.yview)
        log_scroll.grid(row=0, column=1, sticky="ns")
        self.log_text.configure(yscrollcommand=log_scroll.set)

    def _build_footer(self) -> None:
        footer = ttk.Frame(self.root, padding=(14, 0, 14, 14))
        footer.grid(row=2, column=0, sticky="ew")
        footer.columnconfigure(0, weight=1)
        ttk.Label(footer, textvariable=self.status_text).grid(row=0, column=0, sticky="w")

    def _on_odds_selected(self, _event: object) -> None:
        self._sync_custom_odds_state()

    def _sync_custom_odds_state(self) -> None:
        is_custom = self.odds_choice.get() == "Custom"
        combo_state = "readonly" if self.worker is None or not self.worker.is_alive() else "disabled"
        entry_state = "normal" if is_custom else "disabled"
        if combo_state == "disabled":
            entry_state = "disabled"
        self.odds_combo.configure(state=combo_state)
        self.custom_entry.configure(state=entry_state)
        if not is_custom:
            self.custom_odds.set(self.odds_choice.get())

    def choose_files(self) -> None:
        selected = filedialog.askopenfilenames(
            title="Select Gen 3 ROMs",
            filetypes=[("GBA ROMs", "*.gba"), ("All files", "*.*")],
        )
        if selected:
            self.add_paths([Path(p) for p in selected])

    def add_paths(self, new_paths: list[Path]) -> None:
        known = set()
        for path in self.paths:
            try:
                known.add(path.resolve())
            except OSError:
                continue

        for path in new_paths:
            if path.suffix.lower() != ".gba":
                continue
            try:
                resolved = path.resolve()
            except OSError:
                continue
            if resolved in known:
                continue
            self.paths.append(path)
            self.file_list.insert("end", str(path))
            known.add(resolved)

    def remove_selected(self) -> None:
        indices = list(self.file_list.curselection())
        if not indices:
            return
        for idx in reversed(indices):
            self.file_list.delete(idx)
            del self.paths[idx]

    def clear_files(self) -> None:
        self.file_list.delete(0, "end")
        self.paths.clear()

    def _append_log(self, text: str) -> None:
        self.log_text.configure(state="normal")
        self.log_text.insert("end", text)
        self.log_text.see("end")
        self.log_text.configure(state="disabled")

    def _selected_odds(self) -> int | None:
        if self.odds_choice.get() == "Custom":
            raw = self.custom_odds.get().strip()
        else:
            raw = self.odds_choice.get()
        if not raw.isdigit():
            return None
        value = int(raw)
        if value <= 0:
            return None
        return value

    def _set_busy(self, busy: bool) -> None:
        entry_state = "normal" if self.odds_choice.get() == "Custom" else "disabled"
        if busy:
            self.patch_button.configure(state="disabled")
            self.odds_combo.configure(state="disabled")
            self.custom_entry.configure(state="disabled")
        else:
            self.patch_button.configure(state="normal")
            self.odds_combo.configure(state="readonly")
            self.custom_entry.configure(state=entry_state)

    def start_patch(self) -> None:
        if self.worker is not None and self.worker.is_alive():
            return
        if not self.paths:
            messagebox.showerror("KiraPatch", "Add at least one .gba ROM first.")
            return

        odds = self._selected_odds()
        if odds is None:
            messagebox.showerror("KiraPatch", "Enter a valid positive odds value.")
            return

        self._append_log(f"\n=== Starting patch run (auto mode, 1/{odds}) ===\n")
        self.status_text.set("Patching...")
        self._set_busy(True)

        paths = list(self.paths)
        self.worker = threading.Thread(
            target=self._run_patch_worker,
            args=(paths, odds),
            daemon=True,
        )
        self.worker.start()

    def _run_patch_worker(self, paths: list[Path], odds: int) -> None:
        passed = 0
        failed = 0

        for path in paths:
            buffer = io.StringIO()
            with contextlib.redirect_stdout(buffer):
                rc = patch_rom(
                    input_path=path,
                    odds=odds,
                    mode="auto",
                    output_path=None,
                    overwrite_output=False,
                    auto_rename_output=True,
                )
            if rc == 0:
                passed += 1
            else:
                failed += 1
            output = buffer.getvalue()
            prefix = f"\n--- {path.name} ---\n"
            self.log_queue.put(("log", prefix + output + "\n"))

        summary = f"Finished. OK: {passed}  FAIL: {failed}"
        self.log_queue.put(("done", summary))

    def _poll_log_queue(self) -> None:
        try:
            while True:
                kind, payload = self.log_queue.get_nowait()
                if kind == "log":
                    self._append_log(str(payload))
                elif kind == "done":
                    summary = str(payload)
                    self._append_log(f"{summary}\n")
                    self.status_text.set(summary)
                    self._set_busy(False)
                    if "FAIL: 0" in summary:
                        messagebox.showinfo("KiraPatch", summary)
                    else:
                        messagebox.showwarning("KiraPatch", summary)
        except Empty:
            pass
        self.root.after(100, self._poll_log_queue)


def main() -> int:
    startup_paths = [Path(arg) for arg in sys.argv[1:] if arg.lower().endswith(".gba")]

    root = tk.Tk()
    KiraPatchApp(root, startup_paths)
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
