import os
import json
import shutil
from typing import List, Tuple

from ..utils.config import WORKSPACE_DIR, TEMPLATES_DIR
from ..utils.logger import get_logger

logger = get_logger(__name__)

def get_used_templates() -> set:
    """Scan all .json workflows in WORKSPACE_DIR and return a set of used template basenames."""
    used = set()
    for fname in os.listdir(WORKSPACE_DIR):
        if not fname.endswith(".json"): continue
        if fname in ("variables.json", "run_history.json", "schedules.json"): continue
        
        path = os.path.join(WORKSPACE_DIR, fname)
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
                
            def scan_actions(actions: List[dict]):
                for a in actions:
                    if a.get("template"):
                        used.add(a["template"])
                    if a.get("template_image"):
                        used.add(os.path.basename(a["template_image"]))
                    if a.get("condition_template"):
                        used.add(a["condition_template"])
                    if "actions" in a and isinstance(a["actions"], list):
                        scan_actions(a["actions"])
            
            scan_actions(data.get("actions", []))
        except Exception as e:
            logger.error(f"Error scanning {fname} for templates: {e}")
            
    return used

def get_orphan_templates() -> List[str]:
    """Return a list of absolute paths to orphaned template images."""
    used = get_used_templates()
    orphans = []
    
    if not os.path.exists(TEMPLATES_DIR):
        return orphans
        
    for fname in os.listdir(TEMPLATES_DIR):
        if fname.lower().endswith(('.png', '.jpg', '.jpeg')):
            if fname not in used:
                orphans.append(os.path.join(TEMPLATES_DIR, fname))
                
    return orphans

def perform_cleanup() -> Tuple[int, int]:
    """Delete orphan templates and return (count, bytes_freed)."""
    orphans = get_orphan_templates()
    bytes_freed = 0
    count = 0
    
    for path in orphans:
        try:
            size = os.path.getsize(path)
            os.remove(path)
            bytes_freed += size
            count += 1
            logger.info(f"Cleaned up orphan template: {os.path.basename(path)}")
        except Exception as e:
            logger.error(f"Failed to delete {path}: {e}")
            
    return count, bytes_freed
