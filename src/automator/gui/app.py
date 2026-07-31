"""
Desktop Automator — Professional GUI
Layout: Header | Sidebar (left) | Content (right)
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

# ── macOS: eagerly load HIServices so pynput doesn't crash on background threads
if sys.platform == "darwin":
    try:
        import HIServices
        HIServices.AXIsProcessTrusted()
    except Exception:
        pass

logger = get_logger(__name__)

# ── Colour palette ────────────────────────────────────────────────────────────
C = {
    "bg":           "#0F1117",
    "sidebar":      "#161B22",
    "card":         "#1C2128",
    "card_hover":   "#21262D",
    "accent":       "#58A6FF",
    "accent2":      "#3FB950",
    "danger":       "#F85149",
    "warning":      "#E3B341",
    "muted":        "#8B949E",
    "border":       "#30363D",
    "text":         "#E6EDF3",
    "text_dim":     "#8B949E",
    "record_red":   "#DA3633",
    "play_green":   "#238636",
}

ICON = {
    "dashboard": "  Dashboard",
    "workflow":  "  Workflow",
    "scheduler": "  Scheduler",
    "variables": "  Variables",
    "history":   "  History",
}


# ── Log handler ───────────────────────────────────────────────────────────────
class ColourLogHandler(logging.Handler):
    LEVEL_COLOURS = {
        logging.DEBUG:   "#8B949E",
        logging.INFO:    "#58A6FF",
        logging.WARNING: "#E3B341",
        logging.ERROR:   "#F85149",
        logging.CRITICAL:"#FF6E6E",
    }

    def __init__(self, textbox: ctk.CTkTextbox):
        super().__init__()
        self.textbox = textbox
        self.setFormatter(logging.Formatter("%(asctime)s  %(message)s", "%H:%M:%S"))

    def emit(self, record):
        msg = self.format(record)
        colour = self.LEVEL_COLOURS.get(record.levelno, "#E6EDF3")
        self.textbox.after(0, self._append, msg, colour)

    def _append(self, msg, colour):
        tb = self.textbox
        tb.configure(state="normal")
        tb.insert("end", msg + "\n", colour)
        tb.see("end")
        lines = int(tb.index("end-1c").split(".")[0])
        if lines > 150:
            tb.delete("1.0", f"{lines - 150}.0")
        tb.configure(state="disabled")


# ── Helpers ───────────────────────────────────────────────────────────────────
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
    files = glob.glob(os.path.join(WORKSPACE_DIR, "*.json"))
    exclude = {
        os.path.basename(VARIABLES_FILE),
        os.path.basename(RUN_HISTORY_FILE),
        os.path.basename(SCHEDULES_FILE),
    }
    return [os.path.basename(f) for f in files if os.path.basename(f) not in exclude] or ["workflow.json"]


ACTION_ICONS = {
    "click":            "🖱",
    "type":             "⌨",
    "sleep":            "⏱",
    "hotkey":           "🔑",
    "run_command":      "⚙",
    "scroll":           "↕",
    "screenshot":       "📷",
    "loop":             "🔁",
    "assert_template":  "🔍",
    "clipboard":        "📋",
    "if_template":      "🔀",
}

ACTION_TYPE_KEYS = list(ACTION_ICONS.keys())


# ═══════════════════════════════════════════════════════════════════════════════
# Main Application
# ═══════════════════════════════════════════════════════════════════════════════
class AutomatorGUI(ctk.CTk):
    def __init__(self):
        super().__init__()

        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        self.title("Desktop Automator")
        self.geometry("920x660")
        self.minsize(820, 580)
        self.configure(fg_color=C["bg"])

        # State
        self.recording = False
        self.recorder: Recorder | None = None
        self.current_workflow_path = os.path.join(WORKSPACE_DIR, "workflow.json")
        self.file_var = ctk.StringVar(value="workflow.json")
        self._active_tab = "dashboard"
        self._tab_buttons: dict[str, ctk.CTkButton] = {}
        self._content_frames: dict[str, ctk.CTkFrame] = {}

        # Services
        self.scheduler = WorkflowScheduler()
        self.var_manager = VariableManager()

        os.makedirs(WORKSPACE_DIR, exist_ok=True)

        self._build_ui()
        self._start_listeners()
        self.scheduler.set_play_callback(self._scheduled_play)
        self.scheduler.start()

    # ── Layout ────────────────────────────────────────────────────────────────

    def _build_ui(self):
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(1, weight=1)

        self._build_header()
        self._build_sidebar()
        self._build_content_area()
        self._switch_tab("dashboard")

    def _build_header(self):
        hdr = ctk.CTkFrame(self, height=52, fg_color=C["sidebar"], corner_radius=0)
        hdr.grid(row=0, column=0, columnspan=2, sticky="ew")
        hdr.grid_propagate(False)
        hdr.grid_columnconfigure(1, weight=1)

        # Logo
        logo = ctk.CTkLabel(
            hdr, text="⚡ Desktop Automator",
            font=ctk.CTkFont(family="SF Pro Display", size=18, weight="bold"),
            text_color=C["accent"]
        )
        logo.grid(row=0, column=0, padx=20, pady=10, sticky="w")

        # Status badge
        self.status_badge = ctk.CTkLabel(
            hdr, text="● IDLE",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=C["accent2"],
            fg_color=C["card"], corner_radius=8,
            padx=10, pady=4
        )
        self.status_badge.grid(row=0, column=2, padx=20, pady=10, sticky="e")

    def _build_sidebar(self):
        sb = ctk.CTkFrame(self, width=180, fg_color=C["sidebar"], corner_radius=0)
        sb.grid(row=1, column=0, sticky="nsew")
        sb.grid_propagate(False)

        # Workflow selector at top of sidebar
        sel_frame = ctk.CTkFrame(sb, fg_color=C["card"], corner_radius=8)
        sel_frame.pack(padx=12, pady=(16, 8), fill="x")

        ctk.CTkLabel(sel_frame, text="Workflow", font=ctk.CTkFont(size=10),
                     text_color=C["muted"]).pack(padx=10, pady=(6, 0), anchor="w")
        self.file_dropdown = ctk.CTkOptionMenu(
            sel_frame, variable=self.file_var,
            values=get_workflow_files(),
            command=self._on_file_select,
            fg_color=C["card_hover"], button_color=C["border"],
            button_hover_color=C["accent"], text_color=C["text"],
            font=ctk.CTkFont(size=12), width=140, dynamic_resizing=False
        )
        self.file_dropdown.pack(padx=8, pady=(2, 6))

        new_btn = ctk.CTkButton(
            sel_frame, text="+ New Workflow", height=28,
            fg_color="transparent", border_width=1, border_color=C["border"],
            hover_color=C["card_hover"], text_color=C["accent"],
            font=ctk.CTkFont(size=11), command=self._create_new_workflow
        )
        new_btn.pack(padx=8, pady=(0, 8), fill="x")

        # Nav tabs
        tabs = [
            ("dashboard", "🏠", "Dashboard"),
            ("workflow",  "📋", "Workflow"),
            ("scheduler", "🕐", "Scheduler"),
            ("variables", "📦", "Variables"),
            ("history",   "📜", "History"),
        ]
        for key, icon, label in tabs:
            btn = ctk.CTkButton(
                sb, text=f" {icon}  {label}", anchor="w",
                height=40, corner_radius=8,
                fg_color="transparent", hover_color=C["card_hover"],
                text_color=C["text_dim"], font=ctk.CTkFont(size=13),
                command=lambda k=key: self._switch_tab(k)
            )
            btn.pack(padx=10, pady=2, fill="x")
            self._tab_buttons[key] = btn

        # Version at bottom
        ctk.CTkLabel(sb, text="v0.2.0", font=ctk.CTkFont(size=10),
                     text_color=C["muted"]).pack(side="bottom", pady=10)

    def _build_content_area(self):
        container = ctk.CTkFrame(self, fg_color=C["bg"], corner_radius=0)
        container.grid(row=1, column=1, sticky="nsew")
        container.grid_rowconfigure(0, weight=1)
        container.grid_columnconfigure(0, weight=1)

        for key, builder in [
            ("dashboard", self._build_dashboard),
            ("workflow",  self._build_workflow_tab),
            ("scheduler", self._build_scheduler_tab),
            ("variables", self._build_variables_tab),
            ("history",   self._build_history_tab),
        ]:
            frame = ctk.CTkFrame(container, fg_color=C["bg"], corner_radius=0)
            frame.grid(row=0, column=0, sticky="nsew")
            self._content_frames[key] = frame
            builder(frame)

    def _switch_tab(self, key: str):
        for k, btn in self._tab_buttons.items():
            if k == key:
                btn.configure(fg_color=C["card"], text_color=C["accent"])
            else:
                btn.configure(fg_color="transparent", text_color=C["text_dim"])

        for k, frame in self._content_frames.items():
            if k == key:
                frame.tkraise()
            # else: stays in grid

        self._active_tab = key

        # Refresh data for tabs that need live data
        if key == "workflow":
            self._refresh_workflow_list()
        elif key == "history":
            self._refresh_history()
        elif key == "variables":
            self._refresh_variables()
        elif key == "scheduler":
            self._refresh_scheduler()

    # ── Dashboard Tab ─────────────────────────────────────────────────────────

    def _build_dashboard(self, parent: ctk.CTkFrame):
        parent.grid_columnconfigure(0, weight=1)
        parent.grid_rowconfigure(2, weight=1)

        # Stats row
        stats = ctk.CTkFrame(parent, fg_color="transparent")
        stats.grid(row=0, column=0, padx=20, pady=(20, 8), sticky="ew")
        stats.grid_columnconfigure((0, 1, 2), weight=1)

        self._stat_workflows = self._make_stat_card(stats, "Workflows", "0", C["accent"], col=0)
        self._stat_actions   = self._make_stat_card(stats, "Actions", "0", C["accent2"], col=1)
        self._stat_runs      = self._make_stat_card(stats, "Total Runs", "0", C["warning"], col=2)

        # Control panel
        ctrl = ctk.CTkFrame(parent, fg_color=C["card"], corner_radius=12)
        ctrl.grid(row=1, column=0, padx=20, pady=8, sticky="ew")
        ctrl.grid_columnconfigure((0, 1, 2), weight=1)

        self.record_btn = ctk.CTkButton(
            ctrl, text="⏺  Record (F9)", height=44,
            fg_color=C["record_red"], hover_color="#c1272a",
            font=ctk.CTkFont(size=14, weight="bold"),
            command=self.start_recording
        )
        self.record_btn.grid(row=0, column=0, padx=16, pady=16, sticky="ew")

        self.stop_btn = ctk.CTkButton(
            ctrl, text="⏹  Stop (F10)", height=44,
            fg_color=C["border"], hover_color=C["card_hover"],
            text_color=C["muted"], font=ctk.CTkFont(size=14, weight="bold"),
            state="disabled", command=self.stop_recording
        )
        self.stop_btn.grid(row=0, column=1, padx=8, pady=16, sticky="ew")

        self.play_btn = ctk.CTkButton(
            ctrl, text="▶  Playback (F11)", height=44,
            fg_color=C["play_green"], hover_color="#1a6b27",
            font=ctk.CTkFont(size=14, weight="bold"),
            command=self.playback
        )
        self.play_btn.grid(row=0, column=2, padx=16, pady=16, sticky="ew")

        # Log console
        log_frame = ctk.CTkFrame(parent, fg_color=C["card"], corner_radius=12)
        log_frame.grid(row=2, column=0, padx=20, pady=(0, 20), sticky="nsew")
        log_frame.grid_rowconfigure(1, weight=1)
        log_frame.grid_columnconfigure(0, weight=1)

        hdr = ctk.CTkFrame(log_frame, fg_color="transparent")
        hdr.grid(row=0, column=0, padx=14, pady=(10, 0), sticky="ew")
        ctk.CTkLabel(hdr, text="Activity Log", font=ctk.CTkFont(size=13, weight="bold"),
                     text_color=C["text"]).pack(side="left")
        ctk.CTkButton(hdr, text="Clear", width=60, height=24,
                      fg_color="transparent", border_width=1, border_color=C["border"],
                      text_color=C["muted"], font=ctk.CTkFont(size=11),
                      command=self._clear_log).pack(side="right")

        self.log_console = ctk.CTkTextbox(
            log_frame, fg_color="#0D1117", text_color=C["text"],
            font=ctk.CTkFont(family="Menlo", size=12),
            state="disabled", corner_radius=8, wrap="word"
        )
        self.log_console.grid(row=1, column=0, padx=12, pady=(6, 12), sticky="nsew")

        # Tag colours for log levels
        for level, colour in ColourLogHandler.LEVEL_COLOURS.items():
            self.log_console.tag_config(colour, foreground=colour)

        # Attach log handler
        handler = ColourLogHandler(self.log_console)
        logging.getLogger("automator").addHandler(handler)
        logger.info("GUI started successfully. Welcome to Desktop Automator!")
        self._update_stats()

    def _make_stat_card(self, parent, label: str, value: str, colour: str, col: int):
        card = ctk.CTkFrame(parent, fg_color=C["card"], corner_radius=12)
        card.grid(row=0, column=col, padx=6, pady=0, sticky="ew")
        ctk.CTkLabel(card, text=label, font=ctk.CTkFont(size=11),
                     text_color=C["muted"]).pack(padx=14, pady=(12, 2), anchor="w")
        val_lbl = ctk.CTkLabel(card, text=value,
                               font=ctk.CTkFont(size=28, weight="bold"), text_color=colour)
        val_lbl.pack(padx=14, pady=(0, 12), anchor="w")
        return val_lbl

    def _update_stats(self):
        wf_files = get_workflow_files()
        self._stat_workflows.configure(text=str(len(wf_files)))

        actions = 0
        for f in wf_files:
            data = load_json(os.path.join(WORKSPACE_DIR, f), {})
            actions += len(data.get("actions", []))
        self._stat_actions.configure(text=str(actions))

        history = load_json(RUN_HISTORY_FILE, [])
        self._stat_runs.configure(text=str(len(history)))

    def _clear_log(self):
        self.log_console.configure(state="normal")
        self.log_console.delete("1.0", "end")
        self.log_console.configure(state="disabled")

    # ── Workflow Tab ──────────────────────────────────────────────────────────

    def _build_workflow_tab(self, parent: ctk.CTkFrame):
        parent.grid_rowconfigure(1, weight=1)
        parent.grid_columnconfigure(0, weight=1)

        # Toolbar
        tb = ctk.CTkFrame(parent, fg_color=C["card"], corner_radius=12)
        tb.grid(row=0, column=0, padx=20, pady=(20, 8), sticky="ew")

        for text, color, cmd in [
            ("🔄  Refresh", "transparent", self._refresh_workflow_list),
            ("➕  Add Action", C["play_green"],  self._open_add_dialog),
            ("🗑  Clear All",  C["record_red"],  self._clear_workflow),
        ]:
            ctk.CTkButton(tb, text=text, height=34, fg_color=color,
                          border_width=0 if color != "transparent" else 1,
                          border_color=C["border"],
                          hover_color=C["card_hover"] if color == "transparent" else None,
                          text_color=C["text"],
                          font=ctk.CTkFont(size=12), command=cmd).pack(
                side="left", padx=8, pady=10)

        # Action list
        self.workflow_list_frame = ctk.CTkScrollableFrame(
            parent, fg_color="transparent", corner_radius=0)
        self.workflow_list_frame.grid(row=1, column=0, padx=20, pady=(0, 20), sticky="nsew")
        self.workflow_list_frame.grid_columnconfigure(0, weight=1)

    def _refresh_workflow_list(self):
        for w in self.workflow_list_frame.winfo_children():
            w.destroy()

        path = self.current_workflow_path
        if not os.path.exists(path):
            ctk.CTkLabel(self.workflow_list_frame, text="No workflow found. Record one first!",
                         text_color=C["muted"]).pack(pady=30)
            return

        data = load_json(path, {})
        actions = data.get("actions", [])
        if not actions:
            ctk.CTkLabel(self.workflow_list_frame, text="Workflow is empty.",
                         text_color=C["muted"]).pack(pady=30)
            return

        for i, action in enumerate(actions):
            self._render_action_row(i, action, len(actions))

    def _render_action_row(self, i: int, action: dict, total: int):
        atype = action.get("type", "unknown")
        icon  = ACTION_ICONS.get(atype, "•")

        row = ctk.CTkFrame(self.workflow_list_frame, fg_color=C["card"], corner_radius=8)
        row.pack(fill="x", pady=3)
        row.grid_columnconfigure(1, weight=1)

        # Index badge
        idx_lbl = ctk.CTkLabel(row, text=f"#{i+1}", width=36,
                               font=ctk.CTkFont(size=11, weight="bold"),
                               text_color=C["muted"])
        idx_lbl.grid(row=0, column=0, padx=(10, 0), pady=10)

        # Icon + summary
        summary = self._action_summary(atype, action)
        info = ctk.CTkLabel(row, text=f"{icon}  {atype.upper()}  —  {summary}",
                            anchor="w", font=ctk.CTkFont(size=12), text_color=C["text"])
        info.grid(row=0, column=1, padx=8, pady=10, sticky="ew")

        # Thumbnail for click actions
        tmpl = action.get("template_image")
        if atype == "click" and tmpl and os.path.exists(tmpl):
            try:
                pil_img = Image.open(tmpl).resize((36, 36))
                ctk_img = ctk.CTkImage(light_image=pil_img, dark_image=pil_img, size=(36, 36))
                ctk.CTkLabel(row, image=ctk_img, text="").grid(row=0, column=2, padx=6, pady=6)
            except Exception:
                pass

        # Controls
        ctrl = ctk.CTkFrame(row, fg_color="transparent")
        ctrl.grid(row=0, column=3, padx=8, pady=6)

        icon_btn = lambda parent, txt, cmd: ctk.CTkButton(
            parent, text=txt, width=32, height=28,
            fg_color="transparent", hover_color=C["border"],
            text_color=C["muted"], font=ctk.CTkFont(size=14), command=cmd
        )
        icon_btn(ctrl, "▶", lambda idx=i: self._test_action(idx)).pack(side="left", padx=1)
        if i > 0:
            icon_btn(ctrl, "▲", lambda idx=i: self._move_up(idx)).pack(side="left", padx=1)
        if i < total - 1:
            icon_btn(ctrl, "▼", lambda idx=i: self._move_down(idx)).pack(side="left", padx=1)
        icon_btn(ctrl, "✏", lambda idx=i, a=action: self._open_edit_dialog(idx, a)).pack(side="left", padx=1)
        icon_btn(ctrl, "⧉", lambda idx=i: self._duplicate_action(idx)).pack(side="left", padx=1)
        del_btn = ctk.CTkButton(ctrl, text="✕", width=32, height=28,
                                fg_color="transparent", hover_color="#3a1a1a",
                                text_color=C["danger"], font=ctk.CTkFont(size=14),
                                command=lambda idx=i: self._delete_action(idx))
        del_btn.pack(side="left", padx=1)

    def _action_summary(self, atype: str, action: dict) -> str:
        if atype == "click":
            return f"({action.get('x')}, {action.get('y')})  {action.get('button','left')} ×{action.get('clicks',1)}"
        if atype == "type":
            return repr(action.get("key", ""))
        if atype == "sleep":
            return f"{action.get('duration', 0)}s"
        if atype == "hotkey":
            return " + ".join(action.get("keys", []))
        if atype == "run_command":
            return action.get("command", "")[:50]
        if atype == "scroll":
            return f"{action.get('amount', 0)} units"
        if atype == "screenshot":
            return action.get("filename", "")
        if atype == "clipboard":
            return f"{action.get('action','set')}  {action.get('text','')[:30]}"
        if atype == "if_template":
            t = action.get("template", "")
            then = len(action.get("then_actions", []))
            else_ = len(action.get("else_actions", []))
            return f"template={t}  then×{then} else×{else_}"
        return ""

    def _modify_workflow(self, mutator):
        """Read workflow, apply mutator(data), save, refresh."""
        path = self.current_workflow_path
        data = load_json(path, {"workflow_name": "workflow", "created_at": "", "actions": []})
        mutator(data)
        save_json(path, data)
        self._refresh_workflow_list()
        self._update_stats()

    def _delete_action(self, idx: int):
        def m(d): d["actions"].pop(idx)
        self._modify_workflow(m)
        logger.info(f"Deleted action #{idx+1}")

    def _duplicate_action(self, idx: int):
        def m(d): d["actions"].insert(idx + 1, copy.deepcopy(d["actions"][idx]))
        self._modify_workflow(m)
        logger.info(f"Duplicated action #{idx+1}")

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
        def m(d): d["actions"] = []
        self._modify_workflow(m)
        logger.info("Cleared all actions.")

    def _test_action(self, idx: int):
        data = load_json(self.current_workflow_path, {})
        actions = data.get("actions", [])
        if 0 <= idx < len(actions):
            def run():
                player = Player()
                player.play_single_action(actions[idx])
            threading.Thread(target=run, daemon=True).start()

    def _open_add_dialog(self):
        dlg = self._make_dialog("Add Action", "400x360")

        ctk.CTkLabel(dlg, text="Action Type", text_color=C["muted"],
                     font=ctk.CTkFont(size=11)).pack(padx=20, pady=(16, 2), anchor="w")
        type_var = ctk.StringVar(value="sleep")
        ctk.CTkOptionMenu(dlg, variable=type_var, values=ACTION_TYPE_KEYS,
                          width=360).pack(padx=20)

        ctk.CTkLabel(dlg, text="Value", text_color=C["muted"],
                     font=ctk.CTkFont(size=11)).pack(padx=20, pady=(12, 2), anchor="w")
        val_entry = ctk.CTkEntry(dlg, width=360, placeholder_text="e.g. 1.5 for sleep")
        val_entry.pack(padx=20)

        hint = ctk.CTkLabel(dlg, text="Duration in seconds", text_color=C["muted"],
                            font=ctk.CTkFont(size=10))
        hint.pack(padx=20, anchor="w")

        HINTS = {
            "sleep": "Duration in seconds (e.g. 1.5)",
            "type": "Text or key to type (e.g. hello or Key.enter)",
            "run_command": "Shell command (e.g. open /Applications/Safari.app)",
            "hotkey": "Keys comma-separated (e.g. cmd,c)",
            "scroll": "Scroll amount (positive=up, negative=down)",
            "screenshot": "Filename (e.g. state.png)",
            "assert_template": "Template filename in workspace/templates/",
            "clipboard": "Format: set|copy|paste  [optional text]",
            "if_template": "Template filename (then/else actions via Edit)",
            "click": "x,y (e.g. 500,300)",
            "loop": "count (e.g. 3)",
        }

        def on_type_change(*_):
            hint.configure(text=HINTS.get(type_var.get(), ""))

        type_var.trace_add("write", on_type_change)

        def save():
            t = type_var.get()
            val = val_entry.get().strip()
            new_action: dict = {"type": t, "time_offset": 0.5}
            try:
                if t == "sleep":     new_action["duration"] = float(val) if val else 1.0
                elif t == "type":    new_action["key"] = val
                elif t == "run_command": new_action["command"] = val; new_action["wait"] = True
                elif t == "hotkey":  new_action["keys"] = [k.strip() for k in val.split(",")]
                elif t == "scroll":  new_action["amount"] = int(val) if val else -3
                elif t == "screenshot": new_action["filename"] = val or "screenshot.png"
                elif t == "assert_template": new_action["template"] = val
                elif t == "clipboard":
                    parts = val.split(None, 1)
                    new_action["action"] = parts[0] if parts else "set"
                    new_action["text"] = parts[1] if len(parts) > 1 else ""
                elif t == "click":
                    coords = [v.strip() for v in val.split(",")]
                    new_action["x"] = int(coords[0]) if len(coords) > 0 else 0
                    new_action["y"] = int(coords[1]) if len(coords) > 1 else 0
                elif t == "loop":    new_action["count"] = int(val) if val else 1; new_action["actions"] = []
                elif t == "if_template": new_action["template"] = val; new_action["then_actions"] = []; new_action["else_actions"] = []

                def m(d): d.setdefault("actions", []).append(new_action)
                self._modify_workflow(m)
                logger.info(f"Added action: {t}")
                dlg.destroy()
            except Exception as e:
                logger.error(f"Error adding action: {e}")

        ctk.CTkButton(dlg, text="Add to Workflow", height=38,
                      fg_color=C["accent"], hover_color=C["play_green"],
                      font=ctk.CTkFont(size=13, weight="bold"),
                      command=save).pack(pady=16, padx=20, fill="x")

    def _open_edit_dialog(self, idx: int, action: dict):
        atype = action.get("type", "unknown")
        dlg = self._make_dialog(f"Edit Action #{idx+1} — {atype.upper()}", "400x260")

        ctk.CTkLabel(dlg, text="Value", text_color=C["muted"],
                     font=ctk.CTkFont(size=11)).pack(padx=20, pady=(16, 2), anchor="w")
        entry = ctk.CTkEntry(dlg, width=360)
        entry.pack(padx=20)

        cur = ""
        if atype == "sleep":     cur = str(action.get("duration", 1.0))
        elif atype == "type":    cur = action.get("key", "")
        elif atype == "run_command": cur = action.get("command", "")
        elif atype == "hotkey":  cur = ",".join(action.get("keys", []))
        elif atype == "click":   cur = f"{action.get('x',0)},{action.get('y',0)}"
        elif atype == "scroll":  cur = str(action.get("amount", 0))
        elif atype == "clipboard": cur = f"{action.get('action','set')} {action.get('text','')}"
        elif atype == "screenshot": cur = action.get("filename", "")
        elif atype == "assert_template": cur = action.get("template", "")
        elif atype == "if_template": cur = action.get("template", "")
        entry.insert(0, cur)

        def save():
            val = entry.get().strip()
            try:
                updated = copy.deepcopy(action)
                if atype == "sleep":     updated["duration"] = float(val)
                elif atype == "type":    updated["key"] = val
                elif atype == "run_command": updated["command"] = val
                elif atype == "hotkey":  updated["keys"] = [k.strip() for k in val.split(",")]
                elif atype == "click":
                    parts = [v.strip() for v in val.split(",")]
                    updated["x"] = int(parts[0]); updated["y"] = int(parts[1])
                elif atype == "scroll":  updated["amount"] = int(val)
                elif atype == "clipboard":
                    parts = val.split(None, 1)
                    updated["action"] = parts[0] if parts else "set"
                    updated["text"] = parts[1] if len(parts) > 1 else ""
                elif atype == "screenshot": updated["filename"] = val
                elif atype in ("assert_template", "if_template"): updated["template"] = val

                def m(d):
                    if 0 <= idx < len(d.get("actions", [])):
                        d["actions"][idx] = updated
                self._modify_workflow(m)
                logger.info(f"Edited action #{idx+1}")
                dlg.destroy()
            except Exception as e:
                logger.error(f"Error editing action: {e}")

        ctk.CTkButton(dlg, text="Save Changes", height=38,
                      fg_color=C["accent"],
                      font=ctk.CTkFont(size=13, weight="bold"),
                      command=save).pack(pady=16, padx=20, fill="x")

    # ── Scheduler Tab ─────────────────────────────────────────────────────────

    def _build_scheduler_tab(self, parent: ctk.CTkFrame):
        parent.grid_rowconfigure(1, weight=1)
        parent.grid_columnconfigure(0, weight=1)

        # Add Schedule form
        form = ctk.CTkFrame(parent, fg_color=C["card"], corner_radius=12)
        form.grid(row=0, column=0, padx=20, pady=(20, 8), sticky="ew")
        form.grid_columnconfigure((0, 1, 2), weight=1)

        ctk.CTkLabel(form, text="Workflow File", text_color=C["muted"],
                     font=ctk.CTkFont(size=11)).grid(row=0, column=0, padx=12, pady=(12, 2), sticky="w")
        self.sched_file_var = ctk.StringVar()
        ctk.CTkOptionMenu(form, variable=self.sched_file_var, values=get_workflow_files(),
                          width=160).grid(row=1, column=0, padx=12, pady=(0, 12), sticky="ew")

        ctk.CTkLabel(form, text="Interval Type", text_color=C["muted"],
                     font=ctk.CTkFont(size=11)).grid(row=0, column=1, padx=12, pady=(12, 2), sticky="w")
        self.sched_type_var = ctk.StringVar(value="minutes")
        ctk.CTkOptionMenu(form, variable=self.sched_type_var,
                          values=["minutes", "hours", "daily_at"],
                          width=140).grid(row=1, column=1, padx=12, pady=(0, 12), sticky="ew")

        ctk.CTkLabel(form, text="Value (number or HH:MM)", text_color=C["muted"],
                     font=ctk.CTkFont(size=11)).grid(row=0, column=2, padx=12, pady=(12, 2), sticky="w")
        self.sched_val_entry = ctk.CTkEntry(form, placeholder_text="e.g. 30 or 09:00")
        self.sched_val_entry.grid(row=1, column=2, padx=12, pady=(0, 12), sticky="ew")

        ctk.CTkButton(form, text="+ Add Schedule", height=34,
                      fg_color=C["accent"], font=ctk.CTkFont(size=12, weight="bold"),
                      command=self._add_schedule).grid(
            row=2, column=0, columnspan=3, padx=12, pady=(0, 12), sticky="ew")

        # List
        self.sched_list_frame = ctk.CTkScrollableFrame(parent, fg_color="transparent")
        self.sched_list_frame.grid(row=1, column=0, padx=20, pady=(0, 20), sticky="nsew")
        self.sched_list_frame.grid_columnconfigure(0, weight=1)

    def _refresh_scheduler(self):
        for w in self.sched_list_frame.winfo_children():
            w.destroy()
        jobs = self.scheduler.get_all()
        if not jobs:
            ctk.CTkLabel(self.sched_list_frame, text="No scheduled jobs yet.",
                         text_color=C["muted"]).pack(pady=30)
            return
        for job in jobs:
            self._render_schedule_row(job)

    def _render_schedule_row(self, job: dict):
        row = ctk.CTkFrame(self.sched_list_frame, fg_color=C["card"], corner_radius=8)
        row.pack(fill="x", pady=3)
        row.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(row, text=job.get("label", ""),
                     font=ctk.CTkFont(size=12), text_color=C["text"], anchor="w").grid(
            row=0, column=0, padx=12, pady=8, sticky="ew")

        meta = f"Runs: {job.get('run_count', 0)}  •  Last: {job.get('last_run') or '—'}"
        ctk.CTkLabel(row, text=meta, font=ctk.CTkFont(size=10),
                     text_color=C["muted"], anchor="w").grid(row=1, column=0, padx=12, pady=(0, 8), sticky="w")

        ctk.CTkButton(row, text="Remove", width=80, height=28,
                      fg_color="transparent", border_width=1, border_color=C["danger"],
                      text_color=C["danger"], hover_color="#3a1a1a",
                      command=lambda jid=job["id"]: self._remove_schedule(jid)).grid(
            row=0, column=1, rowspan=2, padx=12, pady=8)

    def _add_schedule(self):
        f = self.sched_file_var.get()
        t = self.sched_type_var.get()
        v = self.sched_val_entry.get().strip()
        if not f or not v:
            logger.warning("Scheduler: workflow file and value are required.")
            return
        wf_path = os.path.join(WORKSPACE_DIR, f)
        self.scheduler.add(workflow_file=wf_path, interval_type=t, interval_value=v)
        self._refresh_scheduler()

    def _remove_schedule(self, job_id: int):
        self.scheduler.remove(job_id)
        self._refresh_scheduler()

    def _scheduled_play(self, workflow_file: str):
        player = Player(workflow_path=workflow_file)
        player.play()
        self.after(0, self._update_stats)

    # ── Variables Tab ─────────────────────────────────────────────────────────

    def _build_variables_tab(self, parent: ctk.CTkFrame):
        parent.grid_rowconfigure(1, weight=1)
        parent.grid_columnconfigure(0, weight=1)

        # Add variable form
        form = ctk.CTkFrame(parent, fg_color=C["card"], corner_radius=12)
        form.grid(row=0, column=0, padx=20, pady=(20, 8), sticky="ew")
        form.grid_columnconfigure((0, 1), weight=1)

        ctk.CTkLabel(form, text="Key", text_color=C["muted"],
                     font=ctk.CTkFont(size=11)).grid(row=0, column=0, padx=12, pady=(12, 2), sticky="w")
        self.var_key_entry = ctk.CTkEntry(form, placeholder_text="e.g. username")
        self.var_key_entry.grid(row=1, column=0, padx=12, pady=(0, 12), sticky="ew")

        ctk.CTkLabel(form, text="Value", text_color=C["muted"],
                     font=ctk.CTkFont(size=11)).grid(row=0, column=1, padx=12, pady=(12, 2), sticky="w")
        self.var_val_entry = ctk.CTkEntry(form, placeholder_text="e.g. john_doe")
        self.var_val_entry.grid(row=1, column=1, padx=12, pady=(0, 12), sticky="ew")

        ctk.CTkButton(form, text="Set Variable", height=34,
                      fg_color=C["accent"], font=ctk.CTkFont(size=12, weight="bold"),
                      command=self._set_variable).grid(
            row=2, column=0, columnspan=2, padx=12, pady=(0, 12), sticky="ew")

        hint = ctk.CTkLabel(form, text="Use {{variable_name}} in TypeAction to inject value at runtime.",
                            text_color=C["muted"], font=ctk.CTkFont(size=10))
        hint.grid(row=3, column=0, columnspan=2, padx=12, pady=(0, 10))

        # List
        self.var_list_frame = ctk.CTkScrollableFrame(parent, fg_color="transparent")
        self.var_list_frame.grid(row=1, column=0, padx=20, pady=(0, 20), sticky="nsew")
        self.var_list_frame.grid_columnconfigure(0, weight=1)

    def _refresh_variables(self):
        for w in self.var_list_frame.winfo_children():
            w.destroy()
        self.var_manager.load()
        if not self.var_manager.variables:
            ctk.CTkLabel(self.var_list_frame, text="No variables defined yet.",
                         text_color=C["muted"]).pack(pady=30)
            return
        for key, value in self.var_manager.variables.items():
            row = ctk.CTkFrame(self.var_list_frame, fg_color=C["card"], corner_radius=8)
            row.pack(fill="x", pady=3)
            row.grid_columnconfigure(0, weight=1)
            ctk.CTkLabel(row, text=f"  {{{{{key}}}}}  →  {value}",
                         font=ctk.CTkFont(family="Menlo", size=12),
                         text_color=C["text"], anchor="w").grid(row=0, column=0, padx=12, pady=10, sticky="ew")
            ctk.CTkButton(row, text="Delete", width=70, height=28,
                          fg_color="transparent", border_width=1, border_color=C["danger"],
                          text_color=C["danger"], hover_color="#3a1a1a",
                          command=lambda k=key: self._delete_variable(k)).grid(
                row=0, column=1, padx=10, pady=8)

    def _set_variable(self):
        key = self.var_key_entry.get().strip()
        val = self.var_val_entry.get().strip()
        if not key:
            logger.warning("Variable key cannot be empty.")
            return
        self.var_manager.set(key, val)
        self.var_key_entry.delete(0, "end")
        self.var_val_entry.delete(0, "end")
        logger.info(f"Variable set: {{{{{key}}}}} = {val!r}")
        self._refresh_variables()

    def _delete_variable(self, key: str):
        self.var_manager.delete(key)
        logger.info(f"Deleted variable: {key}")
        self._refresh_variables()

    # ── History Tab ───────────────────────────────────────────────────────────

    def _build_history_tab(self, parent: ctk.CTkFrame):
        parent.grid_rowconfigure(1, weight=1)
        parent.grid_columnconfigure(0, weight=1)

        tb = ctk.CTkFrame(parent, fg_color=C["card"], corner_radius=12)
        tb.grid(row=0, column=0, padx=20, pady=(20, 8), sticky="ew")
        ctk.CTkButton(tb, text="🗑  Clear History", height=32,
                      fg_color="transparent", border_width=1, border_color=C["border"],
                      text_color=C["muted"], hover_color=C["card_hover"],
                      command=self._clear_history).pack(side="right", padx=10, pady=8)
        ctk.CTkLabel(tb, text="Run History (latest first)", font=ctk.CTkFont(size=13, weight="bold"),
                     text_color=C["text"]).pack(side="left", padx=14, pady=8)

        self.history_frame = ctk.CTkScrollableFrame(parent, fg_color="transparent")
        self.history_frame.grid(row=1, column=0, padx=20, pady=(0, 20), sticky="nsew")
        self.history_frame.grid_columnconfigure(0, weight=1)

    def _refresh_history(self):
        for w in self.history_frame.winfo_children():
            w.destroy()
        history = load_json(RUN_HISTORY_FILE, [])
        if not history:
            ctk.CTkLabel(self.history_frame, text="No runs recorded yet.",
                         text_color=C["muted"]).pack(pady=30)
            return
        for entry in history:
            success = entry.get("success", False)
            colour = C["accent2"] if success else C["danger"]
            status = "✓ SUCCESS" if success else "✗ FAILED"
            row = ctk.CTkFrame(self.history_frame, fg_color=C["card"], corner_radius=8)
            row.pack(fill="x", pady=3)
            row.grid_columnconfigure(1, weight=1)

            ctk.CTkLabel(row, text=status, font=ctk.CTkFont(size=12, weight="bold"),
                         text_color=colour, width=80).grid(row=0, column=0, padx=12, pady=10)

            info = (f"{entry.get('workflow','?')}  •  "
                    f"{entry.get('timestamp','')}  •  "
                    f"{entry.get('action_count', 0)} actions  •  "
                    f"{entry.get('duration_sec', 0)}s")
            ctk.CTkLabel(row, text=info, font=ctk.CTkFont(size=11),
                         text_color=C["text"], anchor="w").grid(row=0, column=1, padx=8, pady=10, sticky="ew")

            if entry.get("error"):
                ctk.CTkLabel(row, text=entry["error"], font=ctk.CTkFont(size=10),
                             text_color=C["danger"], anchor="w").grid(
                    row=1, column=0, columnspan=2, padx=12, pady=(0, 8), sticky="ew")

    def _clear_history(self):
        save_json(RUN_HISTORY_FILE, [])
        self._refresh_history()
        self._update_stats()
        logger.info("Run history cleared.")

    # ── Recording / Playback ──────────────────────────────────────────────────

    def start_recording(self):
        if self.recording:
            return
        self.recording = True
        self.recorder = Recorder(workflow_path=self.current_workflow_path)
        self.recorder.start()
        logger.info(f"Recording started → {self.file_var.get()}")
        self._set_status("● REC", C["record_red"])
        self.record_btn.configure(state="disabled")
        self.stop_btn.configure(state="normal", fg_color=C["warning"], text_color=C["bg"])
        self.play_btn.configure(state="disabled")

    def stop_recording(self):
        if not self.recording or not self.recorder:
            return
        self.recorder.stop()
        self.recording = False
        logger.info(f"Recording stopped. Saved → {self.file_var.get()}")
        self._set_status("● IDLE", C["accent2"])
        self.record_btn.configure(state="normal")
        self.stop_btn.configure(state="disabled", fg_color=C["border"], text_color=C["muted"])
        self.play_btn.configure(state="normal")
        self._update_stats()
        self.file_dropdown.configure(values=get_workflow_files())
        if self._active_tab == "workflow":
            self._refresh_workflow_list()

    def playback(self):
        if self.recording:
            return
        logger.info(f"Playback started → {self.file_var.get()}")
        self._set_status("▶ PLAY", C["accent"])
        self.play_btn.configure(state="disabled")

        def run():
            try:
                player = Player(workflow_path=self.current_workflow_path)
                player.play()
            except Exception as e:
                logger.error(f"Playback error: {e}")
            finally:
                self.after(0, self._on_playback_done)

        threading.Thread(target=run, daemon=True).start()

    def _on_playback_done(self):
        self._set_status("● IDLE", C["accent2"])
        self.play_btn.configure(state="normal")
        self._update_stats()
        if self._active_tab == "history":
            self._refresh_history()

    def _set_status(self, text: str, colour: str):
        self.status_badge.configure(text=text, text_color=colour)

    # ── Workflow file management ───────────────────────────────────────────────

    def _on_file_select(self, choice: str):
        self.current_workflow_path = os.path.join(WORKSPACE_DIR, choice)
        logger.info(f"Selected workflow: {choice}")
        if self._active_tab == "workflow":
            self._refresh_workflow_list()
        self._update_stats()

    def _create_new_workflow(self):
        dlg = self._make_dialog("New Workflow", "360x180")
        ctk.CTkLabel(dlg, text="Workflow name (without .json):",
                     text_color=C["muted"], font=ctk.CTkFont(size=11)).pack(padx=20, pady=(20, 4), anchor="w")
        entry = ctk.CTkEntry(dlg, width=320, placeholder_text="e.g. daily_backup")
        entry.pack(padx=20)

        def create():
            name = entry.get().strip()
            if not name:
                return
            filename = f"{name}.json"
            path = os.path.join(WORKSPACE_DIR, filename)
            save_json(path, {"workflow_name": name, "created_at": time.strftime("%Y-%m-%dT%H:%M:%S"), "actions": []})
            self.current_workflow_path = path
            self.file_var.set(filename)
            self.file_dropdown.configure(values=get_workflow_files())
            self.sched_file_var.set(filename)
            logger.info(f"Created new workflow: {filename}")
            dlg.destroy()
            if self._active_tab == "workflow":
                self._refresh_workflow_list()

        ctk.CTkButton(dlg, text="Create", height=36,
                      fg_color=C["accent"], font=ctk.CTkFont(size=13, weight="bold"),
                      command=create).pack(pady=16, padx=20, fill="x")

    # ── Input Listeners ───────────────────────────────────────────────────────

    def _start_listeners(self):
        def on_press(key):
            try:
                if key == keyboard.Key.f9:
                    self.after(0, self.start_recording)
                elif key == keyboard.Key.f10:
                    self.after(0, self.stop_recording)
                elif key == keyboard.Key.f11:
                    self.after(0, self.playback)
                else:
                    if self.recording and self.recorder:
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

    # ── Utility ───────────────────────────────────────────────────────────────

    def _make_dialog(self, title: str, geometry: str) -> ctk.CTkToplevel:
        dlg = ctk.CTkToplevel(self)
        dlg.title(title)
        dlg.geometry(geometry)
        dlg.transient(self)
        dlg.grab_set()
        dlg.configure(fg_color=C["bg"])
        return dlg


# ── Entry point ───────────────────────────────────────────────────────────────
def run_gui():
    app = AutomatorGUI()
    app.mainloop()
