# Task 4: Developer View — Action Items and My CRs

Build the developer-focused view with prioritized action items and filtered CR list.

**Files:**
- Modify: `src/cr-tracker.html`

**Interfaces:**
- Consumes: `crs` in-memory array with steps, `teamMembers`, `currentUser`, `LIFECYCLE_TEMPLATE`, `computeCRInfo()`, `completeStep()` (from Task 3), existing view toggle mechanism
- Produces: Developer view UI with action item cards and per-CR compact checklists, filtered by selected developer

## Steps

- [ ] **Step 1: Implement view toggle and developer selector**

The view toggle buttons in the top bar already exist (`.view-toggle-btn` with "PM" and "Dev" text). Wire them to actually switch views:

- When "Dev" is selected, hide the PM-specific content (KPI strip, pipeline table, "Add CR" button) and show the developer view content
- When "PM" is selected, show PM content, hide developer view
- Store current view in `localStorage` key `crTrackerView` (values: "pm" or "dev")
- Restore on page load

Developer View top area shows:
- A developer selector dropdown populated from `teamMembers.filter(m => m.role === 'developer')`. Show it next to the view toggle or below the top bar.
- Store selected developer in `localStorage` key `crTrackerSelectedDev`

When in Dev view, hide "Add CR" and "Manage Team" buttons.

- [ ] **Step 2: Build the "My Action Items" section**

Create a container `#dev-view` (hidden by default). Inside it:

**Section: "My Action Items"**

For the selected developer, find all active CRs where `cr.developer === selectedDeveloper` (the in-memory CR uses `cr.crNumber` for the ID, `cr.developer` for developer name, `cr.change_owner` for change owner). For each CR, find the current actionable step — the first step where:
- status is "pending" or "in_progress" (not "locked" or "completed")
- AND the step's `ownerRole` in LIFECYCLE_TEMPLATE matches a role the developer fills ("AMS Developer", "AMS Developer Peer")

For each actionable step, create a card:

```html
<div class="action-card" style="border-left: 4px solid {urgencyColor}">
  <div class="action-card-header">
    <span class="mono">{crNumber}</span>
    <span class="action-card-desc">{description}</span>
  </div>
  <div class="action-card-step">Step {N}: {stepName}</div>
  <div class="action-card-meta">
    Pending {days} days · {phase} phase
    {hint text if available}
  </div>
  <div class="action-card-footer">
    <textarea class="action-comment" placeholder="Add a comment (optional)" rows="1"></textarea>
    <button class="btn btn-primary btn-sm" onclick="completeStep('{crNumber}', {stepNum})">Mark Complete</button>
  </div>
</div>
```

Urgency levels (determines border color and sort order):
- **Critical** (red, `--status-blocked`): step days pending > threshold from template
- **Warning** (amber, `--status-risk`): days > 50% of threshold
- **Normal** (green, `--status-ok`): within threshold

Sort: critical first, then warning, then normal. Within each level, by days pending descending.

Add CSS for `.action-card`, `.action-card-header`, `.action-card-step`, `.action-card-meta`, `.action-card-footer`.

- [ ] **Step 3: Build the "My CRs" section**

Below action items, add a "My CRs" section showing a compact lifecycle view for each of the developer's assigned CRs.

Each CR gets a card:
- Header: CR number (mono) + description
- A horizontal phase progress bar (5 segments, same as pipeline table but wider)
- Compact step summary per phase:
  - For completed phases: "4/4 Scope steps complete" with a green check
  - For the current phase: list individual steps with status icons
  - For future phases: show as dimmed "0/N steps"

This gives the developer a quick overview without the full PM-level detail.

- [ ] **Step 4: Handle empty states**

If the selected developer has no pending action items:
"All caught up — no pending actions for {name}."

If the developer has no CRs at all:
"No CRs assigned to {name}."

Style empty states with muted text, centered.

- [ ] **Step 5: Commit**

```bash
git add src/cr-tracker.html
git commit -m "feat: developer view with prioritized action items and my CRs"
```

## Existing patterns

- View toggle: `.view-toggle-btn.active` marks the active tab
- Responsive: hide secondary columns at 560px, stack grids at smaller
- DB not needed for this task — developer view is purely computed from in-memory `crs` data
- `completeStep()` is async — the onclick should work with it naturally
- Use `computeCRInfo(cr)` to get current step, phase, status, daysPending
