# Task 2: CR Creation and Pipeline Table

Add the ability to create CRs and display them in the PM pipeline table.

**Files:**
- Modify: `src/cr-tracker.html`

**Interfaces:**
- Consumes: `LIFECYCLE_TEMPLATE` constant (already in file), `team` collection (for developer/owner dropdowns), `window.claude.db` for persistence, `teamMembers` in-memory array, `escHtml()`/`escAttr()` helpers, `formatDate()`, `renderAll()`, `renderKPIs()` functions
- Produces: CR documents in `crs` collection, 24 step documents per CR in `crs/{crNumber}/steps` collection, rendered pipeline table rows with phase progress bars, updated KPI counts

## Steps

- [ ] **Step 1: Build the "Add CR" modal form**

Replace the current `openAddCRModal()` placeholder (line ~1432, currently shows `alert('Add CR — coming in Task 2')`) with a real modal. Add the modal HTML to the markup section (near the existing `team-modal`). The modal contains:

- CR Number (text input — free-form, e.g., "CHG0012345")
- Description (text input)
- Developer (dropdown populated from `teamMembers` array, filtered to role="developer")
- Change Owner (dropdown populated from `teamMembers` array, filtered to role="change_owner")
- Target Release Date (date picker — defaults to next Thursday)
- "Create" and "Cancel" buttons

Validation: CR Number required and must be unique (check against in-memory `crs` array). Description required.

Follow the existing modal pattern from `team-modal`: same `.modal-scrim`/`.modal-card` classes, Escape key and click-outside dismiss, focus ring styles.

- [ ] **Step 2: Implement CR creation logic**

On "Create":
1. Save CR document to `crs/{crNumber}` via `window.claude?.db?.set('crs', crNumber, {...})` with fields: description, developer, developer_email, change_owner, change_owner_email, target_release_date, created_date (ISO string of today), status ("active")
2. Create 24 step documents. Use a batch if available, otherwise sequential writes. Each step document ID is `step_${String(n).padStart(2,'0')}`, saved to collection `crs/${crNumber}/steps`. Each doc contains:
   ```javascript
   {
     status: template.hardGate && template.prerequisites.length > 0 ? "locked" : "pending",
     completed_date: null,
     completed_by: null,
     comment: "",
     override_reason: null
   }
   ```
   Exception: step 1 always starts as "pending" regardless of gate status.
3. Write an audit log entry to `audit` collection with doc ID `${Date.now()}_${crNumber}`:
   ```javascript
   { action: "cr_created", cr_number: crNumber, actor: currentUser, details: "CR created", timestamp: new Date().toISOString() }
   ```
4. Add the CR to the in-memory `crs` array (with its steps).
5. Close modal and call `renderAll()`.

- [ ] **Step 3: Render the pipeline table**

Modify `renderCRTable()` (currently renders an empty state) to show real CRs. For each active CR, render a table row:

- **CR #**: `<span class="mono">{crNumber}</span>`, clickable (use `onclick="toggleCRExpand('{crNumber}')"` — the expand function already exists)
- **Description**: truncated to ~40 chars with full text in title attribute
- **Phase**: a mini 5-segment progress bar. Determine current phase from the first non-completed step. Each segment is a small inline block colored by its phase token (use inline style or data-attribute for the phase color). Completed phases are filled; current is filled; future phases are outlined/faded.
- **Current Step**: name of the first step where status !== "completed", trimmed to fit
- **Owner**: resolve the ownerRole from the template to the actual person name. If ownerRole contains "Developer" → use CR's developer field. If "Change Owner" → use CR's change_owner field. Otherwise show the role name as-is.
- **Status**: badge using existing status colors. Compute: if current step's template has `hardGate: true` and its status is "locked" → "Blocked" (red). Else if days pending > threshold → "At Risk" (amber). Else → "On Track" (green).
- **Days**: days since the previous step was completed (or CR creation for step 1). Use `Math.floor((Date.now() - new Date(prevCompletedDate).getTime()) / 86400000)`.
- **Deadline**: target_release_date formatted as "Sep 18".

Sort: Blocked first, then At Risk, then On Track.

- [ ] **Step 4: Update KPI cards with live counts**

Modify `renderKPIs()` to use real data. After computing table rows (which determines each CR's status), update:
- **Total Active CRs**: `crs.filter(c => c.status === 'active').length`
- **On Track**: count with computed row status "ok"
- **At Risk**: count with "risk"
- **Blocked**: count with "blocked"

Color-code each KPI value by its status color token.

- [ ] **Step 5: Load CRs from DB on boot**

Modify the `boot()` function to load existing CRs from the DB after loading team members. For each CR in the `crs` collection, also load its steps from `crs/{crNumber}/steps`. Populate the in-memory `crs` array, then call `renderAll()`.

Handle the DB list response defensively (same pattern as team member loading).

- [ ] **Step 6: Commit**

```bash
git add src/cr-tracker.html
git commit -m "feat: CR creation form and pipeline table with KPI cards"
```

## Important existing code patterns to follow

- All DB writes use `try/catch` with `window.claude?.db?.set(...)` 
- All dynamic HTML uses `escHtml()` and `escAttr()` for XSS prevention
- Modals use `hidden` attribute (not display style)
- Modal class structure: `.modal-scrim > .modal-card > .modal-header + .modal-body + .modal-footer`
- Current user comes from `currentUser` variable (set via localStorage and user chip)
- `teamMembers` is the in-memory array of team members loaded at boot
- `crs` is the in-memory array that currently starts empty — populate it
