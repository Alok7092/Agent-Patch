# CR Lifecycle Tracker — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build an interactive artifact dashboard that enforces the 24-step CR lifecycle through hard gates and automated Outlook email alerts, serving both a PM overview and a developer action-items view.

**Architecture:** A single Claude artifact (HTML page) with `db` and `user` capabilities for shared persistent state. The dashboard reads/writes CR and step data through the artifact's runtime DB. A separate Claude-side alert engine reads the same DB and dispatches Outlook emails via MCP for handoffs, overdue items, and deadline warnings.

**Tech Stack:** HTML/CSS/JS (vanilla — no framework), Claude artifact runtime (`window.claude.db`, `window.claude.user`), Outlook MCP for email alerts, Google Fonts for typography.

**Spec:** `docs/superpowers/specs/2026-09-14-cr-lifecycle-tracker-design.md`

## Global Constraints

- Single HTML file published as a Claude artifact — no build step, no bundler, no framework.
- All state lives in the artifact DB (`window.claude.db`) — no localStorage for app state (localStorage only for UI preferences like view toggle).
- External scripts only from `cdnjs.cloudflare.com` — but this project needs none.
- Google Fonts only external stylesheet allowed.
- Must work at phone width (~400px) and support light/dark themes.
- The artifact `capabilities` declaration must include `db` and `user`.
- `currentUser` throughout the app refers to the name selected in the view's user/developer selector (stored in `localStorage`), NOT the `window.claude.user` identity. The `user` capability is declared so the DB can scope per-user data if needed later, but the primary identity mechanism is the dropdown selector.
- All 24 lifecycle steps, their phases, owners, hard gate prerequisites, and overdue thresholds are embedded as a constant in the page code — the template is the source of truth.
- CR numbers entered by users (free text, e.g., "CHG0012345") — no auto-generation.

---

## File Structure

| File | Responsibility |
|------|---------------|
| `src/cr-tracker.html` | The complete artifact: markup, styles, and all application logic in one file. Published via the Artifact tool. |
| `docs/superpowers/plans/alert-engine-runbook.md` | Instructions for the PM to trigger Claude-powered monitoring and email alerts. Not code — a runbook. |

The artifact is self-contained. The alert engine is conversational — the PM asks Claude to "check my CRs" or starts a `/loop`, and Claude reads the artifact DB and sends emails through Outlook MCP.

## DB Collections

| Collection | Document ID | Contents |
|------------|-------------|----------|
| `crs` | `{crNumber}` (e.g., `CHG0012345`) | CR metadata: description, developer, developer_email, change_owner, change_owner_email, target_release_date, created_date, status |
| `crs/{crNumber}/steps` | `step_{nn}` (e.g., `step_05`) | Step state: status, completed_date, completed_by, comment, override_reason |
| `audit` | auto-generated timestamp ID | action, cr_number, actor, details, timestamp |
| `team` | `{name}` | Team member record: name, email, role (pm / developer / change_owner) |

Steps carry only mutable state — the step's name, phase, owner_role, prerequisites, thresholds, and hard_gate flag are all derived from the embedded template constant and never stored in the DB.

---

### Task 1: Artifact Foundation — Shell, Tokens, Layout, Team Setup

Build the HTML skeleton with the design system, theme support, empty view scaffolding, and the team-member management needed before any CRs can be created.

**Files:**
- Create: `src/cr-tracker.html`

**Interfaces:**
- Consumes: nothing (first task)
- Produces: Published artifact URL with `db` and `user` capabilities. A working page with top bar, view toggle, empty KPI card row, empty table area, and a "Manage Team" flow for adding team members (name + email + role). Team members stored in `team` collection. The `LIFECYCLE_TEMPLATE` constant (array of 24 step definitions) available to all later code.

**Design tokens:**

```
Color palette (light):
  --surface:        #F6F7F9    (cool grey ground — not pure white)
  --surface-raised: #FFFFFF    (cards)
  --text:           #1A1D23    (near-black with a blue cast)
  --text-muted:     #6B7280    (secondary text)
  --border:         #E2E5EB    (subtle dividers)
  --accent:         #4361EE    (action blue — buttons, links, active phase)
  --accent-hover:   #3A56D4

Phase colors (constant across themes):
  --phase-scope:      #6366F1  (indigo)
  --phase-build:      #8B5CF6  (violet)
  --phase-test:       #F59E0B  (amber)
  --phase-golive:     #F97316  (orange)
  --phase-validation: #10B981  (emerald)

Status colors:
  --status-ok:      #10B981  (on track — emerald)
  --status-risk:    #F59E0B  (at risk — amber)
  --status-blocked: #EF4444  (blocked — red)
  --status-locked:  #9CA3AF  (locked — grey)

Dark theme overrides:
  --surface:        #111318
  --surface-raised: #1A1D25
  --text:           #E8EAED
  --text-muted:     #9CA3AF
  --border:         #2D3139
```

