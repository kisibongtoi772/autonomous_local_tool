import tkinter as tk
import customtkinter as ctk
from typing import Callable

from ..utils.config import T

class FloatingStatus(ctk.CTkToplevel):
    def __init__(self, parent, on_stop: Callable[[], None], on_pause: Callable[[], None] = None, on_resume: Callable[[], None] = None, on_view_vars: Callable[[], None] = None):
        super().__init__(parent)
        self.on_stop = on_stop
        self.on_pause = on_pause
        self.on_resume = on_resume
        self.on_view_vars = on_view_vars
        self._is_paused = False
        
        self.title("Run HUD")
        self.geometry("380x48")
        self.overrideredirect(True)
        self.attributes('-topmost', True)
        
        # Position at top center
        sw = self.winfo_screenwidth()
        x = (sw - 380) // 2
        y = 40
        self.geometry(f"+{x}+{y}")
        
        self.configure(fg_color="systemTransparent" if self.tk.call('tk', 'windowingsystem') == 'aqua' else "#1E1E1E")
        self.attributes('-alpha', 0.95)
        
        # Main background container (Pill shape)
        self.main_frame = ctk.CTkFrame(self, fg_color="#1E1E1E", border_width=1, border_color="#10B981", corner_radius=24)
        self.main_frame.pack(fill="both", expand=True)
        
        # Blinking dot
        self.dot_label = ctk.CTkLabel(self.main_frame, text="▶", font=ctk.CTkFont("SF Pro Text", 16), text_color="#10B981")
        self.dot_label.pack(side="left", padx=(16, 4))
        
        # Status text
        self.text_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        self.text_frame.pack(side="left", fill="both", expand=True, padx=(4, 4))
        
        # Determine workflow name from parent if available
        wf_name = "Workflow"
        if hasattr(parent, "file_var"):
            wf_name = parent.file_var.get()
            
        self.title_label = ctk.CTkLabel(
            self.text_frame, text=wf_name, 
            font=ctk.CTkFont("SF Pro Text", 10, "bold"), text_color="#10B981", anchor="w"
        )
        self.title_label.pack(side="top", anchor="w", pady=(6, 0))
        
        self.status_label = ctk.CTkLabel(
            self.text_frame, text="Initializing...", 
            font=ctk.CTkFont("SF Pro Text", 11), text_color="#FFFFFF", anchor="w"
        )
        self.status_label.pack(side="top", anchor="w")
        
        # Pause / Resume Button
        self.pause_btn = ctk.CTkButton(
            self.main_frame, text="⏸", width=28, height=28,
            fg_color="#374151", hover_color="#4B5563",
            text_color="white", font=ctk.CTkFont("SF Pro Text", 12),
            corner_radius=14, command=self._handle_pause_resume
        )
        self.pause_btn.pack(side="right", padx=(2, 6))

        # Stop Button
        self.stop_btn = ctk.CTkButton(
            self.main_frame, text="⏹", width=28, height=28,
            fg_color="#EF4444", hover_color="#B91C1C",
            text_color="white", font=ctk.CTkFont("SF Pro Text", 12),
            corner_radius=14, command=self._handle_stop
        )
        self.stop_btn.pack(side="right", padx=(2, 2))
        
        # Vars Button (Optional)
        if on_view_vars:
            self.vars_btn = ctk.CTkButton(
                self.main_frame, text="{x}", width=28, height=28,
                fg_color="#3B82F6", hover_color="#2563EB",
                text_color="white", font=ctk.CTkFont("SF Pro Text", 12, "bold"),
                corner_radius=14, command=self._handle_view_vars
            )
            self.vars_btn.pack(side="right", padx=(0, 2))
        
        self._is_blinking = True
        self._blink_id = None
        
        self._blink_dot()
        
    def update_status(self, text: str):
        if not self.winfo_exists():
            return
        if self._is_paused:
            text = f"[PAUSED] {text}"
        if len(text) > 35:
            text = text[:32] + "..."
        self.status_label.configure(text=text)
        self.update_idletasks()
        
    def _handle_pause_resume(self):
        if self._is_paused:
            # Resume
            self._is_paused = False
            self.pause_btn.configure(text="⏸", fg_color="#374151")
            self.title_label.configure(text_color="#10B981")
            self.main_frame.configure(border_color="#10B981")
            status_text = self.status_label.cget("text").replace("[PAUSED] ", "")
            self.status_label.configure(text=status_text)
            if self.on_resume:
                self.on_resume()
        else:
            # Pause
            self._is_paused = True
            self.pause_btn.configure(text="▶", fg_color="#F59E0B")
            self.title_label.configure(text_color="#F59E0B")
            self.main_frame.configure(border_color="#F59E0B")
            self.status_label.configure(text=f"[PAUSED] {self.status_label.cget('text')}")
            if self.on_pause:
                self.on_pause()
                
    def _handle_stop(self):
        self.status_label.configure(text="STOPPING...")
        self.stop_btn.configure(state="disabled")
        self.pause_btn.configure(state="disabled")
        if self.on_stop:
            self.on_stop()
            
    def force_pause(self):
        if not self._is_paused:
            self._handle_pause_resume()

    def _handle_view_vars(self):
        if self.on_view_vars:
            self.on_view_vars()
            
    def _blink_dot(self):
        if not self.winfo_exists():
            return
        if not self._is_paused:
            self._is_blinking = not self._is_blinking
            color = "#10B981" if self._is_blinking else "#1E1E1E"
            self.dot_label.configure(text_color=color)
        else:
            self.dot_label.configure(text_color="#F59E0B")
            
        self._blink_id = self.after(800, self._blink_dot)

    def destroy(self):
        if self._blink_id:
            self.after_cancel(self._blink_id)
        super().destroy()
