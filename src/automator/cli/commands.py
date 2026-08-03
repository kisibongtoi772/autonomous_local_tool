import sys
import time
from pynput import keyboard
from ..core.recorder import Recorder
from ..core.player import Player
from ..utils.logger import get_logger

logger = get_logger(__name__)

recorder = None
recording = False

def on_press(key):
    global recorder, recording
    
    try:
        if key == keyboard.Key.f9:
            if not recording:
                logger.info("[Hotkey] F9 pressed: Starting recording...")
                recording = True
                recorder = Recorder()
                recorder.start()
            else:
                logger.warning("[Hotkey] Already recording!")
                
        elif key == keyboard.Key.f10:
            if recording and recorder:
                logger.info("[Hotkey] F10 pressed: Stopping recording...")
                recorder.stop()
                recording = False
            else:
                logger.warning("[Hotkey] Not currently recording.")
                
        elif key == keyboard.Key.f11:
            if not recording:
                logger.info("[Hotkey] F11 pressed: Playing back...")
                player = Player()
                player.play()
            else:
                logger.warning("[Hotkey] Cannot play while recording!")
                
    except Exception as e:
        logger.error(f"Error handling hotkey: {e}")

def run_cli():
    logger.info("=========================================")
    logger.info("         Desktop Automator CLI           ")
    logger.info("=========================================")
    logger.info(" Record Press F9 to start recording.")
    logger.info(" Stop  Press F10 to stop recording.")
    logger.info(" Play  Press F11 to playback the last recording.")
    logger.info(" Error: Press Ctrl+C in this terminal to exit.")
    logger.info("=========================================")
    
    listener = keyboard.Listener(on_press=on_press)
    listener.start()
    
    try:
        while True:
            time.sleep(0.1)
    except KeyboardInterrupt:
        logger.info("Exiting...")
        sys.exit(0)