Typography:
- **Display / headings:** `Inter` (variable weight, tight tracking for headings)
- **Monospace (CR numbers, dates, data):** `JetBrains Mono`
- Both from Google Fonts. Fallback: system-ui, -apple-system, sans-serif / ui-monospace, monospace.

Layout:
- Max content width 1200px, centered with 24px side padding.
- KPI cards: CSS grid, 4 columns on desktop, 2 on tablet, 1 on phone.
- Pipeline table: full width, rows expand on click.
- Top bar: sticky, with title left, controls right.

- [ ] **Step 1: Create the HTML file with design tokens and theme support**

Write `src/cr-tracker.html` with:
- `<title>CR Lifecycle Tracker</title>`
- Google Fonts link for Inter (weights 400, 500, 600, 700) and JetBrains Mono (400, 500)
- Full CSS token system in `:root`, `@media (prefers-color-scheme: dark)` guarded as `:root:not([data-theme="light"])`, and `:root[data-theme="dark"]`
- Body with explicit background from token, 24px side padding via `padding-inline`, `padding-block` for vertical
- Top bar (sticky): "CR Lifecycle Tracker" title, view toggle (PM / Developer), "Add CR" button (disabled until team exists), "Manage Team" button
- KPI card row: 4 placeholder cards (Total, On Track, At Risk, Blocked) showing "—"
- Empty pipeline table area with column headers: CR #, Description, Phase, Current Step, Owner, Status, Days, Deadline
- Empty state message: "No CRs yet. Add your first CR to get started."

- [ ] **Step 2: Embed the LIFECYCLE_TEMPLATE constant**

Add a `<script>` section with `LIFECYCLE_TEMPLATE` — an array of 24 objects:

