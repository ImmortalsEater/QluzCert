# 004 — Add `prefers-reduced-motion` coverage (modal, kanban, toast) and `hover: hover` pointer gating (kanban card, table row)

- **Status**: DONE
- **Commit**: 41a9be2
- **Severity**: MEDIUM
- **Category**: Accessibility
- **Estimated scope**: 2 files (`cert_manager.css`, `dashboard.html`), ~4 small additions

## Problem

Two separate AUDIT.md category 6 gaps, both currently unaddressed outside of `buttons.css`:

**1. No `prefers-reduced-motion` handling for movement in the modal, kanban hover, or toast.** The only existing reduced-motion block in the whole static tree is scoped to `.btn`:

```css
/* core/app_Gestor/static/css/components/buttons.css:371-384 — existing, correct, the only one */
@media (prefers-reduced-motion: reduce) {
  .btn {
    transition: background-color 150ms ease, border-color 150ms ease, color 150ms ease;
  }
  .btn:active {
    transform: none;
  }
  .btn.is-loading::before {
    animation-duration: 1200ms;
  }
}
```

Three components move (not just fade) with no equivalent gate:

```css
/* core/app_Gestor/static/css/cert_manager.css:184-185 — modal, current */
  .modal{background:var(--surface);border-radius:12px;width:100%;max-width:680px;max-height:90vh;overflow:hidden;display:flex;flex-direction:column;box-shadow:0 20px 60px rgba(0,0,0,.2);transform:scale(0.95);opacity:0;transition:transform 150ms ease-out,opacity 150ms ease-out}
  .modal-overlay.open .modal{transform:scale(1);opacity:1;transition:transform 200ms cubic-bezier(0.23,1,0.32,1),opacity 200ms ease-out}
```

```css
/* core/app_Gestor/static/css/cert_manager.css:197 — kanban card hover, current */
  .kanban-card:hover{border-color:var(--border-strong);transform:translateY(-1px)}
```

```html
<!-- core/app_Gestor/templates/dashboard.html:19-20 — toast, current -->
      .toast{...opacity:0;transform:translateY(8px) scale(0.98);transition:opacity 200ms cubic-bezier(0.23,1,0.32,1),transform 200ms cubic-bezier(0.23,1,0.32,1)}
      .toast.toast-visible{opacity:1;transform:translateY(0) scale(1)}
```

Per AUDIT.md category 6, reduced motion should keep opacity/color feedback but drop position/scale movement — none of these three do that today.

**2. No `hover: hover` / `pointer: fine` gate on `.kanban-card:hover` or `tbody tr:hover`.** A repo-wide search confirms zero existing usage of `@media (hover: hover)` anywhere in the codebase. On touch devices, tapping a kanban card or a table row can leave it visually "stuck" hovered until something else is tapped:

```css
/* core/app_Gestor/static/css/cert_manager.css:197 — current */
  .kanban-card:hover{border-color:var(--border-strong);transform:translateY(-1px)}
```

```css
/* core/app_Gestor/static/css/cert_manager.css:131,133 — current */
  tbody tr{border-bottom:1px solid var(--border);transition:background-color 120ms ease}
  tbody tr:hover{background:#fafaf8}
```

```css
/* core/app_Gestor/static/css/cert_manager.css:153 — current */
  .google-drive-table tbody tr:hover td:last-child{background:#fafaf8}
```

## Target

Add one new reduced-motion block to `cert_manager.css` (near the existing motion-heavy rules, right after the modal block) and one to the toast `<style>` block in `dashboard.html`. Add one new pointer-gate block to `cert_manager.css` for kanban + table hover.

```css
/* core/app_Gestor/static/css/cert_manager.css — new block, insert immediately after line 189 (.modal-foot rule) */
  @media (prefers-reduced-motion: reduce) {
    .modal{transform:none;transition:opacity 150ms ease-out}
    .modal-overlay.open .modal{transform:none;transition:opacity 200ms ease-out}
    .kanban-card:hover{transform:none}
  }
```

```css
/* core/app_Gestor/static/css/cert_manager.css — new block, insert immediately after line 203 (.kanban-card-footer rule), or adjacent to the reduced-motion block above — either location is fine as long as it doesn't sit inside another rule */
  @media (hover: hover) and (pointer: fine) {
    .kanban-card:hover{border-color:var(--border-strong);transform:translateY(-1px)}
  }
  @media (hover: hover) and (pointer: fine) {
    tbody tr:hover{background:#fafaf8}
    .google-drive-table tbody tr:hover td:last-child{background:#fafaf8}
  }
```

