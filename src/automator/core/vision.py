import pyautogui
import os
from typing import Optional, Tuple
from ..utils.logger import get_logger
from ..utils.config import CONFIDENCE_THRESHOLD

logger = get_logger(__name__)

def locate_template(template_path: str) -> Optional[Tuple[int, int]]:
    """
    Tries to find the template image on the screen.
    Returns (x, y) coordinates if found, else None.
    """
    if not template_path or not os.path.exists(template_path):
        logger.warning(f"Template path invalid or does not exist: {template_path}")
        return None
        
    try:
        location = pyautogui.locateCenterOnScreen(template_path, confidence=CONFIDENCE_THRESHOLD)
        if location:
            # Check if location has x and y attributes (PyAutoGUI sometimes returns a Box or Point)
            try:
                return int(location.x), int(location.y)
            except AttributeError:
                # If it's a tuple-like
                return int(location[0]), int(location[1])
    except Exception as e:
        logger.debug(f"Template matching failed or not found: {e}")
        
    return None