```javascript
const LIFECYCLE_TEMPLATE = [
  {
    step: 1,
    name: "Create CR/CD by filling out ServiceNow form",
    phase: "Scope",
    ownerRole: "Change Owner",
    crStatus: "New",
    cdStatus: "-",
    hardGate: false,
    prerequisites: [],
    overdueThresholdDays: 3,
    hint: "Developer will request for CR/CD creation in a mail with FS/TS sharepoint link"
  },
  {
    step: 2,
    name: "Create FS/TS document with test cases",
    phase: "Scope",
    ownerRole: "AMS Developer",
    crStatus: "New",
    cdStatus: "Created",
    hardGate: false,
    prerequisites: [],
    overdueThresholdDays: 3,
    hint: "If same object is locked by Project team, align with Project team and inform business with expected release date"
  },
  {
    step: 3,
    name: "Request peer review of FS/TS",
    phase: "Scope",
    ownerRole: "AMS Developer",
    crStatus: "New",
    cdStatus: "Created",
    hardGate: false,
    prerequisites: [],
    overdueThresholdDays: 3,
    hint: ""
  },
  {
    step: 4,
    name: "Request review of FS/TS by HSY IS",
    phase: "Scope",
    ownerRole: "AMS Developer",
    crStatus: "New",
    cdStatus: "Created",
    hardGate: false,
    prerequisites: [],
    overdueThresholdDays: 3,
    hint: "Get the FS/TS approved by IS. TS can have basic details on design and approach."
  },
  {
    step: 5,
    name: "Begin development",
    phase: "Build",
    ownerRole: "AMS Developer",
    crStatus: "New",
    cdStatus: "DEV: TR create/develop",
    hardGate: true,
    prerequisites: [3, 4],
    overdueThresholdDays: 3,
    hint: ""
  },
  {
    step: 6,
    name: "Development complete (ATC Check)",
    phase: "Build",
    ownerRole: "AMS Developer",
    crStatus: "New",
    cdStatus: "DEV: TR create/develop",
    hardGate: false,
    prerequisites: [],
    overdueThresholdDays: 3,
    hint: "Include the ATC check excel file in the CR folder"
  },
  {
    step: 7,
    name: "Request peer code review",
    phase: "Build",
    ownerRole: "AMS Developer Peer",
    crStatus: "New",
    cdStatus: "DEV: TR create/develop",
    hardGate: false,
    prerequisites: [],
    overdueThresholdDays: 3,
    hint: ""
  },
  {
    step: 8,
    name: "Perform unit testing",
    phase: "Build",
    ownerRole: "AMS Developer",
    crStatus: "New",
    cdStatus: "DEV: TR create/develop",
    hardGate: false,
    prerequisites: [],
    overdueThresholdDays: 3,
    hint: ""
  },
  {
    step: 9,
    name: "Release transport tasks, move CD to QA",
    phase: "Test",
    ownerRole: "AMS Developer",
    crStatus: "New",
    cdStatus: "QA: Main TR imported",
    hardGate: true,
    prerequisites: [6, 7, 8],
    overdueThresholdDays: 2,
    hint: ""
  },
  {
    step: 10,
    name: "Request CoE team for Live Compare result",
    phase: "Test",
    ownerRole: "AMS Developer",
    crStatus: "Assess",
    cdStatus: "QA: Main TR imported",
    hardGate: false,
    prerequisites: [],
    overdueThresholdDays: 2,
    hint: "Reach out to Vibin Ravi (vravi@hersheys.com) for Live Compare"
  },
  {
    step: 11,
    name: "Create qTest test cases",
    phase: "Test",
    ownerRole: "AMS Developer",
    crStatus: "Assess",
    cdStatus: "QA: Main TR imported",
    hardGate: false,
    prerequisites: [],
    overdueThresholdDays: 2,
    hint: ""
  },
  {
    step: 12,
    name: "Add qTest test cases per Live Compare results",
    phase: "Test",
    ownerRole: "AMS Developer",
    crStatus: "Assess",
    cdStatus: "QA: Main TR imported",
    hardGate: false,
    prerequisites: [],
    overdueThresholdDays: 2,
    hint: ""
  },
  {
    step: 13,
    name: "Perform SIT, document results in qTest and CR",
    phase: "Test",
    ownerRole: "AMS Developer",
    crStatus: "Assess",
    cdStatus: "QA: Main TR imported",
    hardGate: false,
    prerequisites: [],
    overdueThresholdDays: 2,
    hint: ""
  },
  {
    step: 14,
    name: "Request qTest results review by HSY IS L4 (optional)",
    phase: "Test",
    ownerRole: "AMS Developer",
    crStatus: "Assess",
    cdStatus: "QA: Main TR imported",
    hardGate: false,
    prerequisites: [],
    overdueThresholdDays: 2,
    optional: true,
    hint: ""
  },
  {
    step: 15,
    name: "UAT begins",
    phase: "Test",
    ownerRole: "HSY Business Users",
    crStatus: "Assess",
    cdStatus: "QA: Main TR imported",
    hardGate: false,
    prerequisites: [],
    overdueThresholdDays: 2,
    hint: "UAT mail should be sent out a week in advance of production release date"
  },
  {
    step: 16,
    name: "UAT Signoff",
    phase: "Test",
    ownerRole: "HSY Business Users",
    crStatus: "Assess",
    cdStatus: "QA: Main TR imported",
    hardGate: false,
    prerequisites: [],
    overdueThresholdDays: 2,
    hint: "If UAT is not signed off by Thursday, request CR/CD push out"
  },
  {
    step: 17,
    name: "Request review by HSY IS L4, move CD to PreProd Review",
    phase: "Go-live",
    ownerRole: "AMS Change Owner",
    crStatus: "Assess",
    cdStatus: "PreProd Review",
    hardGate: true,
    prerequisites: [13, 16],
    overdueThresholdDays: 1,
    hint: "Before requesting IS approval: ensure qTest is updated in CR, FS/TS link in CR description, ATC check done, CD in PreProd Review status"
  },
  {
    step: 18,
    name: "IS L4 approves or escalates to CAB, move CD to HSY Quality Approval",
    phase: "Go-live",
    ownerRole: "HSY IS L4",
    crStatus: "Assess",
    cdStatus: "HSY Quality Approval",
    hardGate: false,
    prerequisites: [],
    overdueThresholdDays: 1,
    hint: "Follow up with IS to get CR in Authorize status and CD in HSY Quality Approval by Thursday"
  },
  {
    step: 19,
    name: "CR & CD goes to CAB (if qualifies)",
    phase: "Go-live",
    ownerRole: "AMS Change Owner",
    crStatus: "Authorize",
    cdStatus: "HSY Quality Approval",
    hardGate: false,
    prerequisites: [],
    overdueThresholdDays: 1,
    hint: "Change owner to present the CR in CAB"
  },
  {
    step: 20,
    name: "CAB approves or rejects",
    phase: "Go-live",
    ownerRole: "HSY Release Managers",
    crStatus: "Authorize",
    cdStatus: "HSY Quality Approval",
    hardGate: false,
    prerequisites: [],
    overdueThresholdDays: 1,
    hint: ""
  },
  {
    step: 21,
    name: "CR & CD released into production, CD to Deploy",
    phase: "Validation",
    ownerRole: "Basis / HSY Release Managers",
    crStatus: "Implement",
    cdStatus: "Deploy",
    hardGate: false,
    prerequisites: [],
    overdueThresholdDays: 3,
    hint: ""
  },
  {
    step: 22,
    name: "AMS team validates post release, CD to Imported into Production",
    phase: "Validation",
    ownerRole: "Basis / HSY Release Managers",
    crStatus: "Implement",
    cdStatus: "Imported into Production",
    hardGate: false,
    prerequisites: [],
    overdueThresholdDays: 3,
    hint: ""
  },
  {
    step: 23,
    name: "Business users validate, CD to Completed",
    phase: "Validation",
    ownerRole: "Basis / HSY Release Managers",
    crStatus: "Implement",
    cdStatus: "Completed",
    hardGate: false,
    prerequisites: [],
    overdueThresholdDays: 3,
    hint: ""
  },
  {
    step: 24,
    name: "Request HSY IS for CR closure",
    phase: "Validation",
    ownerRole: "AMS Change Owner",
    crStatus: "Closed",
    cdStatus: "Completed",
    hardGate: true,
    prerequisites: [22, 23],
    overdueThresholdDays: 3,
    hint: "Make sure Live Task and QCoE task is completed before requesting HSY IS for CR closure"
  }
];
```

