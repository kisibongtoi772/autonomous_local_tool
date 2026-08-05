import os
import shutil
import time
import glob
from typing import List, Dict
import logging

logger = logging.getLogger(__name__)
MAX_BACKUPS = 10

def backup_workflow(workflow_path: str):
    """Creates a backup of the current workflow file before it's modified."""
    if not os.path.exists(workflow_path):
        return

    workspace_dir = os.path.dirname(workflow_path)
    filename = os.path.basename(workflow_path)
    
    backup_dir = os.path.join(workspace_dir, ".backups", filename)
    os.makedirs(backup_dir, exist_ok=True)
    
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    backup_path = os.path.join(backup_dir, f"{timestamp}.json")
    
    try:
        shutil.copy2(workflow_path, backup_path)
    except Exception as e:
        logger.error(f"Failed to backup workflow {filename}: {e}")
        return

    # Cleanup old backups
    try:
        backups = sorted(glob.glob(os.path.join(backup_dir, "*.json")))
        if len(backups) > MAX_BACKUPS:
            for old_backup in backups[:-MAX_BACKUPS]:
                os.remove(old_backup)
    except Exception as e:
        logger.error(f"Failed to cleanup old backups for {filename}: {e}")


def get_backups(workflow_path: str) -> List[Dict]:
    """Returns a list of available backups for a given workflow file."""
    workspace_dir = os.path.dirname(workflow_path)
    filename = os.path.basename(workflow_path)
    
    backup_dir = os.path.join(workspace_dir, ".backups", filename)
    if not os.path.exists(backup_dir):
        return []
        
    backups = []
    for filepath in sorted(glob.glob(os.path.join(backup_dir, "*.json")), reverse=True):
        basename = os.path.basename(filepath)
        timestamp = basename.replace(".json", "")
        try:
            # Parse YYYYMMDD_HHMMSS
            struct_time = time.strptime(timestamp, "%Y%m%d_%H%M%S")
            formatted_time = time.strftime("%Y-%m-%d %H:%M:%S", struct_time)
        except ValueError:
            formatted_time = timestamp
            
        backups.append({
            "path": filepath,
            "filename": basename,
            "display_time": formatted_time
        })
        
    return backups


def restore_backup(workflow_path: str, backup_path: str) -> bool:
    """Restores a backup to the workflow path."""
    if not os.path.exists(backup_path):
        return False
        
    try:
        shutil.copy2(backup_path, workflow_path)
        return True
    except Exception as e:
        logger.error(f"Failed to restore backup from {backup_path}: {e}")
        return False
