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
from typing import Any

import customtkinter as ctk
from PIL import Image
from pynput import keyboard, mouse

from ..core.recorder import Recorder
from ..core.player import Player
from ..core.scheduler import WorkflowScheduler
from ..core.variable_manager import VariableManager
from ..utils.logger import get_logger
from ..utils.config import (
    WORKSPACE_DIR, VARIABLES_FILE, RUN_HISTORY_FILE, SCHEDULES_FILE
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
    "click":           "Click",
    "type":            "Type",
    "sleep":           "Sleep",
    "hotkey":          "Hotkey",
    "run_command":     "Command",
    "scroll":          "Scroll",
    "screenshot":      "Screenshot",
    "loop":            "Loop",
    "assert_template": "Assert",
    "clipboard":       "Clipboard",
    "if_template":     "Conditional",
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
    hv = T["accent_d"] if primary else (T["err"] + "CC" if danger else T["hover"])
    b  = ctk.CTkButton(
        parent, text=text, command=command,
        fg_color=fg, hover_color=hv,
        text_color=T["text"],
        font=ctk.CTkFont(*FONT_BODY),
        border_width=0 if (primary or danger) else 1,
        border_color=T["border"],
        corner_radius=6, height=32,
        width=width or 120,
        **kw
    )
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
        self.recording   = False
        self.recorder:  Recorder | None = None
        self.file_var    = ctk.StringVar(value="workflow.json")
        self._active_nav = "dashboard"
        self._nav_btns:    dict[str, ctk.CTkButton] = {}
        self._panels:      dict[str, ctk.CTkFrame]  = {}

        # Services
        self.scheduler   = WorkflowScheduler()
        self.var_manager = VariableManager()

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
             ).pack(pady=(6, 0), fill="x")

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
        btn_row.grid(row=1, column=0, sticky="ew", padx=16, pady=(0, 12))

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
        self.play_btn.pack(side="left")

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

        for text, cmd, primary in [
            ("Refresh",    self._refresh_workflow, False),
            ("Add Action", self._open_add_dialog,  True),
            ("Clear All",  self._clear_workflow,   False),
        ]:
            _btn(tb, text, cmd, primary=primary,
                 danger=(text == "Clear All")).pack(side="left", padx=(8, 0), pady=8)

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
        for w in self._wf_list.winfo_children():
            w.destroy()

        path = os.path.join(WORKSPACE_DIR, self.file_var.get())
        if not os.path.exists(path):
            _label(self._wf_list, "No workflow file found.", colour=T["dim"]).pack(pady=30)
            return

        data    = load_json(path, {})
        actions = data.get("actions", [])

        if not actions:
            _label(self._wf_list, "Workflow is empty. Record or add actions.", colour=T["dim"]).pack(pady=30)
            return

        for i, action in enumerate(actions):
            self._render_action_row(i, action, len(actions))

    def _render_action_row(self, i: int, action: dict, total: int):
        atype   = action.get("type", "unknown")
        label   = ACTION_LABELS.get(atype, atype.upper())
        summary = self._action_summary(atype, action)

        row = ctk.CTkFrame(self._wf_list, fg_color=T["raised"], corner_radius=6)
        row.pack(fill="x", pady=2)
        row.grid_columnconfigure(2, weight=1)

        # Index
        _label(row, str(i + 1), size=10, colour=T["dim"],
               anchor="center", width=40).grid(row=0, column=0, padx=(10, 0), pady=8)

        # Type badge
        badge = ctk.CTkFrame(row, fg_color=T["border"], corner_radius=4, width=80)
        badge.grid(row=0, column=1, padx=8, pady=8)
        _label(badge, label, size=10, colour=T["label"]).pack(padx=8, pady=3)

        # Summary
        _label(row, summary, size=11, colour=T["text"],
               anchor="w").grid(row=0, column=2, padx=4, pady=8, sticky="ew")

        # Controls — plain text buttons only
        ctrl = ctk.CTkFrame(row, fg_color="transparent")
        ctrl.grid(row=0, column=3, padx=8, pady=4)

        def _ctrl_btn(parent, txt, cmd):
            return ctk.CTkButton(
                parent, text=txt, width=32, height=26,
                fg_color="transparent", hover_color=T["hover"],
                text_color=T["dim"], font=ctk.CTkFont("SF Pro Text", 11),
                corner_radius=4, border_width=0, command=cmd
            )

        _ctrl_btn(ctrl, "Run",  lambda idx=i: self._test_action(idx)).pack(side="left", padx=1)
        if i > 0:
            _ctrl_btn(ctrl, "Up",  lambda idx=i: self._move_up(idx)).pack(side="left", padx=1)
        if i < total - 1:
            _ctrl_btn(ctrl, "Dn",  lambda idx=i: self._move_down(idx)).pack(side="left", padx=1)
        _ctrl_btn(ctrl, "Edit", lambda idx=i, a=action: self._open_edit_dialog(idx, a)).pack(side="left", padx=1)
        _ctrl_btn(ctrl, "Dupe", lambda idx=i: self._duplicate_action(idx)).pack(side="left", padx=1)

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
        return ""

    def _modify_workflow(self, mutator):
        path = os.path.join(WORKSPACE_DIR, self.file_var.get())
        data = load_json(path, {"workflow_name": "workflow", "created_at": "", "actions": []})
        mutator(data)
        save_json(path, data)
        self._refresh_workflow()
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

    def _open_add_dialog(self):
        dlg = self._dialog("Add Action", "400x340")

        _label(dlg, "Type", size=10, colour=T["dim"]).pack(padx=20, pady=(16, 2), anchor="w")
        type_var = ctk.StringVar(value="sleep")
        ctk.CTkOptionMenu(
            dlg, variable=type_var, values=list(ACTION_LABELS.keys()),
            fg_color=T["raised"], button_color=T["border"],
            text_color=T["text"], font=ctk.CTkFont(*FONT_BODY),
            width=360, corner_radius=6
        ).pack(padx=20)

        _label(dlg, "Value", size=10, colour=T["dim"]).pack(padx=20, pady=(12, 2), anchor="w")
        entry = ctk.CTkEntry(
            dlg, width=360, fg_color=T["raised"], border_color=T["border"],
            text_color=T["text"], font=ctk.CTkFont(*FONT_BODY), corner_radius=6
        )
        entry.pack(padx=20)

        HINTS = {
            "sleep": "seconds  (e.g. 1.5)",
            "type": "text or key  (e.g. hello  or  Key.enter)",
            "run_command": "shell command  (e.g. open /Applications/Safari.app)",
            "hotkey": "keys comma-separated  (e.g. cmd,c)",
            "scroll": "amount  (positive=up  negative=down)",
            "screenshot": "filename  (e.g. state.png)",
            "assert_template": "template filename in workspace/templates/",
            "clipboard": "action text  (e.g. set Hello World)",
            "if_template": "template filename  (add branches via Edit)",
            "click": "x,y  (e.g. 500,300)",
            "loop": "count  (e.g. 3)",
        }
        hint = _label(dlg, HINTS.get("sleep", ""), size=10, colour=T["dim"])
        hint.pack(padx=20, pady=(3, 0), anchor="w")

        type_var.trace_add("write", lambda *_: hint.configure(text=HINTS.get(type_var.get(), "")))

        def save():
            t   = type_var.get()
            val = entry.get().strip()
            a:  dict = {"type": t, "time_offset": 0.5}
            try:
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
                self._modify_workflow(lambda d: d.setdefault("actions", []).append(a))
                logger.info(f"Added action: {t}")
                dlg.destroy()
            except Exception as e:
                logger.error(f"Add action error: {e}")

        _btn(dlg, "Add to Workflow", save, primary=True, width=360).pack(pady=16, padx=20)

    def _open_edit_dialog(self, idx: int, action: dict):
        atype = action.get("type", "unknown")
        dlg   = self._dialog(f"Edit  #{idx+1}  —  {ACTION_LABELS.get(atype, atype)}", "400x240")

        _label(dlg, "Value", size=10, colour=T["dim"]).pack(padx=20, pady=(16, 2), anchor="w")
        entry = ctk.CTkEntry(
            dlg, width=360, fg_color=T["raised"], border_color=T["border"],
            text_color=T["text"], font=ctk.CTkFont(*FONT_BODY), corner_radius=6
        )
        entry.pack(padx=20)

        cur = {
            "sleep":           str(action.get("duration", 1.0)),
            "type":            action.get("key", ""),
            "run_command":     action.get("command", ""),
            "hotkey":          ",".join(action.get("keys", [])),
            "click":           f"{action.get('x',0)},{action.get('y',0)}",
            "scroll":          str(action.get("amount", 0)),
            "clipboard":       f"{action.get('action','set')} {action.get('text','')}",
            "screenshot":      action.get("filename", ""),
            "assert_template": action.get("template", ""),
            "if_template":     action.get("template", ""),
        }.get(atype, "")
        entry.insert(0, cur)

        def save():
            val = entry.get().strip()
            upd = copy.deepcopy(action)
            try:
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

                def m(d):
                    if 0 <= idx < len(d.get("actions", [])):
                        d["actions"][idx] = upd
                self._modify_workflow(m)
                logger.info(f"Edited action #{idx+1}")
                dlg.destroy()
            except Exception as e:
                logger.error(f"Edit error: {e}")

        _btn(dlg, "Save Changes", save, primary=True, width=360).pack(pady=16, padx=20)

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
        _label(form, "Use  {{variable_name}}  inside TypeAction to inject the value at runtime.",
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
        path = os.path.join(WORKSPACE_DIR, self.file_var.get())
        self.recorder = Recorder(workflow_path=path)
        self.recorder.start()
        logger.info(f"Recording  →  {self.file_var.get()}")
        self._set_status("Recording", T["err"])
        self.record_btn.configure(state="disabled")
        self.stop_btn.configure(state="normal", fg_color=T["warn"], text_color=T["bg"])
        self.play_btn.configure(state="disabled")

    def stop_recording(self):
        if not self.recording or not self.recorder: return
        self.recorder.stop()
        self.recording = False
        logger.info(f"Stopped  →  saved to  {self.file_var.get()}")
        self._set_status("Idle", T["ok"])
        self.record_btn.configure(state="normal")
        self.stop_btn.configure(state="disabled", fg_color=T["raised"], text_color=T["dim"])
        self.play_btn.configure(state="normal")
        self.file_dropdown.configure(values=get_workflow_files())
        self._refresh_stats()

    def playback(self):
        if self.recording: return
        logger.info(f"Playback  →  {self.file_var.get()}")
        self._set_status("Playing", T["accent"])
        self.play_btn.configure(state="disabled")

        def run():
            try:
                Player(workflow_path=os.path.join(WORKSPACE_DIR, self.file_var.get())).play()
            except Exception as e:
                logger.error(f"Playback error: {e}")
            finally:
                self.after(0, self._on_done)

        threading.Thread(target=run, daemon=True).start()

    def _on_done(self):
        self._set_status("Idle", T["ok"])
        self.play_btn.configure(state="normal")
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
        if self._active_nav == "workflow":
            self._refresh_workflow()
        self._refresh_stats()

    def _new_workflow(self):
        dlg = self._dialog("New Workflow", "360x160")
        _label(dlg, "Workflow name (without .json):", size=10, colour=T["dim"]).pack(
            padx=20, pady=(16, 4), anchor="w")
        entry = ctk.CTkEntry(
            dlg, width=320, fg_color=T["raised"], border_color=T["border"],
            text_color=T["text"], font=ctk.CTkFont(*FONT_BODY), corner_radius=6,
            placeholder_text="e.g. daily_backup"
        )
        entry.pack(padx=20)

        def create():
            name = entry.get().strip()
            if not name: return
            filename = f"{name}.json"
            path     = os.path.join(WORKSPACE_DIR, filename)
            save_json(path, {"workflow_name": name, "created_at": time.strftime("%Y-%m-%dT%H:%M:%S"), "actions": []})
            self.file_var.set(filename)
            self.file_dropdown.configure(values=get_workflow_files())
            logger.info(f"Created workflow: {filename}")
            dlg.destroy()

        _btn(dlg, "Create", create, primary=True, width=320).pack(pady=14, padx=20)

    # ── Input listeners ───────────────────────────────────────────────────────

    def _start_listeners(self):
        def on_press(key):
            try:
                if   key == keyboard.Key.f9:  self.after(0, self.start_recording)
                elif key == keyboard.Key.f10: self.after(0, self.stop_recording)
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
