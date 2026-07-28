# 005 — Add open/close motion to the column-selector panel and the row-action kebab menu

- **Status**: DONE
- **Commit**: 41a9be2
- **Severity**: HIGH
- **Category**: Physicality & origin (+ Missed opportunity, + Cohesion for the chevron sub-fix)
- **Estimated scope**: 3 files (`buttons.css`, `cert_manager.css`, `cert_manager.core.js`), ~4 edits

## Problem

Both floating popovers in the app teleport open/closed via a bare `display:none`/`display:flex` toggle — no transition, no transform, no `transform-origin` at all, despite both being anchored to a visible trigger button and opened "tens of times a day":

```css
/* core/app_Gestor/static/css/cert_manager.css:105-106 — column-selector panel, current */
  .column-selector-panel{position:absolute;right:0;top:calc(100% + 8px);background:var(--surface);border-radius:12px;box-shadow:0 1px 1px rgba(0,0,0,.04),0 4px 8px rgba(0,0,0,.06),0 16px 32px rgba(0,0,0,.10);display:none;flex-direction:column;gap:2px;padding:4px;min-width:230px;max-height:320px;overflow-y:auto;overflow-x:hidden;z-index:20;scrollbar-width:thin;scrollbar-color:var(--border) transparent}
  .column-selector-panel.open{display:flex}
```

```css
/* core/app_Gestor/static/css/cert_manager.css:119-120 — kebab row-action menu, current */
  #action-menu-dropdown{position:fixed;display:none;flex-direction:column;gap:2px;padding:4px;min-width:180px;background:var(--surface);border-radius:12px;box-shadow:0 1px 1px rgba(0,0,0,.04),0 4px 8px rgba(0,0,0,.06),0 16px 32px rgba(0,0,0,.10);z-index:60}
  #action-menu-dropdown.open{display:flex}
```

AUDIT.md category 3 requires "Popovers/dropdowns/tooltips scale from their trigger, not center" — there's nothing to scale from today, and category 8 explicitly names this pattern: "Spatially-connected UI (a panel that appears from a trigger) with no motion explaining where it came from."

The kebab menu's anchor point is computed dynamically in JS and can flip above or below its trigger depending on viewport space:

```js
// core/app_Gestor/static/js/cert_manager.core.js:559-590 — openRowActionMenu, current
function openRowActionMenu(e, id){
  e.stopPropagation();
  const menu = document.getElementById('action-menu-dropdown');
  if(!menu) return;
  const wasOpenForThisRow = menu.classList.contains('open') && menu.dataset.forId === id;
  closeActionMenu();
  document.getElementById('column-selector-panel')?.classList.remove('open');
  document.getElementById('save-menu')?.classList.remove('open');
  if(wasOpenForThisRow) return;

  menu.dataset.forId = id;
  menu.innerHTML = `
    <a href="/planilha/${id}/documentos/" class="action-menu-item" role="menuitem" onclick="event.preventDefault(); closeActionMenu(); navigateIfExists('${id}', this.href);"><i class="ti ti-folder"></i>Documentos</a>
    <button type="button" class="action-menu-item" role="menuitem" onclick="closeActionMenu(); openHistoricoCliente('${id}')"><i class="ti ti-history"></i>Histórico</button>
    <div class="action-menu-divider"></div>
    <button type="button" class="action-menu-item action-menu-item-danger" role="menuitem" onclick="closeActionMenu(); deletePlanilhaCliente('${id}')"><i class="ti ti-trash"></i>Excluir</button>
  `;

  const btn = e.currentTarget;
  const rect = btn.getBoundingClientRect();
  menu.classList.add('open');
  const menuRect = menu.getBoundingClientRect();
  let top = rect.bottom + 6;
  let left = rect.right - menuRect.width;
  if(left < 8) left = 8;
  if(top + menuRect.height > window.innerHeight - 8) top = rect.top - menuRect.height - 6;
  menu.style.top = top + 'px';
  menu.style.left = left + 'px';
}
```

Because the menu can land above (flipped) or below its trigger, a static CSS `transform-origin` would be wrong on the flipped-up branch — the origin has to be computed alongside the existing `top` calculation.

