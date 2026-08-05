import customtkinter as ctk
from typing import List, Callable, Tuple
import logging

logger = logging.getLogger(__name__)

class SpotlightPalette(ctk.CTkToplevel):
    def __init__(self, parent, commands: List[Tuple[str, str, Callable]]):
        super().__init__(parent)
        self.title("Spotlight Command Palette")
        
        # Center the window
        window_width = 700
        window_height = 500
        
        parent.update_idletasks()
        try:
            px = parent.winfo_rootx() + (parent.winfo_width() // 2) - (window_width // 2)
            py = parent.winfo_rooty() + (parent.winfo_height() // 2) - (window_height // 2)
            self.geometry(f"{window_width}x{window_height}+{px}+{py}")
        except:
            self.geometry(f"{window_width}x{window_height}")
            
        self.attributes("-topmost", True)
        self.transient(parent)
        self.focus_force()
        self.configure(fg_color="#0A0C10")
        
        self.all_commands = commands
        self.filtered_commands = list(commands)
        self.selected_index = 0
        self.item_widgets = []
        
        # UI Setup
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)
        
        self.search_var = ctk.StringVar()
        self.search_var.trace_add("write", self.on_search)
        
        self.search_entry = ctk.CTkEntry(
            self, textvariable=self.search_var, 
            font=ctk.CTkFont("SF Pro Display", 24),
            placeholder_text="Search files, actions, commands... (Type to filter)",
            height=60, corner_radius=8,
            fg_color="#181C22", border_color="#3A3F4A", text_color="white",
            border_width=2
        )
        self.search_entry.grid(row=0, column=0, sticky="ew", padx=16, pady=16)
        
        self.list_frame = ctk.CTkScrollableFrame(self, fg_color="#111318", corner_radius=8)
        self.list_frame.grid(row=1, column=0, sticky="nsew", padx=16, pady=(0, 16))
        
        # Keybindings
        self.search_entry.bind("<Return>", self.on_enter)
        self.search_entry.bind("<Up>", self.on_up)
        self.search_entry.bind("<Down>", self.on_down)
        self.bind("<Escape>", lambda e: self.destroy())
        
        self.render_list()
        self.search_entry.focus()
        
    def on_search(self, *args):
        query = self.search_var.get().lower().strip()
        if not query:
            self.filtered_commands = list(self.all_commands)
        else:
            self.filtered_commands = [
                cmd for cmd in self.all_commands
                if query in cmd[0].lower() or query in cmd[1].lower()
            ]
        self.selected_index = 0
        self.render_list()
        
    def render_list(self):
        for w in self.item_widgets:
            w.destroy()
        self.item_widgets.clear()
        
        if not self.filtered_commands:
            lbl = ctk.CTkLabel(self.list_frame, text="No matches found.", text_color="gray", font=ctk.CTkFont("SF Pro Text", 14))
            lbl.pack(pady=20)
            self.item_widgets.append(lbl)
            return
            
        for i, cmd in enumerate(self.filtered_commands[:100]): # Limit to 100
            category, title, callback = cmd
            
            is_sel = (i == self.selected_index)
            bg_color = "#2563EB" if is_sel else "#181C22"
            
            row = ctk.CTkFrame(self.list_frame, fg_color=bg_color, corner_radius=6, height=45)
            row.pack(fill="x", pady=3, padx=4)
            row.pack_propagate(False)
            
            cat_lbl = ctk.CTkLabel(row, text=f"[{category}]", text_color="#A1A1AA" if not is_sel else "#D1D5DB", font=ctk.CTkFont("SF Pro Text", 12, "bold"))
            cat_lbl.pack(side="left", padx=(12, 8))
            
            title_lbl = ctk.CTkLabel(row, text=title, text_color="white", font=ctk.CTkFont("SF Pro Text", 15))
            title_lbl.pack(side="left", padx=4)
            
            # Click to select and run
            def make_handler(idx):
                def handler(e):
                    self.selected_index = idx
                    self.on_enter()
                return handler
                
            for w in (row, cat_lbl, title_lbl):
                w.bind("<Button-1>", make_handler(i))
                
            self.item_widgets.append(row)
            
        # Ensure scroll visibility if possible
        if self.selected_index > 0:
            try:
                self.list_frame._parent_canvas.yview_moveto(self.selected_index / max(1, len(self.filtered_commands)))
            except: pass

    def on_up(self, e):
        if self.selected_index > 0:
            self.selected_index -= 1
            self.render_list()
        return "break"
        
    def on_down(self, e):
        if self.selected_index < len(self.filtered_commands) - 1 and self.selected_index < 99:
            self.selected_index += 1
            self.render_list()
        return "break"
        
    def on_enter(self, e=None):
        if 0 <= self.selected_index < len(self.filtered_commands):
            cmd = self.filtered_commands[self.selected_index]
            callback = cmd[2]
            self.destroy() 
            self.master.after(50, callback) 
