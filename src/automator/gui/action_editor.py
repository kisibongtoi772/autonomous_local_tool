import tkinter as tk
import customtkinter as ctk
import copy
from typing import Callable
from ..utils.config import T, FONT_BODY

def open_action_editor(app, idx: int, action: dict, on_save: Callable[[dict], None]):
    """Smart Form Builder for editing actions with type-specific UI."""
    atype = action.get("type", "unknown")
    dlg = app._dialog(f"Edit {atype.title()}", "440x420")
    
    # We will build form fields in a scrollable frame
    form = ctk.CTkScrollableFrame(dlg, fg_color="transparent")
    form.pack(fill="both", expand=True, padx=20, pady=(16, 2))
    
    # Helper to add a label
    def _lbl(text):
        from .components import _label
        lbl = _label(form, text, size=10, colour=T["dim"])
        lbl.pack(anchor="w", pady=(8, 2))
        return lbl
        
    fields = {}
    
    # --- Contextual UI ---
    if atype == "sleep":
        _lbl("Duration (seconds)")
        dur = ctk.CTkEntry(form, fg_color=T["raised"], text_color=T["text"], border_color=T["border"])
        dur.pack(fill="x")
        dur.insert(0, str(action.get("duration", 1.0)))
        fields["duration"] = dur
        
    elif atype == "click":
        row = ctk.CTkFrame(form, fg_color="transparent")
        row.pack(fill="x")
        
        x_frame = ctk.CTkFrame(row, fg_color="transparent")
        x_frame.pack(side="left", fill="x", expand=True, padx=(0, 4))
        from .components import _label
        _label(x_frame, "X Coordinate", size=10, colour=T["dim"]).pack(anchor="w", pady=(8, 2))
        x_ent = ctk.CTkEntry(x_frame, fg_color=T["raised"], text_color=T["text"], border_color=T["border"])
        x_ent.pack(fill="x")
        x_ent.insert(0, str(action.get("x", 0)))
        fields["x"] = x_ent
        
        y_frame = ctk.CTkFrame(row, fg_color="transparent")
        y_frame.pack(side="left", fill="x", expand=True, padx=(4, 0))
        _label(y_frame, "Y Coordinate", size=10, colour=T["dim"]).pack(anchor="w", pady=(8, 2))
        y_ent = ctk.CTkEntry(y_frame, fg_color=T["raised"], text_color=T["text"], border_color=T["border"])
        y_ent.pack(fill="x")
        y_ent.insert(0, str(action.get("y", 0)))
        fields["y"] = y_ent
        
        def on_locate():
            def cb(x, y):
                x_ent.delete(0, "end"); x_ent.insert(0, str(x))
                y_ent.delete(0, "end"); y_ent.insert(0, str(y))
                dlg.deiconify()
            from .pickers import CoordinatePicker
            dlg.withdraw()
            CoordinatePicker(app, cb, lambda: dlg.deiconify())
            
        btn = ctk.CTkButton(form, text="🎯 Locate on Screen", command=on_locate, fg_color=T["raised"], hover_color=T["hover"], text_color=T["text"])
        btn.pack(fill="x", pady=12)
        
    elif atype in ("wait_for_template", "assert_template", "if_template"):
        _lbl("Template Image")
        row = ctk.CTkFrame(form, fg_color="transparent")
        row.pack(fill="x")
        
        tpl_ent = ctk.CTkEntry(row, fg_color=T["raised"], text_color=T["text"], border_color=T["border"])
        tpl_ent.pack(side="left", fill="x", expand=True)
        tpl_ent.insert(0, action.get("template", ""))
        fields["template"] = tpl_ent
        
        def on_pick():
            def cb(img):
                tpl_ent.delete(0, "end"); tpl_ent.insert(0, img)
                dlg.deiconify()
            from .pickers import TemplatePicker
            dlg.withdraw()
            TemplatePicker(app, cb, lambda: dlg.deiconify())
            
        def on_snip():
            def cb(img):
                tpl_ent.delete(0, "end"); tpl_ent.insert(0, img)
                dlg.deiconify()
            from .pickers import SnippingTool
            dlg.withdraw()
            SnippingTool(app, cb, lambda: dlg.deiconify())
            
        ctk.CTkButton(row, text="🖼 Pick", width=50, command=on_pick, fg_color=T["raised"]).pack(side="left", padx=4)
        ctk.CTkButton(row, text="✂ Snip", width=50, command=on_snip, fg_color=T["raised"]).pack(side="left")
        
        if atype == "wait_for_template":
            _lbl("Timeout (seconds)")
            timeout_ent = ctk.CTkEntry(form, fg_color=T["raised"], text_color=T["text"], border_color=T["border"])
            timeout_ent.pack(fill="x")
            timeout_ent.insert(0, str(action.get("timeout", 10.0)))
            fields["timeout"] = timeout_ent
            
    elif atype == "hotkey":
        _lbl("Keys (comma separated, e.g. ctrl, c)")
        row = ctk.CTkFrame(form, fg_color="transparent")
        row.pack(fill="x")
        key_ent = ctk.CTkEntry(row, fg_color=T["raised"], text_color=T["text"], border_color=T["border"])
        key_ent.pack(side="left", fill="x", expand=True)
        key_ent.insert(0, ",".join(action.get("keys", [])))
        fields["keys"] = key_ent
        
        def on_key():
            def cb(k):
                key_ent.delete(0, "end"); key_ent.insert(0, k)
                dlg.deiconify()
            from .pickers import HotkeyPicker
            dlg.withdraw()
            HotkeyPicker(app, cb, lambda: dlg.deiconify())
            
        ctk.CTkButton(row, text="⌨️ Press", width=60, command=on_key, fg_color=T["raised"]).pack(side="left", padx=4)
        
    else:
        # Fallback for others
        _lbl(f"Value for {atype}")
        fallback_ent = ctk.CTkEntry(form, fg_color=T["raised"], text_color=T["text"], border_color=T["border"])
        fallback_ent.pack(fill="x")
        
        # Determine current generic string value
        cur_val = ""
        if atype == "type":             cur_val = action.get("key", "")
        elif atype == "run_command":    cur_val = action.get("command", "")
        elif atype == "scroll":         cur_val = str(action.get("amount", 0))
        elif atype == "clipboard":      cur_val = f"{action.get('action','set')} {action.get('text','')}"
        elif atype == "screenshot":     cur_val = action.get("filename", "")
        elif atype == "run_workflow":   cur_val = action.get("workflow_file", "")
        elif atype == "prompt_user":    cur_val = action.get("message", "") + (f"|{action.get('save_to_variable')}" if action.get("require_input") else "")
        elif atype == "app_focus":      cur_val = action.get("app_name", "")
        elif atype == "notification":   cur_val = action.get("message", "") + (f"|{action.get('title')}" if action.get("title") != "Automator" else "")
        elif atype == "comment":        cur_val = action.get("text", "")
        
        fallback_ent.insert(0, cur_val)
        fields["_generic"] = fallback_ent
        
        # Add Variable Picker helper
        def on_var():
            def cb(v):
                pos = fallback_ent.index("insert")
                fallback_ent.insert(pos, v)
                dlg.deiconify()
            from .pickers import VariablePicker
            dlg.withdraw()
            VariablePicker(app, cb, lambda: dlg.deiconify())
        ctk.CTkButton(form, text="{x} Insert Variable", command=on_var, fg_color=T["raised"], text_color=T["dim"]).pack(pady=8, anchor="w")

    # --- Advanced Section ---
    from .components import _label
    _label(form, "Advanced", size=11, colour=T["text"], weight="bold").pack(anchor="w", pady=(24, 4))
    
    adv_row = ctk.CTkFrame(form, fg_color="transparent")
    adv_row.pack(fill="x")
    
    rc_frame = ctk.CTkFrame(adv_row, fg_color="transparent")
    rc_frame.pack(side="left", fill="x", expand=True, padx=(0, 4))
    _label(rc_frame, "Retry Count", size=10, colour=T["dim"]).pack(anchor="w", pady=(4, 2))
    rc_ent = ctk.CTkEntry(rc_frame, fg_color=T["raised"], text_color=T["text"], border_color=T["border"])
    rc_ent.pack(fill="x")
    rc_ent.insert(0, str(action.get("retry_count", 0)))
    fields["retry_count"] = rc_ent
    
    rd_frame = ctk.CTkFrame(adv_row, fg_color="transparent")
    rd_frame.pack(side="left", fill="x", expand=True, padx=(4, 0))
    _label(rd_frame, "Retry Delay (s)", size=10, colour=T["dim"]).pack(anchor="w", pady=(4, 2))
    rd_ent = ctk.CTkEntry(rd_frame, fg_color=T["raised"], text_color=T["text"], border_color=T["border"])
    rd_ent.pack(fill="x")
    rd_ent.insert(0, str(action.get("retry_delay", 0.5)))
    fields["retry_delay"] = rd_ent
    
    # --- Submit Logic ---
    def on_submit():
        upd = copy.deepcopy(action)
        try:
            upd["retry_count"] = int(rc_ent.get())
            upd["retry_delay"] = float(rd_ent.get())
            
            if atype == "sleep":
                upd["duration"] = float(fields["duration"].get())
            elif atype == "click":
                upd["x"] = int(fields["x"].get())
                upd["y"] = int(fields["y"].get())
            elif atype in ("wait_for_template", "assert_template", "if_template"):
                upd["template"] = fields["template"].get()
                if atype == "wait_for_template":
                    upd["timeout"] = float(fields["timeout"].get())
            elif atype == "hotkey":
                upd["keys"] = [k.strip() for k in fields["keys"].get().split(",")]
            else:
                val = fields["_generic"].get().strip()
                if atype == "type":             upd["key"] = val
                elif atype == "run_command":    upd["command"] = val
                elif atype == "scroll":         upd["amount"] = int(val)
                elif atype == "clipboard":
                    parts = val.split(None, 1)
                    upd["action"] = parts[0] if parts else "set"
                    upd["text"]   = parts[1] if len(parts) > 1 else ""
                elif atype == "screenshot":     upd["filename"] = val
                elif atype == "run_workflow":   upd["workflow_file"] = val
                elif atype == "prompt_user":
                    parts = val.split("|", 1)
                    upd["message"] = parts[0].strip()
                    if len(parts) > 1:
                        upd["require_input"] = True
                        upd["save_to_variable"] = parts[1].strip()
                    else:
                        upd["require_input"] = False
                        upd.pop("save_to_variable", None)
                elif atype == "app_focus":      upd["app_name"] = val
                elif atype == "notification":
                    parts = val.split("|", 1)
                    if len(parts) > 1:
                        upd["title"] = parts[1].strip()
                        upd["message"] = parts[0].strip()
                    else:
                        upd["message"] = val
                elif atype == "comment":        upd["text"] = val
                
            dlg.destroy()
            on_save(upd)
            
        except ValueError as e:
            from tkinter import messagebox
            messagebox.showerror("Validation Error", f"Invalid input format: {e}", parent=dlg)
            
    btn_frame = ctk.CTkFrame(dlg, fg_color="transparent")
    btn_frame.pack(fill="x", padx=20, pady=20)
    
    ctk.CTkButton(btn_frame, text="Cancel", width=100, command=dlg.destroy, fg_color="transparent", border_width=1, border_color=T["border"], text_color=T["dim"]).pack(side="left")
    ctk.CTkButton(btn_frame, text="Save Changes", width=120, command=on_submit, fg_color=T["primary"], text_color=T["text"]).pack(side="right")
