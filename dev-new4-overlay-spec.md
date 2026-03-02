# ScreenAlert: Overlay Reliability & UX Specification (dev-new4)

## Overview

This document defines the `dev-new4` scope focused on overlay robustness, clarity, and operator control.

Primary goals:
1. Ensure overlay visuals always reflect true attachment state.
2. Standardize unavailable/reattach transitions without stale imagery.
3. Improve reconnect/operator workflows for single-window and bulk recovery.
4. Keep status semantics consistent between cards, aggregate badge, and overlays.

Date: March 2, 2026

---

## 1) Overlay State Model

### 1.1 Required states
Each overlay must support explicit runtime states:
- `available`: live image updates are shown.
- `unavailable-hidden`: overlay window is hidden while source is unavailable.
- `unavailable-placeholder`: overlay remains visible with blue `Not Available` placeholder.

### 1.2 Source of truth
- Availability is determined by strict window identity validation and successful capture.
- Overlay state must not be inferred solely from cached image presence.

### 1.3 Queue hygiene
- On transition to unavailable, pending image queue entries are cleared.
- Returning to available requires a fresh valid capture before live image display resumes.

---

## 2) Identity & Reconnect Contract

### 2.1 Strict identity
A monitored window is considered valid only when:
- Title matches exactly (case-insensitive, trimmed).
- Resolution matches exactly (`width x height`).
- Optional persisted metadata checks (class/monitor) may be enforced when present.

### 2.2 No fallback matching
- No partial-title, fuzzy, or largest-window fallback is allowed during auto reconnect.

### 2.3 Retry policy
- Automatic reconnect is one-shot per loss event.
- After failure, recovery is manual via reconnect commands.

---

## 3) UI/UX Requirements

### 3.1 Unavailable overlay setting
- Add/retain setting: `Show Overlay if Unavailable`.
- `false`: hide overlay when unavailable.
- `true`: show blue placeholder with centered `Not Available` text.

### 3.2 Status semantics
- Region card unavailable status is blue `N/A`.
- Aggregate badge is blue `Overall: N/A` when no active monitored region has a valid source.

### 3.3 Reconnect controls
- `Edit -> Reconnect All Windows` reconnects all configured windows.
- `Windows -> All` context reconnects all configured windows.
- `Windows -> <window>` context reconnects only selected window.

---

## 4) Functional Acceptance Criteria

1. No stale image remains visible after source window becomes unavailable.
2. Overlay behavior follows setting (`hidden` vs `blue placeholder`) exactly.
3. Auto reconnect does not attach to near-match windows.
4. Auto reconnect attempts once per loss event, then stops retrying.
5. Manual reconnect-all and reconnect-single commands operate on correct scope.
6. UI preview and region thumbnails never display image from a window failing strict identity.
7. Region and aggregate unavailable statuses are consistently blue.

---

## 5) Non-goals / Out of Scope

- No redesign of image detection algorithms.
- No introduction of advanced fuzzy matching heuristics.
- No additional overlay themes/colors beyond current design language.

---

## 6) Validation Plan

### Manual scenarios
1. Attach window, confirm live overlay image.
2. Close/rename/resize source window to break identity.
3. Verify overlay transitions to hidden or blue placeholder per setting.
4. Verify region/aggregate statuses change to blue `N/A`.
5. Confirm no repeated auto reconnect attempts after one failure.
6. Use reconnect-single on one window node; verify only that node reconnects.
7. Use reconnect-all; verify all configured windows are attempted.
8. Restore exact title+size source; confirm manual reconnect succeeds and live imagery resumes.

### Technical checks
- Compile changed UI/engine/renderer modules.
- Confirm no new errors in modified files.

---

## 7) Engineering Decisions

### 7.1 Overlay availability as first-class state
- **Decision:** Track availability independently from image buffers.
- **Reason:** Prevent stale-frame persistence and ambiguous UI behavior.

### 7.2 Deterministic reconnect behavior
- **Decision:** Enforce strict identity with no fallback.
- **Reason:** Prioritize correctness and process fidelity over aggressive auto-reattach.

### 7.3 Operator-driven recovery after failure
- **Decision:** Use one-shot auto reconnect and manual command for further attempts.
- **Reason:** Reduces churn and gives explicit operator control.

---

*End of dev-new4 overlay specification.*
