# ScreenAlert: Overlay Design Statements (dev-new4)

## Overview

This document defines the `dev-new4` scope as **overlay design-only guidance**.

Primary goals:
1. Define clear visual states for overlays.
2. Standardize placeholder and text treatment for unavailable overlays.
3. Keep overlay visual language consistent and minimal.
4. Define per-window overlay interaction behavior (focus, move, resize, sync-resize).

Date: March 2, 2026

---

## 1) Overlay Visual States

### 1.1 Visible design states
- `Live`: overlay displays captured region imagery.
- `Hidden`: overlay is not shown.
- `Unavailable Placeholder`: overlay shows a blue background with centered `Not Available`.

### 1.2 State appearance requirements
- Placeholder text is center-aligned and high-contrast against the blue background.
- Placeholder visuals must not include stale captured imagery.
- Live state should prioritize readable content with minimal chrome.

### 1.3 Transition visuals
- State transitions should be immediate and unambiguous.
- Hidden and placeholder states should be visually distinct from live imagery.

---

## 2) Overlay Layout & Composition

### 2.1 Composition
- Overlay content area is the primary visual element.
- Border/chrome should remain minimal and non-distracting.
- Placeholder mode should not introduce extra controls or decorative elements.

### 2.2 Copy and messaging
- Placeholder copy is concise: `Not Available`.
- Copy should avoid technical jargon and remain operator-friendly.

### 2.3 Color usage
- Blue is the canonical unavailable visual treatment.
- Live imagery should preserve source fidelity and avoid tinted overlays unless explicitly configured elsewhere.

---

## 3) Consistency Statements

### 3.1 Cross-view consistency
- Unavailable overlays must communicate the same semantic state as unavailable indicators elsewhere in the UI.
- Terminology remains consistent: `Not Available` for overlay placeholder.

### 3.2 Simplicity
- Overlay presentation should stay minimal (no extra badges, popups, or added UI controls in overlay scope).

### 3.3 Accessibility/readability
- Placeholder text and foreground/background contrast must remain readable at normal operating opacity levels.

---

## 4) Overlay Interaction Design

### 4.1 Per-window interaction model
- Interactions apply per overlay window unless a modifier explicitly enables synchronized behavior.
- Overlay interaction must not alter unrelated windows by default.

### 4.2 Left-click behavior (focus source app)
- **Left click on overlay** activates the monitored source window and brings it to the front.
- If source window is unavailable, no activation occurs and current unavailable visual state remains.

### 4.3 Right-click drag behavior (move overlay)
- **Right-click drag** moves that overlay window.
- Movement is continuous and follows pointer drag with no jump at drag start.
- Movement updates that overlay’s stored position (per window identity).

### 4.4 Combined left+right drag behavior (resize overlay)
- **Left+right click drag together** resizes the overlay.
- Anchor point is the **upper-left corner**; width/height expand or contract relative to that fixed anchor.
- Resize respects minimum/maximum overlay size constraints defined by app limits.

### 4.5 Shift-modified synchronized resize
- **Shift + (left+right drag)** enables synchronized resize mode for all overlays.
- All overlays are first normalized to a shared geometry model, then resized together.
- During synchronized resize, all affected overlays update in real time using the same delta behavior.

### 4.6 Geometry persistence
- Overlay geometry is persisted **per specific monitored window** in config.
- Persisted values include at minimum: `x`, `y`, `width`, `height`.
- On restart/reload, each overlay restores its last saved geometry for that specific window.

### 4.7 Save timing
- Geometry changes from move/resize should be saved on interaction end (mouse/button release).
- Optional debounce during drag is allowed, but final release state is authoritative.

---

## 5) Additional Gaps Closed

### 5.1 Input conflict resolution
- If gesture interpretation is ambiguous, priority order is:
	1. Shift + left+right drag (sync resize)
	2. Left+right drag (single-overlay resize)
	3. Right-click drag (single-overlay move)
	4. Left click (focus source window)

### 5.2 Drag lifecycle rules
- Capture interaction start geometry and pointer origin at gesture start.
- Apply deltas relative to start state to prevent cumulative drift.
- Canceling an interaction reverts to last committed geometry.

### 5.3 Multi-monitor behavior
- Move and resize must remain stable across multi-monitor coordinates.
- Persisted coordinates preserve monitor-space placement.

