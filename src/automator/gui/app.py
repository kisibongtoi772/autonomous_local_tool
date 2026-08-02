"""
Desktop Automator — Professional Dashboard
Stack: CustomTkinter (lightweight, native, no extra runtime)
Design: Minimal · Typography-driven · Zero emoji icons
"""
from __future__ import annotations

import copy
import json
import logging
import os
import sys
import glob
import threading
import time
import zipfile
import shutil
import tkinter.filedialog
from typing import Any, Callable

import customtkinter as ctk
from PIL import Image
from pynput import keyboard, mouse

from ..core.recorder import Recorder
from ..core.player import Player
from ..core.scheduler import WorkflowScheduler
from ..core.variable_manager import VariableManager
from ..utils.logger import get_logger
from ..utils.config import (
    WORKSPACE_DIR, VARIABLES_FILE, RUN_HISTORY_FILE, SCHEDULES_FILE, TEMPLATES_DIR
)

# macOS: pre-load HIServices on main thread to prevent pynput crash on bg threads
if sys.platform == "darwin":
    try:
        import HIServices
        HIServices.AXIsProcessTrusted()
    except Exception:
        pass

logger = get_logger(__name__)

# ── Design tokens ─────────────────────────────────────────────────────────────
T = {
    # Backgrounds
    "bg":       "#0A0C10",
    "surface":  "#111318",
    "raised":   "#181C22",
    "hover":    "#1E232C",
    "border":   "#262B35",

    # Accent (single blue accent — no rainbow)
    "accent":   "#3B82F6",
    "accent_d": "#2563EB",

    # Status
    "ok":       "#22C55E",
    "warn":     "#F59E0B",
    "err":      "#EF4444",

    # Text
    "text":     "#E2E8F0",
    "dim":      "#64748B",
    "label":    "#94A3B8",
}

FONT_MONO  = ("Menlo", 11)
FONT_BODY  = ("SF Pro Text", 12)
FONT_BOLD  = ("SF Pro Text", 12, "bold")
FONT_SM    = ("SF Pro Text", 10)
FONT_HEAD  = ("SF Pro Display", 16, "bold")
FONT_NUM   = ("SF Pro Display", 24, "bold")


# ── Utilities ─────────────────────────────────────────────────────────────────
def load_json(path: str, default=None):
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return default if default is not None else {}


