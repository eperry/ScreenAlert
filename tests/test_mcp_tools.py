"""
Integration tests for all ScreenAlert MCP tools.

Starts a real MCPServer on a test port (18765) with a mock engine and a
real ConfigManager seeded with one window and one region.  Tests every tool
plus the HTTP-only endpoints (/health, /status, /skills).

Run with:
    pytest tests/test_mcp_tools.py -v
Or directly:
    python tests/test_mcp_tools.py
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import tempfile
import time
import threading
import warnings
from pathlib import Path
from typing import Any, Dict, List, Optional
from unittest.mock import MagicMock

import pytest
import requests

# ── Path setup ────────────────────────────────────────────────────────────────

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

# Suppress urllib3 InsecureRequest warnings from requests with verify=False
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ── Test constants ─────────────────────────────────────────────────────────────

TEST_PORT = 18765
TEST_WINDOW_ID = "aabb-ccdd-1111"
TEST_WINDOW_TITLE = "Test Window - ScreenAlert"
TEST_WINDOW_HWND = 99001
TEST_REGION_ID = "aabb-ccdd-2222"
TEST_REGION_NAME = "Test Region"
TEST_REGION_RECT = [10, 10, 200, 150]

_BASE_HTTPS = f"https://127.0.0.1:{TEST_PORT}/v1"
_SESSION: Optional[requests.Session] = None


# ── Mock engine objects ────────────────────────────────────────────────────────

class _MockMonitor:
    """Minimal RegionMonitor stub."""

    STATE_OK = "ok"
    STATE_ALERT = "alert"

    def __init__(self, region_id: str, thumbnail_id: str, config: dict):
        self.region_id = region_id
        self.thumbnail_id = thumbnail_id
        self.config = config
        self._state = self.STATE_OK
        self._alert_start_time = None

    @property
    def state(self) -> str:
        return self._state

    def is_alert(self) -> bool:
        return self._state == self.STATE_ALERT


class _MockMonitoringEngine:
    """Minimal MonitoringEngine stub."""

    def __init__(self, region_id: str, thumbnail_id: str, region_cfg: dict):
        self._monitors: Dict[str, _MockMonitor] = {
            region_id: _MockMonitor(region_id, thumbnail_id, region_cfg)
        }

    def get_monitor(self, region_id: str) -> Optional[_MockMonitor]:
        return self._monitors.get(region_id)

    def get_thumbnail_monitors(self, thumbnail_id: str) -> List[_MockMonitor]:
        return [m for m in self._monitors.values() if m.thumbnail_id == thumbnail_id]

    def remove_region(self, region_id: str) -> bool:
        self._monitors.pop(region_id, None)
        return True

    def add_region(self, region_id: str, thumbnail_id: str, config: dict,
                   global_config=None) -> _MockMonitor:
        m = _MockMonitor(region_id, thumbnail_id, config)
        self._monitors[region_id] = m
        return m


class _MockWindowManager:
    def get_window_list(self, use_cache: bool = True) -> list:
        return [
            {
                "hwnd": TEST_WINDOW_HWND,
                "title": TEST_WINDOW_TITLE,
                "class": "TestWindowClass",
                "size": (1280, 720),
                "rect": (0, 0, 1280, 720),
            }
        ]

    def find_window_by_title(self, title: str, **kwargs) -> Optional[dict]:
        if title.lower() in TEST_WINDOW_TITLE.lower():
            return {"hwnd": TEST_WINDOW_HWND, "title": TEST_WINDOW_TITLE}
        return None


class _MockRenderer:
    def set_thumbnail_user_visibility(self, tid: str, visible: bool) -> None:
        pass

    def set_thumbnail_opacity(self, tid: str, opacity: float) -> None:
        pass


class MockEngine:
    """
    Lightweight mock of ScreenAlertEngine that satisfies the interface
    expected by all MCP tool modules.
    """

    def __init__(self, config, region_cfg: dict):
        self._config = config
        self.running = True
        self.paused = False
        self.event_logger = None
        self._connected: Dict[str, bool] = {TEST_WINDOW_ID: True}
        self._next_thumbnail_id = "new-window-001"

        self.monitoring_engine = _MockMonitoringEngine(
            TEST_REGION_ID, TEST_WINDOW_ID, region_cfg
        )
        self.window_manager = _MockWindowManager()
        self.renderer = _MockRenderer()

    # ── engine interface ──────────────────────────────────────────────────────

    def is_thumbnail_connected(self, thumbnail_id: str) -> bool:
        return self._connected.get(thumbnail_id, False)

    def is_running(self) -> bool:
        return self.running

    def reconnect_window(self, thumbnail_id: str) -> str:
        return "already_valid"

    def reconnect_all_windows(self) -> dict:
        return {"total": 1, "reconnected": 0, "failed": 0, "already_valid": 1}

    def set_paused(self, paused: bool) -> None:
        self.paused = paused

    def add_thumbnail(self, title: str, hwnd: int, **kwargs) -> Optional[str]:
        return self._next_thumbnail_id

    def remove_thumbnail(self, thumbnail_id: str) -> bool:
        return True

    def add_region(self, thumbnail_id: str, name: str, rect: tuple,
                   alert_threshold: float = None) -> Optional[str]:
        # Mirror real engine: add to config so the region is findable by ID
        region_config = {
            "name": name,
            "rect": list(rect),
            "alert_threshold": alert_threshold or 0.99,
            "enabled": True,
            "sound_file": "",
            "tts_message": "Alert {window} {region_name}",
            "change_detection_method": "ssim",
        }
        region_id = self._config.add_region_to_thumbnail(thumbnail_id, region_config)
        if region_id:
            self._config.save()
            self.monitoring_engine.add_region(region_id, thumbnail_id, region_config)
        return region_id

    def _get_global_detection_config(self) -> dict:
        return {}


# ── Helpers ────────────────────────────────────────────────────────────────────

def _parse(result) -> Any:
    """Parse FastMCP call_tool result into a Python object.

    FastMCP returns different shapes depending on the return type annotation:
    - tuple (list[TextContent], {'result': value}) — typed annotations like Dict/List[dict]
    - list[TextContent] with one item — plain dict/str return
    - list[TextContent] with multiple items — (shouldn't happen with our tools)
    """
    if isinstance(result, tuple):
        # Structured output mode: second element is {'result': actual_value}
        _content, structured = result
        return structured.get("result", structured)
    if isinstance(result, list) and result:
        if len(result) == 1:
            text = getattr(result[0], "text", result[0])
            try:
                return json.loads(text)
            except (json.JSONDecodeError, TypeError):
                return text
        # Multiple TextContent items — reconstruct as list
        items = []
        for item in result:
            text = getattr(item, "text", item)
            try:
                items.append(json.loads(text))
            except (json.JSONDecodeError, TypeError):
                items.append(text)
        return items
    return result


def _call(mcp, name: str, args: dict = None) -> Any:
    """Call an MCP tool synchronously and return parsed result."""
    return _parse(asyncio.run(mcp.call_tool(name, args or {})))


def _http_get(path: str, key: str, verify: bool = False) -> requests.Response:
    return requests.get(
        f"{_BASE_HTTPS}/{path.lstrip('/')}",
        headers={"Authorization": f"Bearer {key}"},
        verify=verify,
        timeout=10,
    )


def _wait_for_server(port: int, timeout: float = 15.0) -> bool:
    """Poll /v1/health until the server responds or timeout expires."""
    deadline = time.time() + timeout
    url = f"https://127.0.0.1:{port}/v1/health"
    while time.time() < deadline:
        try:
            r = requests.get(url, verify=False, timeout=2)
            if r.status_code == 200:
                return True
        except requests.exceptions.ConnectionError:
            pass
        time.sleep(0.25)
    return False


# ── Fixtures / module-level setup ──────────────────────────────────────────────

class _TestState:
    """Holds shared state for the test session."""
    tmpdir: str = ""
    config = None
    engine: MockEngine = None
    event_logger = None
    mcp_server = None
    api_key: str = ""
    mcp = None  # FastMCP instance (direct tool call tests)


_S = _TestState()


@pytest.fixture(scope="module", autouse=True)
def _start_mcp_server():
    """
    Module-scoped fixture: creates all mock objects, seeds test data in
    ConfigManager, starts the MCPServer on TEST_PORT, and tears it all down
    after the module's tests complete.
    """
    import secrets
    from screenalert_core.core.config_manager import ConfigManager
    from screenalert_core.mcp.event_logger import EventLogger
    from screenalert_core.mcp.server import MCPServer
    from mcp.server.fastmcp import FastMCP
    import screenalert_core.mcp.tools.windows as win_mod
    import screenalert_core.mcp.tools.regions as reg_mod
    import screenalert_core.mcp.tools.monitoring as mon_mod
    import screenalert_core.mcp.tools.settings as set_mod
    import screenalert_core.mcp.tools.event_log as el_mod
    import screenalert_core.mcp.tools.images as img_mod

    # ── Temp directory ────────────────────────────────────────────────────────
    tmpdir = tempfile.mkdtemp(prefix="sa_mcp_test_")
    _S.tmpdir = tmpdir

    cfg_file = os.path.join(tmpdir, "test_config.json")

    # ── Real ConfigManager ────────────────────────────────────────────────────
    config = ConfigManager(config_path=cfg_file)

    # Override MCP port and API key for test isolation
    api_key = secrets.token_hex(16)
    config.set_mcp_enabled(True)
    config.set_mcp_port(TEST_PORT)
    config.set_mcp_api_key(api_key)
    cert_path = os.path.join(tmpdir, "test_cert.pem")
    key_path = os.path.join(tmpdir, "test_key.pem")
    config.set_mcp_ssl_cert_path(cert_path)
    config.set_mcp_ssl_key_path(key_path)
    config.save()

    _S.api_key = api_key

    # ── Seed a test window + region ───────────────────────────────────────────
    from screenalert_core.utils.helpers import generate_uuid

    thumbnail = {
        "id": TEST_WINDOW_ID,
        "window_title": TEST_WINDOW_TITLE,
        "window_hwnd": TEST_WINDOW_HWND,
        "window_class": "TestWindowClass",
        "window_size": [1280, 720],
        "monitor_id": 0,
        "window_slot": None,
        "position": {"x": 0, "y": 0, "monitor": 0},
        "size": {"width": 320, "height": 240},
        "opacity": 0.8,
        "always_on_top": True,
        "show_border": True,
        "enabled": True,
        "monitored_regions": [
            {
                "id": TEST_REGION_ID,
                "name": TEST_REGION_NAME,
                "rect": TEST_REGION_RECT,
                "alert_threshold": 0.99,
                "enabled": True,
                "sound_file": "",
                "tts_message": "Alert {window} {region_name}",
                "change_detection_method": "ssim",
            }
        ],
    }
    config._config["thumbnails"] = [thumbnail]
    config.save()

    region_cfg = thumbnail["monitored_regions"][0]

    # ── Mock engine ───────────────────────────────────────────────────────────
    engine = MockEngine(config, region_cfg)
    _S.engine = engine
    _S.config = config

    # ── Event logger ──────────────────────────────────────────────────────────
    log_path = os.path.join(tmpdir, "events.jsonl")
    event_logger = EventLogger(log_path=log_path, max_rows=500, enabled=True)
    event_logger.start()
    _S.event_logger = event_logger

    # ── FastMCP instance for direct-call tests ────────────────────────────────
    mcp = FastMCP("ScreenAlert-test")
    win_mod.register(mcp, engine, config, event_logger)
    reg_mod.register(mcp, engine, config, event_logger)
    mon_mod.register(mcp, engine, config, event_logger)
    set_mod.register(mcp, engine, config, event_logger)
    el_mod.register(mcp, engine, config, event_logger)
    img_mod.register(mcp, engine, config, event_logger)

    # Register ping (utility tool — normally registered by MCPServer directly)
    @mcp.tool(description="Verify connectivity.")
    def ping() -> dict:
        return {"version": "test", "uptime_seconds": 0, "monitoring_state": "running"}

    _S.mcp = mcp

    # ── Real MCPServer (HTTPS on TEST_PORT) ───────────────────────────────────
    mcp_server = MCPServer(engine=engine, config=config, event_logger=event_logger)
    mcp_server.start()
    _S.mcp_server = mcp_server

    # Wait for server to be ready
    assert _wait_for_server(TEST_PORT, timeout=20), \
        f"MCP server did not start on port {TEST_PORT} within 20 seconds"

    yield  # ── run all tests ──────────────────────────────────────────────────

    # ── Teardown ──────────────────────────────────────────────────────────────
    mcp_server.stop()
    event_logger.stop()

    import shutil
    shutil.rmtree(tmpdir, ignore_errors=True)


# ═══════════════════════════════════════════════════════════════════════════════
# HTTP endpoint tests (no MCP protocol, just raw HTTP)
# ═══════════════════════════════════════════════════════════════════════════════

class TestHTTPEndpoints:

    def test_health_no_auth(self):
        """Health check is public and returns {status: ok}."""
        r = requests.get(f"{_BASE_HTTPS}/health", verify=False, timeout=5)
        assert r.status_code == 200
        assert r.json() == {"status": "ok"}

    def test_health_with_auth(self):
        """Health also works with auth header."""
        r = _http_get("/health", _S.api_key)
        assert r.status_code == 200

    def test_status_requires_auth(self):
        """Status endpoint returns 401 without auth."""
        r = requests.get(f"{_BASE_HTTPS}/status", verify=False, timeout=5)
        assert r.status_code == 401

    def test_status_with_auth(self):
        """Status returns expected fields."""
        r = _http_get("/status", _S.api_key)
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "ok"
        assert "version" in data
        assert "uptime_seconds" in data
        assert "active_connections" in data
        assert "cert_fingerprint" in data

    def test_skills_with_auth(self):
        """Skills returns a list of all registered tools."""
        r = _http_get("/skills", _S.api_key)
        assert r.status_code == 200
        skills = r.json()
        assert isinstance(skills, list)
        names = {s["name"] for s in skills}
        # Verify all expected tools are registered
        for expected in [
            "ping", "list_windows", "find_desktop_windows", "add_window",
            "remove_window", "reconnect_window", "reconnect_all_windows",
            "get_window_settings", "set_window_setting",
            "list_regions", "add_region", "remove_region", "copy_region",
            "list_alerts", "acknowledge_alert",
            "get_region_settings", "set_region_setting",
            "pause_monitoring", "resume_monitoring", "mute_alerts",
            "get_monitoring_status",
            "get_global_settings", "set_global_setting",
            "get_event_log", "get_event_summary", "clear_event_log",
            "get_alert_image", "get_alert_diagnostic_images",
        ]:
            assert expected in names, f"Tool '{expected}' missing from /v1/skills"

    def test_auth_wrong_key(self):
        """Wrong API key returns 401."""
        r = requests.get(
            f"{_BASE_HTTPS}/status",
            headers={"Authorization": "Bearer wrongkey123"},
            verify=False,
            timeout=5,
        )
        assert r.status_code == 401

    def test_resources_endpoint(self):
        """Resources index returns HTML."""
        r = _http_get("/resources", _S.api_key)
        assert r.status_code == 200
        assert "html" in r.headers.get("content-type", "").lower()


# ═══════════════════════════════════════════════════════════════════════════════
# Direct tool tests (call via FastMCP.call_tool — no HTTP overhead)
# ═══════════════════════════════════════════════════════════════════════════════

class TestUtilityTools:

    def test_ping(self):
        result = _call(_S.mcp, "ping")
        assert "version" in result
        assert "uptime_seconds" in result
        assert "monitoring_state" in result
        assert result["monitoring_state"] == "running"


class TestWindowTools:

    def test_list_windows_all(self):
        result = _call(_S.mcp, "list_windows")
        assert isinstance(result, list)
        assert len(result) >= 1
        win = next((w for w in result if w["id"] == TEST_WINDOW_ID), None)
        assert win is not None
        assert win["name"] == TEST_WINDOW_TITLE
        assert win["status"] == "connected"

    def test_list_windows_filter_match(self):
        result = _call(_S.mcp, "list_windows", {"filter": "Test Window"})
        assert any(w["id"] == TEST_WINDOW_ID for w in result)

    def test_list_windows_filter_no_match(self):
        result = _call(_S.mcp, "list_windows", {"filter": "xyzzy_no_match"})
        assert result == []

    def test_find_desktop_windows(self):
        result = _call(_S.mcp, "find_desktop_windows")
        assert isinstance(result, list)
        assert len(result) >= 1
        assert result[0]["hwnd"] == TEST_WINDOW_HWND

    def test_find_desktop_windows_filter(self):
        result = _call(_S.mcp, "find_desktop_windows", {"filter": "Test Window"})
        assert len(result) >= 1

    def test_find_desktop_windows_limit(self):
        result = _call(_S.mcp, "find_desktop_windows", {"limit": 1})
        assert len(result) <= 1

    def test_add_window_duplicate(self):
        """Adding a window with an existing title returns 409."""
        result = _call(_S.mcp, "add_window", {"title": TEST_WINDOW_TITLE})
        assert result.get("code") == 409
        assert "existing_id" in result

    def test_add_window_new(self):
        """Adding a new window returns id and name."""
        result = _call(_S.mcp, "add_window",
                       {"title": "Brand New Window", "hwnd": 99999})
        assert "id" in result
        assert result["name"] == "Brand New Window"

    def test_add_window_missing_title(self):
        result = _call(_S.mcp, "add_window", {"title": ""})
        assert result.get("code") == 400

    def test_remove_window_dry_run(self):
        """remove_window without confirm returns dry_run preview."""
        result = _call(_S.mcp, "remove_window",
                       {"window_id": TEST_WINDOW_ID, "confirm": False})
        assert result.get("dry_run") is True
        assert result["id"] == TEST_WINDOW_ID
        assert "regions_count" in result

    def test_remove_window_confirm(self):
        """remove_window with confirm=true executes deletion."""
        result = _call(_S.mcp, "remove_window",
                       {"window_id": TEST_WINDOW_ID, "confirm": True})
        assert result.get("ok") is True
        assert "regions_deleted" in result

    def test_remove_window_not_found(self):
        result = _call(_S.mcp, "remove_window",
                       {"window_id": "does-not-exist", "confirm": True})
        assert result.get("code") == 404

    def test_reconnect_window_by_id(self):
        result = _call(_S.mcp, "reconnect_window",
                       {"window_id": TEST_WINDOW_ID})
        assert result["result"] == "already_valid"

    def test_reconnect_window_not_found(self):
        result = _call(_S.mcp, "reconnect_window",
                       {"window_id": "bad-id"})
        assert result.get("code") == 404

    def test_reconnect_all_windows(self):
        result = _call(_S.mcp, "reconnect_all_windows")
        assert "total" in result
        assert "reconnected" in result
        assert "failed" in result
        assert "already_valid" in result

    def test_get_window_settings_by_id(self):
        result = _call(_S.mcp, "get_window_settings",
                       {"window_id": TEST_WINDOW_ID})
        assert "name" in result
        assert "opacity" in result
        assert "enabled" in result
        assert result["name"]["value"] == TEST_WINDOW_TITLE

    def test_get_window_settings_by_name(self):
        result = _call(_S.mcp, "get_window_settings",
                       {"window_name": "Test Window"})
        assert result["name"]["value"] == TEST_WINDOW_TITLE

    def test_set_window_setting_opacity(self):
        result = _call(_S.mcp, "set_window_setting",
                       {"window_id": TEST_WINDOW_ID, "key": "opacity", "value": 0.7})
        assert result.get("ok") is True

    def test_set_window_setting_opacity_out_of_range(self):
        result = _call(_S.mcp, "set_window_setting",
                       {"window_id": TEST_WINDOW_ID, "key": "opacity", "value": 5.0})
        assert result.get("code") == 422

    def test_set_window_setting_enabled(self):
        result = _call(_S.mcp, "set_window_setting",
                       {"window_id": TEST_WINDOW_ID, "key": "enabled", "value": False})
        assert result.get("ok") is True

    def test_set_window_setting_unknown_key(self):
        result = _call(_S.mcp, "set_window_setting",
                       {"window_id": TEST_WINDOW_ID, "key": "bogus_key", "value": 1})
        assert result.get("code") == 400


class TestRegionTools:

    def test_list_regions_all(self):
        result = _call(_S.mcp, "list_regions")
        assert isinstance(result, list)
        region = next((r for r in result if r["id"] == TEST_REGION_ID), None)
        assert region is not None
        assert region["name"] == TEST_REGION_NAME
        assert region["window_id"] == TEST_WINDOW_ID

    def test_list_regions_by_window(self):
        result = _call(_S.mcp, "list_regions",
                       {"window_id": TEST_WINDOW_ID})
        assert any(r["id"] == TEST_REGION_ID for r in result)

    def test_add_region_valid(self):
        result = _call(_S.mcp, "add_region", {
            "window_id": TEST_WINDOW_ID,
            "name": "New Region",
            "rect": {"x": 0, "y": 0, "width": 100, "height": 80},
        })
        assert "id" in result
        assert result["name"] == "New Region"

    def test_add_region_missing_name(self):
        result = _call(_S.mcp, "add_region", {
            "window_id": TEST_WINDOW_ID,
            "name": "",
            "rect": {"x": 0, "y": 0, "width": 100, "height": 80},
        })
        assert result.get("code") == 400

    def test_add_region_missing_rect(self):
        result = _call(_S.mcp, "add_region", {
            "window_id": TEST_WINDOW_ID,
            "name": "Bad Region",
        })
        assert result.get("code") == 400

    def test_add_region_bad_rect(self):
        result = _call(_S.mcp, "add_region", {
            "window_id": TEST_WINDOW_ID,
            "name": "Bad Rect",
            "rect": {"x": 0, "y": 0, "width": -10, "height": 80},
        })
        assert result.get("code") == 422

    def test_remove_region(self):
        # Create a temporary region, then remove it — avoids destroying TEST_REGION_ID
        added = _call(_S.mcp, "add_region", {
            "window_id": TEST_WINDOW_ID,
            "name": "Temp Remove Test",
            "rect": {"x": 5, "y": 5, "width": 50, "height": 50},
        })
        assert "id" in added, f"Setup failed: {added}"
        result = _call(_S.mcp, "remove_region", {"region_id": added["id"]})
        assert result.get("ok") is True

    def test_remove_region_not_found(self):
        result = _call(_S.mcp, "remove_region", {"region_id": "bad-region-id"})
        assert result.get("code") == 404

    def test_copy_region(self):
        result = _call(_S.mcp, "copy_region", {
            "region_id": TEST_REGION_ID,
            "target_window_id": TEST_WINDOW_ID,
            "name": "Copied Region",
        })
        assert "id" in result
        assert result["name"] == "Copied Region"

    def test_list_alerts_no_active(self):
        """By default no monitors are in alert state."""
        result = _call(_S.mcp, "list_alerts")
        assert isinstance(result, list)
        # Default state is ok, so no alerts
        assert not any(r["region_id"] == TEST_REGION_ID for r in result)

    def test_list_alerts_with_active(self):
        """Manually set a monitor to alert state, verify it appears."""
        monitor = _S.engine.monitoring_engine.get_monitor(TEST_REGION_ID)
        monitor._state = "alert"
        result = _call(_S.mcp, "list_alerts")
        assert any(r["region_id"] == TEST_REGION_ID for r in result)
        monitor._state = "ok"  # reset

    def test_acknowledge_alert(self):
        monitor = _S.engine.monitoring_engine.get_monitor(TEST_REGION_ID)
        monitor._state = "alert"
        result = _call(_S.mcp, "acknowledge_alert", {"region_id": TEST_REGION_ID})
        assert result.get("ok") is True
        assert result.get("was_alert") is True
        assert monitor._state == "ok"

    def test_acknowledge_alert_not_found(self):
        result = _call(_S.mcp, "acknowledge_alert", {"region_id": "bad-id"})
        assert result.get("code") == 404

    def test_get_region_settings(self):
        result = _call(_S.mcp, "get_region_settings",
                       {"region_id": TEST_REGION_ID})
        assert "name" in result
        assert "rect" in result
        assert "alert_threshold" in result
        assert "enabled" in result
        assert result["name"]["value"] == TEST_REGION_NAME

    def test_get_region_settings_not_found(self):
        result = _call(_S.mcp, "get_region_settings", {"region_id": "bad"})
        assert result.get("code") == 404

    def test_set_region_setting_name(self):
        result = _call(_S.mcp, "set_region_setting", {
            "region_id": TEST_REGION_ID,
            "key": "name",
            "value": "Renamed Region",
        })
        assert result.get("ok") is True

    def test_set_region_setting_threshold(self):
        result = _call(_S.mcp, "set_region_setting", {
            "region_id": TEST_REGION_ID,
            "key": "alert_threshold",
            "value": 0.95,
        })
        assert result.get("ok") is True

    def test_set_region_setting_threshold_out_of_range(self):
        result = _call(_S.mcp, "set_region_setting", {
            "region_id": TEST_REGION_ID,
            "key": "alert_threshold",
            "value": 1.5,
        })
        assert result.get("code") == 422

    def test_set_region_setting_detection_method(self):
        result = _call(_S.mcp, "set_region_setting", {
            "region_id": TEST_REGION_ID,
            "key": "change_detection_method",
            "value": "phash",
        })
        assert result.get("ok") is True

    def test_set_region_setting_detection_method_invalid(self):
        result = _call(_S.mcp, "set_region_setting", {
            "region_id": TEST_REGION_ID,
            "key": "change_detection_method",
            "value": "magical_ai",
        })
        assert result.get("code") == 422

    def test_set_region_setting_unknown_key(self):
        result = _call(_S.mcp, "set_region_setting", {
            "region_id": TEST_REGION_ID,
            "key": "does_not_exist",
            "value": True,
        })
        assert result.get("code") == 400


class TestMonitoringTools:

    def test_get_monitoring_status(self):
        result = _call(_S.mcp, "get_monitoring_status")
        assert result["state"] in ("running", "paused", "stopped")
        assert "muted" in result
        assert "mute_remaining_seconds" in result
        assert "active_windows" in result

    def test_pause_monitoring(self):
        result = _call(_S.mcp, "pause_monitoring")
        assert result.get("ok") is True
        assert _S.engine.paused is True

    def test_resume_monitoring(self):
        _S.engine.paused = True
        result = _call(_S.mcp, "resume_monitoring")
        assert result.get("ok") is True
        assert _S.engine.paused is False

    def test_mute_alerts_valid(self):
        result = _call(_S.mcp, "mute_alerts", {"seconds": 60})
        assert result.get("ok") is True
        assert "muted_until" in result

    def test_mute_alerts_out_of_range_low(self):
        result = _call(_S.mcp, "mute_alerts", {"seconds": 0})
        assert result.get("code") == 422

    def test_mute_alerts_out_of_range_high(self):
        result = _call(_S.mcp, "mute_alerts", {"seconds": 9999})
        assert result.get("code") == 422

    def test_mute_extends_existing(self):
        """Muting twice should extend (not reset) the mute."""
        _S.config.set_mute_until_ts(0)  # start fresh
        r1 = _call(_S.mcp, "mute_alerts", {"seconds": 60})
        r2 = _call(_S.mcp, "mute_alerts", {"seconds": 60})
        # Both must succeed; r2 timestamp >= r1 timestamp
        assert r1.get("ok") and r2.get("ok")
        assert r2["muted_until"] >= r1["muted_until"]
        _S.config.set_mute_until_ts(0)  # cleanup


class TestGlobalSettingsTools:

    def test_get_global_settings(self):
        result = _call(_S.mcp, "get_global_settings")
        assert isinstance(result, dict)
        for key in ["opacity", "always_on_top", "log_level",
                    "refresh_rate_ms", "enable_sound", "event_log_enabled"]:
            assert key in result, f"Key '{key}' missing from get_global_settings"
            assert "value" in result[key]
            assert "type" in result[key]

    def test_set_global_setting_opacity(self):
        result = _call(_S.mcp, "set_global_setting",
                       {"key": "opacity", "value": 0.6})
        assert result.get("ok") is True
        assert _S.config.get_opacity() == pytest.approx(0.6, abs=0.01)

    def test_set_global_setting_bool(self):
        original = _S.config.get_enable_sound()
        result = _call(_S.mcp, "set_global_setting",
                       {"key": "enable_sound", "value": not original})
        assert result.get("ok") is True
        assert _S.config.get_enable_sound() is (not original)

    def test_set_global_setting_log_level(self):
        result = _call(_S.mcp, "set_global_setting",
                       {"key": "log_level", "value": "WARNING"})
        assert result.get("ok") is True
        assert _S.config.get_log_level() == "WARNING"

    def test_set_global_setting_invalid_log_level(self):
        result = _call(_S.mcp, "set_global_setting",
                       {"key": "log_level", "value": "EXTREME"})
        assert result.get("code") == 422

    def test_set_global_setting_refresh_rate_valid(self):
        result = _call(_S.mcp, "set_global_setting",
                       {"key": "refresh_rate_ms", "value": 500})
        assert result.get("ok") is True

    def test_set_global_setting_refresh_rate_too_low(self):
        result = _call(_S.mcp, "set_global_setting",
                       {"key": "refresh_rate_ms", "value": 10})
        assert result.get("code") == 422

    def test_set_global_setting_unknown_key(self):
        result = _call(_S.mcp, "set_global_setting",
                       {"key": "nonexistent_setting", "value": True})
        assert result.get("code") == 400

    def test_set_global_setting_overlay_scaling_mode(self):
        result = _call(_S.mcp, "set_global_setting",
                       {"key": "overlay_scaling_mode", "value": "stretch"})
        assert result.get("ok") is True

    def test_set_global_setting_overlay_scaling_mode_invalid(self):
        result = _call(_S.mcp, "set_global_setting",
                       {"key": "overlay_scaling_mode", "value": "warp"})
        assert result.get("code") == 422


class TestEventLogTools:

    def test_get_event_log_empty(self):
        result = _call(_S.mcp, "get_event_log")
        assert "events" in result
        assert "total" in result
        assert "has_more" in result
        assert isinstance(result["events"], list)

    def test_get_event_log_after_logging(self):
        _S.event_logger.log("test", "unit_test_event", "test_suite",
                            detail="hello")
        result = _call(_S.mcp, "get_event_log", {"category": "test"})
        assert result["total"] >= 1
        assert any(e["event"] == "unit_test_event"
                   for e in result["events"])

    def test_get_event_log_limit(self):
        for i in range(5):
            _S.event_logger.log("test", f"bulk_event_{i}", "test_suite")
        result = _call(_S.mcp, "get_event_log", {"limit": 2})
        assert len(result["events"]) <= 2

    def test_get_event_log_filter_category(self):
        _S.event_logger.log("system", "sys_event", "test_suite")
        result = _call(_S.mcp, "get_event_log", {"category": "system"})
        assert all(e["category"] == "system" for e in result["events"])

    def test_get_event_summary(self):
        result = _call(_S.mcp, "get_event_summary")
        assert "total" in result
        assert "counts_by_category" in result
        assert "counts_by_event" in result

    def test_get_event_summary_since(self):
        result = _call(_S.mcp, "get_event_summary",
                       {"since": "2099-01-01T00:00:00+00:00"})
        assert result["total"] == 0  # Future date — no events

    def test_clear_event_log_category(self):
        _S.event_logger.log("alerts", "fake_alert", "test_suite")
        result = _call(_S.mcp, "clear_event_log", {"category": "alerts"})
        assert "entries_deleted" in result

    def test_clear_event_log_all(self):
        result = _call(_S.mcp, "clear_event_log")
        assert "entries_deleted" in result

    def test_get_event_log_after_id_cursor(self):
        """after_id cursor should skip events up to and including that id."""
        _S.event_logger.log("test", "cursor_a", "test_suite")
        _S.event_logger.log("test", "cursor_b", "test_suite")
        first = _call(_S.mcp, "get_event_log",
                      {"category": "test", "limit": 100})
        events = first.get("events", [])
        if len(events) >= 2:
            pivot_id = events[0]["id"]
            result = _call(_S.mcp, "get_event_log",
                           {"after_id": pivot_id, "category": "test"})
            # No event should have the pivot id
            assert not any(e["id"] == pivot_id
                           for e in result.get("events", []))


class TestImageTools:

    def test_get_alert_image_no_event_id(self):
        """Missing both event_id and window_id/region_id returns 400."""
        result = _call(_S.mcp, "get_alert_image")
        assert result.get("code") in (400, 404, 503)

    def test_get_alert_image_missing_region_id(self):
        """window_id without region_id returns 400."""
        result = _call(_S.mcp, "get_alert_image",
                       {"window_id": TEST_WINDOW_ID})
        assert result.get("code") in (400, 404, 503)

    def test_get_alert_image_no_capture(self):
        """window_id + region_id with no capture on disk returns 404."""
        result = _call(_S.mcp, "get_alert_image", {
            "window_id": TEST_WINDOW_ID,
            "region_id": TEST_REGION_ID,
        })
        # No capture file recorded → 404 (or 503 if event log disabled)
        assert result.get("code") in (404, 503)

    def test_get_alert_image_bad_event_id(self):
        result = _call(_S.mcp, "get_alert_image",
                       {"event_id": "does-not-exist"})
        assert result.get("code") in (404, 503)

    def test_get_alert_diagnostic_images_missing_event(self):
        result = _call(_S.mcp, "get_alert_diagnostic_images",
                       {"event_id": "nonexistent-event"})
        # Returns a list with an error dict
        assert isinstance(result, list)
        assert result[0].get("code") in (404, 503)

    def test_get_alert_diagnostic_images_no_event_id(self):
        result = _call(_S.mcp, "get_alert_diagnostic_images", {"event_id": ""})
        assert isinstance(result, list)
        assert result[0].get("code") == 400


# ═══════════════════════════════════════════════════════════════════════════════
# Tool count / registration smoke test
# ═══════════════════════════════════════════════════════════════════════════════

class TestToolRegistration:

    def test_all_28_tools_registered(self):
        tools = asyncio.run(_S.mcp.list_tools())
        names = {t.name for t in tools}
        expected = {
            # Utility
            "ping",
            # Windows (8)
            "list_windows", "find_desktop_windows", "add_window", "remove_window",
            "reconnect_window", "reconnect_all_windows",
            "get_window_settings", "set_window_setting",
            # Regions (8)
            "list_regions", "add_region", "remove_region", "copy_region",
            "list_alerts", "acknowledge_alert",
            "get_region_settings", "set_region_setting",
            # Monitoring (4)
            "pause_monitoring", "resume_monitoring", "mute_alerts",
            "get_monitoring_status",
            # Settings (2)
            "get_global_settings", "set_global_setting",
            # Event log (3)
            "get_event_log", "get_event_summary", "clear_event_log",
            # Images (2)
            "get_alert_image", "get_alert_diagnostic_images",
        }
        missing = expected - names
        extra = names - expected
        assert not missing, f"Missing tools: {missing}"
        # Extra tools are fine (utility tools like ping already counted)

    def test_tool_descriptions_non_empty(self):
        tools = asyncio.run(_S.mcp.list_tools())
        for t in tools:
            assert t.description, f"Tool '{t.name}' has no description"


# ═══════════════════════════════════════════════════════════════════════════════
# Standalone runner
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import subprocess
    result = subprocess.run(
        [sys.executable, "-m", "pytest", __file__, "-v", "--tb=short"],
        cwd=str(ROOT),
    )
    sys.exit(result.returncode)
