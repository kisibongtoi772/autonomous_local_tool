from typing import Callable
import customtkinter as ctk

class FloatingStatus(ctk.CTkToplevel):
    def __init__(self, parent, on_stop: Callable[[], None], on_pause: Callable[[], None] = None, on_resume: Callable[[], None] = None):
        super().__init__(parent)
        self.on_stop = on_stop
        self.on_pause = on_pause
        self.on_resume = on_resume
        self._is_paused = False
        
        # Make it stay on top and remove window decorations
        self.attributes('-topmost', True)
        self.overrideredirect(True)
        
        # Main background container to simulate border
        self.main_frame = ctk.CTkFrame(self, fg_color="#1E1E1E", border_width=1, border_color="#333333", corner_radius=0)
        self.main_frame.pack(fill="both", expand=True)
        
        # Position at top right
        w, h = 400, 50
        sw = self.winfo_screenwidth()
        x = sw - w - 20
        y = 40
        self.geometry(f"{w}x{h}+{x}+{y}")
        
        # Layout
        self.main_frame.grid_columnconfigure(0, weight=1)
        self.main_frame.grid_rowconfigure(0, weight=1)
        
        self.status_label = ctk.CTkLabel(
            self.main_frame, text="Preparing...", 
            font=ctk.CTkFont("SF Pro Text", 12), text_color="#FFFFFF",
            anchor="w", justify="left"
        )
        self.status_label.grid(row=0, column=0, padx=(15, 10), pady=10, sticky="ew")

        # Pause/Resume Button
        self.pause_btn = ctk.CTkButton(
            self.main_frame, text="PAUSE", width=70, height=28,
            fg_color="#FF9500", hover_color="#D17A00",
            text_color="white", font=ctk.CTkFont("SF Pro Text", 12, "bold"),
            corner_radius=4, command=self._handle_pause_resume
        )
        self.pause_btn.grid(row=0, column=1, padx=(0, 10), pady=10)
        
        # Stop Button
        self.stop_btn = ctk.CTkButton(
            self.main_frame, text="STOP", width=60, height=28,
            fg_color="#FF3B30", hover_color="#D70015",
            text_color="white", font=ctk.CTkFont("SF Pro Text", 12, "bold"),
            corner_radius=4, command=self._handle_stop
        )
        self.stop_btn.grid(row=0, column=2, padx=(0, 15), pady=10)

    def update_status(self, text: str):
        if self._is_paused:
            text = f"[PAUSED] {text}"
        if len(text) > 42:
            text = text[:39] + "..."
        self.status_label.configure(text=text)
        self.update_idletasks()
        
    def _handle_pause_resume(self):
        if self._is_paused:
            # Resume
            self._is_paused = False
            self.pause_btn.configure(text="PAUSE", fg_color="#FF9500", hover_color="#D17A00")
            status_text = self.status_label.cget("text").replace("[PAUSED] ", "")
            self.status_label.configure(text=status_text)
            if self.on_resume:
                self.on_resume()
        else:
            # Pause
            self._is_paused = True
            self.pause_btn.configure(text="RESUME", fg_color="#34C759", hover_color="#248A3D")
            self.status_label.configure(text=f"[PAUSED] {self.status_label.cget('text')}")
            if self.on_pause:
                self.on_pause()

    def _handle_stop(self):
        self.status_label.configure(text="Stopping...")
        self.stop_btn.configure(state="disabled")
        self.pause_btn.configure(state="disabled")
        if self.on_stop:
            self.on_stop()
            
    def force_pause(self):
        if not self._is_paused:
            self._handle_pause_resume()