- [ ] **Step 3: Build the team management UI**

Add a "Manage Team" modal that lets the PM add team members before creating CRs:
- Modal with form: Name, Email, Role dropdown (PM / Developer / Change Owner)
- "Add Member" button saves to `team` collection via `window.claude.db`
- List of current team members with delete option
- On page load, fetch team members from DB to populate dropdowns elsewhere
- The "Add CR" button stays disabled until at least one team member with role "Developer" and one with role "Change Owner" exist

- [ ] **Step 4: Publish the artifact and verify**

Publish `src/cr-tracker.html` as an artifact with capabilities `{ "db": {}, "user": {} }`.

Verify:
- Page loads with correct typography (Inter headings, JetBrains Mono for data)
- Light and dark themes both render correctly
- Top bar is sticky with title, view toggle, and buttons
- KPI cards show "—" placeholder values
- Empty state message displays
- "Manage Team" opens a modal, can add a team member, member persists on reload
- "Add CR" is disabled until team has a developer and change owner

- [ ] **Step 5: Commit**

```bash
git add src/cr-tracker.html
git commit -m "feat: CR lifecycle tracker — artifact foundation with design system, team management, and lifecycle template"
```

---

### Task 2: CR Creation and Pipeline Table

Add the ability to create CRs and display them in the PM pipeline table.

**Files:**
- Modify: `src/cr-tracker.html`

**Interfaces:**
- Consumes: `LIFECYCLE_TEMPLATE` constant, `team` collection (for developer/owner dropdowns), `window.claude.db` for persistence
- Produces: CR documents in `crs` collection, 24 step documents per CR in `crs/{crNumber}/steps` collection, rendered pipeline table rows with phase progress bars

- [ ] **Step 1: Build the "Add CR" modal form**

When the user clicks "Add CR", show a modal with:
- CR Number (text input — free-form, e.g., "CHG0012345")
- Description (text input)
- Developer (dropdown populated from `team` collection, filtered to role=developer)
- Change Owner (dropdown populated from `team` collection, filtered to role=change_owner)
- Target Release Date (date picker — defaults to next Thursday)
- "Create" and "Cancel" buttons

Validation: CR Number required and unique (check DB before saving). Description required.

- [ ] **Step 2: Implement CR creation logic**

On "Create":
1. Save CR document to `crs/{crNumber}` with fields: description, developer, developer_email, change_owner, change_owner_email, target_release_date, created_date (today), status ("active")
2. Create 24 step documents in `crs/{crNumber}/steps` collection. Each step document (`step_01` through `step_24`) stores only mutable state:
   ```javascript
   {
     status: "pending",  // or "locked" if step has prerequisites and they aren't met
     completed_date: null,
     completed_by: null,
     comment: "",
     override_reason: null
   }
   ```
   Step 1 starts as "pending". Steps with `hardGate: true` and unmet prerequisites start as "locked". All others start as "pending".
3. Write an audit log entry: `{ action: "cr_created", cr_number, actor: currentUser, details: "CR created", timestamp: now }`
4. Close modal and refresh the pipeline table.

- [ ] **Step 3: Render the pipeline table**

On page load (and after any CR mutation), fetch all docs from `crs` collection and their steps. For each active CR, render a table row:

