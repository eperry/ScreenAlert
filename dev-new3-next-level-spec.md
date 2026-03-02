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

---

## 9) Validation Notes

- Automated suite: `pytest -q tests` passing (`10 passed`).
- Manual checks completed:
  - Add Window list population and inline size display.
  - Persistent filter restore.
  - Repeated TTS dispatch on recurring alert cycles.

---

*End of next-level specification.*
