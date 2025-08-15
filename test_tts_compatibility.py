#!/usr/bin/env python3
"""
TTS Compatibility Test Script for ScreenAlert
Tests all TTS methods to verify functionality in both script and compiled versions
"""

import platform
import sys
import os

def test_tts_methods():
    """Test all available TTS methods"""
    
    test_message = "Testing ScreenAlert TTS functionality"
    print(f"Testing TTS on {platform.system()} with message: '{test_message}'")
    print("=" * 60)
    
    if platform.system() == "Windows":
        
        # Test 1: Windows SAPI via win32com
        print("\n[TEST 1] Windows SAPI via win32com...")
        try:
            import win32com.client
            speaker = win32com.client.Dispatch("SAPI.SpVoice")
            speaker.Speak(test_message)
            print("✅ Windows SAPI (win32com) - SUCCESS")
        except Exception as e:
            print(f"❌ Windows SAPI (win32com) - FAILED: {e}")
        
        # Test 2: Windows SAPI via PowerShell
        print("\n[TEST 2] Windows SAPI via PowerShell...")
        try:
            import subprocess
            
            escaped_message = test_message.replace("'", "''")
            ps_cmd = f"""
Add-Type -AssemblyName System.Speech
$synth = New-Object System.Speech.Synthesis.SpeechSynthesizer
$synth.Speak('{escaped_message}')
"""
            
            result = subprocess.run([
                'powershell', '-Command', ps_cmd
            ], capture_output=True, text=True, timeout=10)
            
            if result.returncode == 0:
                print("✅ PowerShell SAPI - SUCCESS")
            else:
                print(f"❌ PowerShell SAPI - FAILED: {result.stderr}")
                
        except Exception as e:
            print(f"❌ PowerShell SAPI - FAILED: {e}")
        
        # Test 3: pyttsx3
        print("\n[TEST 3] pyttsx3...")
        try:
            import pyttsx3
            engine = pyttsx3.init()
            engine.say(test_message)
            engine.runAndWait()
            print("✅ pyttsx3 - SUCCESS")
        except Exception as e:
            print(f"❌ pyttsx3 - FAILED: {e}")
    
    else:
        # Non-Windows TTS
        print(f"\n[TEST] {platform.system()} TTS...")
        try:
            if os.system(f"espeak '{test_message}' &") == 0:
                print("✅ espeak - SUCCESS")
            elif os.system(f"say '{test_message}' &") == 0:
                print("✅ say command - SUCCESS")
            else:
                print("❌ System TTS commands - FAILED")
        except Exception as e:
            print(f"❌ System TTS - FAILED: {e}")
    
    print("\n" + "=" * 60)
    print("TTS Test completed!")

def test_screenalert_tts():
    """Test the actual ScreenAlert TTS function"""
    print("\n[SCREENALERT TTS TEST]")
    print("Testing ScreenAlert's speak_tts function...")
    
    try:
        # Import the speak_tts function from screenalert
        sys.path.insert(0, '.')
        from screenalert import speak_tts
        
        speak_tts("ScreenAlert TTS test successful")
        print("✅ ScreenAlert speak_tts function - SUCCESS")
        
    except Exception as e:
        print(f"❌ ScreenAlert speak_tts function - FAILED: {e}")

if __name__ == "__main__":
    print("ScreenAlert TTS Compatibility Test")
    print("=" * 60)
    
    if len(sys.argv) > 1 and sys.argv[1] == "--screenalert-only":
        test_screenalert_tts()
    else:
        test_tts_methods()
        test_screenalert_tts()
