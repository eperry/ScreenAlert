"""Alert system for sounds and text-to-speech"""

import logging
import platform
import queue
import subprocess
import threading
from typing import Optional

logger = logging.getLogger(__name__)

# Platform-specific imports
if platform.system() == "Windows":
    try:
        import pyttsx3
    except ImportError:
        pyttsx3 = None
    
    try:
        import pygame
        pygame.mixer.init()
    except:
        pygame = None
else:
    pyttsx3 = None
    pygame = None


class AlertSystem:
    """Handles sound and TTS alerts"""
    
    def __init__(self):
        """Initialize alert system"""
        self.tts_engine = None
        self.pygame_initialized = False
        self._tts_queue: "queue.Queue[Optional[str]]" = queue.Queue()
        self._tts_stop = threading.Event()
        self._tts_thread: Optional[threading.Thread] = None
        
        # Try to initialize pygame mixer
        if pygame:
            try:
                pygame.mixer.init()
                self.pygame_initialized = True
            except Exception as e:
                logger.warning(f"Failed to initialize pygame mixer: {e}")
        
        # Initialize TTS engine
        if pyttsx3:
            try:
                # Probe engine availability once.
                probe_engine = pyttsx3.init()
                probe_engine.setProperty('rate', 150)
                probe_engine.setProperty('volume', 0.9)
                self.tts_engine = probe_engine
                self._tts_thread = threading.Thread(target=self._tts_worker, daemon=True)
                self._tts_thread.start()
            except Exception as e:
                logger.warning(f"Failed to initialize TTS: {e}")
                self.tts_engine = None

    def _tts_worker(self) -> None:
        """Background worker: serializes TTS and uses fresh engine per message."""
        while not self._tts_stop.is_set():
            try:
                message = self._tts_queue.get(timeout=0.2)
            except queue.Empty:
                continue

            if message is None:
                continue

            try:
                engine = pyttsx3.init()
                engine.setProperty('rate', 150)
                engine.setProperty('volume', 0.9)
                engine.say(message)
                engine.runAndWait()
                logger.info(f"Spoke TTS: {message}")
            except Exception as err:
                logger.error(f"Error speaking: {err}")
    
    def play_sound(self, sound_file: str) -> bool:
        """Play a sound file
        
        Args:
            sound_file: Path to sound file
        
        Returns:
            True if successful
        """
        if not sound_file:
            return False
        
        if not self.pygame_initialized:
            logger.warning("Pygame mixer not initialized, cannot play sound")
            return False
        
        try:
            import os
            if not os.path.exists(sound_file):
                logger.warning(f"Sound file not found: {sound_file}")
                return False
            
            pygame.mixer.music.load(sound_file)
            pygame.mixer.music.play()
            logger.debug(f"Playing sound: {sound_file}")
            return True
        
        except Exception as e:
            logger.error(f"Error playing sound {sound_file}: {e}")
            return False
    
    def speak_tts(self, message: str) -> bool:
        """Speak text via TTS
        
        Args:
            message: Text to speak
        
        Returns:
            True if successful
        """
        if not message:
            return False

        # Windows-specific robust TTS path: isolated PowerShell process per utterance.
        # This avoids pyttsx3/SAPI run-loop deadlocks that can suppress repeated alerts.
        if platform.system() == "Windows":
            try:
                escaped = message.replace("'", "''")
                ps_cmd = (
                    "Add-Type -AssemblyName System.Speech; "
                    "$s = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
                    "$s.Rate = 0; $s.Volume = 100; "
                    f"$s.Speak('{escaped}')"
                )
                creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
                subprocess.Popen(
                    ["powershell", "-NoProfile", "-Command", ps_cmd],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    creationflags=creationflags,
                )
                logger.info(f"Queued TTS: {message}")
                return True
            except Exception as e:
                logger.error(f"Error speaking via PowerShell TTS: {e}")
                return False
        
        if not self.tts_engine:
            logger.warning("TTS engine not initialized, cannot speak")
            return False
        
        try:
            self._tts_queue.put_nowait(message)
            logger.info(f"Queued TTS: {message}")
            return True
        
        except Exception as e:
            logger.error(f"Error speaking: {e}")
            return False
    
    def play_alert(self, sound_file: Optional[str] = None, 
                  tts_message: Optional[str] = None) -> bool:
        """Play alert with sound and/or TTS
        
        Returns:
            True if at least one alert was played
        """
        played = False
        
        if sound_file:
            played = self.play_sound(sound_file) or played
        else:
            # Default system beep when no sound file configured
            try:
                import winsound
                winsound.PlaySound("SystemHand", winsound.SND_ALIAS | winsound.SND_ASYNC)
                played = True
            except Exception as e:
                logger.debug(f"Fallback system sound failed: {e}")
        
        if tts_message:
            played = self.speak_tts(tts_message) or played
        
        return played
    
    def stop_audio(self) -> None:
        """Stop all audio playback"""
        if self.pygame_initialized:
            try:
                pygame.mixer.music.stop()
            except:
                pass
    
    def cleanup(self) -> None:
        """Clean up resources"""
        self._tts_stop.set()
        try:
            self._tts_queue.put_nowait(None)
        except Exception:
            pass
        if self._tts_thread and self._tts_thread.is_alive():
            try:
                self._tts_thread.join(timeout=1.0)
            except Exception:
                pass

        self.stop_audio()
        if self.tts_engine:
            try:
                self.tts_engine.setProperty('_eng', None)
            except:
                pass
