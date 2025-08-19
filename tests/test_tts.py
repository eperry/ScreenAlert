#!/usr/bin/env python
# -*- coding: utf-8 -*-

import json

# Read the config file
with open('screenalert_config.json', 'r') as f:
    config = json.load(f)

print('=== TTS Configuration Analysis ===')
print(f'Default TTS: {config.get("default_tts", "NOT SET")}')
print(f'Total regions: {len(config.get("regions", []))}')

for i, region in enumerate(config.get('regions', [])):
    name = region.get('name', f'Region {i+1}')
    mute_tts = region.get('mute_tts', False)
    tts_msg = region.get('tts_message', 'Uses default')
    print(f'Region {i+1} ({name}): mute_tts={mute_tts}, tts_message="{tts_msg}"')

print(f'\nFinal TTS messages that would be spoken:')
default_tts = config.get('default_tts', 'Alert {name}')
for i, region in enumerate(config.get('regions', [])):
    name = region.get('name', f'Region {i+1}')
    mute_tts = region.get('mute_tts', False)
    if not mute_tts:
        tts_message = region.get('tts_message') or default_tts.replace('{name}', name)
        print(f'  {name}: "{tts_message}"')
    else:
        print(f'  {name}: MUTED')

print('\n=== Testing TTS Function ===')

# Import and test the TTS function
import pyttsx3
import platform

def speak_tts(message):
    if not message:
        print('[DEBUG] TTS: No message provided')
        return
    
    print(f'[DEBUG] TTS: Attempting to speak: "{message}"')
    
    try:
        if platform.system() == "Windows" and pyttsx3:
            print('[DEBUG] TTS: Using pyttsx3 on Windows')
            engine = pyttsx3.init()
            
            # Set properties for better speech
            rate = engine.getProperty('rate')
            engine.setProperty('rate', max(150, rate - 50))  # Slower speech
            
            engine.say(message)
            engine.runAndWait()
            print('[DEBUG] TTS: Speech completed successfully')
            return True
            
    except Exception as e:
        print(f'[ERROR] TTS: pyttsx3 failed: {e}')
        
        # Fallback to Windows SAPI
        try:
            print('[DEBUG] TTS: Trying Windows SAPI fallback')
            import win32com.client
            speaker = win32com.client.Dispatch('SAPI.SpVoice')
            speaker.Speak(message)
            print('[DEBUG] TTS: SAPI speech completed successfully')
            return True
        except Exception as e2:
            print(f'[ERROR] TTS: SAPI fallback failed: {e2}')
    
    return False

# Test each region's TTS message
for i, region in enumerate(config.get('regions', [])):
    name = region.get('name', f'Region {i+1}')
    mute_tts = region.get('mute_tts', False)
    if not mute_tts:
        tts_message = region.get('tts_message') or default_tts.replace('{name}', name)
        print(f'\n--- Testing TTS for {name} ---')
        result = speak_tts(tts_message)
        print(f'Success: {result}')
    else:
        print(f'\n--- Skipping {name} (muted) ---')
