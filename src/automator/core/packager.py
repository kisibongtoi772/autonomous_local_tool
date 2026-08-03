import os
import json
import zipfile
import shutil
import tempfile
from typing import List

from ..utils.config import WORKSPACE_DIR, TEMPLATES_DIR
from ..utils.logger import get_logger

logger = get_logger(__name__)

def _extract_templates_from_actions(actions: List[dict]) -> set:
    used = set()
    for a in actions:
        if a.get("template"):
            used.add(a["template"])
        if a.get("template_image"):
            used.add(os.path.basename(a["template_image"]))
        if a.get("condition_template"):
            used.add(a["condition_template"])
        if "actions" in a and isinstance(a["actions"], list):
            used.update(_extract_templates_from_actions(a["actions"]))
    return used

def export_workflow(workflow_filename: str, export_zip_path: str) -> bool:
    """Package a workflow and its templates into a zip file."""
    try:
        wf_path = os.path.join(WORKSPACE_DIR, workflow_filename)
        if not os.path.exists(wf_path):
            raise FileNotFoundError(f"Workflow not found: {wf_path}")
            
        with open(wf_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            
        templates = _extract_templates_from_actions(data.get("actions", []))
        
        with tempfile.TemporaryDirectory() as tmpdir:
            # Copy workflow file
            shutil.copy2(wf_path, os.path.join(tmpdir, workflow_filename))
            
            # Copy templates
            for tmpl in templates:
                src = os.path.join(TEMPLATES_DIR, tmpl)
                if os.path.exists(src):
                    shutil.copy2(src, os.path.join(tmpdir, tmpl))
                    
            # Create Zip
            # Ensure export_zip_path ends with .zip
            if not export_zip_path.endswith(".zip"):
                export_zip_path += ".zip"
                
            with zipfile.ZipFile(export_zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
                for root, _, files in os.walk(tmpdir):
                    for file in files:
                        file_path = os.path.join(root, file)
                        arcname = os.path.relpath(file_path, tmpdir)
                        zf.write(file_path, arcname)
                        
        logger.info(f"Exported workflow {workflow_filename} to {export_zip_path}")
        return True
    except Exception as e:
        logger.error(f"Failed to export workflow: {e}")
        return False

def import_workflow(zip_path: str) -> bool:
    """Extract a workflow zip, placing json in workspace and images in templates."""
    try:
        with zipfile.ZipFile(zip_path, 'r') as zf:
            with tempfile.TemporaryDirectory() as tmpdir:
                zf.extractall(tmpdir)
                
                # Move files
                for file in os.listdir(tmpdir):
                    src = os.path.join(tmpdir, file)
                    if file.endswith(".json"):
                        # Handle conflicts? Just overwrite for now
                        shutil.copy2(src, os.path.join(WORKSPACE_DIR, file))
                        logger.info(f"Imported workflow file: {file}")
                    elif file.lower().endswith(('.png', '.jpg', '.jpeg')):
                        shutil.copy2(src, os.path.join(TEMPLATES_DIR, file))
                        logger.info(f"Imported template image: {file}")
                        
        logger.info(f"Successfully imported {os.path.basename(zip_path)}")
        return True
    except Exception as e:
        logger.error(f"Failed to import workflow: {e}")
        return False
