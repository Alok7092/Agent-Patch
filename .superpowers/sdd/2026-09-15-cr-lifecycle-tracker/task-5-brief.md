# Task 5: Audit Log Viewer

Surface the audit trail so the PM can see who did what, when, and review override decisions.

**Files:**
- Modify: `src/cr-tracker.html`

**Interfaces:**
- Consumes: `audit` collection from DB (entries have fields: action, cr_number, actor, details, timestamp), in-memory audit data if cached
- Produces: Per-CR "Activity Log" section in the expanded detail panel, plus a global audit log slide-out panel accessible from the top bar (PM view only)

## Steps

- [ ] **Step 1: Add per-CR audit log in the detail panel**

In the expanded CR detail panel (built by Task 3's `buildDetailInner(cr)` or equivalent function), add a collapsible "Activity Log" section at the bottom. Implementation:

1. Add a toggle button/header: "Activity Log" with a collapse/expand chevron
2. When expanded, fetch audit entries for this CR from the DB: query the `audit` collection filtering by `cr_number === cr.crNumber`
3. Render entries in reverse-chronological order (newest first):

```
Sep 14, 10:32 AM · Aravind · Completed Step 4: Request review of FS/TS by HSY IS
Sep 14, 09:15 AM · Alok    · ⚠ Override Gate on Step 5: "IS approved verbally, formal coming Monday"
Sep 13, 03:00 PM · Dev-A   · Completed Step 3: Request peer review of FS/TS
Sep 12, 11:00 AM · Hari    · CR created
```

Each entry shows: formatted timestamp, actor, action description.
- Override entries (`action === 'gate_overridden'`) get a distinct style: amber left border or amber background tint, and show the override reason in the details
- Step skip entries (`action === 'step_skipped'`) show with a muted style

If DB is unavailable, show "Activity log requires database connection."

Use the DB query API: `window.claude?.db?.query?.('audit', { where: [['cr_number', '==', crNumber]] })` — or fall back to listing all audit docs and filtering in JS if query isn't available.

- [ ] **Step 2: Add global audit log (PM only)**

Add a button in the top bar (PM view only): a simple text button or icon labeled "Activity" (or use the existing layout pattern).

Clicking it opens a slide-out panel (right side) or a modal showing the last 50 audit entries across ALL CRs, reverse-chronological.

Each entry shows the CR number as a prefix:
```
CHG0012345 · Sep 14, 10:32 AM · Aravind · Completed Step 4
CHG0056789 · Sep 14, 09:15 AM · Alok    · ⚠ Override Gate on Step 5
```

Add filter chips at the top: "All", "Completions", "Overrides", "CR Created"
- "All" shows everything (default)
- "Completions" filters to `action === 'step_completed'`
- "Overrides" filters to `action === 'gate_overridden'`
- "CR Created" filters to `action === 'cr_created'`

The panel can be closed with an X button, Escape key, or clicking outside.

Style: use the existing modal or slide-out patterns in the codebase.

- [ ] **Step 3: Cache audit entries in memory**

To avoid re-fetching audit entries every time the detail panel is opened:
- Maintain an in-memory `auditLog` array
- Load all audit entries at boot (in the `boot()` function, after loading CRs)
- When new audit entries are created (by `completeStep`, `overrideGate`, `cancelCR`, `saveCR`), push them to the in-memory array too
- The audit log UI reads from the in-memory array, filtered as needed

- [ ] **Step 4: Commit**

```bash
git add src/cr-tracker.html
git commit -m "feat: audit log viewer — per-CR and global activity log"
```

## Existing patterns

- Modal/panel: `.modal-scrim[hidden]` > `.modal-card`, Escape dismiss, click-outside dismiss
- DB reads: `try { const docs = await window.claude?.db?.list?.('audit'); ... } catch(e) { ... }`
- Dynamic HTML: `escHtml()` / `escAttr()`
- Audit entry shape: `{ action: 'step_completed'|'gate_overridden'|'step_skipped'|'cr_created'|'cr_cancelled', cr_number: string, actor: string, details: string, timestamp: ISO string }`
- Timestamp formatting: use `formatDate()` or write a more detailed formatter that includes time
