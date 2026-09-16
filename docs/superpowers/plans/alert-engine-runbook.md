# CR Lifecycle Tracker — Alert Engine Runbook

> This runbook describes how to use Claude as your CR monitoring assistant. Claude reads your CR data from the dashboard's database and sends alert emails via Outlook when steps are overdue, deadlines are approaching, or handoffs are needed.

## Quick Start

Open Claude and say one of these:

- **"Check my CRs for overdue steps and send alerts"** — one-time scan
- **"Send handoff notifications for steps completed today"** — handoff emails
- **"Give me a daily summary of all CR statuses"** — summary email to you

---

## 1. Daily Morning Check

Say to Claude:

> "Check all CRs in the CR Lifecycle Tracker for overdue steps and deadline warnings, and send alerts."

Claude will:

1. Read all CR documents from the artifact database (collection: `crs`)
2. For each active CR, read its steps (collection: `crs/{crNumber}/steps`)
3. Compare each pending step's age against its overdue threshold
4. Check for deadline warnings based on the target release date and today's day of week
5. Send emails via Outlook to step owners and you (PM)
6. Report a summary of what was found and sent

---

## 2. Email Templates

### Handoff Notification

Sent when a step is completed and the next step belongs to a different person.

```
To:      {next_owner_email}
Subject: CR {cr_number}: Your action needed — {next_step_name}

Hi {next_owner_name},

{completed_by} has completed "{completed_step_name}" for CR {cr_number} ({description}).

Your next step: {next_step_name} (Step {next_step_number})
Phase: {phase}
Target release: {target_release_date}

Dashboard: {artifact_url}
```

### Overdue Alert

Sent when a step has been pending longer than its threshold.

```
To:      {step_owner_email}, {pm_email}
Subject: ⚠ CR {cr_number}: Step overdue — {step_name} ({days} days)

Hi {step_owner_name},

Step {step_number} "{step_name}" for CR {cr_number} has been pending for {days} days
(threshold: {threshold} days).

CR: {cr_number} — {description}
Phase: {phase}
Developer: {developer}
Target release: {target_release_date}

Please complete this step or update the CR status.
Dashboard: {artifact_url}
```

### Deadline Warning (Wednesday — UAT Signoff)

Sent on Wednesday if UAT signoff is not yet complete for a CR targeting this week.

```
To:      {developer_email}, {pm_email}
Subject: 🚨 CR {cr_number}: UAT signoff needed by Thursday

Hi {developer_name},

CR {cr_number} ({description}) is targeting release on {target_release_date},
but UAT signoff (Step 16) is not yet complete.

If UAT is not signed off by Thursday, the CR will need to be pushed
to the next release window.

Current status: {current_step_name} (Step {current_step_number})
Dashboard: {artifact_url}
```

---

## 3. Overdue Thresholds

| Phase | Threshold | Rationale |
|-------|-----------|-----------|
| Scope | 3 days | Spec work should not stall |
| Build | 3 days | Development has buffer |
| Test | 2 days | Tight — Thursday release window |
| Go-live | 1 day | Critical path, no buffer |
| Validation | 3 days | Post-release, less urgent |

A step is "overdue" when it has been pending for more days than its phase threshold.

---

## 4. Deadline Warning Schedule

These warnings are tied to the weekly Thursday release window:

| Day | Warning | Condition |
|-----|---------|-----------|
| **Monday** | Test phase incomplete | Any CR targeting this week's release still has incomplete Test phase steps (steps 9-16) |
| **Wednesday** | UAT signoff missing | Step 16 (UAT Signoff) is not completed for a CR targeting this week |
| **Thursday AM** | No CAB approval | Step 20 (CAB approves or rejects) is not completed for a CR targeting this week |

---

## 5. Setting Up Recurring Monitoring

To have Claude check automatically every 4 hours during your session:

```
/loop 4h Check all CRs in the artifact DB for overdue steps and deadline warnings. For any overdue step, send an email to the step owner and PM. For any deadline warning (Monday: incomplete Test phase, Wednesday: no UAT signoff, Thursday: no CAB approval), send the appropriate alert email. After checking, report a summary of what was found and sent.
```

**Important:** The `/loop` runs only while your Claude session is active. Start it each morning when you begin work. It stops when you close Claude.

---

## 6. Handoff Notifications

When a developer completes a step and the next step belongs to someone else, ask Claude:

> "Send handoff notifications for any steps completed today across all CRs."

Claude will:
1. Read the audit log for today's entries with action `step_completed`
2. For each completion, check if the next step's `ownerRole` differs from the completed step's `ownerRole`
3. If yes, send a handoff email to the next step's owner
4. Report which handoff emails were sent

Alternatively, you can ask for handoffs on a specific CR:

> "Send a handoff notification for CR CHG0012345 — step 8 was just completed."

---

## 7. Daily Summary Email

Ask Claude:

> "Send me a daily summary email of all my CRs."

Claude will compose a single email to you with:
- Total active CRs and their current phases
- Any overdue steps (with days overdue)
- Any CRs at risk of missing the Thursday release window
- Steps completed in the last 24 hours
- Next actions needed from each team member

---

## Artifact Database Reference

For Claude to read your CR data, it uses these collections:

| Collection | What's in it |
|------------|-------------|
| `crs` | CR records: cr_number, description, developer, change_owner, target_release_date, status |
| `crs/{crNumber}/steps` | 24 step records per CR: status, completed_date, completed_by, comment |
| `audit` | Activity log: action, cr_number, actor, details, timestamp |
| `team` | Team members: name, email, role |

The LIFECYCLE_TEMPLATE (step names, phases, thresholds, prerequisites) is embedded in the dashboard code — Claude knows it from the spec.
