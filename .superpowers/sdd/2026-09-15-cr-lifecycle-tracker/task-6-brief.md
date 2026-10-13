# Task 6: Alert Engine Runbook

Document how the PM uses Claude to monitor CRs and send automated alerts. This is NOT dashboard code — it's a documentation file.

**Files:**
- Create: `docs/superpowers/plans/alert-engine-runbook.md`

**Interfaces:**
- Consumes: Knowledge of artifact DB collections (`crs`, `crs/{crNumber}/steps`, `audit`, `team`), Outlook MCP tool name (`mcp__outlook-mcp__send_email`), LIFECYCLE_TEMPLATE overdue thresholds
- Produces: A markdown runbook the PM reads and follows

## Content to write

The runbook should cover these sections:

### 1. Daily Morning Check (on-demand)

The PM opens Claude and says: "Check my CRs for overdue steps and deadline warnings, and send alerts."

Describe what Claude does:
1. Reads all CR docs from artifact DB using `Artifact read_db` with collection `crs`
2. For each active CR, reads steps from `crs/{crNumber}/steps`
3. Computes overdue steps (days pending > threshold)
4. Computes deadline warnings based on target_release_date vs. day of week
5. Sends emails via `mcp__outlook-mcp__send_email`
6. Sends a daily summary to PM

### 2. Email Templates

Three templates with placeholders:

**Handoff notification:**
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

**Overdue alert:**
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

Please complete this step or update the CR status.
Dashboard: {artifact_url}
```

**Deadline warning (Wednesday — UAT signoff):**
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

### 3. Overdue Thresholds

List the thresholds per phase:
- Scope steps: 3 days
- Build steps: 3 days
- Test steps: 2 days
- Go-live steps: 1 day
- Validation steps: 3 days

### 4. Deadline Warning Schedule

- **Monday:** Alert if any CR targeting this week still has incomplete Test phase steps
- **Wednesday:** Alert if UAT signoff (step 16) is not done
- **Thursday morning:** Final warning for CRs without CAB approval (step 20)

### 5. Setting Up Recurring Monitoring

```
/loop 4h Check all CRs in the artifact DB at {artifact_url} for overdue steps and deadline warnings. For any overdue step, send an email to the step owner and PM. For any deadline warning (Monday: incomplete Test phase, Wednesday: no UAT signoff, Thursday: no CAB approval), send the appropriate alert email. After checking, report a summary of what was found and sent.
```

Note: /loop runs only while Claude session is active. Start each morning.

### 6. Handoff Triggers

"Send handoff notifications for any steps completed today across all CRs."

Claude reads audit log for today's completions, checks if each triggers a handoff (next step has different ownerRole), sends emails.

## Steps

- [ ] **Step 1: Write the runbook file**

Create `docs/superpowers/plans/alert-engine-runbook.md` with all sections above. Use clear markdown formatting. Include a header note: "This runbook describes how to use Claude as your CR monitoring assistant."

- [ ] **Step 2: Commit**

```bash
git add docs/superpowers/plans/alert-engine-runbook.md
git commit -m "docs: alert engine runbook — monitoring commands and email templates"
```