- **CR #**: monospace, clickable (expands detail — Task 3)
- **Description**: truncated to ~40 chars with tooltip
- **Phase**: a mini 5-segment progress bar. Each segment is colored by its phase color token. The current phase segment is filled; completed phases are filled; future phases are outlined. Current phase determined by: the phase of the first non-completed step.
- **Current Step**: name of the first non-completed step (trimmed to fit)
- **Owner**: the owner_role from the template for the current step, resolved to the actual person (developer name or change_owner name from the CR record, depending on role)
- **Status**: badge — "On Track" (green) if current step is within threshold, "At Risk" (amber) if over threshold but not at a hard gate, "Blocked" (red) if at a hard gate with unmet prereqs
- **Days**: number of days the current step has been pending (calculated from: if step has completed_date of previous step, use that as start; otherwise use CR created_date for step 1)
- **Deadline**: target_release_date formatted as "Sep 18"

The table is sorted by status severity (Blocked first, then At Risk, then On Track).

- [ ] **Step 4: Update KPI cards with live counts**

After rendering the table, compute:
- **Total Active CRs**: count of CRs with status=active
- **On Track**: CRs where current step is within its overdue threshold
- **At Risk**: CRs where current step exceeds its threshold
- **Blocked**: CRs where current step is a hard gate with unmet prerequisites

Each card shows the count and a colored indicator dot.

- [ ] **Step 5: Publish, verify, commit**

Republish the artifact (same file path — redeploys to same URL).

Verify:
- "Add CR" opens form with team members in dropdowns
- Creating a CR stores it in DB (check via Artifact read_db)
- New CR appears in pipeline table with correct phase progress bar
- KPI cards update to show "1" total
- Creating a second CR works, table shows both sorted by status
- Duplicate CR number is rejected

```bash
git add src/cr-tracker.html
git commit -m "feat: CR creation form and pipeline table with KPI cards"
```

---

### Task 3: Step Checklist, Hard Gates, and Step Completion

The core enforcement engine — the expanded CR detail view with the full 24-step checklist, hard gate blocking, step completion, and PM override.

**Files:**
- Modify: `src/cr-tracker.html`

**Interfaces:**
- Consumes: `LIFECYCLE_TEMPLATE`, CR and step documents from DB, `team` collection for owner resolution
- Produces: Interactive step checklist UI, step completion writes to `crs/{crNumber}/steps/{stepId}`, audit log entries for completions and overrides

- [ ] **Step 1: Build the expanded CR detail panel**

When a CR row in the pipeline table is clicked, expand an inline detail panel below that row (accordion style — clicking again collapses). The panel contains:

**Header row:** CR number (large, mono), description, developer name, change owner, target release date, and a "Cancel CR" button (sets status to "cancelled", removes from active list).

**Step checklist:** Grouped by phase, with a phase header bar for each group (colored by phase token). Each step row shows:

```
[status icon]  Step N: Step name                    Owner    Date completed    [Action]
```

Status icons:
- `✓` (green circle) — completed
- `●` (blue) — in progress (the first pending step after all completed ones)
- `○` (grey outline) — pending
- `🔒` (grey lock) — locked (hard gate, prerequisites not met)
- `⚠` (amber triangle) — completed out of order (skipped warning)

The "Action" column shows:
- Nothing for completed steps
- "Mark Complete" button for the current in-progress step and any unlocked pending step
- A lock icon with tooltip "Requires: [prerequisite names]" for locked steps
- "Skip (optional)" link for step 14 only (the optional step)

- [ ] **Step 2: Implement step completion logic**

When "Mark Complete" is clicked:

```javascript
async function completeStep(crNumber, stepNum) {
  const template = LIFECYCLE_TEMPLATE[stepNum - 1];

  // 1. Hard gate check
  if (template.hardGate) {
    const prereqStatuses = await Promise.all(
      template.prerequisites.map(p =>
        db.get(`crs/${crNumber}/steps`, `step_${String(p).padStart(2, '0')}`)
      )
    );
    const unmet = template.prerequisites.filter((p, i) =>
      prereqStatuses[i].status !== 'completed'
    );
    if (unmet.length > 0) {
      const names = unmet.map(p => `Step ${p}: ${LIFECYCLE_TEMPLATE[p-1].name}`);
      showError(`Cannot complete — prerequisites not met:\n${names.join('\n')}`);
      return;
    }
  }

  // 2. Soft enforcement: check if any earlier non-optional step in same phase is not completed
  const earlierInPhase = LIFECYCLE_TEMPLATE.filter(t =>
    t.step < stepNum && t.phase === template.phase && !t.optional
  );
  const earlierStatuses = await Promise.all(
    earlierInPhase.map(t =>
      db.get(`crs/${crNumber}/steps`, `step_${String(t.step).padStart(2, '0')}`)
    )
  );
  const hasSkippedEarlier = earlierStatuses.some(s => s.status !== 'completed');

  // 3. Show completion dialog
  // - Prompt for optional comment
  // - Confirm actor name (from current user / selected developer)
  // - On confirm: update step doc
  const stepId = `step_${String(stepNum).padStart(2, '0')}`;
  await db.set(`crs/${crNumber}/steps`, stepId, {
    status: hasSkippedEarlier ? 'skipped_warning' : 'completed',
    completed_date: new Date().toISOString(),
    completed_by: currentUser,
    comment: userComment || '',
    override_reason: null
  });

  // 4. Write audit log
  await db.set('audit', `${Date.now()}_${crNumber}_${stepNum}`, {
    action: 'step_completed',
    cr_number: crNumber,
    actor: currentUser,
    details: `Completed step ${stepNum}: ${template.name}`,
    timestamp: new Date().toISOString()
  });

  // 5. Re-evaluate locked steps — if this step was a prerequisite for a hard-gated step,
  //    check if that gate is now fully satisfied and unlock it
  refreshCRDetail(crNumber);
  refreshPipelineTable();
}
```

