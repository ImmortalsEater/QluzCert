# 002 — Consolidate the duplicated `cubic-bezier(0.23,1,0.32,1)` literal into `var(--ease-out-strong)`

- **Status**: DONE
- **Commit**: 41a9be2
- **Severity**: MEDIUM
- **Category**: Cohesion & tokens
- **Estimated scope**: 2 files, 2 one-line edits

## Problem

The exact curve `cubic-bezier(0.23, 1, 0.32, 1)` is already tokenized as `--ease-out-strong` in `core/app_Gestor/static/css/components/buttons.css:25` (inside a global `:root` block), but it is hand-typed as a literal two more times instead of referencing the token:

```css
/* core/app_Gestor/static/css/cert_manager.css:185 — current */
  .modal-overlay.open .modal{transform:scale(1);opacity:1;transition:transform 200ms cubic-bezier(0.23,1,0.32,1),opacity 200ms ease-out}
```

```html
<!-- core/app_Gestor/templates/dashboard.html:19 — current -->
      .toast{display:flex;align-items:flex-start;gap:8px;min-width:200px;padding:12px 14px;border-radius:10px;color:#fff;box-shadow:0 8px 24px rgba(0,0,0,0.16);font-size:13px;line-height:1.4;opacity:0;transform:translateY(8px) scale(0.98);transition:opacity 200ms cubic-bezier(0.23,1,0.32,1),transform 200ms cubic-bezier(0.23,1,0.32,1)}
```

Three literal copies of one curve across three files (`buttons.css`, `cert_manager.css`, `dashboard.html`) is exactly the "duplicated near-identical easing" pattern AUDIT.md category 7 flags for consolidation. Both usages are confirmed reachable: `buttons.css` is `@import`ed at the very top of `cert_manager.css` (`cert_manager.css:1`), which is `<link>`ed at `dashboard.html:15`, immediately before the inline `<style>` block containing the toast rule (`dashboard.html:16-33`) — so `var(--ease-out-strong)` is in scope in both places already, no new `:root` declaration needed.

## Target

```css
/* core/app_Gestor/static/css/cert_manager.css:185 — target */
  .modal-overlay.open .modal{transform:scale(1);opacity:1;transition:transform 200ms var(--ease-out-strong),opacity 200ms ease-out}
```

```html
<!-- core/app_Gestor/templates/dashboard.html:19 — target -->
      .toast{display:flex;align-items:flex-start;gap:8px;min-width:200px;padding:12px 14px;border-radius:10px;color:#fff;box-shadow:0 8px 24px rgba(0,0,0,0.16);font-size:13px;line-height:1.4;opacity:0;transform:translateY(8px) scale(0.98);transition:opacity 200ms var(--ease-out-strong),transform 200ms var(--ease-out-strong)}
```

## Repo conventions to follow

- Easing tokens live in the `:root` block at the top of `core/app_Gestor/static/css/components/buttons.css:24-27`: `--ease-out-strong: cubic-bezier(0.23, 1, 0.32, 1);` and `--ease-out-mechanical: cubic-bezier(0.4, 0, 0.2, 1);`.
- Exemplar of correct usage: `core/app_Gestor/static/css/components/buttons.css:49` — `transition: background-color 150ms ease, border-color 150ms ease, color 150ms ease, transform 120ms var(--ease-out-strong);`.

## Steps

1. In `core/app_Gestor/static/css/cert_manager.css:185`, replace the literal `cubic-bezier(0.23,1,0.32,1)` with `var(--ease-out-strong)` (one occurrence, in the `transform` transition only — leave `opacity 200ms ease-out` untouched, it already correctly uses the built-in `ease-out`).
2. In `core/app_Gestor/templates/dashboard.html:19`, replace both occurrences of the literal `cubic-bezier(0.23,1,0.32,1)` with `var(--ease-out-strong)` (the `opacity` and `transform` transitions both currently use the literal — both become the token).

## Boundaries

- Do NOT touch `buttons.css` — the token already exists there correctly; this plan only removes the two duplicate literals elsewhere.
- Do NOT change durations, the `opacity 200ms ease-out` portion of the modal rule, or any other property.
- Do NOT touch `.toast.toast-visible` (`dashboard.html:20`) — it has no easing to change.
- If the cited lines don't match exactly what's in the repo (drift since commit `41a9be2`), STOP and report instead of improvising.

## Verification

- **Mechanical**: `python manage.py test core.app_Gestor.tests` — this is a pure CSS-value swap with no behavior change, so the suite should stay green (it doesn't assert on CSS). No build step exists in this repo (no bundler) — reload the page to pick up the change.
- **Feel check**: run the dev server (`python manage.py runserver`), open the dashboard.
  - Open any modal (e.g. "Novo Cliente") — the scale-in should look and feel identical to before (same curve, just tokenized).
  - Trigger a toast (e.g. save something) — its slide/scale-in should also look identical to before.
  - In DevTools → Elements, inspect `.modal` and `.toast` and confirm the computed `transition` value resolves to the same cubic-bezier as before (`0.23, 1, 0.32, 1`) — the token must resolve to the exact same curve, not a different one.
- **Done when**: both files reference `var(--ease-out-strong)` instead of the literal, no other transition values changed, and modal/toast entrance motion is visually unchanged.