A `display: none` → `flex` toggle is also the exact pattern that, per AUDIT.md category 4, breaks retargeting if a transition is bolted on without also removing the `display` cliff-edge — so this plan follows the same `opacity`/`visibility`/`pointer-events` pattern already used correctly by `.modal-overlay` (`cert_manager.css:182-183`) instead of layering a transition on top of `display: none`.

Separately, the column-selector's chevron indicator already animates on open/close but uses a bare, untokenized `ease` for what is a rotation (AUDIT.md's easing decision order calls rotation "moving/morphing on screen" → `ease-in-out`, not the default `ease`):

```css
/* core/app_Gestor/static/css/cert_manager.css:111 — current */
  .chevron{transition:transform 150ms ease}
```

## Target

**1. New token** — add `--ease-in-out` alongside the existing two tokens (needed for the chevron fix, step 4):

```css
/* core/app_Gestor/static/css/components/buttons.css:24-27 — target */
:root {
  --ease-out-strong: cubic-bezier(0.23, 1, 0.32, 1);
  --ease-out-mechanical: cubic-bezier(0.4, 0, 0.2, 1);
  --ease-in-out: cubic-bezier(0.77, 0, 0.175, 1);
}
```

**2. Column-selector panel** — replace the `display:none`/`.open{display:flex}` pattern with opacity/scale, mirroring `.modal-overlay`'s structure:

```css
/* core/app_Gestor/static/css/cert_manager.css:105-106 — target */
  .column-selector-panel{position:absolute;right:0;top:calc(100% + 8px);background:var(--surface);border-radius:12px;box-shadow:0 1px 1px rgba(0,0,0,.04),0 4px 8px rgba(0,0,0,.06),0 16px 32px rgba(0,0,0,.10);display:flex;flex-direction:column;gap:2px;padding:4px;min-width:230px;max-height:320px;overflow-y:auto;overflow-x:hidden;z-index:20;scrollbar-width:thin;scrollbar-color:var(--border) transparent;opacity:0;visibility:hidden;pointer-events:none;transform:scale(0.95);transform-origin:top right;transition:opacity 180ms var(--ease-out-strong),transform 180ms var(--ease-out-strong),visibility 180ms}
  .column-selector-panel.open{opacity:1;visibility:visible;pointer-events:auto;transform:scale(1)}
```

**3. Kebab row-action menu** — same pattern; `transform-origin` defaults to `top right` here (JS sets it explicitly per-open in step 4 below, since it can also flip to `bottom right`):

```css
/* core/app_Gestor/static/css/cert_manager.css:119-120 — target */
  #action-menu-dropdown{position:fixed;display:flex;flex-direction:column;gap:2px;padding:4px;min-width:180px;background:var(--surface);border-radius:12px;box-shadow:0 1px 1px rgba(0,0,0,.04),0 4px 8px rgba(0,0,0,.06),0 16px 32px rgba(0,0,0,.10);z-index:60;opacity:0;visibility:hidden;pointer-events:none;transform:scale(0.95);transform-origin:top right;transition:opacity 180ms var(--ease-out-strong),transform 180ms var(--ease-out-strong),visibility 180ms}
  #action-menu-dropdown.open{opacity:1;visibility:visible;pointer-events:auto;transform:scale(1)}
```

**4. JS: compute `transform-origin` alongside the existing flip calculation**:

```js
/* core/app_Gestor/static/js/cert_manager.core.js:580-589 — target (only the tail of openRowActionMenu changes) */
  const btn = e.currentTarget;
  const rect = btn.getBoundingClientRect();
  menu.classList.add('open');
  const menuRect = menu.getBoundingClientRect();
  let top = rect.bottom + 6;
  let left = rect.right - menuRect.width;
  if(left < 8) left = 8;
  let flipped = false;
  if(top + menuRect.height > window.innerHeight - 8){ top = rect.top - menuRect.height - 6; flipped = true; }
  menu.style.top = top + 'px';
  menu.style.left = left + 'px';
  menu.style.transformOrigin = flipped ? 'bottom right' : 'top right';
```

**5. Chevron** — swap the bare `ease` for the new token:

```css
/* core/app_Gestor/static/css/cert_manager.css:111 — target */
  .chevron{transition:transform 150ms var(--ease-in-out)}
```

## Repo conventions to follow

