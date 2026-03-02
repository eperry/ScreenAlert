"""Alert system for sounds and text-to-speech"""

import logging
import platform
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
                self.tts_engine = pyttsx3.init()
                self.tts_engine.setProperty('rate', 150)  # Speed
                self.tts_engine.setProperty('volume', 0.9)  # Volume
            except Exception as e:
                logger.warning(f"Failed to initialize TTS: {e}")
                self.tts_engine = None
    
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
        
        if not self.tts_engine:
            logger.warning("TTS engine not initialized, cannot speak")
            return False
        
        try:
            self.tts_engine.say(message)
            self.tts_engine.runAndWait()
            logger.debug(f"Speaking: {message}")
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
        self.stop_audio()
        if self.tts_engine:
            try:
                self.tts_engine.setProperty('_eng', None)
            except:
                pass