```html
<!-- core/app_Gestor/templates/dashboard.html — new rule, insert immediately after line 20 (.toast.toast-visible rule), inside the existing <style> block -->
      @media (prefers-reduced-motion: reduce) {
        .toast{transform:none;transition:opacity 200ms ease-out}
        .toast.toast-visible{transform:none}
      }
```

## Repo conventions to follow

- Exemplar reduced-motion block to imitate the shape of: `core/app_Gestor/static/css/components/buttons.css:371-384` (quoted in full above) — keeps color/opacity transitions, sets `transform: none` on the moving states.
- Keep the new blocks near the rules they modify (don't create a separate "accessibility.css" file — this repo has no such convention; `buttons.css` puts its reduced-motion block at the bottom of the same file it belongs to).

## Steps

1. In `core/app_Gestor/static/css/cert_manager.css`, immediately after line 189 (`.modal-foot{...}`), insert the reduced-motion block shown in Target above (modal + kanban-card hover transform removal, three selectors total).
2. In `core/app_Gestor/static/css/cert_manager.css`, immediately after line 203 (`.kanban-card-footer{...}`), insert the two `@media (hover: hover) and (pointer: fine)` blocks shown in Target above, moving the existing `.kanban-card:hover` declaration (currently unconditional at line 197) so it only applies inside the new media query — **do not leave a duplicate unconditional copy at line 197**, remove the original `border-color`/`transform` declarations from line 197 once they're moved inside the media query (the selector `.kanban-card:hover{...}` should exist only once, inside the media query, after this step).
3. Similarly move `tbody tr:hover{background:#fafaf8}` (currently line 133) and `.google-drive-table tbody tr:hover td:last-child{background:#fafaf8}` (currently line 153) inside the new `@media (hover: hover) and (pointer: fine)` block from step 2 — remove them from their original unconditional locations once moved.
4. In `core/app_Gestor/templates/dashboard.html`, immediately after line 20 (`.toast.toast-visible{...}`), insert the reduced-motion block shown in Target above.

## Boundaries

- Do NOT change `tbody tr{border-bottom:1px solid var(--border);transition:background-color 120ms ease}` (line 131) itself — only the `:hover` rule moves into the media query; the base row styling and its `transition` declaration stay exactly where they are (they're harmless with no hover to trigger, and removing them would change the transition-out behavior when a touch device's `:hover` state clears).
- Do NOT touch `.kanban-card.dragging`, `.kanban-card.drag-over-top`, `.kanban-card.drag-over-bottom` (lines 198-200) — those are drag-state feedback, not hover, and are out of scope for both the reduced-motion and pointer-gate fixes here.
- Do NOT add a reduced-motion rule for the kanban drag-over border indicators (`.kanban-col.drag-over`, `.kanban-card.drag-over-top/bottom`) — those are color-only, no movement, already compliant, nothing to fix.
- Do NOT change any duration or easing values — this plan only adds conditional gating, it doesn't retune existing motion.
- If any cited line doesn't match exactly what's in the repo (drift since commit `41a9be2`), STOP and report instead of improvising.

## Verification

- **Mechanical**: `python manage.py test core.app_Gestor.tests` should stay green (pure CSS change).
- **Feel check**: run the dev server.
  - In Chrome DevTools → Rendering panel, set "Emulate CSS media feature `prefers-reduced-motion`" to `reduce`. Reload the dashboard:
    - Open a modal — it should now appear/disappear via an opacity fade only, no scale/grow motion.
    - Trigger a toast — it should fade in/out only, no slide-up motion.
    - Hover a kanban card — the border-color change should still happen (comprehension-aiding, correctly kept), but no `translateY` lift.
  - Turn the emulation back to "No emulation," then in DevTools → Device toolbar, switch to a touch device emulation (e.g. a tablet) and tap a kanban card and a table row: the hover state should no longer trigger/stick after the tap (since `pointer: fine` won't match a touch pointer).
  - On a normal mouse/trackpad (no touch emulation), confirm kanban card hover and table row hover still work exactly as before — border darkening, background tint, and the 1px lift on kanban cards.
- **Done when**: all three `@media` blocks exist as specified, `.kanban-card:hover`/`tbody tr:hover`/`.google-drive-table tbody tr:hover td:last-child` each appear exactly once (inside their new media query, not duplicated), reduced-motion emulation removes movement but keeps color feedback on modal/kanban/toast, and touch-device emulation no longer sticks hover state on kanban cards or table rows.
