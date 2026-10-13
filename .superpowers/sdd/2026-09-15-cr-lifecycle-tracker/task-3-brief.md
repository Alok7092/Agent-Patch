# Task 3: Step Checklist, Hard Gates, and Step Completion

The core enforcement engine — the expanded CR detail view with the full 24-step checklist, hard gate blocking, step completion, and PM override.

**Files:**
- Modify: `src/cr-tracker.html`

**Interfaces:**
- Consumes: `LIFECYCLE_TEMPLATE`, CR and step data from in-memory `crs` array (each CR has a `steps` object keyed by step_01..step_24), `teamMembers`, `currentUser`, DB via `window.claude?.db`
- Produces: Interactive step checklist UI inside the expanded CR detail panel, `completeStep(crNumber, stepNum)` function, `overrideGate(crNumber, stepNum)` function, audit log entries for completions and overrides

## Steps

- [ ] **Step 1: Build the expanded CR detail panel**

The `toggleCRExpand()` function already exists and tracks expanded CRs in a Set. When `renderCRTable()` renders a CR that is expanded, it should render a detail panel directly below that CR's row.

The detail panel contains:

**Header row:** CR number (large, mono), description, developer name, change owner, target release date, and a "Cancel CR" button (sets CR status to "cancelled" in DB and in-memory, re-renders).

**Step checklist:** Grouped by phase, with a colored phase header bar for each group. Use the phase color tokens: `--phase-scope`, `--phase-build`, `--phase-test`, `--phase-golive`, `--phase-validation`. Each step row shows:

```
[status icon]  Step N: Step name                    Owner    Date completed    [Action]
```

Status icons (use spans with appropriate colors):
- Completed: green checkmark circle
- In progress: blue filled circle (the first pending step after all completed ones)
- Pending: grey outline circle
- Locked: grey lock icon (hard gate, prerequisites not met)
- Skipped warning: amber triangle (completed out of order)

The "Action" column shows:
- Nothing for completed steps
- "Mark Complete" button for pending/in-progress steps (if not locked)
- Lock icon with tooltip "Requires: [prerequisite names]" for locked steps
- "Skip" link for step 14 only (optional step)

Add CSS for the detail panel: `.cr-detail`, `.phase-group`, `.phase-header`, `.step-row`, `.step-icon`, `.step-name`, `.step-owner`, `.step-date`, `.step-action`.

- [ ] **Step 2: Implement `completeStep(crNumber, stepNum)` function**

```javascript
async function completeStep(crNumber, stepNum) {
  const template = LIFECYCLE_TEMPLATE[stepNum - 1];
  const cr = crs.find(c => c.cr_number === crNumber);
  if (!cr) return;

  // 1. Hard gate check
  if (template.hardGate && template.prerequisites.length > 0) {
    const unmet = template.prerequisites.filter(p => {
      const stepId = `step_${String(p).padStart(2, '0')}`;
      return cr.steps[stepId]?.status !== 'completed';
    });
    if (unmet.length > 0) {
      const names = unmet.map(p => `Step ${p}: ${LIFECYCLE_TEMPLATE[p-1].name}`);
      showGateBlockedDialog(crNumber, stepNum, names);
      return;
    }
  }

  // 2. Soft enforcement — check if earlier non-optional steps in same phase are incomplete
  const earlierInPhase = LIFECYCLE_TEMPLATE.filter(t =>
    t.step < stepNum && t.phase === template.phase && !t.optional
  );
  const hasSkippedEarlier = earlierInPhase.some(t => {
    const sid = `step_${String(t.step).padStart(2, '0')}`;
    return cr.steps[sid]?.status !== 'completed';
  });

  // 3. Show completion dialog — prompt for optional comment
  const comment = await showCompletionDialog(crNumber, stepNum);
  if (comment === null) return; // cancelled

  // 4. Update step
  const stepId = `step_${String(stepNum).padStart(2, '0')}`;
  const stepData = {
    status: hasSkippedEarlier ? 'skipped_warning' : 'completed',
    completed_date: new Date().toISOString(),
    completed_by: currentUser,
    comment: comment || '',
    override_reason: null
  };

  // Update in-memory
  cr.steps[stepId] = stepData;

  // Update DB
  try {
    await window.claude?.db?.set(`crs/${crNumber}/steps`, stepId, stepData);
  } catch (e) { console.warn('DB write failed', e); }

  // 5. Audit log
  const auditId = `${Date.now()}_${crNumber}_${stepNum}`;
  const auditEntry = {
    action: 'step_completed',
    cr_number: crNumber,
    actor: currentUser,
    details: `Completed step ${stepNum}: ${template.name}`,
    timestamp: new Date().toISOString()
  };
  try {
    await window.claude?.db?.set('audit', auditId, auditEntry);
  } catch (e) { console.warn('Audit write failed', e); }

  // 6. Re-evaluate locked steps
  reevaluateLocks(cr);
  renderAll();
}
```

