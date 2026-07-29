import customtkinter as ctk
import threading
from pynput import keyboard
from ..core.recorder import Recorder
from ..core.player import Player
from ..utils.logger import get_logger

logger = get_logger(__name__)

class AutomatorGUI(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("Desktop Automator")
        self.geometry("400x300")
        self.resizable(False, False)
        
        # Set theme
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        self.recording = False
        self.recorder = None

        self.setup_ui()
        self.start_hotkey_listener()

    def setup_ui(self):
        # Title
        self.title_label = ctk.CTkLabel(self, text="Desktop Automator", font=ctk.CTkFont(size=24, weight="bold"))
        self.title_label.pack(pady=20)

        # Status
        self.status_label = ctk.CTkLabel(self, text="Status: Ready", font=ctk.CTkFont(size=14))
        self.status_label.pack(pady=10)

        # Buttons Frame
        self.btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.btn_frame.pack(pady=20)

        # Record Button
        self.record_btn = ctk.CTkButton(self.btn_frame, text="🔴 Record (F9)", command=self.start_recording, fg_color="#c0392b", hover_color="#e74c3c")
        self.record_btn.grid(row=0, column=0, padx=10, pady=10)

        # Stop Button
        self.stop_btn = ctk.CTkButton(self.btn_frame, text="⏹ Stop (F10)", command=self.stop_recording, state="disabled")
        self.stop_btn.grid(row=0, column=1, padx=10, pady=10)

        # Playback Button
        self.play_btn = ctk.CTkButton(self, text="▶️ Playback (F11)", command=self.playback, width=200)
        self.play_btn.pack(pady=10)

    def start_recording(self):
        if not self.recording:
            logger.info("GUI: Starting recording...")
            self.recording = True
            self.recorder = Recorder()
            self.recorder.start()
            
            # Update UI
            self.status_label.configure(text="Status: 🔴 Recording...", text_color="#e74c3c")
            self.record_btn.configure(state="disabled")
            self.stop_btn.configure(state="normal")
            self.play_btn.configure(state="disabled")

    def stop_recording(self):
        if self.recording and self.recorder:
            logger.info("GUI: Stopping recording...")
            self.recorder.stop()
            self.recording = False
            
            # Update UI
            self.status_label.configure(text="Status: ⏹ Saved to workspace/workflow.json", text_color="white")
            self.record_btn.configure(state="normal")
            self.stop_btn.configure(state="disabled")
            self.play_btn.configure(state="normal")

    def playback(self):
        if not self.recording:
            logger.info("GUI: Playing back...")
            self.status_label.configure(text="Status: ▶️ Playing back...", text_color="#3498db")
            
            def run_playback():
                try:
                    player = Player()
                    player.play()
                except Exception as e:
                    logger.error(f"Playback error: {e}")
                finally:
                    self.after(0, lambda: self.status_label.configure(text="Status: Ready", text_color="white"))
                    
            # Run playback in background thread so it doesn't freeze the GUI
            threading.Thread(target=run_playback, daemon=True).start()

    def start_hotkey_listener(self):
        def on_press(key):
            try:
                if key == keyboard.Key.f9:
                    self.after(0, self.start_recording)
                elif key == keyboard.Key.f10:
                    self.after(0, self.stop_recording)
                elif key == keyboard.Key.f11:
                    self.after(0, self.playback)
            except Exception as e:
                logger.error(f"Error handling hotkey: {e}")

        self.listener = keyboard.Listener(on_press=on_press)
        self.listener.start()

def run_gui():
    app = AutomatorGUI()
    app.mainloop()
