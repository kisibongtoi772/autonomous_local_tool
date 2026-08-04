import os
import time
import tkinter as tk
import customtkinter as ctk
import pyautogui
from PIL import Image

from ..utils.config import T
from ..core.config import TEMPLATES_DIR

class DiagnosticsModal(ctk.CTkToplevel):
    def __init__(self, parent, workflow_actions):
        super().__init__(parent)
        self.parent_app = parent
        self.workflow_actions = workflow_actions
        
        self.title("Pre-flight Screen Diagnostics")
        self.geometry("600x500")
        self.transient(parent)
        self.grab_set()
        
        # Center the modal
        self.update_idletasks()
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        x = (sw - 600) // 2
        y = (sh - 500) // 2
        self.geometry(f"+{x}+{y}")
        
        self.configure(fg_color=T["bg"])
        
        # Header
        hdr = ctk.CTkFrame(self, fg_color="transparent")
        hdr.pack(fill="x", padx=20, pady=(20, 10))
        ctk.CTkLabel(hdr, text="🩺 Template Diagnostics", font=ctk.CTkFont("SF Pro Text", 18, "bold"), text_color=T["text"]).pack(side="left")
        ctk.CTkLabel(hdr, text="Scans all template images against current screen", font=ctk.CTkFont("SF Pro Text", 11), text_color=T["dim"]).pack(side="left", padx=10, side="bottom")
        
        # Action Log / Results
        self.scroll = ctk.CTkScrollableFrame(self, fg_color=T["surface"], corner_radius=8)
        self.scroll.pack(fill="both", expand=True, padx=20, pady=(0, 20))
        
        self.btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.btn_frame.pack(fill="x", padx=20, pady=(0, 20))
        
        self.close_btn = ctk.CTkButton(self.btn_frame, text="Close", fg_color=T["raised"], hover_color=T["hover"], text_color=T["text"], command=self.destroy, width=100)
        self.close_btn.pack(side="right")
        
        # Collect templates
        self.templates_to_check = []
        self.seen_templates = set()
        self._collect_templates(self.workflow_actions)
        
        if not self.templates_to_check:
            ctk.CTkLabel(self.scroll, text="No image templates found in this workflow.", text_color=T["dim"]).pack(pady=20)
            return
            
        # Start scanning
        self.after(100, self._run_diagnostics)
        
    def _collect_templates(self, actions):
        for action in actions:
            atype = action.get("type", "")
            tmpl = action.get("template") or action.get("template_image")
            if tmpl and tmpl not in self.seen_templates:
                self.seen_templates.add(tmpl)
                conf = action.get("confidence") or action.get("condition_confidence", 0.8)
                self.templates_to_check.append({
                    "template": tmpl,
                    "confidence": conf,
                    "type": atype
                })
            
            # recursive for loop/group
            if "actions" in action:
                self._collect_templates(action["actions"])
            if "then_actions" in action:
                self._collect_templates(action["then_actions"])
            if "else_actions" in action:
                self._collect_templates(action["else_actions"])
                
    def _run_diagnostics(self):
        # Temporarily hide self to take screenshot
        self.withdraw()
        self.parent_app.withdraw()
        self.update()
        time.sleep(0.3)
        
        screenshot = pyautogui.screenshot()
        
        self.parent_app.deiconify()
        self.deiconify()
        
        for item in self.templates_to_check:
            self._check_item(item, screenshot)
            
    def _check_item(self, item, screenshot):
        tmpl = item["template"]
        conf = float(item["confidence"])
        
        row = ctk.CTkFrame(self.scroll, fg_color="transparent")
        row.pack(fill="x", pady=4, padx=8)
        
        path = os.path.join(TEMPLATES_DIR, tmpl)
        if not os.path.exists(path):
            ctk.CTkLabel(row, text="⚠️", font=ctk.CTkFont(size=14), text_color=T["err"]).pack(side="left")
            ctk.CTkLabel(row, text=f" {tmpl} (Missing File)", font=ctk.CTkFont(size=12, weight="bold"), text_color=T["err"]).pack(side="left")
            return
            
        try:
            # Add timeout to avoid blocking main thread forever
            res = pyautogui.locate(path, screenshot, confidence=conf)
            if res:
                ctk.CTkLabel(row, text="✅", font=ctk.CTkFont(size=14), text_color=T["ok"]).pack(side="left")
                ctk.CTkLabel(row, text=f" {tmpl}", font=ctk.CTkFont(size=12, weight="bold"), text_color=T["ok"]).pack(side="left")
                ctk.CTkLabel(row, text=f" (Conf: {conf})", font=ctk.CTkFont(size=11), text_color=T["dim"]).pack(side="left")
                
                # Add locate button
                ctk.CTkButton(
                    row, text="🎯 Locate", width=60, height=24,
                    fg_color="#EF4444", hover_color="#B91C1C", text_color="white",
                    command=lambda: self._trigger_locate(tmpl, conf)
                ).pack(side="right")
            else:
                ctk.CTkLabel(row, text="❌", font=ctk.CTkFont(size=14), text_color=T["err"]).pack(side="left")
                ctk.CTkLabel(row, text=f" {tmpl}", font=ctk.CTkFont(size=12, weight="bold"), text_color=T["err"]).pack(side="left")
                ctk.CTkLabel(row, text=f" (Not found @ {conf})", font=ctk.CTkFont(size=11), text_color=T["dim"]).pack(side="left")
                
                ctk.CTkButton(
                    row, text="🎛 Tune", width=50, height=24,
                    fg_color=T["accent"], text_color=T["text"],
                    command=lambda: self._trigger_tune(tmpl, conf)
                ).pack(side="right", padx=4)
        except Exception as e:
            ctk.CTkLabel(row, text="⚠️", font=ctk.CTkFont(size=14), text_color=T["err"]).pack(side="left")
            ctk.CTkLabel(row, text=f" Error matching {tmpl}", font=ctk.CTkFont(size=11), text_color=T["err"]).pack(side="left")

    def _trigger_locate(self, tmpl, conf):
        from .pickers import ScreenLocator
        self.withdraw()
        self.parent_app.withdraw()
        ScreenLocator(self.parent_app, tmpl, conf, lambda: (self.parent_app.deiconify(), self.deiconify()))
        
    def _trigger_tune(self, tmpl, conf):
        from .pickers import ConfidenceTuner
        self.withdraw()
        self.parent_app.withdraw()
        ConfidenceTuner(self.parent_app, tmpl, conf, lambda new_conf: print(f"Tuned {tmpl} to {new_conf}"), lambda: (self.parent_app.deiconify(), self.deiconify()))
