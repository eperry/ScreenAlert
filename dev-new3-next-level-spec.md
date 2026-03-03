# ScreenAlert: Next-Level Changes Specification (dev-new3)

## Overview

This document defines the **next set of changes** after the completed `dev-new2` work.  
Primary goals:

1. Finalize alert-triggered TTS behavior at region level.
2. Move main-screen action buttons into menu/context-menu workflows.
3. Improve region-card form clarity with explicit labels.
4. Add file and help menu actions for save/save-as and logs access.

Date: March 2, 2026

## Implementation Status (March 2, 2026)

Status for this spec: **Implemented and stabilized**.

Implemented beyond the initial draft:
- Add Window dialog now renders each window as two lines (title + indented size line) instead of using a separate details panel.
- Add Window filters are persisted to config (`last_window_filter`, `last_window_size_filter_op`, `last_window_size_filter_value`).
- Size filtering operators `==`, `<=`, `>=` are supported using `WIDTHxHEIGHT` input.
- Selected window metadata (`window_class`, `window_size`, `monitor_id`) is passed from selection UI into thumbnail creation and persisted for reconnect matching.
- TTS dispatch logging was added for runtime diagnostics.
- Edit menu pause command is dynamic (`Pause All` / `Resume All`) based on live engine state.
- Main bottom status line is split into two objects: left status message and right aggregate badge with state color coding.
- `Windows -> All` now hides Window Info and expands Regions to full available right-panel height.
- Selecting a region node renders only that single region card for focused editing.
- Window Info was compacted and now includes `Size: WIDTHxHEIGHT`.
- Region cards were visually tightened (spacing, control widths, preview sizing) for denser layout.
- Scrollbars now auto-hide when content fully fits (main tree, main region list, Add Window list, Region Editor canvas/list).
- Unavailable-window overlay behavior is configurable: hide overlay when unattached, or show blue placeholder with `Not Available`.
- Region and aggregate `N/A` states are now blue for consistency.
- Reconnect behavior is strict and deterministic: exact title + exact size matching only, no fallback matching.
- Automatic reconnect is one-shot per loss event (no repeated auto-retry loops after failure).
- UI preview and region-card image paths enforce strict window identity validation to prevent stale/wrong HWND imagery.
- Reconnect actions were added: Edit menu + `Windows -> All` context reconnect all, while window-node context reconnects only the selected window.

---

---

## 1) Text-to-Speech (TTS) Requirements

### 1.1 Trigger
- TTS triggers when an **Alert** event happens for a region.

### 1.2 Spoken content
- Spoken text is generated from a per-region template.
- Default template per region:
  - `Alert {window} {region_name}`
- Users can append any extra text.

### 1.3 Per-region editable text field
- Each region card must include an editable text input for TTS text.
- Field value is persisted in config per region.
- On new region creation, default to `Alert {window} {region_name}`.

### 1.4 Template variables
- Supported placeholders:
  - `{window}` = monitored window title
  - `{region_name}` = region display name
- Unknown placeholders are left as literal text.

### 1.5 Persistence
- Save/reload this per-region TTS text in config file.
- Existing regions with missing field should auto-default on load.

---

## 2) Main UI Action Relocation (Buttons off main screen)

### 2.1 Remove top action buttons
- Remove these buttons from the top control area:
  - Add Window
  - Pause All
  - Add Region
  - Remove Region
  - Remove Window
  - Settings

### 2.2 Menu placement

#### Edit menu
- Add Window
- Pause All
- Settings

#### File menu
- Save
- Save As

#### Help menu
- Logs (opens log folder in Windows File Explorer)

### 2.3 Context-menu placement (Tree view)

#### `Windows -> ALL` right-click
- Add Window
- Pause All
- Remove Window (for selected window where applicable)

#### `Windows -> <window name>` right-click
- Add Region
- Remove All Regions

#### `Windows -> <window name> -> <region name>` right-click
- Remove Region

Notes:
- Context options should be enabled/disabled based on selection type.
- If a command is invalid for current selection, it should be disabled (not hidden).

---

## 3) Region Card Labeling Updates

### 3.1 Name field label
- Add a visible label next to the region name editor.
- Label text: `Name:`

### 3.2 Alert text field label
- Add a visible label next to the region alert/TTS text editor.
- Label text: `Alert Text:`

---

## 4) Menu Command Behavior Details

### 4.1 Save
- Immediate save of current config to active config path.

### 4.2 Save As
- Prompts user for destination file path.
- Writes full config snapshot to chosen location.

### 4.3 Help -> Logs
- Opens `%APPDATA%\ScreenAlert\logs` in Windows File Explorer.
- If folder does not exist, create it first, then open.

---

## 5) Acceptance Criteria

### TTS
- Alert in any region plays TTS based on that region’s template.
- Editing region TTS text persists after app restart.
- Default template appears for newly created regions.
- Repeated alert cycles (re-entering ALERT after WARNING/OK) must continue producing TTS, not only the first alert.

### UI relocation
- No main-screen action buttons remain for Add/Pause/Add Region/Remove Region/Remove Window/Settings.
- Commands are available via menus and tree right-click exactly as specified.

### Region card labels
- `Name:` label appears next to region name field.
- `Alert Text:` label appears next to region TTS text field.

### Menu actions
- File -> Save works.
- File -> Save As works.
- Help -> Logs opens the logs directory in Explorer.

### Add Window dialog
- Dialog does not include a separate "Window Details" section.
- Each list item shows title with an indented size line beneath it.
- Filter text and size filter inputs persist across dialog opens and app restarts.
- Size filter compares width and height directly based on selected operator.

### Selection and layout behavior
- Bottom aggregate status appears on the right of the same status line and keeps color-coded state.
- `All` selection uses full right-panel height for region content.
- Region-node selection shows only the selected region card.
- Window Info displays attached window size (`WIDTHxHEIGHT`).

