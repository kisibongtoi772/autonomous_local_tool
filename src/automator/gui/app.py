import logging
import customtkinter as ctk
import threading
import json
import os
from pynput import keyboard
from ..core.recorder import Recorder
from ..core.player import Player
from ..utils.logger import get_logger

logger = get_logger(__name__)

class GUILoggingHandler(logging.Handler):
    def __init__(self, textbox):
        super().__init__()
        self.textbox = textbox
        self.setFormatter(logging.Formatter('%(asctime)s - %(message)s', '%H:%M:%S'))

    def emit(self, record):
        msg = self.format(record)
        # Use after to safely update UI from other threads
        self.textbox.after(0, self.append_to_textbox, msg)
        
    def append_to_textbox(self, msg):
        self.textbox.configure(state="normal")
        self.textbox.insert("end", msg + "\n")
        self.textbox.see("end")
        # Keep only the last 100 lines to prevent memory issues
        lines = int(self.textbox.index('end-1c').split('.')[0])
        if lines > 100:
            self.textbox.delete("1.0", f"{lines - 100}.0")
        self.textbox.configure(state="disabled")

logger = get_logger(__name__)

class AutomatorGUI(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("Desktop Automator")
        self.geometry("500x500")
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
        self.title_label.pack(pady=10)

        # Tabview
        self.tabview = ctk.CTkTabview(self, width=460, height=420)
        self.tabview.pack(padx=20, pady=10, fill="both", expand=True)
        
        self.tabview.add("Dashboard")
        self.tabview.add("Workflow")

        self.setup_dashboard_tab()
        self.setup_workflow_tab()

    def setup_dashboard_tab(self):
        dashboard = self.tabview.tab("Dashboard")

        # Status
        self.status_label = ctk.CTkLabel(dashboard, text="Status: Ready", font=ctk.CTkFont(size=14))
        self.status_label.pack(pady=5)

        # Buttons Frame
        self.btn_frame = ctk.CTkFrame(dashboard, fg_color="transparent")
        self.btn_frame.pack(pady=10)

        # Record Button
        self.record_btn = ctk.CTkButton(self.btn_frame, text="🔴 Record (F9)", command=self.start_recording, fg_color="#c0392b", hover_color="#e74c3c")
        self.record_btn.grid(row=0, column=0, padx=10, pady=10)

        # Stop Button
        self.stop_btn = ctk.CTkButton(self.btn_frame, text="⏹ Stop (F10)", command=self.stop_recording, state="disabled")
        self.stop_btn.grid(row=0, column=1, padx=10, pady=10)

        # Playback Button
        self.play_btn = ctk.CTkButton(dashboard, text="▶️ Playback (F11)", command=self.playback, width=200)
        self.play_btn.pack(pady=5)

        # Log Console
        self.log_console = ctk.CTkTextbox(dashboard, width=450, height=180, state="disabled", font=ctk.CTkFont(family="Courier", size=12))
        self.log_console.pack(pady=10, padx=10, fill="both", expand=True)

        # Setup GUI logging
        gui_handler = GUILoggingHandler(self.log_console)
        logging.getLogger("automator").addHandler(gui_handler)
        logger.addHandler(gui_handler)
        
        logger.info("GUI started successfully.")

    def setup_workflow_tab(self):
        workflow_tab = self.tabview.tab("Workflow")
        
        # Refresh Button
        self.refresh_btn = ctk.CTkButton(workflow_tab, text="🔄 Refresh Workflow", command=self.load_workflow)
        self.refresh_btn.pack(pady=10)
        
        # Scrollable Frame for Steps
        self.workflow_frame = ctk.CTkScrollableFrame(workflow_tab, width=430, height=300)
        self.workflow_frame.pack(pady=10, padx=10, fill="both", expand=True)
        
        self.load_workflow()

    def load_workflow(self):
        # Clear existing widgets
        for widget in self.workflow_frame.winfo_children():
            widget.destroy()
            
        workflow_path = "workspace/workflow.json"
        if not os.path.exists(workflow_path):
            lbl = ctk.CTkLabel(self.workflow_frame, text="No workflow found. Record one first!")
            lbl.pack(pady=20)
            return
            
        try:
            with open(workflow_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                
            actions = data.get("actions", [])
            if not actions:
                lbl = ctk.CTkLabel(self.workflow_frame, text="Workflow is empty.")
                lbl.pack(pady=20)
                return
                
            for i, action in enumerate(actions):
                action_type = action.get("type", "unknown")
                details = f"[{i+1}] {action_type.upper()}"
                
                if action_type == "click":
                    details += f" at ({action.get('x')}, {action.get('y')}) - {action.get('button', 'left')} click(s): {action.get('clicks', 1)}"
                elif action_type == "type":
                    details += f" text: '{action.get('text', '')}'"
                elif action_type == "sleep":
                    details += f" for {action.get('duration', 0)}s"
                elif action_type == "hotkey":
                    details += f" keys: {action.get('keys', [])}"
                elif action_type == "run_command":
                    details += f" cmd: '{action.get('command', '')}'"
                    
                lbl = ctk.CTkLabel(self.workflow_frame, text=details, anchor="w", justify="left")
                lbl.pack(fill="x", padx=10, pady=2)
                
        except Exception as e:
            lbl = ctk.CTkLabel(self.workflow_frame, text=f"Error loading workflow:\n{e}", text_color="#e74c3c")
            lbl.pack(pady=20)

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