def save_json(path: str, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def get_workflow_files():
    excluded = {
        os.path.basename(VARIABLES_FILE),
        os.path.basename(RUN_HISTORY_FILE),
        os.path.basename(SCHEDULES_FILE),
    }
    files = [
        os.path.basename(f)
        for f in glob.glob(os.path.join(WORKSPACE_DIR, "*.json"))
        if os.path.basename(f) not in excluded
    ]
    return files or ["workflow.json"]


ACTION_LABELS = {
    "click":            "Click",
    "type":             "Type",
    "sleep":            "Sleep",
    "hotkey":           "Hotkey",
    "run_command":      "Command",
    "scroll":           "Scroll",
    "screenshot":       "Screenshot",
    "loop":             "Loop",
    "assert_template":  "Assert",
    "clipboard":        "Clipboard",
    "if_template":      "Conditional",
    "wait_for_template":"Wait For",
    "run_workflow":      "Sub-Workflow",
    "prompt_user":       "Prompt",
    "comment":          "Comment / Group",
}


# ── Log handler ───────────────────────────────────────────────────────────────
class LogHandler(logging.Handler):
    _COLOURS = {
        logging.DEBUG:    T["dim"],
        logging.INFO:     T["text"],
        logging.WARNING:  T["warn"],
        logging.ERROR:    T["err"],
        logging.CRITICAL: T["err"],
    }

    def __init__(self, textbox: ctk.CTkTextbox):
        super().__init__()
        self.textbox = textbox
        self.setFormatter(logging.Formatter("%(asctime)s  %(levelname)-5s  %(message)s", "%H:%M:%S"))

    def emit(self, record):
        msg  = self.format(record)
        col  = self._COLOURS.get(record.levelno, T["text"])
        self.textbox.after(0, self._write, msg, col)

    def _write(self, msg: str, col: str):
        tb = self.textbox
        tb.configure(state="normal")
        tb.insert("end", msg + "\n", col)
        tb.see("end")
        lines = int(tb.index("end-1c").split(".")[0])
        if lines > 200:
            tb.delete("1.0", f"{lines - 200}.0")
        tb.configure(state="disabled")


# ── Shared widget factory ─────────────────────────────────────────────────────
def _btn(parent, text: str, command, width=None, primary=False, danger=False, **kw):
    fg = T["accent"] if primary else (T["err"] if danger else T["raised"])
    hv = T["accent_d"] if primary else ("#C03030" if danger else T["hover"])
    defaults = dict(
        fg_color=fg, hover_color=hv,
        text_color=T["text"],
        font=ctk.CTkFont(*FONT_BODY),
        border_width=0 if (primary or danger) else 1,
        border_color=T["border"],
        corner_radius=6, height=32,
        width=width or 120,
    )
    # kw overrides defaults — prevents duplicate keyword errors
    defaults.update(kw)
    b = ctk.CTkButton(parent, text=text, command=command, **defaults)
    return b


def _label(parent, text: str, size=12, weight="normal", colour=None, **kw):
    return ctk.CTkLabel(
        parent, text=text,
        font=ctk.CTkFont("SF Pro Text", size, weight),
        text_color=colour or T["text"], **kw
    )


def _sep(parent):
    return ctk.CTkFrame(parent, height=1, fg_color=T["border"], corner_radius=0)


# ═══════════════════════════════════════════════════════════════════════════════
# Application
# ═══════════════════════════════════════════════════════════════════════════════
class AutomatorGUI(ctk.CTk):

    def __init__(self):
        super().__init__()
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        self.title("Desktop Automator")
        self.geometry("960x640")
        self.minsize(800, 560)
        self.configure(fg_color=T["bg"])

        # State
        self.recording    = False
        self.recorder:   Recorder | None = None
        self._player:    Player | None   = None   # Active player (for stop)
        self.file_var    = ctk.StringVar(value="workflow.json")
        self._active_nav = "dashboard"
        self._nav_btns:    dict[str, ctk.CTkButton] = {}
        self._panels:      dict[str, ctk.CTkFrame]  = {}

        # Playback settings
        self._speed_var   = ctk.DoubleVar(value=1.0)
        self._step_mode   = ctk.BooleanVar(value=False)

        # Services
        self.scheduler   = WorkflowScheduler()
        self.var_manager = VariableManager()

        # Undo/Redo Stacks
        self._undo_stack = []
        self._redo_stack = []
        
        # Bulk Edit Mode
        self._bulk_mode = False
        self._selected_indices = set()

        os.makedirs(WORKSPACE_DIR, exist_ok=True)

        self._build()
        self._start_listeners()
        self.scheduler.set_play_callback(self._run_scheduled)
        self.scheduler.start()

    # ── Top-level layout ──────────────────────────────────────────────────────

    def _build(self):
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self._build_sidebar()
        self._build_main()
        self._nav_to("dashboard")

    # ── Sidebar ───────────────────────────────────────────────────────────────

    def _build_sidebar(self):
        sb = ctk.CTkFrame(self, width=190, fg_color=T["surface"], corner_radius=0)
        sb.grid(row=0, column=0, sticky="nsew")
        sb.grid_propagate(False)

        # App name
        ctk.CTkLabel(
            sb, text="Desktop\nAutomator",
            font=ctk.CTkFont("SF Pro Display", 15, "bold"),
            text_color=T["text"], justify="left"
        ).pack(padx=18, pady=(22, 4), anchor="w")

        _label(sb, "Local Automation Tool", size=10, colour=T["dim"]).pack(
            padx=18, pady=(0, 16), anchor="w")

        _sep(sb).pack(fill="x", padx=0)

        # Workflow selector
        sel = ctk.CTkFrame(sb, fg_color="transparent")
        sel.pack(fill="x", padx=12, pady=12)

        _label(sel, "Workflow", size=10, colour=T["dim"]).pack(anchor="w", pady=(0, 4))
        self.file_dropdown = ctk.CTkOptionMenu(
            sel, variable=self.file_var,
            values=get_workflow_files(),
            command=self._on_file_select,
            fg_color=T["raised"], button_color=T["border"],
            button_hover_color=T["hover"],
            text_color=T["text"],
            font=ctk.CTkFont(*FONT_BODY),
            width=166, dynamic_resizing=False,
            corner_radius=6
        )
        self.file_dropdown.pack(fill="x")

        _btn(sel, "New Workflow", self._new_workflow, width=166,
             fg_color="transparent",
             border_width=1, border_color=T["border"],
             text_color=T["dim"],
             hover_color=T["hover"]
             ).pack(pady=(6, 2), fill="x")

        wf_mgmt_row = ctk.CTkFrame(sel, fg_color="transparent")
        wf_mgmt_row.pack(fill="x", pady=(2, 0))
        wf_mgmt_row.grid_columnconfigure((0, 1, 2), weight=1)

        _btn(wf_mgmt_row, "Rename", self._rename_workflow, width=10,
             fg_color="transparent", border_width=1, border_color=T["border"],
             text_color=T["dim"], hover_color=T["hover"], font=ctk.CTkFont(*FONT_SM)
             ).grid(row=0, column=0, padx=(0, 4), sticky="ew")
        _btn(wf_mgmt_row, "Dupe", self._duplicate_workflow_file, width=10,
             fg_color="transparent", border_width=1, border_color=T["border"],
             text_color=T["dim"], hover_color=T["hover"], font=ctk.CTkFont(*FONT_SM)
             ).grid(row=0, column=1, padx=(0, 4), sticky="ew")
        _btn(wf_mgmt_row, "Delete", self._delete_workflow_file, width=10,
             fg_color="transparent", border_width=1, border_color=T["border"],
             text_color=T["err"], hover_color="#2A1515", font=ctk.CTkFont(*FONT_SM)
             ).grid(row=0, column=2, sticky="ew")

        pkg_mgmt_row = ctk.CTkFrame(sel, fg_color="transparent")
        pkg_mgmt_row.pack(fill="x", pady=(2, 0))
        pkg_mgmt_row.grid_columnconfigure((0, 1), weight=1)

        _btn(pkg_mgmt_row, "Export", self._export_package, width=10,
             fg_color="transparent", border_width=1, border_color=T["border"],
             text_color=T["dim"], hover_color=T["hover"], font=ctk.CTkFont(*FONT_SM)
             ).grid(row=0, column=0, padx=(0, 4), sticky="ew")
        _btn(pkg_mgmt_row, "Import", self._import_package, width=10,
             fg_color="transparent", border_width=1, border_color=T["border"],
             text_color=T["dim"], hover_color=T["hover"], font=ctk.CTkFont(*FONT_SM)
             ).grid(row=0, column=1, sticky="ew")

        _sep(sb).pack(fill="x", padx=0, pady=4)

        # Nav items
        nav_items = [
            ("dashboard", "Dashboard"),
            ("workflow",  "Workflow Editor"),
            ("scheduler", "Scheduler"),
            ("variables", "Variables"),
            ("history",   "Run History"),
        ]
        for key, label in nav_items:
            b = ctk.CTkButton(
                sb, text=label, anchor="w",
                height=36, corner_radius=6,
                fg_color="transparent",
                hover_color=T["hover"],
                text_color=T["dim"],
                font=ctk.CTkFont(*FONT_BODY),
                command=lambda k=key: self._nav_to(k)
            )
            b.pack(padx=10, pady=2, fill="x")
            self._nav_btns[key] = b

        # Status indicator at bottom
        _sep(sb).pack(fill="x", padx=0, side="bottom")
        self._status_row = ctk.CTkFrame(sb, fg_color="transparent")
        self._status_row.pack(side="bottom", fill="x", padx=14, pady=10)

        self._status_dot = ctk.CTkLabel(
            self._status_row, text="●", width=14,
            font=ctk.CTkFont("SF Pro Text", 10),
            text_color=T["ok"]
        )
        self._status_dot.pack(side="left")

        self._status_text = _label(self._status_row, "Idle", size=11, colour=T["label"])
        self._status_text.pack(side="left", padx=(4, 0))

    # ── Main content area ─────────────────────────────────────────────────────

    def _build_main(self):
        main = ctk.CTkFrame(self, fg_color=T["bg"], corner_radius=0)
        main.grid(row=0, column=1, sticky="nsew")
        main.grid_rowconfigure(0, weight=1)
        main.grid_columnconfigure(0, weight=1)

        for key, builder in [
            ("dashboard", self._build_dashboard),
            ("workflow",  self._build_workflow),
            ("scheduler", self._build_scheduler),
            ("variables", self._build_variables),
            ("history",   self._build_history),
        ]:
            f = ctk.CTkFrame(main, fg_color=T["bg"], corner_radius=0)
            f.grid(row=0, column=0, sticky="nsew")
            self._panels[key] = f
            builder(f)

    def _nav_to(self, key: str):
        for k, b in self._nav_btns.items():
            if k == key:
                b.configure(fg_color=T["raised"], text_color=T["text"])
            else:
                b.configure(fg_color="transparent", text_color=T["dim"])

        for k, f in self._panels.items():
            if k == key:
                f.tkraise()

        self._active_nav = key

        # Refresh live data
        refresh = {
            "workflow":  self._refresh_workflow,
            "variables": self._refresh_variables,
            "history":   self._refresh_history,
            "scheduler": self._refresh_scheduler,
        }
        if key in refresh:
            refresh[key]()

    # ── PANEL: Dashboard ──────────────────────────────────────────────────────

    def _build_dashboard(self, p: ctk.CTkFrame):
        p.grid_columnconfigure(0, weight=1)
        p.grid_rowconfigure(2, weight=1)

        # Page header
        self._page_header(p, "Dashboard", row=0)

        # Stats + controls in one top section
        top = ctk.CTkFrame(p, fg_color="transparent")
        top.grid(row=1, column=0, sticky="ew", padx=24, pady=(0, 12))
        top.grid_columnconfigure((0, 1, 2), weight=1)

        self._stat_wf   = self._stat_card(top, "Workflows",  0)
        self._stat_acts = self._stat_card(top, "Actions",    1)
        self._stat_runs = self._stat_card(top, "Total Runs", 2)

        # Controls card
        ctrl = ctk.CTkFrame(p, fg_color=T["surface"], corner_radius=8)
        ctrl.grid(row=2, column=0, sticky="nsew", padx=24, pady=(0, 12))
        ctrl.grid_columnconfigure(0, weight=1)
        ctrl.grid_rowconfigure(1, weight=1)

        ctrl_hdr = ctk.CTkFrame(ctrl, fg_color="transparent")
        ctrl_hdr.grid(row=0, column=0, sticky="ew", padx=16, pady=(12, 8))
        _label(ctrl_hdr, "Controls", size=11, colour=T["dim"]).pack(side="left")
        _label(ctrl_hdr, "F9  Record   F10  Stop   F11  Playback",
               size=10, colour=T["border"]).pack(side="right")

        btn_row = ctk.CTkFrame(ctrl, fg_color="transparent")
        btn_row.grid(row=1, column=0, sticky="ew", padx=16, pady=(0, 8))

        self.record_btn = ctk.CTkButton(
            btn_row, text="Record", height=36, width=110,
            fg_color=T["err"], hover_color="#CC3333",
            text_color=T["text"], font=ctk.CTkFont(*FONT_BOLD),
            corner_radius=6, command=self.start_recording
        )
        self.record_btn.pack(side="left", padx=(0, 8))

        self.stop_btn = ctk.CTkButton(
            btn_row, text="Stop", height=36, width=90,
            fg_color=T["raised"], hover_color=T["hover"],
            text_color=T["dim"], font=ctk.CTkFont(*FONT_BOLD),
            border_width=1, border_color=T["border"],
            corner_radius=6, state="disabled", command=self.stop_recording
        )
        self.stop_btn.pack(side="left", padx=(0, 8))

        self.play_btn = ctk.CTkButton(
            btn_row, text="Playback", height=36, width=110,
            fg_color=T["accent"], hover_color=T["accent_d"],
            text_color=T["text"], font=ctk.CTkFont(*FONT_BOLD),
            corner_radius=6, command=self.playback
        )
        self.play_btn.pack(side="left", padx=(0, 8))

        self.stop_play_btn = ctk.CTkButton(
            btn_row, text="Stop Playback", height=36, width=120,
            fg_color=T["raised"], hover_color="#2A1515",
            text_color=T["dim"], font=ctk.CTkFont(*FONT_BODY),
            border_width=1, border_color=T["border"],
            corner_radius=6, state="disabled", command=self._stop_playback
        )
        self.stop_play_btn.pack(side="left")

        # ── Playback options row ─────────────────────────────────────────────
        opt_row = ctk.CTkFrame(ctrl, fg_color="transparent")
        opt_row.grid(row=2, column=0, sticky="ew", padx=16, pady=(0, 12))

        _label(opt_row, "Speed", size=10, colour=T["dim"]).pack(side="left")

        self._speed_label = _label(opt_row, "1.0x", size=10, colour=T["label"])
        self._speed_label.pack(side="left", padx=(8, 0))

        speed_slider = ctk.CTkSlider(
            opt_row, from_=0.25, to=4.0, number_of_steps=15,
            variable=self._speed_var,
            width=140, height=16,
            button_color=T["accent"], button_hover_color=T["accent_d"],
            progress_color=T["border"], fg_color=T["raised"],
            command=self._on_speed_change
        )
        speed_slider.pack(side="left", padx=(6, 20))

        ctk.CTkCheckBox(
            opt_row, text="Step-by-step",
            variable=self._step_mode,
            font=ctk.CTkFont(*FONT_SM),
            text_color=T["label"],
            fg_color=T["accent"], hover_color=T["accent_d"],
            border_color=T["border"], checkmark_color=T["text"],
            width=14, height=14, corner_radius=3
        ).pack(side="left")

        # ── Progress Bar & Step Indicator ────────────────────────────────────
        prog_row = ctk.CTkFrame(ctrl, fg_color="transparent")
        prog_row.grid(row=3, column=0, sticky="ew", padx=16, pady=(0, 12))

        self.progress_bar = ctk.CTkProgressBar(
            prog_row, height=6, fg_color=T["raised"], progress_color=T["accent"], corner_radius=3
        )
        self.progress_bar.pack(side="left", fill="x", expand=True, padx=(0, 12))
        self.progress_bar.set(0.0)

        self.progress_label = _label(prog_row, "Ready", size=10, colour=T["dim"])
        self.progress_label.pack(side="right")

        # Log console
        log_wrap = ctk.CTkFrame(p, fg_color=T["surface"], corner_radius=8)
        log_wrap.grid(row=3, column=0, sticky="nsew", padx=24, pady=(0, 24))
        log_wrap.grid_rowconfigure(1, weight=1)
        log_wrap.grid_columnconfigure(0, weight=1)

        p.grid_rowconfigure(3, weight=2)

        lhdr = ctk.CTkFrame(log_wrap, fg_color="transparent")
        lhdr.grid(row=0, column=0, sticky="ew", padx=14, pady=(10, 4))
        _label(lhdr, "Activity Log", size=11, colour=T["dim"]).pack(side="left")
        _btn(lhdr, "Clear", self._clear_log, width=60,
             height=24,
             fg_color="transparent",
             border_width=1, border_color=T["border"],
             text_color=T["dim"]
             ).pack(side="right")

        self.log_box = ctk.CTkTextbox(
            log_wrap,
            fg_color=T["bg"],
            text_color=T["text"],
            font=ctk.CTkFont(*FONT_MONO),
            state="disabled",
            corner_radius=6,
            wrap="word",
            border_width=0
        )
        self.log_box.grid(row=1, column=0, padx=12, pady=(0, 12), sticky="nsew")

        for col in (T["text"], T["dim"], T["warn"], T["err"]):
            self.log_box.tag_config(col, foreground=col)

        # Attach log handler
        handler = LogHandler(self.log_box)
        logging.getLogger("automator").addHandler(handler)
        logger.info("Desktop Automator ready.")
        self._refresh_stats()

    def _stat_card(self, parent, label: str, col: int) -> ctk.CTkLabel:
        card = ctk.CTkFrame(parent, fg_color=T["surface"], corner_radius=8)
        card.grid(row=0, column=col, padx=(0 if col == 0 else 8, 0), pady=(0, 12), sticky="ew")
        _label(card, label, size=10, colour=T["dim"]).pack(padx=14, pady=(12, 2), anchor="w")
        val = ctk.CTkLabel(card, text="0",
                           font=ctk.CTkFont("SF Pro Display", 26, "bold"),
                           text_color=T["text"])
        val.pack(padx=14, pady=(0, 12), anchor="w")
        return val

    def _refresh_stats(self):
        wf = get_workflow_files()
        self._stat_wf.configure(text=str(len(wf)))
        total = sum(len(load_json(os.path.join(WORKSPACE_DIR, f), {}).get("actions", [])) for f in wf)
        self._stat_acts.configure(text=str(total))
        history = load_json(RUN_HISTORY_FILE, [])
        self._stat_runs.configure(text=str(len(history)))

    def _clear_log(self):
        self.log_box.configure(state="normal")
        self.log_box.delete("1.0", "end")
        self.log_box.configure(state="disabled")

    # ── PANEL: Workflow Editor ─────────────────────────────────────────────────

    def _build_workflow(self, p: ctk.CTkFrame):
        p.grid_columnconfigure(0, weight=1)
        p.grid_rowconfigure(1, weight=1)

        self._page_header(p, "Workflow Editor", row=0)

        # Toolbar
        tb = ctk.CTkFrame(p, fg_color=T["surface"], corner_radius=8)
        tb.grid(row=0, column=0, sticky="ew", padx=24, pady=(56, 8))

        _btn(tb, "Refresh",    self._refresh_workflow, False).pack(side="left", padx=(8, 0), pady=8)
        
        self._undo_btn = _btn(tb, "↶ Undo", self._undo, False)
        self._undo_btn.pack(side="left", padx=(8, 0), pady=8)
        
        self._redo_btn = _btn(tb, "↷ Redo", self._redo, False)
        self._redo_btn.pack(side="left", padx=(8, 0), pady=8)
        
        _btn(tb, "Add Action", self._open_add_dialog,  True).pack(side="left", padx=(8, 0), pady=8)
        _btn(tb, "Bulk Edit",  self._toggle_bulk_mode, False).pack(side="left", padx=(8, 0), pady=8)
        _btn(tb, "Gallery",    self._open_template_gallery_dialog, False).pack(side="left", padx=(8, 0), pady=8)
        _btn(tb, "Clear All",  self._clear_workflow,   False, danger=True).pack(side="left", padx=(8, 0), pady=8)

        self._wf_search_var = ctk.StringVar()
        self._wf_search_var.trace_add("write", lambda *_: self._refresh_workflow())
        search_entry = ctk.CTkEntry(
            tb, placeholder_text="Filter actions...",
            textvariable=self._wf_search_var, width=150,
            fg_color=T["raised"], border_color=T["border"],
            text_color=T["text"], font=ctk.CTkFont(*FONT_BODY),
            corner_radius=6
        )
        search_entry.pack(side="right", padx=8, pady=8)

        # Column headers
        hdr = ctk.CTkFrame(p, fg_color="transparent")
        hdr.grid(row=1, column=0, sticky="ew", padx=24)
        hdr.grid_columnconfigure(2, weight=1)

        for col, txt, w in [
            (0, "#",     40),
            (1, "Type",  90),
            (2, "Summary", 0),
            (3, "Actions", 120),
        ]:
            anchor = "w" if col in (1, 2) else "center"
            _label(hdr, txt, size=10, colour=T["dim"], anchor=anchor, width=w
                   ).grid(row=0, column=col, padx=(12 if col == 0 else 4), pady=4, sticky="ew")

        _sep(p).grid(row=2, column=0, sticky="ew", padx=24)

        # Scrollable list
        self._wf_list = ctk.CTkScrollableFrame(
            p, fg_color="transparent", corner_radius=0,
            scrollbar_button_color=T["border"],
            scrollbar_button_hover_color=T["hover"]
        )
        self._wf_list.grid(row=3, column=0, sticky="nsew", padx=24, pady=(0, 24))
        self._wf_list.grid_columnconfigure(2, weight=1)
        p.grid_rowconfigure(3, weight=1)

    def _refresh_workflow(self):
        self._action_rows = []
        for w in self._wf_list.winfo_children():
            w.destroy()
            
        if hasattr(self, "_bulk_toolbar") and self._bulk_toolbar.winfo_exists():
            self._bulk_toolbar.destroy()

        path = os.path.join(WORKSPACE_DIR, self.file_var.get())
        if not os.path.exists(path):
            _label(self._wf_list, "No workflow file found.", colour=T["dim"]).pack(pady=30)
            return

        data    = load_json(path, {})
        actions = data.get("actions", [])
        query   = self._wf_search_var.get().strip().lower() if hasattr(self, "_wf_search_var") else ""

        if not actions:
            _label(self._wf_list, "Workflow is empty. Record or add actions.", colour=T["dim"]).pack(pady=30)
            return

        if self._bulk_mode:
            self._build_bulk_toolbar(self._wf_list)

        rendered_count = 0
        for i, action in enumerate(actions):
            atype = action.get("type", "").lower()
            summary = self._action_summary(action.get("type", ""), action).lower()
            if query and query not in atype and query not in summary and query not in str(action).lower():
                continue
            self._render_action_row(i, action, len(actions))
            rendered_count += 1

        if query and rendered_count == 0:
            _label(self._wf_list, f"No actions match '{query}'", colour=T["dim"]).pack(pady=30)

    def _render_action_row(self, i: int, action: dict, total: int):
        atype   = action.get("type", "unknown")
        label   = ACTION_LABELS.get(atype, atype.upper())
        summary = self._action_summary(atype, action)
        enabled = action.get("enabled", True)
        
        row = ctk.CTkFrame(self._wf_list, fg_color=T["raised"], corner_radius=6)
        row.pack(fill="x", pady=2)
        row.grid_columnconfigure(2, weight=1)
        if hasattr(self, "_action_rows"):
            self._action_rows.append(row)

        # Index & Toggle
        idx_frame = ctk.CTkFrame(row, fg_color="transparent")
        idx_frame.grid(row=0, column=0, padx=8, pady=8)
        
        if atype == "comment":
            row.configure(fg_color="#1F2937") # deep blue-grey for separator
            _label(idx_frame, "💬", size=14).pack(side="left")
            
            summary_frame = ctk.CTkFrame(row, fg_color="transparent")
            summary_frame.grid(row=0, column=1, columnspan=2, padx=12, pady=8, sticky="ew")
            _label(summary_frame, f"--- {action.get('text', '')} ---", size=11, colour=T["accent"], weight="bold").pack(side="left")
        else:
            if self._bulk_mode:
                def on_check(checked_idx=i, var=None):
                    if var.get():
                        self._selected_indices.add(checked_idx)
                    else:
                        self._selected_indices.discard(checked_idx)
                        
                chk_var = ctk.BooleanVar(value=(i in self._selected_indices))
                ctk.CTkCheckBox(
                    idx_frame, text="", width=24, height=24, checkbox_width=20, checkbox_height=20,
                    border_width=2, corner_radius=4, variable=chk_var,
                    command=lambda i=i, v=chk_var: on_check(i, v)
                ).pack(side="left")
            else:
                toggle_text = "●" if enabled else "○"
                toggle_color = T["ok"] if enabled else T["dim"]
                
                def toggle():
                    def m(d):
                        if 0 <= i < len(d.get("actions", [])):
                            d["actions"][i]["enabled"] = not enabled
                    self._modify_workflow(m)
                
                ctk.CTkButton(
                    idx_frame, text=toggle_text, width=24, height=24,
                    fg_color="transparent", hover_color=T["hover"],
                    text_color=toggle_color, font=ctk.CTkFont("SF Pro Text", 12),
                    corner_radius=4, border_width=0, command=toggle
                ).pack(side="left")
            
            _label(idx_frame, str(i + 1), size=10, colour=T["dim"],
                   anchor="center", width=20).pack(side="left")

            # Type badge
            badge = ctk.CTkFrame(row, fg_color=T["border"], corner_radius=4, width=80)
            badge.grid(row=0, column=1, padx=8, pady=8)
            badge_color = T["text"] if enabled else T["dim"]
            _label(badge, label, size=10, colour=badge_color).pack(padx=8, pady=3)

            # Summary & Note
            summary_frame = ctk.CTkFrame(row, fg_color="transparent")
            summary_frame.grid(row=0, column=2, padx=4, pady=8, sticky="ew")
            
            note = action.get("note", "").strip()
            main_color = "#FFFFFF" if enabled else T["dim"]
            sub_color = T["text"] if enabled else T["dim"]
            
            if note:
                _label(summary_frame, f"[{note}]", size=11, colour=main_color, weight="bold").pack(side="left", padx=(0, 8))
                _label(summary_frame, summary, size=11, colour=T["dim"]).pack(side="left")
            else:
                _label(summary_frame, summary, size=11, colour=sub_color).pack(side="left")
                
            retry = action.get("retry_count", 0)
            if retry > 0:
                _label(summary_frame, f"[↺ {retry}x]", size=11, colour=T["warn"]).pack(side="left", padx=(8, 0))

        # Controls — plain text buttons only
        ctrl = ctk.CTkFrame(row, fg_color="transparent")
        ctrl.grid(row=0, column=3, padx=8, pady=4)

        def _ctrl_btn(parent, txt, cmd, text_color=T["dim"]):
            return ctk.CTkButton(
                parent, text=txt, width=32, height=26,
                fg_color="transparent", hover_color=T["hover"],
                text_color=text_color, font=ctk.CTkFont("SF Pro Text", 11),
                corner_radius=4, border_width=0, command=cmd
            )

        _ctrl_btn(ctrl, "▶1",  lambda idx=i: self._test_action(idx), text_color=T["accent"]).pack(side="left", padx=1)
        _ctrl_btn(ctrl, "▶▶",  lambda idx=i: self.playback(start_idx=idx), text_color=T["accent"]).pack(side="left", padx=1)
        tmpl_file = action.get("template") or action.get("template_image")
        if tmpl_file:
            _ctrl_btn(ctrl, "Img", lambda t=tmpl_file: self._show_template_preview_dialog(t)).pack(side="left", padx=1)
            _ctrl_btn(ctrl, "Find", lambda a=action: self._test_template_match(a)).pack(side="left", padx=1)
        if i > 0:
            _ctrl_btn(ctrl, "Up",  lambda idx=i: self._move_up(idx)).pack(side="left", padx=1)
        if i < total - 1:
            _ctrl_btn(ctrl, "Dn",  lambda idx=i: self._move_down(idx)).pack(side="left", padx=1)
        _ctrl_btn(ctrl, "Edit", lambda idx=i, a=action: self._open_edit_dialog(idx, a)).pack(side="left", padx=1)
        _ctrl_btn(ctrl, "Dupe", lambda idx=i: self._duplicate_action(idx)).pack(side="left", padx=1)
        _ctrl_btn(ctrl, "Ins",  lambda idx=i: self._open_add_dialog(insert_idx=idx + 1)).pack(side="left", padx=1)

        del_btn = ctk.CTkButton(
            ctrl, text="Del", width=32, height=26,
            fg_color="transparent", hover_color="#2A1515",
            text_color=T["err"], font=ctk.CTkFont("SF Pro Text", 11),
            corner_radius=4, command=lambda idx=i: self._delete_action(idx)
        )
        del_btn.pack(side="left", padx=1)

    def _action_summary(self, atype: str, a: dict) -> str:
        if atype == "click":
            return f"({a.get('x')}, {a.get('y')})  button={a.get('button','left')}  clicks={a.get('clicks',1)}"
        if atype == "type":      return repr(a.get("key", ""))
        if atype == "sleep":     return f"{a.get('duration', 0)} s"
        if atype == "hotkey":    return " + ".join(a.get("keys", []))
        if atype == "run_command": return a.get("command", "")[:60]
        if atype == "scroll":    return f"amount={a.get('amount', 0)}"
        if atype == "screenshot": return a.get("filename", "")
        if atype == "clipboard": return f"{a.get('action','set')}  {a.get('text','')[:40]}"
        if atype == "if_template":
            return (f"template={a.get('template','')}  "
                    f"then×{len(a.get('then_actions',[]))}  else×{len(a.get('else_actions',[]))}")
        if atype == "loop":      return f"repeat={a.get('count',1)}  steps={len(a.get('actions',[]))}"
        if atype == "wait_for_template":
            return f"template={a.get('template','')}  timeout={a.get('timeout',10)}s  on_timeout={a.get('on_timeout','error')}"
        if atype == "run_workflow":     return f"file={a.get('workflow_file','')}"
        if atype == "prompt_user":      return f"msg={a.get('message','')[:50]}"
        if atype == "comment":          return a.get("text", "")
        for k in ["template", "template_image"]:
            if k in a: return a[k]
        return ""

    def _update_undo_redo_buttons(self):
        if hasattr(self, "_undo_btn"):
            if self._undo_stack:
                self._undo_btn.configure(state="normal", text_color=T["text"])
            else:
                self._undo_btn.configure(state="disabled", text_color=T["dim"])
                
        if hasattr(self, "_redo_btn"):
            if self._redo_stack:
                self._redo_btn.configure(state="normal", text_color=T["text"])
            else:
                self._redo_btn.configure(state="disabled", text_color=T["dim"])

    def _modify_workflow(self, mutator):
        path = os.path.join(WORKSPACE_DIR, self.file_var.get())
        data = load_json(path, {"workflow_name": "workflow", "created_at": "", "actions": []})
        
        prev_actions = copy.deepcopy(data.get("actions", []))
        
        mutator(data)
        
        if data.get("actions", []) != prev_actions:
            self._undo_stack.append(prev_actions)
            self._redo_stack.clear()
            self._update_undo_redo_buttons()
            
        save_json(path, data)
        self._refresh_workflow()

    def _undo(self):
        if not self._undo_stack: return
        path = os.path.join(WORKSPACE_DIR, self.file_var.get())
        data = load_json(path, {"workflow_name": "workflow", "created_at": "", "actions": []})
        
        self._redo_stack.append(copy.deepcopy(data.get("actions", [])))
        data["actions"] = self._undo_stack.pop()
        
        save_json(path, data)
        self._refresh_workflow()
        self._update_undo_redo_buttons()
        logger.info("Undo successful.")

    def _redo(self):
        if not self._redo_stack: return
        path = os.path.join(WORKSPACE_DIR, self.file_var.get())
        data = load_json(path, {"workflow_name": "workflow", "created_at": "", "actions": []})
        
        self._undo_stack.append(copy.deepcopy(data.get("actions", [])))
        data["actions"] = self._redo_stack.pop()
        
        save_json(path, data)
        self._refresh_workflow()
        self._update_undo_redo_buttons()
        logger.info("Redo successful.")
        self._refresh_stats()

    def _delete_action(self, idx: int):
        self._modify_workflow(lambda d: d["actions"].pop(idx))
        logger.info(f"Deleted action #{idx+1}")

    def _duplicate_action(self, idx: int):
        def m(d): d["actions"].insert(idx + 1, copy.deepcopy(d["actions"][idx]))
        self._modify_workflow(m)

    def _move_up(self, idx: int):
        if idx <= 0: return
        def m(d): d["actions"][idx], d["actions"][idx-1] = d["actions"][idx-1], d["actions"][idx]
        self._modify_workflow(m)

    def _move_down(self, idx: int):
        def m(d):
            if idx < len(d["actions"]) - 1:
                d["actions"][idx], d["actions"][idx+1] = d["actions"][idx+1], d["actions"][idx]
        self._modify_workflow(m)

    def _clear_workflow(self):
        self._modify_workflow(lambda d: d.update({"actions": []}))
        logger.info("Workflow cleared.")

    def _test_action(self, idx: int):
        data = load_json(os.path.join(WORKSPACE_DIR, self.file_var.get()), {})
        acts = data.get("actions", [])
        if 0 <= idx < len(acts):
            threading.Thread(
                target=lambda: Player().play_single_action(acts[idx]),
                daemon=True
            ).start()

    def _open_add_dialog(self, insert_idx: int = None):
        dlg = self._dialog("Add Action" if insert_idx is None else "Insert Action", "400x470")

        _label(dlg, "Type", size=10, colour=T["dim"]).pack(padx=20, pady=(16, 2), anchor="w")
        type_var = ctk.StringVar(value="sleep")
        ctk.CTkOptionMenu(
            dlg, variable=type_var, values=list(ACTION_LABELS.keys()),
            fg_color=T["raised"], button_color=T["border"],
            text_color=T["text"], font=ctk.CTkFont(*FONT_BODY),
            width=360, corner_radius=6
        ).pack(padx=20)

        _label(dlg, "Value", size=10, colour=T["dim"]).pack(padx=20, pady=(12, 2), anchor="w")
        
        val_frame = ctk.CTkFrame(dlg, fg_color="transparent")
        val_frame.pack(padx=20, fill="x")
        
        entry = ctk.CTkEntry(
            val_frame, fg_color=T["raised"], border_color=T["border"],
            text_color=T["text"], font=ctk.CTkFont(*FONT_BODY), corner_radius=6
        )
        entry.pack(side="left", fill="x", expand=True)

        def open_snipping():
            from .snipping_tool import SnippingTool
            dlg.withdraw()
            def on_capture(filename):
                dlg.deiconify()
                entry.delete(0, "end")
                entry.insert(0, filename)
            def on_cancel():
                dlg.deiconify()
            SnippingTool(self, on_capture, on_cancel)

        def open_coord_picker():
            from .coord_picker import CoordinatePicker
            dlg.withdraw()
            def on_pick(x, y):
                dlg.deiconify()
                entry.delete(0, "end")
                entry.insert(0, f"{x},{y}")
            def on_cancel():
                dlg.deiconify()
            CoordinatePicker(self, on_pick, on_cancel)
            
        def open_hotkey_picker():
            from .hotkey_picker import HotkeyPicker
            dlg.withdraw()
            def on_capture(combo):
                dlg.deiconify()
                entry.delete(0, "end")
                entry.insert(0, combo)
            def on_cancel():
                dlg.deiconify()
            HotkeyPicker(self, on_capture, on_cancel)

        capture_btn = _btn(val_frame, "✂", open_snipping, width=32, fg_color="transparent", border_width=1, border_color=T["border"], text_color=T["dim"])
        capture_btn.pack(side="right", padx=(8, 0))
        
        coord_btn = _btn(val_frame, "🎯", open_coord_picker, width=32, fg_color="transparent", border_width=1, border_color=T["border"], text_color=T["dim"])
        coord_btn.pack(side="right", padx=(8, 0))

        hotkey_btn = _btn(val_frame, "⌨️", open_hotkey_picker, width=32, fg_color="transparent", border_width=1, border_color=T["border"], text_color=T["dim"])
        hotkey_btn.pack(side="right", padx=(8, 0))

        HINTS = {
            "sleep": "seconds  (e.g. 1.5)",
            "type": "text or key  (e.g. hello  or  Key.enter)",
            "run_command": "shell command  (e.g. open /Applications/Safari.app)",
            "hotkey": "keys comma-separated (e.g. cmd,c). Use ⌨️ to record",
            "scroll": "amount  (positive=up  negative=down)",
            "screenshot": "filename  (e.g. state.png)",
            "assert_template": "template filename in workspace/templates/",
            "clipboard": "action text  (e.g. set Hello World)",
            "if_template": "template filename  (add branches via Edit)",
            "click": "x,y  (e.g. 500,300)",
            "loop": "count  (e.g. 3)",
            "wait_for_template": "template,timeout  (e.g. btn.png,15  or just  btn.png)",
            "run_workflow": "filename in workspace/  (e.g. setup.json)",
            "prompt_user": "message to display  (e.g. Enter name:|username)",
            "comment": "text to display (e.g. --- Login Section ---)",
        }
        hint = _label(dlg, HINTS.get("sleep", ""), size=10, colour=T["dim"])
        hint.pack(padx=20, pady=(3, 0), anchor="w")

        type_var.trace_add("write", lambda *_: hint.configure(text=HINTS.get(type_var.get(), "")))

        _label(dlg, "Note (Optional)", size=10, colour=T["dim"]).pack(padx=20, pady=(16, 2), anchor="w")
        note_entry = ctk.CTkEntry(
            dlg, width=360, fg_color=T["raised"], border_color=T["border"],
            text_color=T["text"], font=ctk.CTkFont(*FONT_BODY), corner_radius=6
        )
        note_entry.pack(padx=20)
        
        adv_frame = ctk.CTkFrame(dlg, fg_color="transparent")
        adv_frame.pack(padx=20, pady=(16, 2), fill="x")
        
        _label(adv_frame, "Retry Count", size=10, colour=T["dim"]).pack(side="left")
        retry_count = ctk.CTkEntry(adv_frame, width=60, fg_color=T["raised"], border_color=T["border"], text_color=T["text"])
        retry_count.pack(side="left", padx=(8, 20))
        retry_count.insert(0, "0")
        
        _label(adv_frame, "Delay (s)", size=10, colour=T["dim"]).pack(side="left")
        retry_delay = ctk.CTkEntry(adv_frame, width=60, fg_color=T["raised"], border_color=T["border"], text_color=T["text"])
        retry_delay.pack(side="left", padx=(8, 0))
        retry_delay.insert(0, "0.5")

        def _build_new_action() -> dict:
            t   = type_var.get()
            val = entry.get().strip()
            a:  dict = {"type": t, "time_offset": 0.5}
            if   t == "sleep":     a["duration"] = float(val or 1)
            elif t == "type":      a["key"] = val
            elif t == "run_command": a["command"] = val; a["wait"] = True
            elif t == "hotkey":    a["keys"] = [k.strip() for k in val.split(",")]
            elif t == "scroll":    a["amount"] = int(val or -3)
            elif t == "screenshot": a["filename"] = val or "screenshot.png"
            elif t == "assert_template": a["template"] = val
            elif t == "clipboard":
                parts = val.split(None, 1)
                a["action"] = parts[0] if parts else "set"
                a["text"]   = parts[1] if len(parts) > 1 else ""
            elif t == "click":
                x, y = [v.strip() for v in val.split(",")]
                a["x"] = int(x); a["y"] = int(y)
            elif t == "loop": a["count"] = int(val or 1); a["actions"] = []
            elif t == "if_template": a["template"] = val; a["then_actions"] = []; a["else_actions"] = []
            elif t == "wait_for_template":
                parts = [v.strip() for v in val.split(",")]
                a["template"] = parts[0] if parts else val
                a["timeout"]  = float(parts[1]) if len(parts) > 1 else 10.0
            elif t == "run_workflow": a["workflow_file"] = val
            elif t == "prompt_user":
                parts = val.split("|", 1)
                a["message"] = parts[0].strip()
                if len(parts) > 1:
                    a["require_input"] = True
                    a["save_to_variable"] = parts[1].strip()
            elif t == "comment": a["text"] = val
            
            note_val = note_entry.get().strip()
            if note_val:
                a["note"] = note_val
                
            rc = int(retry_count.get() or 0)
            rd = float(retry_delay.get() or 0.5)
            if rc > 0:
                a["retry_count"] = rc
                a["retry_delay"] = rd
            return a

        def save():
            try:
                a = _build_new_action()
                def m(d):
                    actions = d.setdefault("actions", [])
                    if insert_idx is not None:
                        actions.insert(insert_idx, a)
                    else:
                        actions.append(a)
                self._modify_workflow(m)
                
                logger.info(f"Added action: {a['type']}")
                dlg.destroy()
            except Exception as e:
                logger.error(f"Add action error: {e}")

        def test():
            try:
                a = _build_new_action()
                threading.Thread(
                    target=lambda: Player(speed=self._speed_var.get()).play_single_action(a),
                    daemon=True
                ).start()
            except Exception as e:
                logger.error(f"Test action error: {e}")

        btn_frame = ctk.CTkFrame(dlg, fg_color="transparent")
        btn_frame.pack(pady=16, padx=20, fill="x")
        
        _btn(btn_frame, "Add to Workflow", save, primary=True, width=250).pack(side="left")
        _btn(btn_frame, "▶ Test", test, width=100, fg_color=T["accent"], text_color=T["text"]).pack(side="right")

    def _open_edit_dialog(self, idx: int, action: dict):
        atype = action.get("type", "unknown")
        dlg = self._dialog(f"Edit {atype.title()}", "400x370")

        _label(dlg, "Value", size=10, colour=T["dim"]).pack(padx=20, pady=(16, 2), anchor="w")
        val_frame = ctk.CTkFrame(dlg, fg_color="transparent")
        val_frame.pack(padx=20, fill="x")
        
        entry = ctk.CTkEntry(
            val_frame, fg_color=T["raised"], border_color=T["border"],
            text_color=T["text"], font=ctk.CTkFont(*FONT_BODY), corner_radius=6
        )
        entry.pack(side="left", fill="x", expand=True)

        def open_snipping():
            from .snipping_tool import SnippingTool
            dlg.withdraw()
            def on_capture(filename):
                dlg.deiconify()
                entry.delete(0, "end")
                entry.insert(0, filename)
            def on_cancel():
                dlg.deiconify()
            SnippingTool(self, on_capture, on_cancel)

        def open_coord_picker():
            from .coord_picker import CoordinatePicker
            dlg.withdraw()
            def on_pick(x, y):
                dlg.deiconify()
                entry.delete(0, "end")
                entry.insert(0, f"{x},{y}")
            def on_cancel():
                dlg.deiconify()
            CoordinatePicker(self, on_pick, on_cancel)
            
        def open_hotkey_picker():
            from .hotkey_picker import HotkeyPicker
            dlg.withdraw()
            def on_capture(combo):
                dlg.deiconify()
                entry.delete(0, "end")
                entry.insert(0, combo)
            def on_cancel():
                dlg.deiconify()
            HotkeyPicker(self, on_capture, on_cancel)

        capture_btn = _btn(val_frame, "✂", open_snipping, width=32, fg_color="transparent", border_width=1, border_color=T["border"], text_color=T["dim"])
        capture_btn.pack(side="right", padx=(8, 0))
        
        coord_btn = _btn(val_frame, "🎯", open_coord_picker, width=32, fg_color="transparent", border_width=1, border_color=T["border"], text_color=T["dim"])
        coord_btn.pack(side="right", padx=(8, 0))

        hotkey_btn = _btn(val_frame, "⌨️", open_hotkey_picker, width=32, fg_color="transparent", border_width=1, border_color=T["border"], text_color=T["dim"])
        hotkey_btn.pack(side="right", padx=(8, 0))

        cur = {
            "sleep":            str(action.get("duration", 1.0)),
            "type":             action.get("key", ""),
            "run_command":      action.get("command", ""),
            "hotkey":           ",".join(action.get("keys", [])),
            "click":            f"{action.get('x',0)},{action.get('y',0)}",
            "scroll":           str(action.get("amount", 0)),
            "clipboard":        f"{action.get('action','set')} {action.get('text','')}",
            "screenshot":       action.get("filename", ""),
            "assert_template":  action.get("template", ""),
            "if_template":      action.get("template", ""),
            "wait_for_template":f"{action.get('template','')},{action.get('timeout',10)}",
            "run_workflow":     action.get("workflow_file", ""),
            "prompt_user":      action.get("message", "") + (f"|{action.get('save_to_variable')}" if action.get("require_input") else ""),
            "comment":          action.get("text", ""),
        }.get(atype, "")
        entry.insert(0, cur)
        
        _label(dlg, "Note (Optional)", size=10, colour=T["dim"]).pack(padx=20, pady=(16, 2), anchor="w")
        note_entry = ctk.CTkEntry(
            dlg, width=360, fg_color=T["raised"], border_color=T["border"],
            text_color=T["text"], font=ctk.CTkFont(*FONT_BODY), corner_radius=6
        )
        note_entry.pack(padx=20)
        note_entry.insert(0, action.get("note", ""))

        adv_frame = ctk.CTkFrame(dlg, fg_color="transparent")
        adv_frame.pack(padx=20, pady=(16, 2), fill="x")
        
        _label(adv_frame, "Retry Count", size=10, colour=T["dim"]).pack(side="left")
        retry_count = ctk.CTkEntry(adv_frame, width=60, fg_color=T["raised"], border_color=T["border"], text_color=T["text"])
        retry_count.pack(side="left", padx=(8, 20))
        retry_count.insert(0, str(action.get("retry_count", 0)))
        
        _label(adv_frame, "Delay (s)", size=10, colour=T["dim"]).pack(side="left")
        retry_delay = ctk.CTkEntry(adv_frame, width=60, fg_color=T["raised"], border_color=T["border"], text_color=T["text"])
        retry_delay.pack(side="left", padx=(8, 0))
        retry_delay.insert(0, str(action.get("retry_delay", 0.5)))

        def _build_updated_action() -> dict:
            val = entry.get().strip()
            upd = copy.deepcopy(action)
            if   atype == "sleep":            upd["duration"] = float(val)
            elif atype == "type":             upd["key"] = val
            elif atype == "run_command":      upd["command"] = val
            elif atype == "hotkey":           upd["keys"] = [k.strip() for k in val.split(",")]
            elif atype == "click":
                x, y = [v.strip() for v in val.split(",")]
                upd["x"] = int(x); upd["y"] = int(y)
            elif atype == "scroll":           upd["amount"] = int(val)
            elif atype == "clipboard":
                parts = val.split(None, 1)
                upd["action"] = parts[0] if parts else "set"
                upd["text"]   = parts[1] if len(parts) > 1 else ""
            elif atype == "screenshot":       upd["filename"] = val
            elif atype in ("assert_template","if_template"): upd["template"] = val
            elif atype == "wait_for_template":
                parts = [v.strip() for v in val.split(",")]
                upd["template"] = parts[0] if parts else val
                upd["timeout"]  = float(parts[1]) if len(parts) > 1 else 10.0
            elif atype == "run_workflow":     upd["workflow_file"] = val
            elif atype == "prompt_user":
                parts = val.split("|", 1)
                upd["message"] = parts[0].strip()
                if len(parts) > 1:
                    upd["require_input"] = True
                    upd["save_to_variable"] = parts[1].strip()
                else:
                    upd["require_input"] = False
                    upd.pop("save_to_variable", None)
            elif atype == "comment":          upd["text"] = val
            
            note_val = note_entry.get().strip()
            if note_val:
                upd["note"] = note_val
            elif "note" in upd:
                del upd["note"]

            rc = int(retry_count.get() or 0)
            rd = float(retry_delay.get() or 0.5)
            if rc > 0:
                upd["retry_count"] = rc
                upd["retry_delay"] = rd
            else:
                upd.pop("retry_count", None)
                upd.pop("retry_delay", None)
            return upd

        def save():
            try:
                upd = _build_updated_action()
                def m(d):
                    if 0 <= idx < len(d.get("actions", [])):
                        d["actions"][idx] = upd
                self._modify_workflow(m)
                logger.info(f"Edited action #{idx+1}")
                dlg.destroy()
            except Exception as e:
                logger.error(f"Edit error: {e}")

        def test():
            try:
                upd = _build_updated_action()
                threading.Thread(
                    target=lambda: Player(speed=self._speed_var.get()).play_single_action(upd),
                    daemon=True
                ).start()
            except Exception as e:
                logger.error(f"Test error: {e}")

        btn_frame = ctk.CTkFrame(dlg, fg_color="transparent")
        btn_frame.pack(pady=16, padx=20, fill="x")
        
        _btn(btn_frame, "Save Changes", save, primary=True, width=250).pack(side="left")
        _btn(btn_frame, "▶ Test", test, width=100, fg_color=T["accent"], text_color=T["text"]).pack(side="right")

    def _toggle_bulk_mode(self):
        self._bulk_mode = not self._bulk_mode
        self._selected_indices.clear()
        self._refresh_workflow()

    def _build_bulk_toolbar(self, parent):
        self._bulk_toolbar = ctk.CTkFrame(parent, fg_color=T["surface"], corner_radius=6)
        self._bulk_toolbar.pack(fill="x", pady=(0, 10))
        
        _label(self._bulk_toolbar, "Bulk Edit Mode", colour=T["accent"], weight="bold").pack(side="left", padx=12)
        
        _btn(self._bulk_toolbar, "Cancel", self._toggle_bulk_mode).pack(side="right", padx=12, pady=6)
        _btn(self._bulk_toolbar, "🗑 Delete", self._bulk_delete, danger=True).pack(side="right", padx=6, pady=6)
        _btn(self._bulk_toolbar, "⧉ Duplicate", self._bulk_duplicate).pack(side="right", padx=6, pady=6)

    def _bulk_delete(self):
        if not self._selected_indices: return
        self._push_undo()
        path = os.path.join(WORKSPACE_DIR, self.file_var.get())
        data = load_json(path, {})
        actions = data.get("actions", [])
        
        new_actions = [a for i, a in enumerate(actions) if i not in self._selected_indices]
        data["actions"] = new_actions
        save_json(path, data)
        self._selected_indices.clear()
        self._toggle_bulk_mode()  # exit bulk mode
        self._refresh_stats()

    def _bulk_duplicate(self):
        if not self._selected_indices: return
        self._push_undo()
        path = os.path.join(WORKSPACE_DIR, self.file_var.get())
        data = load_json(path, {})
        actions = data.get("actions", [])
        
        new_actions = []
        for i, a in enumerate(actions):
            new_actions.append(a)
            if i in self._selected_indices:
                dupe = copy.deepcopy(a)
                new_actions.append(dupe)
                
        data["actions"] = new_actions
        save_json(path, data)
        self._selected_indices.clear()
        self._toggle_bulk_mode()  # exit bulk mode
        self._refresh_stats()

    # ── PANEL: Scheduler ──────────────────────────────────────────────────────

    def _build_scheduler(self, p: ctk.CTkFrame):
        p.grid_columnconfigure(0, weight=1)
        p.grid_rowconfigure(1, weight=1)
        self._page_header(p, "Scheduler", row=0)

        form = ctk.CTkFrame(p, fg_color=T["surface"], corner_radius=8)
        form.grid(row=0, column=0, sticky="ew", padx=24, pady=(56, 8))
        form.grid_columnconfigure((0, 1, 2), weight=1)

        fields = [
            ("Workflow", 0), ("Interval", 1), ("Value (N or HH:MM)", 2)
        ]
        for label, col in fields:
            _label(form, label, size=10, colour=T["dim"]).grid(
                row=0, column=col, padx=12, pady=(12, 2), sticky="w")

        self._sched_file = ctk.StringVar()
        ctk.CTkOptionMenu(
            form, variable=self._sched_file,
            values=get_workflow_files(),
            fg_color=T["raised"], button_color=T["border"],
            text_color=T["text"], font=ctk.CTkFont(*FONT_BODY),
            width=160, corner_radius=6
        ).grid(row=1, column=0, padx=12, pady=(0, 12), sticky="ew")

        self._sched_type = ctk.StringVar(value="minutes")
        ctk.CTkOptionMenu(
            form, variable=self._sched_type,
            values=["minutes", "hours", "daily_at"],
            fg_color=T["raised"], button_color=T["border"],
            text_color=T["text"], font=ctk.CTkFont(*FONT_BODY),
            width=130, corner_radius=6
        ).grid(row=1, column=1, padx=12, pady=(0, 12), sticky="ew")

        self._sched_val = ctk.CTkEntry(
            form, fg_color=T["raised"], border_color=T["border"],
            text_color=T["text"], font=ctk.CTkFont(*FONT_BODY),
            corner_radius=6, placeholder_text="e.g. 30 or 09:00"
        )
        self._sched_val.grid(row=1, column=2, padx=12, pady=(0, 12), sticky="ew")

        _btn(form, "Add Schedule", self._add_schedule, primary=True).grid(
            row=2, column=0, columnspan=3, padx=12, pady=(0, 12), sticky="ew")

        # List header
        lhdr = ctk.CTkFrame(p, fg_color="transparent")
        lhdr.grid(row=1, column=0, sticky="ew", padx=24, pady=(8, 4))
        for col, txt in enumerate(["Workflow", "Schedule", "Runs", "Last Run", ""]):
            _label(lhdr, txt, size=10, colour=T["dim"]).grid(row=0, column=col, padx=6, sticky="w")
        lhdr.grid_columnconfigure(0, weight=1)

        _sep(p).grid(row=2, column=0, sticky="ew", padx=24)

        self._sched_list = ctk.CTkScrollableFrame(p, fg_color="transparent")
        self._sched_list.grid(row=3, column=0, sticky="nsew", padx=24, pady=(0, 24))
        self._sched_list.grid_columnconfigure(0, weight=1)
        p.grid_rowconfigure(3, weight=1)

    def _refresh_scheduler(self):
        for w in self._sched_list.winfo_children():
            w.destroy()
        jobs = self.scheduler.get_all()
        if not jobs:
            _label(self._sched_list, "No scheduled jobs.", colour=T["dim"]).pack(pady=24)
            return
        for job in jobs:
            row = ctk.CTkFrame(self._sched_list, fg_color=T["raised"], corner_radius=6)
            row.pack(fill="x", pady=2)
            row.grid_columnconfigure(0, weight=1)

            txt = (f"{os.path.basename(job.get('workflow_file',''))}    "
                   f"{job.get('interval_value','')} {job.get('interval_type','')}    "
                   f"Runs: {job.get('run_count',0)}    "
                   f"Last: {job.get('last_run') or '—'}")
            _label(row, txt, size=11, colour=T["text"], anchor="w").grid(
                row=0, column=0, padx=12, pady=10, sticky="ew")

            _btn(row, "Remove", lambda jid=job["id"]: self._remove_schedule(jid),
                 danger=True, width=70, height=28).grid(row=0, column=1, padx=10, pady=8)

    def _add_schedule(self):
        f = self._sched_file.get()
        t = self._sched_type.get()
        v = self._sched_val.get().strip()
        if not f or not v:
            logger.warning("Scheduler: file and value required."); return
        self.scheduler.add(os.path.join(WORKSPACE_DIR, f), t, v)
        self._refresh_scheduler()

    def _remove_schedule(self, job_id: int):
        self.scheduler.remove(job_id)
        self._refresh_scheduler()

    def _run_scheduled(self, wf_path: str):
        Player(workflow_path=wf_path).play()
        self.after(0, self._refresh_stats)

    # ── PANEL: Variables ──────────────────────────────────────────────────────

    def _build_variables(self, p: ctk.CTkFrame):
        p.grid_columnconfigure(0, weight=1)
        p.grid_rowconfigure(1, weight=1)
        self._page_header(p, "Variables", row=0)

        form = ctk.CTkFrame(p, fg_color=T["surface"], corner_radius=8)
        form.grid(row=0, column=0, sticky="ew", padx=24, pady=(56, 8))
        form.grid_columnconfigure((0, 1), weight=1)

        _label(form, "Key", size=10, colour=T["dim"]).grid(row=0, column=0, padx=12, pady=(12,2), sticky="w")
        self._var_key = ctk.CTkEntry(
            form, fg_color=T["raised"], border_color=T["border"],
            text_color=T["text"], font=ctk.CTkFont(*FONT_BODY),
            corner_radius=6, placeholder_text="e.g. username"
        )
        self._var_key.grid(row=1, column=0, padx=12, pady=(0, 12), sticky="ew")

        _label(form, "Value", size=10, colour=T["dim"]).grid(row=0, column=1, padx=12, pady=(12,2), sticky="w")
        self._var_val = ctk.CTkEntry(
            form, fg_color=T["raised"], border_color=T["border"],
            text_color=T["text"], font=ctk.CTkFont(*FONT_BODY),
            corner_radius=6, placeholder_text="e.g. john_doe"
        )
        self._var_val.grid(row=1, column=1, padx=12, pady=(0, 12), sticky="ew")

        _btn(form, "Set Variable", self._set_variable, primary=True).grid(
            row=2, column=0, columnspan=2, padx=12, pady=(0, 6), sticky="ew")
        _label(form, "Use  {{variable_name}}  inside TypeAction to inject the value at runtime.\n"
                     "Built-in:  {{TIME}}, {{DATE}}, {{DATETIME}}, {{CLIPBOARD}}, {{loop_index}}",
               size=10, colour=T["dim"]).grid(
            row=3, column=0, columnspan=2, padx=12, pady=(0, 10), sticky="w")

        # List header
        lhdr = ctk.CTkFrame(p, fg_color="transparent")
        lhdr.grid(row=1, column=0, sticky="ew", padx=24, pady=(8, 4))
        lhdr.grid_columnconfigure(0, weight=1)
        for col, txt in enumerate(["Variable", "Value", ""]):
            _label(lhdr, txt, size=10, colour=T["dim"]).grid(row=0, column=col, padx=6, sticky="w")

        _sep(p).grid(row=2, column=0, sticky="ew", padx=24)

        self._var_list = ctk.CTkScrollableFrame(p, fg_color="transparent")
        self._var_list.grid(row=3, column=0, sticky="nsew", padx=24, pady=(0, 24))
        self._var_list.grid_columnconfigure(1, weight=1)
        p.grid_rowconfigure(3, weight=1)

    def _refresh_variables(self):
        for w in self._var_list.winfo_children():
            w.destroy()
        self.var_manager.load()
        if not self.var_manager.variables:
            _label(self._var_list, "No variables defined.", colour=T["dim"]).pack(pady=24)
            return
        for key, value in self.var_manager.variables.items():
            row = ctk.CTkFrame(self._var_list, fg_color=T["raised"], corner_radius=6)
            row.pack(fill="x", pady=2)
            row.grid_columnconfigure(1, weight=1)
            _label(row, f"{{{{{key}}}}}", size=11, colour=T["accent"],
                   font=ctk.CTkFont(*FONT_MONO)).grid(row=0, column=0, padx=12, pady=10, sticky="w")
            _label(row, value, size=11, colour=T["text"], anchor="w").grid(
                row=0, column=1, padx=8, pady=10, sticky="ew")
            _btn(row, "Delete", lambda k=key: self._del_variable(k),
                 danger=True, width=70, height=28).grid(row=0, column=2, padx=10, pady=8)

    def _set_variable(self):
        k, v = self._var_key.get().strip(), self._var_val.get().strip()
        if not k: logger.warning("Variable key required."); return
        self.var_manager.set(k, v)
        self._var_key.delete(0, "end"); self._var_val.delete(0, "end")
        logger.info(f"Variable set: {{{{{k}}}}} = {v!r}")
        self._refresh_variables()

    def _del_variable(self, key: str):
        self.var_manager.delete(key)
        logger.info(f"Deleted variable: {key}")
        self._refresh_variables()

    # ── PANEL: History ────────────────────────────────────────────────────────

    def _build_history(self, p: ctk.CTkFrame):
        p.grid_columnconfigure(0, weight=1)
        p.grid_rowconfigure(1, weight=1)
        self._page_header(p, "Run History", row=0)

        tb = ctk.CTkFrame(p, fg_color="transparent")
        tb.grid(row=0, column=0, sticky="ew", padx=24, pady=(56, 4))
        _btn(tb, "Clear History", self._clear_history, danger=True).pack(side="right")

        lhdr = ctk.CTkFrame(p, fg_color="transparent")
        lhdr.grid(row=1, column=0, sticky="ew", padx=24, pady=(4, 2))
        lhdr.grid_columnconfigure(1, weight=1)
        for col, txt in enumerate(["Status", "Workflow", "Time", "Actions", "Duration"]):
            _label(lhdr, txt, size=10, colour=T["dim"]).grid(row=0, column=col, padx=6, sticky="w")

        _sep(p).grid(row=2, column=0, sticky="ew", padx=24)

        self._hist_list = ctk.CTkScrollableFrame(p, fg_color="transparent")
        self._hist_list.grid(row=3, column=0, sticky="nsew", padx=24, pady=(0, 24))
        self._hist_list.grid_columnconfigure(1, weight=1)
        p.grid_rowconfigure(3, weight=1)

    def _refresh_history(self):
        for w in self._hist_list.winfo_children():
            w.destroy()
        history = load_json(RUN_HISTORY_FILE, [])
        if not history:
            _label(self._hist_list, "No runs recorded yet.", colour=T["dim"]).pack(pady=24)
            return
        for entry in history:
            success = entry.get("success", False)
            row = ctk.CTkFrame(self._hist_list, fg_color=T["raised"], corner_radius=6)
            row.pack(fill="x", pady=2)
            row.grid_columnconfigure(1, weight=1)

            # Status badge
            sbadge = ctk.CTkFrame(row, fg_color=T["ok"] if success else T["err"],
                                  corner_radius=4, width=60)
            sbadge.grid(row=0, column=0, padx=(10, 8), pady=8)
            _label(sbadge, "OK" if success else "FAIL", size=10, colour="#000000").pack(padx=6, pady=2)

            _label(row, entry.get("workflow", "?"), size=11, colour=T["text"], anchor="w").grid(
                row=0, column=1, padx=4, pady=8, sticky="ew")
            _label(row, entry.get("timestamp", ""), size=10, colour=T["dim"]).grid(
                row=0, column=2, padx=8, pady=8)
            _label(row, str(entry.get("action_count", 0)), size=10, colour=T["dim"]).grid(
                row=0, column=3, padx=8, pady=8)
            _label(row, f"{entry.get('duration_sec',0)}s", size=10, colour=T["dim"]).grid(
                row=0, column=4, padx=8, pady=8)

            if entry.get("error"):
                _label(row, entry["error"], size=10, colour=T["err"], anchor="w").grid(
                    row=1, column=0, columnspan=5, padx=12, pady=(0, 6), sticky="ew")

    def _clear_history(self):
        save_json(RUN_HISTORY_FILE, [])
        self._refresh_history()
        self._refresh_stats()
        logger.info("Run history cleared.")

    # ── Recording / Playback ──────────────────────────────────────────────────

    def start_recording(self):
        if self.recording: return
        self.recording = True
        
        self._set_status("Prepare...", T["warn"])
        self.record_btn.configure(state="disabled")
        self.stop_btn.configure(state="normal", fg_color=T["warn"], text_color=T["bg"])
        self.play_btn.configure(state="disabled")
        self.stop_play_btn.configure(state="disabled")

        def _do_start():
            if not self.recording:
                return # Aborted during countdown
            path = os.path.join(WORKSPACE_DIR, self.file_var.get())
            self.recorder = Recorder(workflow_path=path)
            self.recorder.start()
            logger.info(f"Recording  →  {self.file_var.get()}")
            self._set_status("Recording", T["err"])
            
        from .countdown_overlay import CountdownOverlay
        self._countdown = CountdownOverlay(self, on_complete=_do_start)

    def stop_recording(self):
        if not self.recording: return
        self.recording = False
        
        if hasattr(self, '_countdown') and self._countdown.winfo_exists():
            self._countdown.destroy()
            
        if self.recorder:
            self.recorder.stop()
        logger.info(f"Stopped  →  saved to  {self.file_var.get()}")
        self._set_status("Idle", T["ok"])
        self.record_btn.configure(state="normal")
        self.stop_btn.configure(state="disabled", fg_color=T["raised"], text_color=T["dim"])
        self.play_btn.configure(state="normal")
        self.stop_play_btn.configure(state="disabled")
        self.file_dropdown.configure(values=get_workflow_files())
        self._refresh_stats()

    def playback(self, start_idx: int = 0):
        if self.recording: return
        speed = round(self._speed_var.get(), 2)
        step  = self._step_mode.get()
        logger.info(f"Playback  →  {self.file_var.get()}  start={start_idx+1}  speed={speed}x  step={step}")
        self._set_status("Playing", T["accent"])
        self.play_btn.configure(state="disabled")
        self.stop_play_btn.configure(state="normal", text_color=T["err"])

        step_cb = self._make_step_callback() if step else None
        prompt_cb = self._make_prompt_callback()
        ripple_cb = self._make_ripple_callback()

        from .floating_status import FloatingStatus
        def _on_pause():
            if hasattr(self, "_player") and self._player:
                self._player.pause()
                
        def _on_resume():
            if hasattr(self, "_player") and self._player:
                self._player.resume()
                
        self._floating_status = FloatingStatus(
            self, on_stop=self._stop_playback, on_pause=_on_pause, on_resume=_on_resume
        )

        def run():
            try:
                p = Player(
                    workflow_path=os.path.join(WORKSPACE_DIR, self.file_var.get()),
                    speed=speed,
                    step_callback=step_cb,
                    progress_callback=self._on_progress_update,
                    prompt_callback=prompt_cb,
                    ripple_callback=ripple_cb,
                )
                self._player = p
                p.play(start_idx=start_idx)
            except Exception as e:
                logger.error(f"Playback error: {e}")
            finally:
                self._player = None
                self.after(0, self._on_done)

        threading.Thread(target=run, daemon=True).start()

    def _stop_playback(self):
        """Signal the active player to stop after the current action."""
        if self._player:
            self._player.stop()
            logger.info("Stop signal sent to player.")
        self.stop_play_btn.configure(state="disabled", text_color=T["dim"])

    def _on_speed_change(self, val):
        self._speed_label.configure(text=f"{round(val, 2)}x")

    def _make_prompt_callback(self) -> Callable:
        import queue
        q: queue.Queue[str] = queue.Queue()
        def callback(action_dict: dict) -> str:
            self.after(0, self._show_prompt_dialog, action_dict, q)
            return q.get()
        return callback
        
    def _make_ripple_callback(self) -> Callable:
        import queue
        q: queue.Queue[str] = queue.Queue()
        def callback(x: int, y: int):
            def _show():
                from .click_ripple import ClickRipple
                ClickRipple(self, x, y, on_complete=lambda: q.put("done"))
            self.after(0, _show)
            return q.get()
        return callback

    def _show_prompt_dialog(self, action_dict: dict, q):
        dlg = ctk.CTkToplevel(self)
        dlg.title("Automation Prompt")
        dlg.geometry("400x240")
        dlg.transient(self)
        dlg.grab_set()

        msg = action_dict.get("message", "Please confirm to continue.")
        lbl = ctk.CTkLabel(dlg, text=msg, font=ctk.CTkFont(*FONT_BODY), text_color=T["text"], wraplength=360)
        lbl.pack(pady=(30, 10), padx=20)
        
        req_input = action_dict.get("require_input", False)
        inp_entry = None
        if req_input:
            inp_entry = ctk.CTkEntry(
                dlg, width=320, fg_color=T["raised"], border_color=T["border"],
                text_color=T["text"], font=ctk.CTkFont(*FONT_BODY), corner_radius=6
            )
            inp_entry.pack(pady=(0, 10), padx=20)
            inp_entry.focus_set()
        
        btn_frame = ctk.CTkFrame(dlg, fg_color="transparent")
        btn_frame.pack(fill="x", side="bottom", pady=20)
        
        def on_ok():
            val = inp_entry.get() if inp_entry else "OK"
            q.put(val)
            dlg.destroy()
            
        def on_cancel():
            q.put("!CANCEL!")
            dlg.destroy()
            
        _btn(btn_frame, "OK", on_ok, primary=True).pack(side="right", padx=20)
        _btn(btn_frame, "Cancel", on_cancel).pack(side="right")

    def _make_step_callback(self) -> Callable:
        """Return a blocking step callback that shows a confirmation dialog."""
        import queue
        q: queue.Queue[str] = queue.Queue()

        def callback(action_dict: dict) -> str:
            self.after(0, self._show_step_dialog, action_dict, q)
            return q.get()  # Block the player thread until user responds

        return callback

    def _show_step_dialog(self, action_dict: dict, q):
        """Tiny overlay asking the user to run / skip / stop."""
        atype   = action_dict.get("type", "?")
        label   = ACTION_LABELS.get(atype, atype)
        summary = self._action_summary(atype, action_dict)

        dlg = ctk.CTkToplevel(self)
        dlg.title("Step Confirm")
        dlg.geometry("360x160")
        dlg.transient(self)
        dlg.configure(fg_color=T["surface"])
        dlg.attributes("-topmost", True)
        dlg.resizable(False, False)

        _label(dlg, f"Next:  {label}", size=12, colour=T["label"]).pack(
            padx=20, pady=(16, 2), anchor="w")
        _label(dlg, summary[:80] or "—", size=11, colour=T["text"]).pack(
            padx=20, pady=(0, 14), anchor="w")

        row = ctk.CTkFrame(dlg, fg_color="transparent")
        row.pack(padx=20)

        def choose(val: str):
            dlg.destroy()
            q.put(val)

        _btn(row, "Run",  lambda: choose("run"),  primary=True, width=90).pack(side="left", padx=(0, 6))
        _btn(row, "Skip", lambda: choose("skip"), width=90).pack(side="left", padx=(0, 6))
        _btn(row, "Stop", lambda: choose("stop"), danger=True, width=90).pack(side="left")

        # If dialog is closed by X, treat as stop
        dlg.protocol("WM_DELETE_WINDOW", lambda: choose("stop"))

    def _on_progress_update(self, step: int, total: int, action_dict: dict):
        self.after(0, self._update_progress_ui, step, total, action_dict)

    def _update_progress_ui(self, step: int, total: int, action_dict: dict):
        pct = step / max(1, total)
        self.progress_bar.set(pct)
        atype = action_dict.get("type", "?")
        label = ACTION_LABELS.get(atype, atype)
        text = f"Step {step}/{total}: {label}"
        self.progress_label.configure(text=text, text_color=T["text"])
        
        if hasattr(self, '_floating_status') and self._floating_status.winfo_exists():
            self._floating_status.update_status(text)
            
        # Highlight current row and auto-scroll
        if hasattr(self, "_action_rows") and len(self._action_rows) >= step > 0:
            idx = step - 1
            if hasattr(self, "_current_highlight_idx") and self._current_highlight_idx is not None:
                old_idx = self._current_highlight_idx
                if 0 <= old_idx < len(self._action_rows):
                    self._action_rows[old_idx].configure(fg_color=T["raised"])
            
            self._action_rows[idx].configure(fg_color=T["accent"])
            self._current_highlight_idx = idx
            
            # Auto-scroll if total is large enough
            if total > 5:
                # yview_moveto takes fraction from 0.0 to 1.0
                # Subtracting a small offset so the item isn't glued to the very top
                scroll_fraction = max(0.0, (idx / total) - 0.1)
                self._wf_list._parent_canvas.yview_moveto(scroll_fraction)

    def _test_template_match(self, action: dict):
        tmpl = action.get("template") or action.get("template_image")
        conf = action.get("confidence", 0.8)
        
        from ..core.vision import locate_template
        loc = locate_template(tmpl, confidence=conf)
        
        if loc:
            x, y = loc
            if action.get("type") == "click":
                x += action.get("offset_x", 0)
                y += action.get("offset_y", 0)
            
            # Show ripple
            from .click_ripple import ClickRipple
            ClickRipple(self, x, y)
            
            self._set_status(f"Template found at ({x}, {y})", T["ok"])
        else:
            self._set_status("Template not found on screen!", T["err"])

    def _on_done(self):
        self._set_status("Idle", T["ok"])
        self.play_btn.configure(state="normal")
        self.stop_play_btn.configure(state="disabled", text_color=T["dim"])
        if hasattr(self, "progress_bar"):
            self.progress_bar.set(0.0)
            self.progress_label.configure(text="Ready", text_color=T["dim"])
            
        # Reset highlight
        if hasattr(self, "_current_highlight_idx") and self._current_highlight_idx is not None:
            old_idx = self._current_highlight_idx
            if hasattr(self, "_action_rows") and 0 <= old_idx < len(self._action_rows):
                self._action_rows[old_idx].configure(fg_color=T["raised"])
            self._current_highlight_idx = None
            
        if hasattr(self, '_floating_status') and self._floating_status.winfo_exists():
            self._floating_status.destroy()
            
        self._refresh_stats()
        if self._active_nav == "history":
            self._refresh_history()

    def _set_status(self, text: str, colour: str):
        self._status_dot.configure(text_color=colour)
        self._status_text.configure(text=text)

    # ── Workflow file management ───────────────────────────────────────────────

    def _on_file_select(self, choice: str):
        self.file_var.set(choice)
        logger.info(f"Workflow: {choice}")
        
        # Reset undo/redo when switching files
        self._undo_stack.clear()
        self._redo_stack.clear()
        self._update_undo_redo_buttons()
        
        if self._active_nav == "workflow":
            self._refresh_workflow()
        self._refresh_stats()

    def _new_workflow(self):
        dlg = self._dialog("New Workflow", "360x260")
        _label(dlg, "Workflow name (without .json):", size=10, colour=T["dim"]).pack(
            padx=20, pady=(16, 4), anchor="w")
        entry = ctk.CTkEntry(
            dlg, width=320, fg_color=T["raised"], border_color=T["border"],
            text_color=T["text"], font=ctk.CTkFont(*FONT_BODY), corner_radius=6,
            placeholder_text="e.g. daily_backup"
        )
        entry.pack(padx=20)

        _label(dlg, "Starter Template:", size=10, colour=T["dim"]).pack(
            padx=20, pady=(12, 4), anchor="w")
        preset_var = ctk.StringVar(value="Blank (Empty)")
        presets = ["Blank (Empty)", "App Launcher & Wait", "Auto Clipboard Injector", "Loop Clicker"]
        ctk.CTkOptionMenu(
            dlg, variable=preset_var, values=presets,
            fg_color=T["raised"], button_color=T["border"],
            text_color=T["text"], font=ctk.CTkFont(*FONT_BODY),
            width=320, corner_radius=6
        ).pack(padx=20)

        def create():
            name = entry.get().strip()
            if not name: return
            filename = f"{name}.json"
            path     = os.path.join(WORKSPACE_DIR, filename)

            actions = []
            chosen = preset_var.get()
            if chosen == "App Launcher & Wait":
                actions = [
                    {"type": "run_command", "command": "open -a Safari", "wait": False, "time_offset": 0.5},
                    {"type": "wait_for_template", "template": "safari_logo.png", "timeout": 10.0, "time_offset": 0.5}
                ]
            elif chosen == "Auto Clipboard Injector":
                actions = [
                    {"type": "clipboard", "action": "set", "text": "{{my_var}}", "time_offset": 0.5},
                    {"type": "clipboard", "action": "paste", "time_offset": 0.5}
                ]
            elif chosen == "Loop Clicker":
                actions = [
                    {"type": "loop", "count": 5, "actions": [
                        {"type": "click", "x": 500, "y": 300, "button": "left", "clicks": 1, "time_offset": 0.5},
                        {"type": "sleep", "duration": 1.0, "time_offset": 0.0}
                    ], "time_offset": 0.5}
                ]

            save_json(path, {"workflow_name": name, "created_at": time.strftime("%Y-%m-%dT%H:%M:%S"), "actions": actions})
            self.file_var.set(filename)
            self.file_dropdown.configure(values=get_workflow_files())
            logger.info(f"Created workflow: {filename} (preset={chosen})")
            dlg.destroy()
            if self._active_nav == "workflow":
                self._refresh_workflow()
            self._refresh_stats()

        _btn(dlg, "Create Workflow", create, primary=True, width=320).pack(pady=16, padx=20)

    def _rename_workflow(self):
        old_filename = self.file_var.get()
        old_name = os.path.splitext(old_filename)[0]
        dlg = self._dialog("Rename Workflow", "360x160")
        _label(dlg, f"New name for '{old_filename}':", size=10, colour=T["dim"]).pack(
            padx=20, pady=(16, 4), anchor="w")
        entry = ctk.CTkEntry(
            dlg, width=320, fg_color=T["raised"], border_color=T["border"],
            text_color=T["text"], font=ctk.CTkFont(*FONT_BODY), corner_radius=6
        )
        entry.insert(0, old_name)
        entry.pack(padx=20)

        def apply_rename():
            new_name = entry.get().strip()
            if not new_name or new_name == old_name:
                dlg.destroy()
                return
            new_filename = f"{new_name}.json"
            old_path = os.path.join(WORKSPACE_DIR, old_filename)
            new_path = os.path.join(WORKSPACE_DIR, new_filename)

            if os.path.exists(new_path):
                logger.warning(f"File '{new_filename}' already exists.")
                return

            try:
                os.rename(old_path, new_path)
                # Update json workflow_name field
                data = load_json(new_path, {})
                data["workflow_name"] = new_name
                save_json(new_path, data)

                self.file_var.set(new_filename)
                self.file_dropdown.configure(values=get_workflow_files())
                logger.info(f"Renamed: {old_filename} -> {new_filename}")
                dlg.destroy()
                if self._active_nav == "workflow":
                    self._refresh_workflow()
                self._refresh_stats()
            except Exception as e:
                logger.error(f"Rename failed: {e}")

        _btn(dlg, "Apply Rename", apply_rename, primary=True, width=320).pack(pady=14, padx=20)

    def _duplicate_workflow_file(self):
        cur_filename = self.file_var.get()
        cur_path = os.path.join(WORKSPACE_DIR, cur_filename)
        if not os.path.exists(cur_path):
            return

        base_name = os.path.splitext(cur_filename)[0]
        dupe_filename = f"{base_name}_copy.json"
        dupe_path = os.path.join(WORKSPACE_DIR, dupe_filename)

        data = load_json(cur_path, {})
        data["workflow_name"] = f"{base_name}_copy"
        save_json(dupe_path, data)

        self.file_var.set(dupe_filename)
        self.file_dropdown.configure(values=get_workflow_files())
        logger.info(f"Duplicated workflow: {cur_filename} -> {dupe_filename}")
        if self._active_nav == "workflow":
            self._refresh_workflow()
        self._refresh_stats()

    def _delete_workflow_file(self):
        cur_filename = self.file_var.get()
        files = get_workflow_files()
        if len(files) <= 1:
            logger.warning("Cannot delete the only remaining workflow file.")
            return

        dlg = self._dialog("Delete Workflow", "360x160")
        _label(dlg, f"Are you sure you want to delete '{cur_filename}'?", size=11, colour=T["err"]).pack(
            padx=20, pady=(20, 14), anchor="w")

        row = ctk.CTkFrame(dlg, fg_color="transparent")
        row.pack(padx=20)

        def confirm_delete():
            cur_path = os.path.join(WORKSPACE_DIR, cur_filename)
            try:
                if os.path.exists(cur_path):
                    os.remove(cur_path)
                logger.info(f"Deleted workflow file: {cur_filename}")
                new_files = get_workflow_files()
                self.file_var.set(new_files[0])
                self.file_dropdown.configure(values=new_files)
                dlg.destroy()
                if self._active_nav == "workflow":
                    self._refresh_workflow()
                self._refresh_stats()
            except Exception as e:
                logger.error(f"Delete failed: {e}")

        _btn(row, "Delete File", confirm_delete, danger=True, width=150).pack(side="left", padx=(0, 10))
        _btn(row, "Cancel", dlg.destroy, width=150).pack(side="left")

    def _export_package(self):
        cur_filename = self.file_var.get()
        cur_path = os.path.join(WORKSPACE_DIR, cur_filename)
        if not os.path.exists(cur_path):
            logger.error("Workflow file not found.")
            return

        save_path = tkinter.filedialog.asksaveasfilename(
            title="Export DAuto Package",
            defaultextension=".dauto",
            filetypes=[("DAuto Package", "*.dauto")],
            initialfile=cur_filename.replace(".json", "")
        )
        if not save_path:
            return

        try:
            data = load_json(cur_path, {})
            # Find referenced images
            images = set()
            for action in data.get("actions", []):
                for k in ["template", "template_image", "filename"]:
                    if k in action and action[k].endswith(".png"):
                        images.add(action[k])

            with zipfile.ZipFile(save_path, 'w', zipfile.ZIP_DEFLATED) as zf:
                # Add workflow json
                zf.write(cur_path, "workflow.json")
                # Add images
                for img in images:
                    img_path = os.path.join(TEMPLATES_DIR, img)
                    if os.path.exists(img_path):
                        zf.write(img_path, f"templates/{img}")

            logger.info(f"Exported package to {save_path} with {len(images)} images.")
        except Exception as e:
            logger.error(f"Failed to export package: {e}")

    def _import_package(self):
        open_path = tkinter.filedialog.askopenfilename(
            title="Import DAuto Package",
            filetypes=[("DAuto Package", "*.dauto")]
        )
        if not open_path:
            return

        try:
            pkg_name = os.path.basename(open_path).replace(".dauto", "")
            with zipfile.ZipFile(open_path, 'r') as zf:
                file_list = zf.namelist()
                if "workflow.json" not in file_list:
                    logger.error("Invalid package: workflow.json missing.")
                    return

                # Read workflow to get name or use pkg_name
                wf_data = json.loads(zf.read("workflow.json"))
                target_json = f"{pkg_name}.json"
                
                # Prevent overwrite
                base = pkg_name
                counter = 1
                while os.path.exists(os.path.join(WORKSPACE_DIR, target_json)):
                    target_json = f"{base}_{counter}.json"
                    counter += 1

                # Save JSON
                wf_data["workflow_name"] = target_json.replace(".json", "")
                save_json(os.path.join(WORKSPACE_DIR, target_json), wf_data)

                # Extract images
                for f in file_list:
                    if f.startswith("templates/") and f.endswith(".png"):
                        img_name = os.path.basename(f)
                        img_data = zf.read(f)
                        with open(os.path.join(TEMPLATES_DIR, img_name), 'wb') as img_f:
                            img_f.write(img_data)

            logger.info(f"Imported package as {target_json}.")
            
            # Refresh UI
            new_files = get_workflow_files()
            self.file_var.set(target_json)
            self.file_dropdown.configure(values=new_files)
            if self._active_nav == "workflow":
                self._refresh_workflow()
            self._refresh_stats()

        except Exception as e:
            logger.error(f"Failed to import package: {e}")

    def _show_template_preview_dialog(self, tmpl_filename: str):
        path = os.path.join(TEMPLATES_DIR, tmpl_filename)
        if not os.path.exists(path):
            logger.warning(f"Template image not found: {path}")
            return

        dlg = self._dialog(f"Template — {tmpl_filename}", "440x360")
        try:
            pil_img = Image.open(path)
            w, h = pil_img.size
            _label(dlg, f"File: {tmpl_filename}  ({w} × {h} px)", size=11, colour=T["dim"]).pack(padx=20, pady=(12, 6))

            max_size = (380, 240)
            pil_img.thumbnail(max_size)
            ctk_img = ctk.CTkImage(light_image=pil_img, dark_image=pil_img, size=pil_img.size)

            img_lbl = ctk.CTkLabel(dlg, image=ctk_img, text="")
            img_lbl.pack(padx=20, pady=10)
        except Exception as e:
            _label(dlg, f"Error loading image: {e}", colour=T["err"]).pack(pady=30)

    def _open_template_gallery_dialog(self):
        dlg = self._dialog("Template Gallery", "560x420")
        files = glob.glob(os.path.join(TEMPLATES_DIR, "*.png"))
        if not files:
            _label(dlg, "No template images captured yet in workspace/templates/.", colour=T["dim"]).pack(pady=40)
            return

        scroll = ctk.CTkScrollableFrame(dlg, fg_color="transparent")
        scroll.pack(fill="both", expand=True, padx=16, pady=16)

        for path in files:
            fname = os.path.basename(path)
            card = ctk.CTkFrame(scroll, fg_color=T["raised"], corner_radius=6)
            card.pack(fill="x", pady=4)
            card.grid_columnconfigure(1, weight=1)

            try:
                pil_img = Image.open(path)
                w, h = pil_img.size
                preview = pil_img.copy()
                preview.thumbnail((48, 48))
                ctk_img = ctk.CTkImage(light_image=preview, dark_image=preview, size=preview.size)
                ctk.CTkLabel(card, image=ctk_img, text="").grid(row=0, column=0, padx=8, pady=8)
                _label(card, f"{fname}\n{w} × {h} px", size=11, colour=T["text"], anchor="w", justify="left").grid(row=0, column=1, padx=8, pady=8, sticky="ew")
            except Exception:
                _label(card, fname, size=11, colour=T["text"], anchor="w").grid(row=0, column=1, padx=8, pady=8, sticky="ew")

            _btn(card, "View", lambda f=fname: self._show_template_preview_dialog(f), width=60, height=26).grid(row=0, column=2, padx=8, pady=8)

    # ── Input listeners ───────────────────────────────────────────────────────

    def _start_listeners(self):
        def on_press(key):
            try:
                if   key == keyboard.Key.f9:  self.after(0, self.start_recording)
                elif key == keyboard.Key.f10:
                    self.after(0, self.stop_recording)
                    self.after(0, self._stop_playback)
                elif key == keyboard.Key.f11: self.after(0, self.playback)
                elif self.recording and self.recorder:
                    self.recorder.on_press(key)
            except Exception:
                pass

        def on_click(x, y, button, pressed):
            try:
                if self.recording and self.recorder:
                    self.recorder.on_click(x, y, button, pressed)
            except Exception:
                pass

        self.keyboard_listener = keyboard.Listener(on_press=on_press)
        self.keyboard_listener.start()
        self.mouse_listener = mouse.Listener(on_click=on_click)
        self.mouse_listener.start()

    # ── Shared UI helpers ─────────────────────────────────────────────────────

    def _page_header(self, parent, title: str, row: int):
        hdr = ctk.CTkFrame(parent, fg_color="transparent", height=44)
        hdr.grid(row=row, column=0, sticky="ew", padx=24, pady=(20, 0))
        hdr.grid_propagate(False)
        ctk.CTkLabel(
            hdr, text=title,
            font=ctk.CTkFont("SF Pro Display", 18, "bold"),
            text_color=T["text"]
        ).pack(side="left", anchor="w")

    def _dialog(self, title: str, geometry: str) -> ctk.CTkToplevel:
        dlg = ctk.CTkToplevel(self)
        dlg.title(title)
        dlg.geometry(geometry)
        dlg.transient(self)
        dlg.grab_set()
        dlg.configure(fg_color=T["bg"])
        return dlg


# ── Entry point ───────────────────────────────────────────────────────────────
def run_gui():
    app = AutomatorGUI()
    app.mainloop()
