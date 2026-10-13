# Task 1: Artifact Foundation — Shell, Tokens, Layout, Team Setup

Build the HTML skeleton with the design system, theme support, empty view scaffolding, and the team-member management needed before any CRs can be created.

**Files:**
- Create: `src/cr-tracker.html`

**Interfaces:**
- Consumes: nothing (first task)
- Produces: A working HTML page with top bar, view toggle, empty KPI card row, empty table area, and a "Manage Team" flow for adding team members (name + email + role). Team members stored in `team` collection. The `LIFECYCLE_TEMPLATE` constant (array of 24 step definitions) available to all later code.

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

## Steps

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
  { step: 1, name: "Create CR/CD by filling out ServiceNow form", phase: "Scope", ownerRole: "Change Owner", crStatus: "New", cdStatus: "-", hardGate: false, prerequisites: [], overdueThresholdDays: 3, hint: "Developer will request for CR/CD creation in a mail with FS/TS sharepoint link" },
  { step: 2, name: "Create FS/TS document with test cases", phase: "Scope", ownerRole: "AMS Developer", crStatus: "New", cdStatus: "Created", hardGate: false, prerequisites: [], overdueThresholdDays: 3, hint: "If same object is locked by Project team, align with Project team and inform business with expected release date" },
  { step: 3, name: "Request peer review of FS/TS", phase: "Scope", ownerRole: "AMS Developer", crStatus: "New", cdStatus: "Created", hardGate: false, prerequisites: [], overdueThresholdDays: 3, hint: "" },
  { step: 4, name: "Request review of FS/TS by HSY IS", phase: "Scope", ownerRole: "AMS Developer", crStatus: "New", cdStatus: "Created", hardGate: false, prerequisites: [], overdueThresholdDays: 3, hint: "Get the FS/TS approved by IS. TS can have basic details on design and approach." },
  { step: 5, name: "Begin development", phase: "Build", ownerRole: "AMS Developer", crStatus: "New", cdStatus: "DEV: TR create/develop", hardGate: true, prerequisites: [3, 4], overdueThresholdDays: 3, hint: "" },
  { step: 6, name: "Development complete (ATC Check)", phase: "Build", ownerRole: "AMS Developer", crStatus: "New", cdStatus: "DEV: TR create/develop", hardGate: false, prerequisites: [], overdueThresholdDays: 3, hint: "Include the ATC check excel file in the CR folder" },
  { step: 7, name: "Request peer code review", phase: "Build", ownerRole: "AMS Developer Peer", crStatus: "New", cdStatus: "DEV: TR create/develop", hardGate: false, prerequisites: [], overdueThresholdDays: 3, hint: "" },
  { step: 8, name: "Perform unit testing", phase: "Build", ownerRole: "AMS Developer", crStatus: "New", cdStatus: "DEV: TR create/develop", hardGate: false, prerequisites: [], overdueThresholdDays: 3, hint: "" },
  { step: 9, name: "Release transport tasks, move CD to QA", phase: "Test", ownerRole: "AMS Developer", crStatus: "New", cdStatus: "QA: Main TR imported", hardGate: true, prerequisites: [6, 7, 8], overdueThresholdDays: 2, hint: "" },
  { step: 10, name: "Request CoE team for Live Compare result", phase: "Test", ownerRole: "AMS Developer", crStatus: "Assess", cdStatus: "QA: Main TR imported", hardGate: false, prerequisites: [], overdueThresholdDays: 2, hint: "Reach out to Vibin Ravi (vravi@hersheys.com) for Live Compare" },
  { step: 11, name: "Create qTest test cases", phase: "Test", ownerRole: "AMS Developer", crStatus: "Assess", cdStatus: "QA: Main TR imported", hardGate: false, prerequisites: [], overdueThresholdDays: 2, hint: "" },
  { step: 12, name: "Add qTest test cases per Live Compare results", phase: "Test", ownerRole: "AMS Developer", crStatus: "Assess", cdStatus: "QA: Main TR imported", hardGate: false, prerequisites: [], overdueThresholdDays: 2, hint: "" },
  { step: 13, name: "Perform SIT, document results in qTest and CR", phase: "Test", ownerRole: "AMS Developer", crStatus: "Assess", cdStatus: "QA: Main TR imported", hardGate: false, prerequisites: [], overdueThresholdDays: 2, hint: "" },
  { step: 14, name: "Request qTest results review by HSY IS L4 (optional)", phase: "Test", ownerRole: "AMS Developer", crStatus: "Assess", cdStatus: "QA: Main TR imported", hardGate: false, prerequisites: [], overdueThresholdDays: 2, optional: true, hint: "" },
  { step: 15, name: "UAT begins", phase: "Test", ownerRole: "HSY Business Users", crStatus: "Assess", cdStatus: "QA: Main TR imported", hardGate: false, prerequisites: [], overdueThresholdDays: 2, hint: "UAT mail should be sent out a week in advance of production release date" },
  { step: 16, name: "UAT Signoff", phase: "Test", ownerRole: "HSY Business Users", crStatus: "Assess", cdStatus: "QA: Main TR imported", hardGate: false, prerequisites: [], overdueThresholdDays: 2, hint: "If UAT is not signed off by Thursday, request CR/CD push out" },
  { step: 17, name: "Request review by HSY IS L4, move CD to PreProd Review", phase: "Go-live", ownerRole: "AMS Change Owner", crStatus: "Assess", cdStatus: "PreProd Review", hardGate: true, prerequisites: [13, 16], overdueThresholdDays: 1, hint: "Before requesting IS approval: ensure qTest is updated in CR, FS/TS link in CR description, ATC check done, CD in PreProd Review status" },
  { step: 18, name: "IS L4 approves or escalates to CAB, move CD to HSY Quality Approval", phase: "Go-live", ownerRole: "HSY IS L4", crStatus: "Assess", cdStatus: "HSY Quality Approval", hardGate: false, prerequisites: [], overdueThresholdDays: 1, hint: "Follow up with IS to get CR in Authorize status and CD in HSY Quality Approval by Thursday" },
  { step: 19, name: "CR & CD goes to CAB (if qualifies)", phase: "Go-live", ownerRole: "AMS Change Owner", crStatus: "Authorize", cdStatus: "HSY Quality Approval", hardGate: false, prerequisites: [], overdueThresholdDays: 1, hint: "Change owner to present the CR in CAB" },
  { step: 20, name: "CAB approves or rejects", phase: "Go-live", ownerRole: "HSY Release Managers", crStatus: "Authorize", cdStatus: "HSY Quality Approval", hardGate: false, prerequisites: [], overdueThresholdDays: 1, hint: "" },
  { step: 21, name: "CR & CD released into production, CD to Deploy", phase: "Validation", ownerRole: "Basis / HSY Release Managers", crStatus: "Implement", cdStatus: "Deploy", hardGate: false, prerequisites: [], overdueThresholdDays: 3, hint: "" },
  { step: 22, name: "AMS team validates post release, CD to Imported into Production", phase: "Validation", ownerRole: "Basis / HSY Release Managers", crStatus: "Implement", cdStatus: "Imported into Production", hardGate: false, prerequisites: [], overdueThresholdDays: 3, hint: "" },
  { step: 23, name: "Business users validate, CD to Completed", phase: "Validation", ownerRole: "Basis / HSY Release Managers", crStatus: "Implement", cdStatus: "Completed", hardGate: false, prerequisites: [], overdueThresholdDays: 3, hint: "" },
  { step: 24, name: "Request HSY IS for CR closure", phase: "Validation", ownerRole: "AMS Change Owner", crStatus: "Closed", cdStatus: "Completed", hardGate: true, prerequisites: [22, 23], overdueThresholdDays: 3, hint: "Make sure Live Task and QCoE task is completed before requesting HSY IS for CR closure" }
];
```

- [ ] **Step 3: Build the team management UI**

Add a "Manage Team" modal that lets the PM add team members before creating CRs:
- Modal with form: Name, Email, Role dropdown (PM / Developer / Change Owner)
- "Add Member" button saves to `team` collection via `window.claude.db`
- List of current team members with delete option
- On page load, fetch team members from DB to populate dropdowns elsewhere
- The "Add CR" button stays disabled until at least one team member with role "Developer" and one with role "Change Owner" exist

- [ ] **Step 4: Commit**

```bash
git add src/cr-tracker.html
git commit -m "feat: CR lifecycle tracker — artifact foundation with design system, team management, and lifecycle template"
```
