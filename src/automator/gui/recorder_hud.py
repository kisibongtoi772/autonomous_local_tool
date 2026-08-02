import tkinter as tk
import customtkinter as ctk
from typing import Callable
from ..core.recorder import Recorder
from ..utils.config import T
from ..utils.logger import get_logger

logger = get_logger(__name__)

class RecorderHUD(ctk.CTkToplevel):
    def __init__(self, parent, on_stop: Callable[[list], None]):
        super().__init__(parent)
        self.parent = parent
        self.on_stop = on_stop
        
        self.title("Recording Macro...")
        self.geometry("300x120")
        self.configure(fg_color=T["bg"])
        self.attributes("-topmost", True)
        self.resizable(False, False)
        
        # Position in top right corner
        self.update_idletasks()
        w = self.winfo_screenwidth()
        self.geometry(f"+{w - 320}+40")
        
        self.recorder = Recorder()
        
        # UI
        main_frame = ctk.CTkFrame(self, fg_color="transparent")
        main_frame.pack(fill="both", expand=True, padx=20, pady=20)
        
        self.status_label = ctk.CTkLabel(
            main_frame, text="🔴 Recording actions...", 
            font=ctk.CTkFont("SF Pro Display", 16, "bold"), text_color=T["err"]
        )
        self.status_label.pack(pady=(0, 10))
        
        self.stop_btn = ctk.CTkButton(
            main_frame, text="⏹ Stop & Save", width=140,
            fg_color=T["surface"], border_width=1, border_color=T["border"],
            text_color=T["text"], hover_color=T["hover"],
            command=self._stop_recording
        )
        self.stop_btn.pack()
        
        # Start immediately
        self.after(100, self._start_recording)
        
        # Handle manual close (X button)
        self.protocol("WM_DELETE_WINDOW", self._stop_recording)
        
    def _start_recording(self):
        # Hide parent
        if hasattr(self.parent, "withdraw"):
            self.parent.withdraw()
            
        logger.info("Starting recorder HUD...")
        self.recorder.start()
        
    def _stop_recording(self):
        logger.info("Stopping recorder HUD...")
        self.recorder.stop(save=False)
        actions = self.recorder.get_recorded_actions()
        
        # Show parent back
        if hasattr(self.parent, "deiconify"):
            self.parent.deiconify()
            
        self.on_stop(actions)
        self.destroy()