Also implement `reevaluateLocks(cr)` — iterates LIFECYCLE_TEMPLATE, and for each hard-gated step, checks if all prerequisites are now completed. If so, and the step is still "locked", update it to "pending" (both in-memory and DB).

Also implement `showCompletionDialog(crNumber, stepNum)` — a modal that shows the step name, an optional comment textarea, and Confirm/Cancel buttons. Returns a promise that resolves with the comment string (or empty string) on confirm, or null on cancel.

- [ ] **Step 3: Implement PM override for hard gates**

Implement `showGateBlockedDialog(crNumber, stepNum, unmetNames)`:

Shows a modal with:
- Title: "Step Locked"
- Message: "This step requires the following prerequisites to be completed:" followed by the list of unmet step names
- If `currentUser`'s role in `teamMembers` is "pm": show an "Override" button plus a textarea for the reason (mandatory, min 10 chars)
- If not PM: just show "Close" button

On override:
1. Update the step in-memory with status "completed", override_reason set, completed_date, completed_by
2. Write to DB
3. Write audit log entry with action "gate_overridden" including the reason
4. Re-evaluate locks, render all

- [ ] **Step 4: Implement "Skip" for optional step 14**

In the step checklist rendering, when step 14 is pending (not completed), show a "Skip" link. Clicking it:
1. Sets step status to "completed" with comment "Skipped — optional step"
2. Writes to DB
3. Writes audit log entry with action "step_skipped"
4. Re-renders

- [ ] **Step 5: Add step hints as tooltips**

Each step with a non-empty `hint` in the template shows an info icon (ℹ) after the step name. Use a simple CSS tooltip pattern:

```css
.hint-trigger { position: relative; cursor: help; color: var(--text-muted); }
.hint-trigger:hover .hint-tooltip,
.hint-trigger:focus .hint-tooltip { display: block; }
.hint-tooltip {
  display: none;
  position: absolute;
  /* styling */
}
```

- [ ] **Step 6: Commit**

```bash
git add src/cr-tracker.html
git commit -m "feat: step checklist with hard gates, PM override, and completion flow"
```

## Existing code patterns to follow

- DB writes: `try { await window.claude?.db?.set(collection, docId, data); } catch(e) { console.warn(...); }`
- All HTML injection: `escHtml()` / `escAttr()`
- Modals: `hidden` attribute, `.modal-scrim > .modal-card`, Escape and click-outside dismiss
- In-memory CR structure: each item in `crs` array has `{ cr_number, description, developer, ..., steps: { step_01: {status, completed_date, completed_by, comment, override_reason}, ... } }`
- Phase colors in CSS: `--phase-scope`, `--phase-build`, `--phase-test`, `--phase-golive`, `--phase-validation`
- The `PHASES` constant (if Task 2 added one) or derive from `LIFECYCLE_TEMPLATE`
