# CR Lifecycle Tracker — Design Spec

## Problem

The AMS team delivers Change Requests (CRs) and Change Documents (CDs) for Hershey's through a 24-step lifecycle spanning 5 phases. Steps are frequently missed, executed out of order, handoffs between people get lost, and deadline-driven milestones (e.g., Thursday UAT signoff cutoff) are missed. There is no enforcement mechanism today — the checklist exists as a static Excel file.

## Solution

An interactive web dashboard (Claude artifact) with a shared database, combined with automated Outlook email alerts. The system enforces the CR lifecycle through hard gates at critical transitions and soft alerts everywhere else.

## Users

- **PM (primary):** Bird's-eye view across all active CRs, deadline tracking, override capability
- **AMS Developers:** Focused view of their action items and CR progress

## Architecture

```
┌─────────────────────┐     ┌──────────────────┐     ┌─────────────┐
│   Dashboard (UI)    │────▶│  Artifact DB     │◀────│   Claude     │
│  PM + Dev views     │     │  (shared state)  │     │  Monitor     │
│  Hard gates in UI   │     │  CR lifecycle    │     │  (periodic)  │
└─────────────────────┘     └──────────────────┘     └──────┬──────┘
                                                            │
                                                     ┌──────▼──────┐
                                                     │   Outlook    │
                                                     │   Emails     │
                                                     └─────────────┘
```

1. **Dashboard** — Claude artifact with shared database. Both PM and developers access the same URL. Role selection via dropdown.
2. **Alert Engine** — Claude monitors CR state and sends Outlook emails for overdue steps, missed deadlines, and handoff notifications. Monitoring runs in two modes: (a) on-demand when the PM asks Claude to "check CRs" or "send alerts," and (b) via a recurring loop (`/loop`) during an active Claude session. Note: cron jobs are session-only and do not persist when Claude exits — the PM should start monitoring at the beginning of each workday.
3. **Hard Gate Logic** — Built into the dashboard UI. Prerequisites must be satisfied before a gated step can be completed.

---

## Dashboard Design

### PM View

**Top Bar:**
- Title: "CR Lifecycle Tracker"
- View toggle: PM View / Developer View
- "Add New CR" button

**KPI Cards:**
- Total Active CRs
- On Track (green)
- At Risk — step pending > threshold (yellow)
- Blocked — hard gate unmet or overdue deadline (red)

**CR Pipeline Table:**
Each row is one CR showing:
- CR number and description
- Current phase with mini progress bar (Scope → Build → Test → Go-live → Validation)
- Current step and owner
- Step status (color-coded: green/yellow/red)
- Days in current step
- Next deadline
- Action buttons

**Expanded CR Detail (click to expand):**
Full 24-step vertical checklist grouped by phase. Each step shows:
- Status icon: ✅ completed, 🔵 in progress, ⬜ pending, 🔒 locked (hard gate), ⚠️ skipped warning
- Step name
- Owner
- Completion date (if done)
- Comments

PM can override any hard gate with a logged reason.

### Developer View

**Top Bar:**
- Same as PM view, defaults to "Developer View"
- Developer name selector (dropdown)

**"My Action Items" (prioritized):**
Cards sorted by urgency showing:
- CR number and description
- Specific step needing action
- Days pending
- Plain-language action description
- "Mark Complete" button (with hard gate check)
- Optional comment field

**"My CRs" (below action items):**
Simplified lifecycle checklist for each of their assigned CRs.

### Completing a Step

When a developer clicks "Mark Complete":
1. Hard gate check — if prerequisites not met, show message: "Cannot complete: [prerequisite step] must be done first"
2. If prerequisites met, mark step done with timestamp and user name
3. If next step belongs to a different person, trigger handoff email
4. Optional comment captured

---

## CR Lifecycle Steps

24 steps across 5 phases, derived from the team's existing CR Checklist:

