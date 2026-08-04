import pyautogui
import os
from typing import Optional, Tuple
from ..utils.logger import get_logger
from ..utils.config import CONFIDENCE_THRESHOLD

logger = get_logger(__name__)

def locate_template(template_path: str, confidence: float = CONFIDENCE_THRESHOLD, region: tuple = None) -> Optional[Tuple[int, int, int, int]]:
    """
    Tries to find the template image on the screen.
    Returns (left, top, width, height) if found, else None.
    """
    if not template_path or not os.path.exists(template_path):
        logger.warning(f"Template path invalid or does not exist: {template_path}")
        return None
        
    try:
        if region:
            # region is (left, top, width, height)
            box = pyautogui.locateOnScreen(template_path, confidence=confidence, region=region)
        else:
            box = pyautogui.locateOnScreen(template_path, confidence=confidence)
        if box:
            try:
                return int(box.left), int(box.top), int(box.width), int(box.height)
            except AttributeError:
                # If it's a tuple-like
                return int(box[0]), int(box[1]), int(box[2]), int(box[3])
    except Exception as e:
        logger.debug(f"Template matching failed or not found: {e}")
        
    return None
