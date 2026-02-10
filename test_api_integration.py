#!/usr/bin/env python3
"""API Integration Test - validates all component interfaces match"""

import sys
from pathlib import Path

# Add workspace to path
sys.path.insert(0, str(Path(__file__).parent))

print("=" * 70)
print("API Integration Test - ScreenAlert v2.0")
print("=" * 70)

errors = []

# Test 1: ConfigManager API
print("\n[1] Testing ConfigManager API...")
try:
    from screenalert_core.core.config_manager import ConfigManager
    import tempfile
    import json
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        config_path = f.name
        json.dump({"thumbnails": [], "app": {}}, f)
    
    config = ConfigManager(config_path)
    
    # Test add_thumbnail signature
    thumbnail_id = config.add_thumbnail(window_title="Test", window_hwnd=12345)
    assert thumbnail_id is not None, "add_thumbnail should return thumbnail_id"
    
    # Test get methods
    assert hasattr(config, 'get_thumbnail'), "Missing get_thumbnail method"
    assert hasattr(config, 'get_all_thumbnails'), "Missing get_all_thumbnails method"
    assert hasattr(config, 'add_region_to_thumbnail'), "Missing add_region_to_thumbnail method"
    assert hasattr(config, 'remove_thumbnail'), "Missing remove_thumbnail method"
    
    # Test settings methods
    assert hasattr(config, 'get_refresh_rate'), "Missing get_refresh_rate"
    assert hasattr(config, 'set_refresh_rate'), "Missing set_refresh_rate"
    assert hasattr(config, 'get_opacity'), "Missing get_opacity"
    assert hasattr(config, 'set_opacity'), "Missing set_opacity"
    assert hasattr(config, 'get_always_on_top'), "Missing get_always_on_top"
    assert hasattr(config, 'set_always_on_top'), "Missing set_always_on_top"
    assert hasattr(config, 'get_verbose_logging'), "Missing get_verbose_logging"
    assert hasattr(config, 'set_verbose_logging'), "Missing set_verbose_logging"
    
    # Test region addition
    region_dict = {
        "name": "Test Region",
        "rect": [10, 20, 100, 100],
        "alert_threshold": 0.99,
        "enabled": True
    }
    region_id = config.add_region_to_thumbnail(thumbnail_id, region_dict)
    assert region_id is not None, "add_region_to_thumbnail should return region_id"
    
    # Verify thumbnail structure
    thumbnail = config.get_thumbnail(thumbnail_id)
    assert thumbnail is not None, "get_thumbnail should return thumbnail"
    assert 'id' in thumbnail, "Thumbnail should have 'id' field"
    assert 'window_hwnd' in thumbnail, "Thumbnail should have 'window_hwnd' field"
    assert 'window_title' in thumbnail, "Thumbnail should have 'window_title' field"
    assert 'monitored_regions' in thumbnail, "Thumbnail should have 'monitored_regions' field"
    
    Path(config_path).unlink(missing_ok=True)
    print("  [PASS] ConfigManager API validated")
    
except AssertionError as e:
    errors.append(f"ConfigManager: {e}")
    print(f"  [FAIL] {e}")
except Exception as e:
    errors.append(f"ConfigManager: {e}")
    print(f"  [FAIL] {e}")

# Test 2: ScreenAlertEngine API
print("\n[2] Testing ScreenAlertEngine API...")
try:
    from screenalert_core.screening_engine import ScreenAlertEngine
    
    engine = ScreenAlertEngine()
    
    # Test method signatures
    assert hasattr(engine, 'add_thumbnail'), "Missing add_thumbnail method"
    assert hasattr(engine, 'remove_thumbnail'), "Missing remove_thumbnail method"
    assert hasattr(engine, 'add_region'), "Missing add_region method"
    assert hasattr(engine, 'start'), "Missing start method"
    assert hasattr(engine, 'stop'), "Missing stop method"
    assert hasattr(engine, 'set_paused'), "Missing set_paused method"
    
    # Test add_thumbnail signature (window_title, window_hwnd)
    import inspect
    sig = inspect.signature(engine.add_thumbnail)
    params = list(sig.parameters.keys())
    assert 'window_title' in params, "add_thumbnail missing window_title parameter"
    assert 'window_hwnd' in params, "add_thumbnail missing window_hwnd parameter"
    
    # Test add_region signature (thumbnail_id, name, rect, alert_threshold)
    sig = inspect.signature(engine.add_region)
    params = list(sig.parameters.keys())
    assert 'thumbnail_id' in params, "add_region missing thumbnail_id parameter"
    assert 'name' in params, "add_region missing name parameter"
    assert 'rect' in params, "add_region missing rect parameter"
    
    # Test callbacks exist
    assert hasattr(engine, 'on_alert'), "Missing on_alert callback"
    assert hasattr(engine, 'on_region_change'), "Missing on_region_change callback"
    assert hasattr(engine, 'on_window_lost'), "Missing on_window_lost callback"
    
    print("  [PASS] ScreenAlertEngine API validated")
    