### Phase 1: Scope
| # | Step | Default Owner | CR Status | CD Status |
|---|------|--------------|-----------|-----------|
| 1 | Create CR/CD by filling out ServiceNow form | Hari/Alok/Aravind | New | - |
| 2 | Create FS/TS document with test cases | AMS Developer | New | Created |
| 3 | Request peer review of FS/TS | AMS Developer | New | Created |
| 4 | Request review of FS/TS by HSY IS | AMS Developer | New | Created |

### Phase 2: Build
| # | Step | Default Owner | CR Status | CD Status |
|---|------|--------------|-----------|-----------|
| 5 | Begin development | AMS Developer | New | DEV: TR create/develop |
| 6 | Development complete (ATC Check) | AMS Developer | New | DEV: TR create/develop |
| 7 | Request peer code review | AMS Developer Peer | New | DEV: TR create/develop |
| 8 | Perform unit testing | AMS Developer | New | DEV: TR create/develop |

### Phase 3: Test
| # | Step | Default Owner | CR Status | CD Status |
|---|------|--------------|-----------|-----------|
| 9 | Release transport tasks, move CD to QA | AMS Developer | New | QA: Main TR imported |
| 10 | Request CoE team for Live Compare result | AMS Developer | Assess | QA: Main TR imported |
| 11 | Create qTest test cases | AMS Developer | Assess | QA: Main TR imported |
| 12 | Add qTest test cases per Live Compare results | AMS Developer | Assess | QA: Main TR imported |
| 13 | Perform SIT, document results in qTest and CR | AMS Developer | Assess | QA: Main TR imported |
| 14 | Request qTest results review by HSY IS L4 (optional) | AMS Developer | Assess | QA: Main TR imported |
| 15 | UAT begins | HSY Business Users | Assess | QA: Main TR imported |
| 16 | UAT Signoff | HSY Business Users | Assess | QA: Main TR imported |

### Phase 4: Go-live
| # | Step | Default Owner | CR Status | CD Status |
|---|------|--------------|-----------|-----------|
| 17 | Request review by HSY IS L4, move CD to PreProd Review | AMS Change Owner | Assess | PreProd Review |
| 18 | IS L4 approves or escalates to CAB, move CD to HSY Quality Approval | HSY IS L4 | Assess | HSY Quality Approval |
| 19 | CR & CD goes to CAB (if qualifies) | AMS Change Owner | Authorize | HSY Quality Approval |
| 20 | CAB approves or rejects | HSY Release Managers | Authorize | HSY Quality Approval |

### Phase 5: Validation
| # | Step | Default Owner | CR Status | CD Status |
|---|------|--------------|-----------|-----------|
| 21 | CR & CD released into production, CD to Deploy | Basis / HSY Release Managers | Implement | Deploy |
| 22 | AMS team validates post release, CD to Imported into Production | Basis / HSY Release Managers | Implement | Imported into Production |
| 23 | Business users validate, CD to Completed | Basis / HSY Release Managers | Implement | Completed |
| 24 | Request HSY IS for CR closure (Live Task and QCoE task completed) | AMS Change Owner | Closed | Completed |

---

## Hard Gates

Four critical boundaries where steps are blocked until prerequisites are satisfied:

### Gate 1: Scope → Build
**Step 5 (Begin development)** requires:
- Step 3 (Peer review of FS/TS) = completed
- Step 4 (IS review of FS/TS) = completed

*Rationale: Developing without approved specs leads to rework.*

### Gate 2: Build → Test
**Step 9 (Release transport to QA)** requires:
- Step 6 (Development complete with ATC check) = completed
- Step 7 (Peer code review) = completed
- Step 8 (Unit testing) = completed

*Rationale: Untested/unreviewed code must not reach QA.*

### Gate 3: Test → Go-live
**Step 17 (Request PreProd review)** requires:
- Step 13 (SIT documented in qTest) = completed
- Step 16 (UAT signoff) = completed

*Rationale: This is the point of no return. Missing UAT signoff means a missed release window.*

### Gate 4: Go-live → Validation
**Step 24 (Request CR closure)** requires:
- Step 22 (Post-release validation) = completed
- Step 23 (Business validation) = completed

