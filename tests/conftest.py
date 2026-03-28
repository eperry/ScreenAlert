"""
Pytest configuration for ScreenAlert tests.

Adds --live flag for running the MCP tool tests against a real ScreenAlert
instance instead of the embedded mock server.

Usage:
    pytest                        # mock server (default)
    pytest --live                 # live ScreenAlert on default port 8765
    pytest --live --live-port 8765 --live-key <key>  # explicit overrides
"""


def pytest_addoption(parser):
    parser.addoption(
        "--live",
        action="store_true",
        default=False,
        help="Run MCP tests against a running ScreenAlert instance",
    )
    parser.addoption(
        "--live-port",
        type=int,
        default=8765,
        help="Port of the live MCP server (default: 8765)",
    )
    parser.addoption(
        "--live-key",
        type=str,
        default="",
        help=(
            "API key for the live MCP server. "
            "If omitted, read from %APPDATA%\\ScreenAlert\\screenalert_config.json"
        ),
    )
