import logging
import customtkinter as ctk
import threading
import json
import os
import glob
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
        self.current_workflow_path = os.path.join("workspace", "workflow.json")

        # Ensure workspace exists
        os.makedirs("workspace", exist_ok=True)

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

        # File selection frame
        self.file_frame = ctk.CTkFrame(dashboard, fg_color="transparent")
        self.file_frame.pack(pady=5)

        self.file_var = ctk.StringVar(value="workflow.json")
        self.file_dropdown = ctk.CTkOptionMenu(self.file_frame, variable=self.file_var, values=self.get_workflow_files(), command=self.on_file_select)
        self.file_dropdown.grid(row=0, column=0, padx=5)

        self.new_file_btn = ctk.CTkButton(self.file_frame, text="New", width=50, command=self.create_new_workflow)
        self.new_file_btn.grid(row=0, column=1, padx=5)

        # Buttons Frame
        self.btn_frame = ctk.CTkFrame(dashboard, fg_color="transparent")
        self.btn_frame.pack(pady=5)

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

    def get_workflow_files(self):
        files = glob.glob("workspace/*.json")
        if not files:
            return ["workflow.json"]
        return [os.path.basename(f) for f in files]

    def on_file_select(self, choice):
        self.current_workflow_path = os.path.join("workspace", choice)
        logger.info(f"Selected workflow: {choice}")
        self.load_workflow()

    def create_new_workflow(self):
        dialog = ctk.CTkInputDialog(text="Enter new workflow name (without .json):", title="New Workflow")
        name = dialog.get_input()
        if name:
            filename = f"{name}.json"
            self.current_workflow_path = os.path.join("workspace", filename)
            # Create empty workflow
            with open(self.current_workflow_path, "w", encoding="utf-8") as f:
                json.dump({"workflow_name": name, "created_at": "", "actions": []}, f)
            # Update dropdown
            self.file_dropdown.configure(values=self.get_workflow_files())
            self.file_var.set(filename)
            logger.info(f"Created and selected new workflow: {filename}")
            self.load_workflow()

    def setup_workflow_tab(self):
        workflow_tab = self.tabview.tab("Workflow")
        
        # Buttons Frame for Workflow Tab
        btn_frame = ctk.CTkFrame(workflow_tab, fg_color="transparent")
        btn_frame.pack(pady=10)

        # Refresh Button
        self.refresh_btn = ctk.CTkButton(btn_frame, text="🔄 Refresh", command=self.load_workflow, width=150)
        self.refresh_btn.grid(row=0, column=0, padx=10)
        
        # Clear All Button
        self.clear_btn = ctk.CTkButton(btn_frame, text="🗑️ Clear All", command=self.clear_workflow, width=120, fg_color="#c0392b", hover_color="#e74c3c")
        self.clear_btn.grid(row=0, column=1, padx=10)

        # Add Action Button
        self.add_action_btn = ctk.CTkButton(btn_frame, text="➕ Add Action", command=self.open_add_action_dialog, width=120, fg_color="#27ae60", hover_color="#2ecc71")
        self.add_action_btn.grid(row=0, column=2, padx=10)
        
        # Scrollable Frame for Steps
        self.workflow_frame = ctk.CTkScrollableFrame(workflow_tab, width=430, height=280)
        self.workflow_frame.pack(pady=10, padx=10, fill="both", expand=True)
        
        self.load_workflow()

    def load_workflow(self):
        # Clear existing widgets
        for widget in self.workflow_frame.winfo_children():
            widget.destroy()
            
        workflow_path = self.current_workflow_path
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
                
                # Create a frame for each row to hold label and buttons
                row_frame = ctk.CTkFrame(self.workflow_frame, fg_color="transparent")
                row_frame.pack(fill="x", padx=5, pady=2)
                
                lbl = ctk.CTkLabel(row_frame, text=details, anchor="w", justify="left")
                lbl.pack(side="left", fill="x", expand=True)
                
                # Button frame for action controls
                ctrl_frame = ctk.CTkFrame(row_frame, fg_color="transparent")
                ctrl_frame.pack(side="right")

                if i > 0:
                    up_btn = ctk.CTkButton(ctrl_frame, text="⬆️", width=30, fg_color="transparent", hover_color="#333333", command=lambda idx=i: self.move_action_up(idx))
                    up_btn.pack(side="left", padx=2)
                
                if i < len(actions) - 1:
                    down_btn = ctk.CTkButton(ctrl_frame, text="⬇️", width=30, fg_color="transparent", hover_color="#333333", command=lambda idx=i: self.move_action_down(idx))
                    down_btn.pack(side="left", padx=2)
                
                # Edit button
                edit_btn = ctk.CTkButton(ctrl_frame, text="✏️", width=30, fg_color="transparent", hover_color="#333333", command=lambda idx=i, act=action: self.open_edit_action_dialog(idx, act))
                edit_btn.pack(side="left", padx=2)
                
                # Delete button for this specific action
                del_btn = ctk.CTkButton(ctrl_frame, text="❌", width=30, fg_color="transparent", text_color="#e74c3c", hover_color="#333333", command=lambda idx=i: self.delete_action(idx))
                del_btn.pack(side="left", padx=2)
                
        except Exception as e:
            lbl = ctk.CTkLabel(self.workflow_frame, text=f"Error loading workflow:\n{e}", text_color="#e74c3c")
            lbl.pack(pady=20)

    def delete_action(self, index):
        workflow_path = self.current_workflow_path
        try:
            with open(workflow_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            if "actions" in data and 0 <= index < len(data["actions"]):
                deleted_action = data["actions"].pop(index)
                logger.info(f"Deleted action {index+1}: {deleted_action.get('type')}")
                
                with open(workflow_path, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=4)
                    
                self.load_workflow()
        except Exception as e:
            logger.error(f"Failed to delete action: {e}")

    def move_action_up(self, index):
        if index <= 0: return
        self._swap_actions(index, index - 1)
        
    def move_action_down(self, index):
        self._swap_actions(index, index + 1)
        
    def _swap_actions(self, idx1, idx2):
        workflow_path = self.current_workflow_path
        try:
            with open(workflow_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                
            if "actions" in data and 0 <= idx1 < len(data["actions"]) and 0 <= idx2 < len(data["actions"]):
                data["actions"][idx1], data["actions"][idx2] = data["actions"][idx2], data["actions"][idx1]
                
                with open(workflow_path, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=4)
                    
                self.load_workflow()
        except Exception as e:
            logger.error(f"Failed to swap actions: {e}")

    def clear_workflow(self):
        workflow_path = self.current_workflow_path
        try:
            if os.path.exists(workflow_path):
                with open(workflow_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                
                data["actions"] = []
                logger.info("Cleared all actions from workflow.")
                
                with open(workflow_path, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=4)
                    
                self.load_workflow()
        except Exception as e:
            logger.error(f"Failed to clear workflow: {e}")

    def open_add_action_dialog(self):
        dialog = ctk.CTkToplevel(self)
        dialog.title("Add Action")
        dialog.geometry("300x350")
        dialog.transient(self)
        
        # Type selection
        ctk.CTkLabel(dialog, text="Action Type:").pack(pady=5)
        type_var = ctk.StringVar(value="sleep")
        type_dropdown = ctk.CTkOptionMenu(dialog, variable=type_var, values=["sleep", "type", "run_command", "hotkey"])
        type_dropdown.pack(pady=5)
        
        # Dynamic inputs frame
        input_frame = ctk.CTkFrame(dialog, fg_color="transparent")
        input_frame.pack(pady=10, fill="both", expand=True)
        
        # Widgets that will be swapped
        val_label = ctk.CTkLabel(input_frame, text="Duration (seconds):")
        val_entry = ctk.CTkEntry(input_frame, width=200)
        val_label.pack(pady=5)
        val_entry.pack(pady=5)
        
        def on_type_change(*args):
            t = type_var.get()
            val_entry.delete(0, "end")
            if t == "sleep":
                val_label.configure(text="Duration (seconds):")
            elif t == "type":
                val_label.configure(text="Text to type:")
            elif t == "run_command":
                val_label.configure(text="Terminal Command:")
            elif t == "hotkey":
                val_label.configure(text="Keys (comma separated, e.g. cmd,c):")
                
        type_var.trace_add("write", on_type_change)
        
        def save_action():
            t = type_var.get()
            val = val_entry.get()
            
            new_action = {"type": t, "time_offset": 0.5}
            
            try:
                if t == "sleep":
                    new_action["duration"] = float(val) if val else 1.0
                elif t == "type":
                    new_action["key"] = val
                elif t == "run_command":
                    new_action["command"] = val
                    new_action["wait"] = True
                elif t == "hotkey":
                    new_action["keys"] = [k.strip() for k in val.split(",")]
                    
                workflow_path = self.current_workflow_path
                with open(workflow_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    
                if "actions" not in data:
                    data["actions"] = []
                    
                data["actions"].append(new_action)
                
                with open(workflow_path, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=4)
                    
                logger.info(f"Manually added action: {t}")
                self.load_workflow()
                dialog.destroy()
            except Exception as e:
                logger.error(f"Error adding action: {e}")
                
        ctk.CTkButton(dialog, text="Add to Workflow", command=save_action).pack(pady=20)

    def open_edit_action_dialog(self, index, action_dict):
        dialog = ctk.CTkToplevel(self)
        dialog.title(f"Edit Action {index+1}")
        dialog.geometry("300x250")
        dialog.transient(self)
        
        t = action_dict.get("type", "unknown")
        ctk.CTkLabel(dialog, text=f"Action Type: {t.upper()}").pack(pady=10)
        
        input_frame = ctk.CTkFrame(dialog, fg_color="transparent")
        input_frame.pack(pady=10, fill="both", expand=True)
        
        val_label = ctk.CTkLabel(input_frame, text="Value:")
        val_entry = ctk.CTkEntry(input_frame, width=200)
        val_label.pack(pady=5)
        val_entry.pack(pady=5)
        
        if t == "sleep":
            val_label.configure(text="Duration (seconds):")
            val_entry.insert(0, str(action_dict.get("duration", 1.0)))
        elif t == "type":
            val_label.configure(text="Text to type:")
            val_entry.insert(0, str(action_dict.get("key", "")))
        elif t == "run_command":
            val_label.configure(text="Terminal Command:")
            val_entry.insert(0, str(action_dict.get("command", "")))
        elif t == "hotkey":
            val_label.configure(text="Keys (comma separated):")
            val_entry.insert(0, ",".join(action_dict.get("keys", [])))
        elif t == "click":
            val_label.configure(text="Click coords (x,y):")
            val_entry.insert(0, f"{action_dict.get('x')},{action_dict.get('y')}")
        else:
            val_entry.configure(state="disabled")
            
        def save_edit():
            val = val_entry.get()
            try:
                if t == "sleep":
                    action_dict["duration"] = float(val) if val else 1.0
                elif t == "type":
                    action_dict["key"] = val
                elif t == "run_command":
                    action_dict["command"] = val
                elif t == "hotkey":
                    action_dict["keys"] = [k.strip() for k in val.split(",")]
                elif t == "click":
                    coords = val.split(",")
                    if len(coords) == 2:
                        action_dict["x"] = int(coords[0].strip())
                        action_dict["y"] = int(coords[1].strip())
                        
                workflow_path = self.current_workflow_path
                with open(workflow_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    
                if "actions" in data and 0 <= index < len(data["actions"]):
                    data["actions"][index] = action_dict
                    
                    with open(workflow_path, "w", encoding="utf-8") as f:
                        json.dump(data, f, indent=4)
                        
                    logger.info(f"Edited action {index+1}")
                    self.load_workflow()
                    dialog.destroy()
            except Exception as e:
                logger.error(f"Error editing action: {e}")
                
        ctk.CTkButton(dialog, text="Save Changes", command=save_edit).pack(pady=20)

    def start_recording(self):
        if not self.recording:
            logger.info(f"GUI: Starting recording to {self.file_var.get()}...")
            self.recording = True
            self.recorder = Recorder(workflow_path=self.current_workflow_path)
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
            self.status_label.configure(text=f"Status: ⏹ Saved to {self.file_var.get()}", text_color="white")
            self.record_btn.configure(state="normal")
            self.stop_btn.configure(state="disabled")
            self.play_btn.configure(state="normal")

    def playback(self):
        if not self.recording:
            logger.info("GUI: Playing back...")
            self.status_label.configure(text="Status: ▶️ Playing back...", text_color="#3498db")
            
            def run_playback():
                try:
                    player = Player(workflow_path=self.current_workflow_path)
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