*Rationale: Premature closure means no one validates the change works in production.*

### PM Override
Any hard gate can be overridden by the PM with a mandatory reason. The override is logged in the audit trail with timestamp and justification.

### Soft Enforcement
All non-gated steps show a ⚠️ yellow warning if completed out of order but are not blocked.

---

## Automated Alerts

Three types of automated emails sent via Outlook:

### 1. Handoff Notifications (immediate)
Triggered when a step is completed and the next step belongs to a different person.

**Recipients:** Next step owner
**Content:** CR number, completed step, next step description, deadline if applicable, dashboard link

### 2. Overdue Alerts (daily scan — morning check)
Triggered when the PM starts the daily monitoring loop (or asks Claude to check). Fires when a step exceeds its pending threshold:
- Scope steps: 3 days
- Build steps: 3 days
- Test steps: 2 days
- Go-live steps: 1 day
- Validation steps: 3 days

**Recipients:** Step owner + PM

### 3. Deadline Warnings (release-cadence-aware)
Tied to the weekly Thursday release window:
- **Monday:** Alert if any CR targeting this week still has incomplete Test phase steps
- **Wednesday:** Alert if UAT signoff is not done
- **Thursday morning:** Final warning for CRs without CAB approval

**Recipients:** PM for all; relevant developer for their CRs

### Daily Summary (PM only)
A single daily email to PM summarizing all CR statuses, overdue items, and upcoming deadlines.

---

## Data Model

### CR Record
| Field | Type | Description |
|-------|------|-------------|
| cr_number | string | Unique identifier (e.g., "CR-1234") |
| description | string | Short description of the change |
| developer | string | Assigned AMS developer name |
| developer_email | string | Developer's email for notifications |
| change_owner | string | Change owner (Hari/Alok/Aravind) |
| change_owner_email | string | Change owner's email |
| target_release_date | date | Target release date (Thursday) |
| created_date | date | When the CR was created |
| status | enum | active / completed / cancelled |

### Step Record (24 per CR)
| Field | Type | Description |
|-------|------|-------------|
| step_number | integer | 1-24 |
| step_name | string | Step description |
| phase | enum | Scope / Build / Test / Go-live / Validation |
| owner_role | string | Default role (AMS Developer, HSY IS, etc.) |
| owner_name | string | Actual person assigned |
| owner_email | string | For notifications |
| status | enum | locked / pending / in_progress / completed / skipped_warning |
| completed_date | datetime | When marked complete |
| completed_by | string | Who marked it complete |
| comment | string | Optional notes |
| is_hard_gate | boolean | Whether this step has hard gate prerequisites |
| prerequisites | array[int] | Step numbers that must be complete first |

### Audit Log
| Field | Type | Description |
|-------|------|-------------|
| timestamp | datetime | When the action occurred |
| cr_number | string | Which CR |
| action | string | step_completed / gate_overridden / cr_created / alert_sent |
| actor | string | Who performed the action |
| details | string | Additional context (e.g., override reason) |

---

## Testing & Rollout Plan

### Testing
1. Seed with one real active CR in its actual current state
2. Verify hard gates block correctly and show clear error messages
3. Verify PM override works and logs the reason
4. Trigger each alert type (handoff, overdue, deadline) and verify email content/recipients
5. Have one developer walk through the developer view without instructions

### Rollout
- **Week 1:** PM enters all 5 active CRs, manages step completions personally
- **Week 2:** Developers start marking their own steps, PM monitors
- **Ongoing:** Adjust thresholds and hard gates based on real usage

---

## Notes from CR Checklist
- Any change in S4 (Greenfield System): perform version comparison between Dev and Production
- Test scenarios should be added in both FS and TS; validation of scenarios to be done in TS
- If same object is locked by Project team, align with Project team and inform business with expected release date
- UAT mail should be sent a week in advance of production release date if business UAT is required
- If technical change and only IS validation required, send test results by previous week Wednesday of release window
