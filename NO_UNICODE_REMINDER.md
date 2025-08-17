# 🚫 NO UNICODE CHARACTERS IN BUILD SCRIPTS! 

## CRITICAL REMINDER FOR GITHUB ACTIONS CI

The GitHub Actions build environment uses Windows cp1252 encoding which **CANNOT HANDLE UNICODE CHARACTERS**.

### ❌ NEVER USE THESE IN PYTHON PRINT STATEMENTS:
- Checkmarks: ✓ ✅ ❌ ✗
- Arrows: → ← ↑ ↓ ► ◄ 
- Symbols: ● ○ ★ ☆ ♦ ♥ ♠ ♣ ⚠️
- Emojis: 🎯 🚀 📊 🔍 🎉 ⭐ 💡 🔧 ⚡ 🛡️ 📝 🔥

### ✅ USE THESE ASCII ALTERNATIVES INSTEAD:
- `[OK]` instead of ✓
- `[SKIP]` instead of ✗  
- `[ERROR]` instead of ❌
- `[SUCCESS]` instead of ✅
- `[WARNING]` instead of ⚠️
- `[INFO]` instead of ℹ️
- `-->` instead of →
- Simple words instead of emojis

## FILES TO WATCH:
- `build_nuitka.py` (MOST IMPORTANT - causes build failures)
- `screenalert.py` 
- Any Python file that prints to console during CI

## THE ERROR LOOKS LIKE:
```
UnicodeEncodeError: 'charmap' codec can't encode character '\u2713' in position 8: character maps to <undefined>
```

**This file itself has Unicode characters as examples only - they should NOT be used in code!**