### Scrollbar behavior
- Any visible scrollbar in active UI surfaces auto-hides when there is nothing to scroll.
- Scrollbar reappears automatically when content exceeds the viewport.

### Unavailable overlay behavior
- When monitored source window is unavailable, stale imagery is never displayed.
- If `Show Overlay if Unavailable` is disabled, overlay windows are hidden until source becomes available.
- If enabled, overlays remain visible and render a blue `Not Available` placeholder.

### Reconnect behavior
- Auto reconnect uses exact title + exact size matching and never falls back to loose/partial matching.
- After one failed auto reconnect attempt for a loss event, no additional automatic attempts are made.
- Manual reconnect commands are available for both all windows and a single selected window.

### Status behavior
- Region `N/A` uses blue styling.
- Aggregate status becomes blue `Overall: N/A` when no active monitored region has a valid attached source window.

---

## 6) Non-goals / Out of Scope

- No redesign of alert state machine behavior in this phase.
- No changes to detection algorithms in this phase.
- No changes to aggregate-status priority rules in this phase.

---

## 7) Suggested Implementation Order

1. Add menu/context-menu command wiring.
2. Remove top-button controls and related tooltips.
3. Add region card labels + per-region alert text field.
4. Wire TTS template rendering and persistence.
5. Add File Save/Save As and Help Logs handlers.
6. Validate with manual flows and existing tests.

---

## 8) Engineering Decisions

### 8.1 TTS backend reliability on Windows
- **Problem:** pyttsx3/SAPI behavior intermittently stalled or failed on repeated alerts in this environment.
- **Decision:** Use Windows `System.Speech` via isolated PowerShell invocation for each TTS utterance on Windows.
- **Rationale:** Avoids pyttsx3 run-loop deadlock/re-entry failure modes observed during repeated alert cycles.
- **Consequence:** Keeps repeat alert speech reliable; introduces external process invocation overhead per utterance.

### 8.2 Dialog filtering semantics
- **Decision:** Size filter input is parsed as `WIDTHxHEIGHT`; invalid/partial input is treated as "no size filter".
- **Decision:** Size rows are display rows only; selection resolves to the corresponding title/window entry.
- **Rationale:** Keeps filtering predictable while preventing accidental blank lists during partial typing.

### 8.3 Window identity persistence
- **Decision:** Persist selected metadata (`window_class`, `window_size`, `monitor_id`) at add-window time, with live metadata fallback in engine.
- **Rationale:** Improves reconnection precision when multiple windows share similar titles.

### 8.4 Auto-hide scrollbar standardization
- **Decision:** Introduced reusable `AutoHideScrollbar` for Tk/ttk views and switched active UI scrollbars to it.
- **Rationale:** Removes unnecessary visual noise while preserving expected scroll behavior when content overflows.
- **Consequence:** All major list/canvas views now adapt scrollbar visibility dynamically without custom per-view hacks.

### 8.5 Strict window identity policy
- **Decision:** Window identity validation and reconnect matching are strict: exact title and exact size are required (with optional class/monitor checks when available).
- **Rationale:** Prevents accidental attachment to wrong process windows that share similar titles.
- **Consequence:** No partial/heuristic fallback reconnect path is permitted.

### 8.6 Reconnect retry policy
- **Decision:** Auto reconnect is attempted once per loss event; failed attempts are not retried automatically.
- **Rationale:** Avoids repeated churn/noise and makes recovery operator-driven when strict identity cannot be satisfied.
- **Consequence:** Manual reconnect commands are the intended recovery action after failure.

### 8.7 Unavailable overlay presentation
- **Decision:** Added `show_overlay_when_unavailable` setting controlling whether overlays are hidden or display a blue `Not Available` placeholder.
- **Rationale:** Supports two operator preferences without allowing stale image persistence.
- **Consequence:** Renderer tracks thumbnail availability state separately from image queue content and clears queued stale frames on unavailable transition.

---

## 9) Validation Notes

- Automated suite: `pytest -q tests` passing (`10 passed`).
- Manual checks completed:
  - Add Window list population and inline size display.
  - Persistent filter restore.
  - Repeated TTS dispatch on recurring alert cycles.

---

## 10) Migrated from dev-new4 (Non-design Runtime Behavior)

The following operational/runtime requirements were moved from `dev-new4` so that `dev-new4` remains design-only.

### 10.1 Identity & reconnect contract
- A monitored window is valid only when strict identity checks pass (exact title + exact size, with optional class/monitor checks when available).
- No fallback matching is allowed for automatic reconnect (no fuzzy, partial-title, or largest-window fallback).
- Automatic reconnect is one-shot per loss event; after failure, recovery is manual.

### 10.2 Reconnect command behavior
- `Edit -> Reconnect All Windows` reconnects all configured windows.
- `Windows -> All` context action reconnects all configured windows.
- `Windows -> <window>` context action reconnects only the selected window.

### 10.3 Runtime acceptance criteria (migrated)
- No stale image remains visible after source window becomes unavailable.
- Overlay behavior follows the unavailable setting exactly (hide vs blue placeholder).
- Automatic reconnect never attaches to near-match windows.
- Automatic reconnect attempts once per loss event and does not continue retrying.
- UI preview and region thumbnails must not display imagery when strict identity fails.

### 10.4 Validation scenarios (migrated)
1. Attach window and confirm live overlay image.
2. Break identity by title/size change and verify unavailable behavior.
3. Verify no repeated auto reconnect attempts after one failed automatic attempt.
4. Verify reconnect-single affects only selected window.
5. Verify reconnect-all attempts all configured windows.
6. Restore exact title+size and verify manual reconnect succeeds.

---

*End of next-level specification.*