### 5.4 Unavailable state interaction
- Focus action is disabled when source app is unavailable.
- Move/resize interactions remain available for overlay layout management.

### 5.5 Configuration schema notes
- Geometry is stored under each thumbnail/overlay entry in config.
- Shift synchronized resize updates each affected overlay entry before save.

### 5.6 Acceptance statements for interactions
1. Left-click on overlay brings its source window to front when available.
2. Right-click drag moves only the targeted overlay.
3. Left+right drag resizes only targeted overlay, anchored at upper-left.
4. Shift + left+right drag resizes all overlays together from normalized geometry.
5. After restart, each overlay restores the geometry last saved for that specific window.

---

## 6) Scope Boundary

The following are intentionally **out of scope for dev-new4** and are specified under `dev-new3`:
- Reconnect policy and matching rules.
- Engine/window identity validation behavior.
- Manual reconnect command behavior.
- Runtime acceptance and diagnostics workflows.

---

## 7) Implementation Notes

### 7.1 Recommended event bindings (Tkinter overlay window)
- `left_click_focus`: bind `<Button-1>` on overlay surface.
- `right_drag_move_start`: bind `<ButtonPress-3>`.
- `right_drag_move_update`: bind `<B3-Motion>`.
- `right_drag_move_end`: bind `<ButtonRelease-3>`.
- `left_right_resize_start`: detect both button states during press/motion (platform-safe fallback: use explicit resize handle if dual-button state is unreliable).
- `left_right_resize_update`: apply delta while dual-button condition holds.
- `left_right_resize_end`: commit geometry on release.
- `shift_sync_mode`: evaluate `event.state` for Shift modifier during resize lifecycle.

### 7.2 Gesture state machine (recommended)
- Maintain per-overlay interaction state: `idle | moving | resizing | sync_resizing`.
- Capture at gesture start:
	- pointer origin (`start_x`, `start_y`),
	- geometry snapshot (`start_width`, `start_height`, `start_pos_x`, `start_pos_y`),
	- anchor (`anchor_x`, `anchor_y` = upper-left for resize).
- During motion, compute deltas from start snapshot (not cumulative frame-to-frame).

### 7.3 Resize math (upper-left anchor)
- Anchor remains fixed at `(anchor_x, anchor_y)`.
- Suggested formulas:
	- `new_width = clamp(start_width + delta_x, min_w, max_w)`
	- `new_height = clamp(start_height + delta_y, min_h, max_h)`
- `x` and `y` remain unchanged while resizing in this mode.

### 7.4 Sync resize behavior (Shift)
- Build a target geometry from initiating overlay and apply shared width/height deltas to all overlays.
- Keep each overlay’s own anchor/position unless product decision explicitly requires full geometry normalization.
- If normalized geometry is required, define it as: shared `width`/`height`, per-overlay `x`/`y` retained unless operator explicitly requests alignment.

### 7.5 Activation/focus behavior
- On left click, call window activation for source HWND.
- If activation fails/unavailable, no crash and no geometry change; retain current visual state.

### 7.6 Persistence strategy
- Write geometry at interaction end (`ButtonRelease`), with optional debounce during drag.
- Persist under each thumbnail entry.
- Example config shape:
	- `thumbnails[].position.x`
	- `thumbnails[].position.y`
	- `thumbnails[].size.width`
	- `thumbnails[].size.height`

### 7.7 Suggested helper APIs (non-binding)
- `begin_overlay_move(thumbnail_id, pointer_x, pointer_y)`
- `update_overlay_move(thumbnail_id, pointer_x, pointer_y)`
- `begin_overlay_resize(thumbnail_id, pointer_x, pointer_y, sync=False)`
- `update_overlay_resize(thumbnail_id, pointer_x, pointer_y, sync=False)`
- `commit_overlay_geometry(thumbnail_id)`
- `commit_all_overlay_geometries()`

### 7.8 Edge-case handling notes
- If overlay is hidden/unavailable, move/resize should still operate on geometry model when overlay shell exists.
- Multi-monitor coordinates should remain in virtual desktop space.
- Enforce min/max size limits uniformly for single and sync resize.

---

*End of dev-new4 overlay design statements.*