- [ ] **Step 3: Implement PM override for hard gates**

When the PM clicks a locked step, show a different dialog:

- Title: "This step is locked"
- Message: "Prerequisites not met: [list prerequisite steps and their status]"
- "Override" button (only visible if current user role is PM)
- Override requires a text reason (mandatory, minimum 10 characters)

On override:
1. Update the step status to "completed" with `override_reason` set
2. Write audit log entry with action "gate_overridden" and the reason
3. Refresh the checklist

- [ ] **Step 4: Implement "Skip" for optional step 14**

Step 14 (qTest results review by IS L4) is optional. Show a "Skip" link next to it. Clicking it sets the step status to "completed" with comment "Skipped — optional step" and completed_by as current user. Audit log records it as "step_skipped".

- [ ] **Step 5: Add step hints as tooltips**

Each step with a non-empty `hint` in the template shows an info icon (ℹ). Hovering/clicking reveals the hint text in a tooltip. This gives developers contextual guidance without cluttering the checklist.

- [ ] **Step 6: Publish, verify, commit**

Republish the artifact.

Verify:
- Click a CR row → detail panel expands with all 24 steps grouped by phase
- Step 1 shows as pending/in-progress, step 5 shows as locked (prerequisites 3, 4 not met)
- Complete steps 1-4 in order → step 5 unlocks
- Try to complete step 9 before steps 6, 7, 8 → blocked with error message naming missing prerequisites
- Complete step 6 but skip step 7 → step 6 shows completed, step 7 shows pending, soft warning if you try step 8
- Use PM override on a locked step → override reason required, logged in audit
- Skip optional step 14 → marked as completed with "Skipped" note
- Hints show on hover for steps that have them
- Pipeline table status updates after step completions

```bash
git add src/cr-tracker.html
git commit -m "feat: step checklist with hard gates, PM override, and completion flow"
```

---

### Task 4: Developer View — Action Items and My CRs

Build the developer-focused view with prioritized action items and filtered CR list.

**Files:**
- Modify: `src/cr-tracker.html`

**Interfaces:**
- Consumes: All CR and step data from DB, `team` collection, `LIFECYCLE_TEMPLATE`
- Produces: Developer view UI with action item cards and per-CR checklists, filtered by selected developer

- [ ] **Step 1: Implement view toggle and developer selector**

The view toggle in the top bar switches between PM View and Developer View. Store the current view in a variable (and `localStorage` for persistence across reloads).

Developer View shows:
- Top bar: same title, view toggle, no "Add CR" button
- Developer selector: dropdown of all team members with role="developer". Selecting one filters all content below.
- The selected developer is stored in `localStorage`.

- [ ] **Step 2: Build the "My Action Items" section**

For the selected developer, find all active CRs where:
- The developer is assigned to the CR, AND
- There exists a step that is pending or in_progress AND the step's `ownerRole` matches the developer's role

For each such step, create an action item card:

```html
<div class="action-card action-card--{urgency}">
  <div class="action-card__urgency">{urgency indicator}</div>
  <div class="action-card__cr">CHG0012345 — Material Master Enhancement</div>
  <div class="action-card__step">Step 7: Request peer code review</div>
  <div class="action-card__meta">Pending 3 days · Build phase</div>
  <div class="action-card__action">
    <textarea placeholder="Add a comment (optional)"></textarea>
    <button>Mark Complete</button>
  </div>
</div>
```

Urgency levels (determines sort order and left border color):
- 🔴 **Critical**: step is overdue (days pending > threshold) OR hard gate is blocking downstream
- 🟡 **Warning**: step is approaching threshold (> 50% of threshold days)
- 🟢 **Normal**: step is within threshold

Sort: critical first, then warning, then normal. Within each level, sort by days pending descending.

The "Mark Complete" button here triggers the same `completeStep()` function from Task 3.

