"""
Variable Manager — resolves {{variable_name}} placeholders in workflow actions.
Variables are stored in workspace/variables.json as a flat key-value dictionary.
"""
import json
import re
import os
from typing import Any, Dict
from ..utils.config import VARIABLES_FILE
from ..utils.logger import get_logger

logger = get_logger(__name__)

class VariableManager:
    def __init__(self, variables_file: str = VARIABLES_FILE):
        self.variables_file = variables_file
        self.variables: Dict[str, str] = {}
        self.load()

    def load(self):
        if os.path.exists(self.variables_file):
            try:
                with open(self.variables_file, "r", encoding="utf-8") as f:
                    self.variables = json.load(f)
                logger.info(f"Loaded {len(self.variables)} variable(s).")
            except Exception as e:
                logger.error(f"Failed to load variables: {e}")
                self.variables = {}
        else:
            self.variables = {}

    def save(self):
        try:
            with open(self.variables_file, "w", encoding="utf-8") as f:
                json.dump(self.variables, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Failed to save variables: {e}")

    def set(self, key: str, value: str):
        self.variables[key] = value
        self.save()

    def delete(self, key: str):
        if key in self.variables:
            del self.variables[key]
            self.save()

    def resolve(self, text: str) -> str:
        """Replace all {{key}} placeholders in text with their variable values."""
        def replacer(match):
            key = match.group(1).strip()
            
            # Built-in Dynamic Variables
            if key == "CLIPBOARD":
                import pyperclip
                return str(pyperclip.paste() or "")
            elif key == "TIME":
                import datetime
                return datetime.datetime.now().strftime("%H:%M:%S")
            elif key == "DATE":
                import datetime
                return datetime.datetime.now().strftime("%Y-%m-%d")
            elif key == "DATETIME":
                import datetime
                return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                
            if key in self.variables:
                return str(self.variables[key])
            logger.warning(f"Variable '{{{{ {key} }}}}' not found, leaving as-is.")
            return match.group(0)
        return re.sub(r"\{\{([^}]+)\}\}", replacer, text)

    def resolve_action(self, action_dict: dict) -> dict:
        """Recursively resolve variables in an action dictionary."""
        import copy
        resolved = copy.deepcopy(action_dict)
        for key, value in resolved.items():
            if isinstance(value, str):
                resolved[key] = self.resolve(value)
            elif isinstance(value, list):
                resolved[key] = [
                    self.resolve_action(item) if isinstance(item, dict) else item
                    for item in value
                ]
        return resolved
