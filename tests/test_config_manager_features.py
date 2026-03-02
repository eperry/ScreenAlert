import json
from pathlib import Path

from screenalert_core.core.config_manager import ConfigManager


def test_export_import_reset_roundtrip(tmp_path: Path):
    cfg_path = tmp_path / "cfg.json"
    mgr = ConfigManager(str(cfg_path))

    mgr.set_refresh_rate(777)
    mgr.set_high_contrast(True)
    mgr.set_default_alert_threshold(0.88)
    assert mgr.save()

    export_path = tmp_path / "export.json"
    assert mgr.export_config(str(export_path))

    mgr.set_refresh_rate(999)
    mgr.save()

    assert mgr.import_config(str(export_path))
    assert mgr.get_refresh_rate() == 777
    assert mgr.get_high_contrast() is True

    assert mgr.reset_to_defaults()
    assert mgr.get_refresh_rate() != 777


def test_alert_history_bounded(tmp_path: Path):
    mgr = ConfigManager(str(tmp_path / "cfg.json"))
    for index in range(250):
        mgr.add_alert_history({"n": index}, max_items=100)
    hist = mgr.get_alert_history()
    assert len(hist) == 100
    assert hist[0]["n"] == 150
    assert hist[-1]["n"] == 249
