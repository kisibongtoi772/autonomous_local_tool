import tkinter as tk
import customtkinter as ctk
from typing import Callable

class FloatingRecorder(ctk.CTkToplevel):
    def __init__(self, parent, recorder_instance, on_stop: Callable[[], None]):
        super().__init__(parent)
        self.recorder = recorder_instance
        self.on_stop = on_stop
        
        self.title("Recording HUD")
        self.geometry("260x50")
        self.overrideredirect(True)
        self.attributes('-topmost', True)
        
        # Position at top center
        sw = self.winfo_screenwidth()
        x = (sw - 260) // 2
        y = 30
        self.geometry(f"+{x}+{y}")
        
        # Main background container
        self.main_frame = ctk.CTkFrame(self, fg_color="#1E1E1E", border_width=1, border_color="#FF3B30", corner_radius=8)
        self.main_frame.pack(fill="both", expand=True)
        
        # Blinking dot
        self.dot_label = ctk.CTkLabel(self.main_frame, text="🔴", font=ctk.CTkFont("SF Pro Text", 14), text_color="#FF3B30")
        self.dot_label.pack(side="left", padx=(15, 5))
        
        # Status text
        self.status_label = ctk.CTkLabel(
            self.main_frame, text="RECORDING", 
            font=ctk.CTkFont("SF Pro Text", 12, "bold"), text_color="#FFFFFF"
        )
        self.status_label.pack(side="left")
        
        # Count label
        self.count_label = ctk.CTkLabel(
            self.main_frame, text="Actions: 0", 
            font=ctk.CTkFont("SF Pro Text", 12), text_color="#A0A0A5"
        )
        self.count_label.pack(side="left", padx=(10, 10))
        
        # Stop Button
        self.stop_btn = ctk.CTkButton(
            self.main_frame, text="⏹ STOP", width=60, height=28,
            fg_color="#FF3B30", hover_color="#D70015",
            text_color="white", font=ctk.CTkFont("SF Pro Text", 11, "bold"),
            corner_radius=4, command=self._handle_stop
        )
        self.stop_btn.pack(side="right", padx=(0, 10))
        
        self._is_blinking = True
        self._poll_id = None
        self._blink_id = None
        
        self._poll_update()
        self._blink_dot()
        
    def _handle_stop(self):
        self.status_label.configure(text="STOPPING...")
        self.stop_btn.configure(state="disabled")
        if self.on_stop:
            self.on_stop()
            
    def _poll_update(self):
        if not self.winfo_exists():
            return
        if self.recorder:
            count = len(self.recorder.actions)
            self.count_label.configure(text=f"Actions: {count}")
        self._poll_id = self.after(100, self._poll_update)
        
    def _blink_dot(self):
        if not self.winfo_exists():
            return
        self._is_blinking = not self._is_blinking
        color = "#FF3B30" if self._is_blinking else "#1E1E1E"
        self.dot_label.configure(text_color=color)
        self._blink_id = self.after(800, self._blink_dot)

    def destroy(self):
        if self._poll_id:
            self.after_cancel(self._poll_id)
        if self._blink_id:
            self.after_cancel(self._blink_id)
        super().destroy()
