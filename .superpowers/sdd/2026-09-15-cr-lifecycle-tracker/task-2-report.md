# Task 2 Report
## Status: DONE

## Commits
- `85d8ee6` feat: CR creation form and pipeline table with KPI cards

## Test summary
All six steps implemented and reviewed in-file: modal HTML present with correct `.modal-scrim`/`.modal-card` structure, `saveCR()` validated and traced (DB writes with try/catch, batch-first step creation, audit log, in-memory push, `renderAll()` call), `loadCRs()` wired into `boot()` with same defensive array-shape pattern as `loadTeam()`, `computeCRInfo()` correctly derives status (blocked/risk/ok), `renderCRTable()` sorts Blocked→At Risk→On Track and always passes all-active-CR infos to `renderKPIs()`, Escape and click-outside handlers added for the new modal.

## Concerns
1. **Phase progress bar uses inline styles** — the brief asked for a 5-segment bar but the existing `.lifecycle-seg` CSS is only used inside the expanded detail row, so the pipeline-table phase bar is built with inline `div` styles rather than reusing those classes. This avoids collisions and works correctly but differs slightly from what a future task might expect to query via CSS selectors.
2. **Developer-view filter** — the old stub filtered by `cr.ownerName === currentUser`; replaced with `cr.developer === currentUser || cr.change_owner === currentUser` since the new CR shape has no `ownerName` field. If the dev-view intent is stricter (only the assigned developer, not the change owner), the filter can be narrowed.
3. **No DB-unavailable step population fallback** — when `dbAvailable` is false, step docs are never persisted but ARE created in-memory (in `saveCR()`), so the UI works for a session. On reload the CR is also lost, which is the expected fallback behavior.
