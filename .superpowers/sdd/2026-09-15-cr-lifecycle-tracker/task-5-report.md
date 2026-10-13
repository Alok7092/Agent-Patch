# Task 5 Report

## Status: DONE

## Commits:
- `2c1e3dd` feat: audit log viewer — per-CR and global activity log

## Test summary:

### Per-CR Activity Log (Step 1)
- `buildPerCRAuditSection(crId)` filters `auditLog` by `cr_number === crId`, sorted newest-first
- Renders in the collapsed "Activity Log" section appended below the step checklist in `buildDetailInner()`
- Collapsible toggle with chevron rotation; `aria-expanded` updated on toggle
- Override entries (`gate_overridden`) get amber left border + reason text below the action
- Skipped entries (`step_skipped`) get muted grey left border
- Timestamp formatted with month/day + 12h time via `formatAuditTimestamp()`
- When DB unavailable: shows "Activity log requires database connection."
- When no entries yet: shows "No activity recorded yet."
- Entry count badge shown in toggle label

### Global Audit Panel (Step 2)
- "Activity" button added to `.top-bar-controls` (id `btn-activity`), hidden by default
- `setView()` shows/hides button based on PM vs. dev view; also closes panel on view switch
- Slide-out panel (`aside.audit-panel`) fixed to right edge with scrim overlay behind it
- Shows last 50 entries across all CRs, newest-first
- Filter chips: All / Completions / Overrides / CR Created
- Dismiss: X button, Escape key (wired into existing keydown handler), click-outside scrim
- Each row shows: CR number (mono accent), actor + action, timestamp
- Override and skipped rows styled consistently with per-CR panel

### In-Memory Cache (Step 3)
- `auditLog = []` state variable added alongside `crs`/`teamMembers`
- `_auditFilter = 'all'` tracks current chip selection
- `loadAuditLog()` called in `boot()` after `loadCRs()` — lists `audit` collection, normalises row shape, sorts newest-first
- All five audit-writing sites now call `auditLog.unshift({ id, ...entry })` immediately after DB write:
  - `saveCR()` (cr_created)
  - `cancelCR()` (cr_cancelled)
  - `completeStep()` (step_completed)
  - `skipStep()` (step_skipped)
  - `confirmGateOverride()` (gate_overridden)

## Concerns:
- None. DB unavailability handled defensively throughout; all dynamic HTML goes through `escHtml()`/`escAttr()`. Responsive down to ~400px (panel width uses `min(480px, 100vw)`). Dark-mode uses existing CSS token variables.