- [ ] **Step 3: Build the "My CRs" section**

Below action items, show a compact lifecycle view for each of the developer's CRs. Each CR gets a card with:

- CR number and description as header
- A horizontal phase progress bar (same as pipeline table but larger)
- Below it, a compact step list showing only: step number, name, and status icon
- Completed steps are collapsed into a count: "4 of 4 Scope steps complete ✓"
- The current phase is expanded showing individual steps

This gives the developer a quick status view without the full PM-level detail.

- [ ] **Step 4: Handle "no action items" state**

If the selected developer has no pending action items, show:
"All caught up — no pending actions for [developer name]."

If the developer has no CRs assigned at all:
"No CRs assigned to [developer name]."

- [ ] **Step 5: Publish, verify, commit**

Republish the artifact.

Verify:
- Toggle to Developer View → developer selector appears
- Select a developer who has CRs → action items appear sorted by urgency
- Complete an action item → it disappears from the list, step updates in "My CRs"
- Select a developer with no CRs → empty state message shows
- Switch back to PM View → full pipeline table visible again
- View preference persists across page reload

```bash
git add src/cr-tracker.html
git commit -m "feat: developer view with prioritized action items and my CRs"
```

---

### Task 5: Audit Log Viewer

Surface the audit trail so the PM can see who did what, when, and review override decisions.

**Files:**
- Modify: `src/cr-tracker.html`

**Interfaces:**
- Consumes: `audit` collection from DB
- Produces: Audit log panel within the expanded CR detail, plus a global audit log accessible from the top bar

- [ ] **Step 1: Add per-CR audit log in the detail panel**

In the expanded CR detail panel (Task 3), add a collapsible "Activity Log" section at the bottom. When expanded, it shows a reverse-chronological list of audit entries for that CR:

```
Sep 14, 10:32 AM · Aravind · Completed Step 4: Request review of FS/TS by HSY IS
Sep 14, 09:15 AM · Alok    · ⚠ Override Gate on Step 5: "IS approved verbally, formal coming Monday"
Sep 13, 03:00 PM · Dev-A   · Completed Step 3: Request peer review of FS/TS
Sep 12, 11:00 AM · Hari    · CR created
```

Each entry shows: timestamp, actor, action description. Override entries are highlighted with amber background and show the reason.

Fetch by querying `audit` collection with filter `cr_number == {crNumber}`, ordered by timestamp descending.

- [ ] **Step 2: Add global audit log (PM only)**

Add a "📋 Activity" button in the top bar (PM view only). Clicking it opens a slide-out panel showing the last 50 audit entries across ALL CRs, reverse-chronological. Each entry shows the CR number as a prefix so the PM can see activity across the board.

Include filter chips: "All", "Completions", "Overrides", "CR Created".

- [ ] **Step 3: Publish, verify, commit**

Republish the artifact.

Verify:
- Expand a CR → Activity Log section shows entries from CR creation and step completions
- Override entries are visually distinct with the reason shown
- Global audit log shows entries across all CRs
- Filter chips work correctly
- Entries are in correct chronological order

```bash
git add src/cr-tracker.html
git commit -m "feat: audit log viewer — per-CR and global activity log"
```

---

### Task 6: Alert Engine Runbook

Document how the PM uses Claude to monitor CRs and send automated alerts. This is not dashboard code — it's instructions for the PM to use in their Claude session.

**Files:**
- Create: `docs/superpowers/plans/alert-engine-runbook.md`

