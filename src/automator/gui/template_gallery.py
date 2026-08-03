import os
import glob
from typing import Callable
import tkinter as tk
import customtkinter as ctk
from PIL import Image

from ..utils.config import T, TEMPLATES_DIR, WORKSPACE_DIR
from ..utils.logger import get_logger
from ..models.workflow import load_json

logger = get_logger(__name__)

def _get_all_workflow_files():
    files = glob.glob(os.path.join(WORKSPACE_DIR, "*.json"))
    return [os.path.basename(f) for f in files]

def _find_used_templates():
    usage_map = {}
    for wf in _get_all_workflow_files():
        path = os.path.join(WORKSPACE_DIR, wf)
        data = load_json(path, {})
        actions = data.get("actions", [])
        
        def _scan_actions(acts):
            for a in acts:
                # Keys that might hold a template filename
                for key in ["template", "template_image", "image"]:
                    val = a.get(key)
                    if val and isinstance(val, str) and (val.endswith(".png") or val.endswith(".jpg")):
                        # normalize
                        bn = os.path.basename(val)
                        if bn not in usage_map:
                            usage_map[bn] = set()
                        usage_map[bn].add(wf)
                
                # Recurse for groups/if/while
                for child_key in ["actions", "true_actions", "false_actions"]:
                    if child_key in a and isinstance(a[child_key], list):
                        _scan_actions(a[child_key])
                        
        _scan_actions(actions)
    return usage_map

class TemplateGallery(ctk.CTkToplevel):
    def __init__(self, parent, on_close: Callable = None):
        super().__init__(parent)
        self.on_close = on_close
        
        self.title("Template Gallery & Cleanup Manager")
        self.geometry("600x700")
        self.configure(fg_color=T["bg"])
        self.transient(parent)
        
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)
        
        # Header
        hdr = ctk.CTkFrame(self, fg_color="transparent")
        hdr.grid(row=0, column=0, sticky="ew", padx=20, pady=20)
        
        ctk.CTkLabel(
            hdr, text="Template Gallery", 
            font=ctk.CTkFont("SF Pro Display", 20, "bold"), text_color=T["text"]
        ).pack(side="left")
        
        ctk.CTkButton(
            hdr, text="Refresh 🔄", width=100,
            fg_color="transparent", border_width=1, border_color=T["border"],
            hover_color=T["hover"], text_color=T["text"],
            command=self._load_data
        ).pack(side="right")
        
        # List
        self.scroll = ctk.CTkScrollableFrame(self, fg_color=T["surface"], corner_radius=8)
        self.scroll.grid(row=1, column=0, sticky="nsew", padx=20, pady=(0, 20))
        
        self._load_data()
        
    def _load_data(self):
        for w in self.scroll.winfo_children():
            w.destroy()
            
        usage_map = _find_used_templates()
        
        if not os.path.exists(TEMPLATES_DIR):
            os.makedirs(TEMPLATES_DIR, exist_ok=True)
            
        all_templates = [f for f in os.listdir(TEMPLATES_DIR) if f.lower().endswith(('.png', '.jpg'))]
        all_templates.sort()
        
        if not all_templates:
            ctk.CTkLabel(
                self.scroll, text="No templates found in workspace/templates/.",
                text_color=T["dim"], font=ctk.CTkFont("SF Pro Text", 13)
            ).pack(pady=40)
            return
            
        for tmpl in all_templates:
            used_in = usage_map.get(tmpl, set())
            self._build_row(tmpl, list(used_in))
            
    def _build_row(self, filename: str, used_in: list):
        row = ctk.CTkFrame(self.scroll, fg_color="transparent")
        row.pack(fill="x", pady=8, padx=8)
        
        # Thumbnail
        path = os.path.join(TEMPLATES_DIR, filename)
        try:
            pil_img = Image.open(path)
            pil_img.thumbnail((80, 80))
            ctk_img = ctk.CTkImage(light_image=pil_img, dark_image=pil_img, size=pil_img.size)
            lbl_img = ctk.CTkLabel(row, image=ctk_img, text="")
            lbl_img.pack(side="left", padx=(0, 16))
        except Exception as e:
            logger.error(f"Failed to load thumbnail for {filename}: {e}")
            lbl_img = ctk.CTkLabel(row, text="[Err]", text_color=T["err"])
            lbl_img.pack(side="left", padx=(0, 16))
            
        # Info
        info = ctk.CTkFrame(row, fg_color="transparent")
        info.pack(side="left", fill="both", expand=True)
        
        ctk.CTkLabel(
            info, text=filename, font=ctk.CTkFont("SF Pro Text", 14, "bold"), text_color=T["text"]
        ).pack(anchor="w")
        
        if not used_in:
            ctk.CTkLabel(
                info, text="Warning: Unused", font=ctk.CTkFont("SF Pro Text", 12), text_color="#F59E0B"
            ).pack(anchor="w")
        else:
            ctk.CTkLabel(
                info, text=f"Used in: {', '.join(used_in)}", font=ctk.CTkFont("SF Pro Text", 12), text_color=T["dim"]
            ).pack(anchor="w")
            
        # Actions
        acts = ctk.CTkFrame(row, fg_color="transparent")
        acts.pack(side="right", fill="y", padx=8)
        
        def _delete():
            try:
                os.remove(path)
                row.destroy()
                logger.info(f"Deleted template: {filename}")
            except Exception as e:
                logger.error(f"Failed to delete {filename}: {e}")
                
        if not used_in:
            ctk.CTkButton(
                acts, text="Delete", width=80, fg_color="#7F1D1D", hover_color="#991B1B",
                text_color="#FECACA", command=_delete
            ).pack(pady=4)
        else:
            ctk.CTkButton(
                acts, text="🗑 Force Delete", width=80, fg_color="transparent", 
                border_width=1, border_color="#7F1D1D", text_color="#EF4444", 
                hover_color="#450A0A", command=_delete
            ).pack(pady=4)

    def destroy(self):
        if self.on_close:
            self.on_close()
        super().destroy()
