#!/usr/bin/env python3
"""Quick test of UI module imports"""

try:
    print("Testing UI module imports...")
    
    from screenalert_core.ui.window_selector_dialog import WindowSelectorDialog
    print("✓ WindowSelectorDialog imported")
    
    from screenalert_core.ui.region_editor_dialog import RegionEditorDialog
    print("✓ RegionEditorDialog imported")
    
    from screenalert_core.ui.settings_dialog import SettingsDialog
    print("✓ SettingsDialog imported")
    
    from screenalert_core.ui.main_window import ScreenAlertMainWindow
    print("✓ ScreenAlertMainWindow imported")
    
    print("\n✓✓✓ All UI modules imported successfully! ✓✓✓")
    
except Exception as e:
    print(f"✗ Import error: {e}")
    import traceback
    traceback.print_exc()
    exit(1)