**Interfaces:**
- Consumes: Artifact DB (via Claude's `Artifact read_db` tool), Outlook MCP (`mcp__outlook-mcp__send_email`)
- Produces: A runbook the PM follows to trigger monitoring

- [ ] **Step 1: Write the runbook**

Create `docs/superpowers/plans/alert-engine-runbook.md` with the following sections:

**Daily Morning Check (on-demand):**
The PM opens Claude and says: "Check my CRs for overdue steps and deadline warnings, and send alerts."

Claude then:
1. Reads all CR documents from the artifact DB using `Artifact read_db` with collection `crs`
2. For each active CR, reads its steps from `crs/{crNumber}/steps`
3. Computes which steps are overdue (days pending > threshold from template)
4. Computes deadline warnings based on target_release_date vs. current day of week
5. For each overdue step, sends an email via `mcp__outlook-mcp__send_email` to the step owner and PM
6. For each deadline warning, sends an email to the relevant developer and PM
7. Sends a daily summary email to the PM

**Email templates for each alert type:**

Handoff notification:
```
To: {next_owner_email}
Subject: CR {cr_number}: Your action needed — {next_step_name}
Body:
Hi {next_owner_name},

{completed_by} has completed "{completed_step_name}" for CR {cr_number} ({description}).

Your next step: {next_step_name} (Step {next_step_number})
Phase: {phase}
Target release: {target_release_date}

Dashboard: {artifact_url}
```

Overdue alert:
```
To: {step_owner_email}, {pm_email}
Subject: ⚠ CR {cr_number}: Step overdue — {step_name} ({days} days)
Body:
Hi {step_owner_name},

Step {step_number} "{step_name}" for CR {cr_number} has been pending for {days} days (threshold: {threshold} days).

CR: {cr_number} — {description}
Phase: {phase}
Developer: {developer}
Target release: {target_release_date}

Please complete this step or update the CR status. Dashboard: {artifact_url}
```

Deadline warning (Wednesday):
```
To: {developer_email}, {pm_email}
Subject: 🚨 CR {cr_number}: UAT signoff needed by Thursday
Body:
Hi {developer_name},

CR {cr_number} ({description}) is targeting release on {target_release_date}, but UAT signoff (Step 16) is not yet complete.

If UAT is not signed off by Thursday, the CR will need to be pushed to the next release window.

Current status: {current_step_name} (Step {current_step_number})
Dashboard: {artifact_url}
```

**Setting up recurring monitoring with /loop:**
```
/loop 4h Check all CRs in the artifact DB at {artifact_url} for overdue steps and deadline warnings. For any overdue step, send an email to the step owner and PM. For any deadline warning (Monday: incomplete Test phase, Wednesday: no UAT signoff, Thursday: no CAB approval), send the appropriate alert email. After checking, report a summary of what was found and sent.
```

Note: The /loop runs only while the Claude session is active. Start it each morning.

- [ ] **Step 2: Write handoff trigger instructions**

When a step is completed in the dashboard and the next step's ownerRole differs from the current step's ownerRole, the PM should ask Claude to send a handoff email. Alternatively, the PM can say:

"Send handoff notifications for any steps completed today across all CRs."

Claude reads the audit log for today's completions, checks if each triggered a handoff, and sends emails for those that did.

- [ ] **Step 3: Commit**

```bash
git add docs/superpowers/plans/alert-engine-runbook.md
git commit -m "docs: alert engine runbook — monitoring commands and email templates"
```

---

### Task 7: Seed Data and End-to-End Verification

Seed the dashboard with one realistic CR to validate the full workflow end-to-end.

**Files:**
- No new files — this task uses the Artifact DB write and the published dashboard

**Interfaces:**
- Consumes: Published artifact with DB, Outlook MCP
- Produces: One seeded CR with steps at various states, verified end-to-end workflow

- [ ] **Step 1: Add team members via the dashboard**

Open the published artifact and add these team members through the "Manage Team" UI:
- At least one PM (the user)
- At least two developers
- At least one change owner

Verify they appear in the team list and populate the CR creation dropdowns.

- [ ] **Step 2: Create a test CR**

Use the "Add CR" button to create a test CR:
- CR Number: "CHG0099999"
- Description: "Test CR — Material Master Enhancement"
- Developer: one of the added developers
- Change Owner: one of the added change owners
- Target Release Date: next Thursday

Verify it appears in the pipeline table with "Scope" phase active, step 1 pending.

- [ ] **Step 3: Walk through the lifecycle**

Complete steps 1-4 in order. Verify:
- Step 5 unlocks after steps 3 and 4 are completed (Gate 1)
- Steps show ✓ icons, dates, and "completed by" names

Complete steps 5-8. Verify:
- Step 9 unlocks after 6, 7, 8 are completed (Gate 2)

Try to complete step 17 without step 13 or 16. Verify:
- Hard gate blocks with clear prerequisite message (Gate 3)

Use PM override on step 17. Verify:
- Override reason dialog appears and is required
- Step completes with override logged in audit
- Audit log shows the override with reason

- [ ] **Step 4: Test the developer view**

Switch to Developer View, select the test developer. Verify:
- Action items show the next pending step for CHG0099999
- "My CRs" shows the CR with correct progress
- Completing a step from the developer view works

- [ ] **Step 5: Test an alert email**

Ask Claude: "Check my CRs in the CR Lifecycle Tracker for any overdue steps and send alerts."

Claude should:
1. Read the artifact DB
2. Find any steps that are overdue
3. Send an email via Outlook MCP to the appropriate recipients
4. Report what was sent

Verify the email arrives with correct content.

- [ ] **Step 6: Clean up test data**

Cancel the test CR (set status to "cancelled") via the dashboard. Verify it disappears from the active pipeline view.

- [ ] **Step 7: Commit any final adjustments**

If any issues were found and fixed during verification:

```bash
git add src/cr-tracker.html
git commit -m "fix: adjustments from end-to-end verification"
```