- Exemplar for the opacity/visibility/pointer-events pattern (avoids the `display:none` transition trap): `core/app_Gestor/static/css/cert_manager.css:182-183`, `.modal-overlay`/`.modal-overlay.open`.
- Easing tokens live in `core/app_Gestor/static/css/components/buttons.css:24-27`.
- Dropdown duration budget (AUDIT.md): 150–250ms — this plan uses 180ms, inside the budget and close to the existing chevron's 150ms for visual consistency between trigger and panel.

## Steps

1. In `core/app_Gestor/static/css/components/buttons.css:24-27`, add the `--ease-in-out: cubic-bezier(0.77, 0, 0.175, 1);` line inside the existing `:root` block (Target section 1).
2. In `core/app_Gestor/static/css/cert_manager.css:105-106`, replace the two `.column-selector-panel`/`.column-selector-panel.open` rules with Target section 2.
3. In `core/app_Gestor/static/css/cert_manager.css:119-120`, replace the two `#action-menu-dropdown`/`#action-menu-dropdown.open` rules with Target section 3.
4. In `core/app_Gestor/static/js/cert_manager.core.js`, inside `openRowActionMenu` (currently lines 580-589), add the `flipped` variable and the `menu.style.transformOrigin = ...` line as shown in Target section 4 — the existing `top`/`left` computation logic doesn't change, only gains the `flipped` tracking and the new style assignment.
5. In `core/app_Gestor/static/css/cert_manager.css:111`, replace `.chevron{transition:transform 150ms ease}` with Target section 5.

## Boundaries

- Do NOT change the mutual-exclusivity logic (`closeActionMenu()`, the `column-selector-panel`/`save-menu` close-on-open-other calls at `core.js:568-569` and `dashboard.html:361-362`) — switching to opacity/visibility instead of `display:none` makes the existing `classList.remove('open')` calls already correct (they now trigger a proper CSS exit transition instead of an instant cut), so no JS logic changes are needed there beyond what step 4 specifies.
- Do NOT touch `#save-menu` (`cert_manager.dashboard.js:33`, styled via the same `.column-selector-panel` class) — it inherits this fix automatically since it shares the class; don't add a separate rule for it.
- Do NOT change `z-index` values (`20` for the column panel, `60` for the kebab menu) — those already prevent real stacking conflicts per the dropdown audit; only the motion changes here.
- Do NOT change the kebab menu's content-rebuild logic (`menu.innerHTML = ...`) or navigation behavior.
- If any cited line/block doesn't match exactly what's in the repo (drift since commit `41a9be2`), STOP and report instead of improvising.

## Verification

- **Mechanical**: `python manage.py test core.app_Gestor.tests` should stay green (no Python changes; JS/CSS only, and no test exercises these dropdowns via headless JS).
- **Feel check**: run the dev server, open the Planilha/Clientes table view.
  - Click "Colunas" — the panel should scale+fade in from its top-right corner (where the button is), not teleport into existence. Click elsewhere to close — it should scale+fade out the same way, not vanish instantly.
  - Click the "⋮" kebab on a row near the top of the table (menu opens downward) — confirm it grows from the top-right corner (near the button).
  - Scroll down so a row's kebab is near the bottom of the viewport, open it — confirm the menu flips above the button and now grows from the **bottom**-right corner (not top-right) — this is the `flipped` branch from step 4; getting this wrong would look like the menu growing from the wrong corner.
  - Click one row's kebab, then immediately click a different row's kebab — the menu should reposition/re-fade smoothly to the new row, no flash of unstyled/empty content.
  - In DevTools → Animations panel, set playback to 10% and confirm both popovers scale from their anchored corner, not from the panel's center.
  - Toggle `prefers-reduced-motion` (Rendering panel) — since this plan doesn't add a reduced-motion block for these two components, note whether that's an acceptable follow-up gap (it is not covered by this plan; if desired, extend plan 004's pattern to `.column-selector-panel`/`#action-menu-dropdown` in a later pass).
- **Done when**: both popovers scale/fade from their trigger corner (dynamically bottom-anchored for the kebab menu when flipped), the chevron rotation uses `var(--ease-in-out)`, and no existing click-outside-to-close or mutual-exclusivity behavior regressed.
