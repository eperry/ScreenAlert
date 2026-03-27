"""Window slot management mixin for ScreenAlertMainWindow.

Manages Alt+1..0 keyboard slot assignments.  Expects the host class to
provide:
  self.config           – ConfigManager
  self.engine           – ScreenAlertEngine
  self.window_manager   – WindowManager
  self.selected_thumbnail_id – str | None
  self.status_var       – tk.StringVar
  self.root             – tk.Tk
  self.window_slot_var  – tk.StringVar
  self.window_slot_combo – ttk.Combobox (may be absent)
  self._get_focus_owner_ids() – returns (primary_id, focus_id)
  self._update_thumbnail_list()
"""

import logging
from typing import Dict, Optional

logger = logging.getLogger(__name__)


class WindowSlotMixin:
    """Alt-slot assignment and activation for the main window."""

    # ── Helpers ──────────────────────────────────────────────────────────

    def _normalize_window_slot(self, value) -> Optional[int]:
        """Return a valid 1–10 slot number or None."""
        try:
            slot = int(value)
        except (TypeError, ValueError):
            return None
        return slot if 1 <= slot <= 10 else None

    def _get_window_slot(self, thumbnail: Optional[Dict]) -> Optional[int]:
        """Return the normalized slot number from *thumbnail* config, or None."""
        if not thumbnail:
            return None
        return self._normalize_window_slot(thumbnail.get("window_slot"))

    def _get_slot_owner_id(self, slot: int) -> Optional[str]:
        """Return the thumbnail id currently assigned to *slot*, or None."""
        for thumbnail in self.config.get_all_thumbnails():
            thumbnail_id = thumbnail.get("id")
            if not thumbnail_id:
                continue
            if self._get_window_slot(thumbnail) == slot:
                return thumbnail_id
        return None

    def _get_first_available_slot(self) -> Optional[int]:
        """Return the first free slot in range 1..10, or None if all taken."""
        used = {
            slot
            for slot in (
                self._get_window_slot(thumb) for thumb in self.config.get_all_thumbnails()
            )
            if slot is not None
        }
        for slot in range(1, 11):
            if slot not in used:
                return slot
        return None

    # ── Assignment ────────────────────────────────────────────────────────

    def _swap_or_assign_window_slot(self, target_thumbnail_id: str, new_slot: int) -> bool:
        """Assign *new_slot* to *target_thumbnail_id*, swapping with its current owner.

        Returns True if any config change was made.
        """
        target = self.config.get_thumbnail(target_thumbnail_id)
        if not target:
            return False

        normalized_slot = self._normalize_window_slot(new_slot)
        if normalized_slot is None:
            return False

        current_slot = self._get_window_slot(target)
        if current_slot == normalized_slot:
            return False

        owner_id = self._get_slot_owner_id(normalized_slot)
        changed = False

        if owner_id and owner_id != target_thumbnail_id:
            owner = self.config.get_thumbnail(owner_id)
            if owner:
                owner_updates = {"window_slot": current_slot if current_slot is not None else None}
                if owner.get("window_slot") != owner_updates["window_slot"]:
                    self.config.update_thumbnail(owner_id, owner_updates)
                    changed = True

        if target.get("window_slot") != normalized_slot:
            self.config.update_thumbnail(target_thumbnail_id, {"window_slot": normalized_slot})
            changed = True

        return changed

    def _assign_default_slot_if_missing(self, thumbnail_id: str) -> None:
        """Assign the next available slot when a window has none."""
        thumbnail = self.config.get_thumbnail(thumbnail_id)
        if not thumbnail or self._get_window_slot(thumbnail) is not None:
            return

        desired = 1 if bool(thumbnail.get("is_primary", False)) else self._get_first_available_slot()
        if desired is None:
            return

        if self._swap_or_assign_window_slot(thumbnail_id, desired):
            self.config.save()
            self.engine.refresh_thumbnail_titles()

    def _ensure_window_slot_consistency(self) -> None:
        """Ensure windows have unique slots and the Primary stays on slot 1."""
        changed = False

        primary_owner_id, _ = self._get_focus_owner_ids()
        slot_one_owner_id = self._get_slot_owner_id(1)

        if primary_owner_id:
            if slot_one_owner_id and slot_one_owner_id != primary_owner_id:
                # Slot 1 is occupied by a non-primary; realign is_primary to the slot owner.
                for thumbnail in self.config.get_all_thumbnails():
                    tid = thumbnail.get("id")
                    if not tid:
                        continue
                    should_be_primary = tid == slot_one_owner_id
                    if bool(thumbnail.get("is_primary", False)) != should_be_primary:
                        self.config.update_thumbnail(tid, {"is_primary": should_be_primary})
                        changed = True
            else:
                changed = self._swap_or_assign_window_slot(primary_owner_id, 1) or changed

        for thumbnail in self.config.get_all_thumbnails():
            tid = thumbnail.get("id")
            if not tid:
                continue
            if self._get_window_slot(thumbnail) is not None:
                continue
            desired = self._get_first_available_slot()
            if desired is None:
                continue
            self.config.update_thumbnail(tid, {"window_slot": desired})
            changed = True

        if changed:
            self.config.save()
            self.engine.refresh_thumbnail_titles()

    # ── UI events ─────────────────────────────────────────────────────────

    def _on_window_slot_changed(self, _event=None) -> None:
        """Handle slot change from the Window Info UI with swap semantics."""
        selected_id = self.selected_thumbnail_id
        if not selected_id:
            return

        selected_thumbnail = self.config.get_thumbnail(selected_id)
        if not selected_thumbnail:
            return

        new_slot = self._normalize_window_slot(self.window_slot_var.get())
        if new_slot is None:
            return

        primary_owner_id, _ = self._get_focus_owner_ids()
        is_selected_primary = bool(selected_thumbnail.get("is_primary", False))
        previous_slot = self._get_window_slot(selected_thumbnail)
        slot_one_owner_id = self._get_slot_owner_id(1)

        if is_selected_primary and new_slot != 1:
            self.window_slot_var.set("1")
            self.status_var.set("Primary window must use slot 1")
            return

        if not is_selected_primary and primary_owner_id and primary_owner_id != selected_id and new_slot == 1:
            self.window_slot_var.set(str(previous_slot) if previous_slot else "")
            self.status_var.set("Slot 1 is reserved for the Primary window")
            return

        if new_slot == 1 and slot_one_owner_id and slot_one_owner_id != selected_id:
            self.window_slot_var.set(str(previous_slot) if previous_slot else "")
            self.status_var.set("Slot 1 cannot be swapped")
            return

        if self._swap_or_assign_window_slot(selected_id, new_slot):
            self.config.save()
            self.engine.refresh_thumbnail_titles()
            self.status_var.set(f"Window slot set to {new_slot}")
        else:
            self.status_var.set(f"Window slot remains {new_slot}")

        selected_thumbnail = self.config.get_thumbnail(selected_id)
        selected_slot = self._get_window_slot(selected_thumbnail)
        self.window_slot_var.set(str(selected_slot) if selected_slot else "")
        self._schedule_clear_window_slot_selection()

    def _schedule_clear_window_slot_selection(self) -> None:
        """Clear selected text in the Alt Slot combobox to prevent an unreadable highlight."""
        combo = getattr(self, "window_slot_combo", None)
        if not combo:
            return

        def _clear() -> None:
            try:
                combo.selection_clear()
            except Exception:
                pass

        try:
            self.root.after_idle(_clear)
        except Exception:
            _clear()

    def _activate_window_by_slot(self, slot: int):
        """Bring the window assigned to Alt *slot* to the foreground."""
        target_slot = self._normalize_window_slot(slot)
        if target_slot is None:
            return "break"

        target_thumbnail = None
        for thumbnail in self.config.get_all_thumbnails():
            if self._get_window_slot(thumbnail) == target_slot:
                target_thumbnail = thumbnail
                break

        label = str(0 if target_slot == 10 else target_slot)
        if not target_thumbnail:
            self.status_var.set(f"No window assigned to Alt+{label}")
            return "break"

        thumbnail_id = target_thumbnail.get("id")
        hwnd = target_thumbnail.get("window_hwnd")
        title = target_thumbnail.get("window_title", "Unknown")
        if not thumbnail_id:
            return "break"

        if not hwnd or not self.window_manager.is_window_valid(hwnd):
            reconnect_state = self.engine.reconnect_window(thumbnail_id)
            if reconnect_state not in ("already_valid", "reconnected"):
                self.status_var.set(f"Alt+{label}: window unavailable")
                return "break"
            refreshed = self.config.get_thumbnail(thumbnail_id)
            hwnd = refreshed.get("window_hwnd") if refreshed else None

        if hwnd and self.window_manager.activate_window(hwnd):
            self.selected_thumbnail_id = thumbnail_id
            self.selected_region_id = None
            self.show_all_regions = False
            self._pending_tree_focus_window_id = thumbnail_id
            self._pending_tree_focus_region_id = None
            self._update_thumbnail_list()
            self.status_var.set(f"Activated Alt+{label}: {title}")
        else:
            self.status_var.set(f"Failed to activate Alt+{label}")

        return "break"
