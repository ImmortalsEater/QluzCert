# 003 — Replace `transition: all` on `.kanban-card` with an explicit property list

- **Status**: DONE
- **Commit**: 41a9be2
- **Severity**: HIGH
- **Category**: Performance
- **Estimated scope**: 1 file, 1 line

## Problem

`.kanban-card` — the single most-dragged, most-hovered element in the app (cards are moved "tens of times a day" by the sales team) — transitions `all` instead of an explicit property list:

```css
/* core/app_Gestor/static/css/cert_manager.css:196 — current */
  .kanban-card{background:var(--surface);border:1px solid var(--border);border-radius:8px;padding:10px;margin-bottom:8px;transition:all .15s;cursor:grab}
```

AUDIT.md category 5 states plainly: "`transition: all` animates unintended properties off-GPU — always a finding." Because this rule sits on every card in the board, it applies to any and every property change on the element (e.g. `border-color`/`transform` from `:hover`, `opacity`/`cursor` from `.dragging`, `border-top`/`border-bottom` from `.drag-over-top`/`.drag-over-bottom` at `cert_manager.css:199-200`), transitioning box-model properties that don't need to animate at all and paying layout/paint cost the two properties that actually change (`border-color`, `transform`) don't require.

## Target

```css
/* core/app_Gestor/static/css/cert_manager.css:196 — target */
  .kanban-card{background:var(--surface);border:1px solid var(--border);border-radius:8px;padding:10px;margin-bottom:8px;transition:border-color 150ms ease,transform 150ms var(--ease-out-strong);cursor:grab}
```

`border-color` covers the `:hover` (`cert_manager.css:197`) and `.drag-over-top`/`.drag-over-bottom` (`cert_manager.css:199-200`) states. `transform` covers the `:hover` lift (`translateY(-1px)`). `opacity` (used only by `.dragging`, `cert_manager.css:198`) is intentionally left out of the transition list — the drag start should feel instant, not fade, since it's a direct manipulation state change, not a mouse-driven hover/focus feedback.

## Repo conventions to follow

- Easing token: `--ease-out-strong: cubic-bezier(0.23, 1, 0.32, 1)`, declared in `core/app_Gestor/static/css/components/buttons.css:24-27` and already in scope (imported at `cert_manager.css:1`).
- Exemplar of an explicit, comma-separated transition property list on a similarly interactive element: `core/app_Gestor/static/css/components/buttons.css:49` — `transition: background-color 150ms ease, border-color 150ms ease, color 150ms ease, transform 120ms var(--ease-out-strong);`.

## Steps

1. In `core/app_Gestor/static/css/cert_manager.css:196`, replace `transition:all .15s` with `transition:border-color 150ms ease,transform 150ms var(--ease-out-strong)`. Leave every other property on that line (`background`, `border`, `border-radius`, `padding`, `margin-bottom`, `cursor`) untouched.

## Boundaries

- Do NOT change `.kanban-card:hover` (`cert_manager.css:197`), `.kanban-card.dragging` (`cert_manager.css:198`), or `.kanban-card.drag-over-top`/`.drag-over-bottom` (`cert_manager.css:199-200`) — only the base rule's `transition` property changes.
- Do NOT touch `.kanban-col` (`cert_manager.css:193`) — its `transition:background-color .15s` is already an explicit single property, out of scope for this plan.
- Do NOT add press feedback (`:active` state) here — that is a separate finding (physicality/origin), not this performance fix.
- If the cited line doesn't match exactly what's in the repo (drift since commit `41a9be2`), STOP and report instead of improvising.

## Verification

- **Mechanical**: `python manage.py test core.app_Gestor.tests` should stay green (pure CSS change, no test asserts on it).
- **Feel check**: run the dev server, open the Kanban view (Funil).
  - Hover over a card: the border should still darken and the card should still lift by 1px, exactly as before — visually indistinguishable from the `transition: all` version.
  - Drag a card over another card: the `drag-over-top`/`drag-over-bottom` border indicator should still animate in smoothly.
  - Start dragging a card: it should still drop to `opacity: .5` instantly (no fade-out lag introduced or removed — this was already instant since `opacity` was never explicitly listed as needing a specific duration, and removing it from `all` keeps it exactly as abrupt as intended).
  - In DevTools → Performance, record a short trace while rapidly hovering across several cards; confirm no unexpected properties (e.g. `padding`, `border-radius`) show up in the "Recalculate Style"/"Paint" flame chart tied to the hover transition.
- **Done when**: `.kanban-card`'s `transition` property lists only `border-color` and `transform`, all existing hover/drag-over visual feedback is unchanged, and no other kanban CSS rule was touched.