except AssertionError as e:
    errors.append(f"ScreenAlertEngine: {e}")
    print(f"  [FAIL] {e}")
except Exception as e:
    errors.append(f"ScreenAlertEngine: {e}")
    print(f"  [FAIL] {e}")

# Test 3: Main Window integration
print("\n[3] Testing MainWindow integration...")
try:
    from screenalert_core.ui.main_window import ScreenAlertMainWindow
    from screenalert_core.screening_engine import ScreenAlertEngine
    
    # Check that MainWindow correctly references config methods
    import inspect
    source = inspect.getsource(ScreenAlertMainWindow)
    
    # Should use get_all_thumbnails, not get_thumbnails
    if 'get_thumbnails()' in source and 'get_all_thumbnails()' not in source:
        raise AssertionError("MainWindow should use config.get_all_thumbnails() not get_thumbnails()")
    
    # Should use window_hwnd, not hwnd
    if "thumbnail['hwnd']" in source:
        raise AssertionError("MainWindow should use thumbnail['window_hwnd'] not thumbnail['hwnd']")
    
    # Should use window_title, not title
    if "thumbnail.get('title'" in source:
        raise AssertionError("MainWindow should use thumbnail['window_title'] not thumbnail['title']")
    
    print("  [PASS] MainWindow integration validated")
    
except AssertionError as e:
    errors.append(f"MainWindow: {e}")
    print(f"  [FAIL] {e}")
except Exception as e:
    errors.append(f"MainWindow: {e}")
    print(f"  [FAIL] {e}")

# Test 4: Dialog APIs
print("\n[4] Testing Dialog APIs...")
try:
    from screenalert_core.ui.window_selector_dialog import WindowSelectorDialog
    from screenalert_core.ui.region_editor_dialog import RegionEditorDialog
    from screenalert_core.ui.settings_dialog import SettingsDialog
    
    # Check signatures
    import inspect
    
    # WindowSelectorDialog(parent, window_manager)
    sig = inspect.signature(WindowSelectorDialog.__init__)
    params = list(sig.parameters.keys())
    assert 'window_manager' in params, "WindowSelectorDialog missing window_manager parameter"
    
    # RegionEditorDialog(parent, window_image)
    sig = inspect.signature(RegionEditorDialog.__init__)
    params = list(sig.parameters.keys())
    assert 'window_image' in params, "RegionEditorDialog missing window_image parameter"
    
    # SettingsDialog(parent, config)
    sig = inspect.signature(SettingsDialog.__init__)
    params = list(sig.parameters.keys())
    assert 'config' in params, "SettingsDialog missing config parameter"
    
    print("  [PASS] Dialog APIs validated")
    
except AssertionError as e:
    errors.append(f"Dialogs: {e}")
    print(f"  [FAIL] {e}")
except Exception as e:
    errors.append(f"Dialogs: {e}")
    print(f"  [FAIL] {e}")

# Summary
print("\n" + "=" * 70)
print("SUMMARY")
print("=" * 70)

if errors:
    print(f"\n[FAILED] {len(errors)} API integration issues found:\n")
    for error in errors:
        print(f"  • {error}")
    sys.exit(1)
else:
    print("\n[SUCCESS] All API integrations validated successfully!")
    print("\nKey findings:")
    print("  • ConfigManager: add_thumbnail(window_title, window_hwnd)")
    print("  • ConfigManager: get_all_thumbnails() returns list of dicts")
    print("  • Thumbnail dict keys: 'id', 'window_hwnd', 'window_title', 'monitored_regions'")
    print("  • ScreenAlertEngine: add_region(thumbnail_id, name, rect)")
    print("  • Region rect format: [x, y, width, height] or (x, y, width, height)")
    print("  • All callbacks: (thumbnail_id, ...) - use IDs not hwnds")
    sys.exit(0)
