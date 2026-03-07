"""Lightweight plugin hook registry for ScreenAlert."""

import logging
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


class PluginHooks:
    """In-process plugin hook registry.

    Hooks are identified by a string event name and can have multiple callbacks.
    """

    def __init__(self) -> None:
        """Initialize empty hook registry."""
        self._hooks: Dict[str, List[Callable[..., Any]]] = {}

    def register(self, event_name: str, callback: Callable[..., Any]) -> None:
        """Register a callback for an event."""
        if event_name not in self._hooks:
            self._hooks[event_name] = []
        self._hooks[event_name].append(callback)

    def unregister(self, event_name: str, callback: Callable[..., Any]) -> bool:
        """Unregister a callback from an event.

        Returns:
            True if removed, False if callback was not found.
        """
        callbacks = self._hooks.get(event_name, [])
        if callback not in callbacks:
            return False
        callbacks.remove(callback)
        if not callbacks and event_name in self._hooks:
            del self._hooks[event_name]
        return True

    def clear(self, event_name: Optional[str] = None) -> None:
        """Clear callbacks for one event or all events."""
        if event_name is None:
            self._hooks.clear()
            return
        self._hooks.pop(event_name, None)

    def list_events(self) -> List[str]:
        """Return sorted list of event names with registered callbacks."""
        return sorted(self._hooks.keys())

    def emit(self, event_name: str, *args, **kwargs) -> None:
        """Emit an event to all registered callbacks."""
        for callback in self._hooks.get(event_name, []):
            try:
                callback(*args, **kwargs)
            except Exception as e:
                logger.warning(f"Plugin hook error on '{event_name}': {e}")
