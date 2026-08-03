import os
import glob
import time
import shutil
from typing import List, Dict

from ..utils.config import WORKSPACE_DIR
from ..utils.logger import get_logger

logger = get_logger(__name__)

VERSIONS_DIR = os.path.join(WORKSPACE_DIR, ".versions")

def _init():
    if not os.path.exists(VERSIONS_DIR):
        try:
            os.makedirs(VERSIONS_DIR)
        except Exception:
            pass

def commit_version(filepath: str):
    """Save a snapshot of the workflow file."""
    _init()
    if not os.path.exists(filepath):
        return
        
    filename = os.path.basename(filepath)
    if not filename.endswith(".json"): return
    if filename in ("variables.json", "run_history.json", "schedules.json"): return
    
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    name, ext = os.path.splitext(filename)
    ver_name = f"{name}__{timestamp}{ext}"
    ver_path = os.path.join(VERSIONS_DIR, ver_name)
    
    try:
        shutil.copy2(filepath, ver_path)
        logger.debug(f"Committed version: {ver_name}")
        
        # Keep only last 50 versions per file
        pattern = os.path.join(VERSIONS_DIR, f"{name}__*{ext}")
        versions = sorted(glob.glob(pattern))
        if len(versions) > 50:
            for old in versions[:-50]:
                os.remove(old)
    except Exception as e:
        logger.error(f"Error committing version for {filename}: {e}")

def get_versions(filename: str) -> List[Dict[str, str]]:
    """Return a list of available versions for a given workflow filename."""
    _init()
    name, ext = os.path.splitext(filename)
    pattern = os.path.join(VERSIONS_DIR, f"{name}__*{ext}")
    versions = sorted(glob.glob(pattern), reverse=True)
    
    res = []
    for v in versions:
        vname = os.path.basename(v)
        # Extract timestamp: name__20260803_143000.json
        ts_part = vname.replace(f"{name}__", "").replace(ext, "")
        try:
            # Parse 20260803_143000 to readable format
            dt = time.strptime(ts_part, "%Y%m%d_%H%M%S")
            readable = time.strftime("%Y-%m-%d %H:%M:%S", dt)
        except:
            readable = ts_part
            
        res.append({
            "path": v,
            "time": readable
        })
    return res

def rollback_version(filepath: str, version_path: str):
    """Restore the given version path over filepath."""
    if not os.path.exists(version_path):
        raise FileNotFoundError(f"Version not found: {version_path}")
        
    # Before rollback, commit the current state just in case!
    commit_version(filepath)
    
    shutil.copy2(version_path, filepath)
    logger.info(f"Rolled back {os.path.basename(filepath)} to {os.path.basename(version_path)}")
