# 001 — Fix semantic button hover background falling back to gray instead of deepening its own color

- **Status**: DONE
- **Commit**: 0508474
- **Severity**: MEDIUM
- **Category**: Cohesion & tokens (hover color state / CSS specificity)
- **Estimated scope**: 1 file, 4 small edits (same pattern repeated)

## Problem

`core/app_Gestor/static/css/components/buttons.css` defines four semantic "soft" button
variants — `.btn-danger`, `.btn-success`, `.btn-warn`, `.btn-info` — each a light tinted
background with colored text/border. On hover, each variant's `:hover` rule darkens the
text and border but never sets `background`:

```css
/* core/app_Gestor/static/css/components/buttons.css:135-144 — current */
.btn-danger {
  background: var(--danger-bg);
  color: var(--danger);
  border-color: var(--danger);
}

.btn-danger:hover {
  color: var(--danger-hover);
  border-color: var(--danger-hover);
}
```

(Same pattern at lines 146–155 for `.btn-success`, 157–166 for `.btn-warn`, 168–177 for
`.btn-info`.)

Because `background` is left undeclared in these `:hover` rules, the cascade falls through
to the base hover rule instead:

```css
/* core/app_Gestor/static/css/components/buttons.css:41-44 — current */
.btn:hover {
  background: var(--surface-alt);
  border-color: var(--border-strong);
}
```

`.btn:hover` (specificity `(0,2,0)`: one class + one pseudo-class) and `.btn-danger:hover`
(also `(0,2,0)`: one class + one pseudo-class) are equally specific, but `.btn:hover` sets
`background` and `.btn-danger:hover` does not — so for the `background` property, the only
declarations in the cascade are `.btn{background:var(--surface)}` (spec `(0,1,0)`),
`.btn:hover{background:var(--surface-alt)}` (spec `(0,2,0)`), and
`.btn-danger{background:var(--danger-bg)}` (spec `(0,1,0)`). `.btn:hover` wins outright on
specificity, regardless of source order. **Result: hovering a `.btn-danger` (or -success /
-warn / -info) button flips its background to neutral gray (`--surface-alt`) instead of
deepening its own color** — the opposite of what a hover state should communicate, and
inconsistent with the two variants that get this right today:

```css
/* core/app_Gestor/static/css/components/buttons.css:79-88 — .btn-secondary, correct pattern */
.btn-secondary {
  background: var(--surface);
  color: var(--text);
  border-color: var(--border);
}

.btn-secondary:hover {
  background: var(--surface-alt);
  border-color: var(--border-strong);
}
```

```css
/* core/app_Gestor/static/css/components/buttons.css:93-103 — .btn-outline/.btn-edit, correct pattern */
.btn-outline,
.btn-edit {
  background: transparent;
  color: var(--accent);
  border-color: var(--accent);
}

.btn-outline:hover,
.btn-edit:hover {
  background: var(--accent-light);
}
```

Both `.btn-secondary` and `.btn-outline`/`.btn-edit` explicitly re-declare `background` in
their own `:hover` rule, so they never fall through to `.btn:hover`'s gray. `.btn-danger`,
`.btn-success`, `.btn-warn`, and `.btn-info` are the only four variants missing this.

Note: none of these four classes are wired into any template or JS yet (confirmed via
repo-wide search — `.btn-edit` is live in `dashboard.html`, the other four are not). This
is not yet visible in the running app, but it is a live defect in the component file, and
it will break the first hover the moment any of these four classes is used in markup.

## Target

Each of the four semantic `:hover` rules should deepen its own background instead of
leaving it to fall through to the neutral gray. Use `color-mix()` blending the variant's
existing `-bg` token toward its existing `-hover` token — no new colors, only tokens that
already exist and are already wired elsewhere in `cert_manager.css`'s `:root`. Use a 30%
mix toward `-hover` for all four, so the family reads as one consistent hover rule rather
than four separately-tuned ones:

```css
/* target */
.btn-danger:hover {
  background: color-mix(in srgb, var(--danger-bg) 70%, var(--danger-hover) 30%);
  color: var(--danger-hover);
  border-color: var(--danger-hover);
}

.btn-success:hover {
  background: color-mix(in srgb, var(--success-bg) 70%, var(--success-hover) 30%);
  color: var(--success-hover);
  border-color: var(--success-hover);
}

.btn-warn:hover {
  background: color-mix(in srgb, var(--warn-bg) 70%, var(--warn-hover) 30%);
  color: var(--warn-hover);
  border-color: var(--warn-hover);
}

.btn-info:hover {
  background: color-mix(in srgb, var(--info-bg) 70%, var(--info-hover) 30%);
  color: var(--info-hover);
  border-color: var(--info-hover);
}
```

The existing `background-color 150ms ease` entry in the base `.btn` transition (line 38,
unchanged) already covers this — hover/color changes correctly use `ease` per this
project's own convention, so no timing or easing change is needed, only the missing
`background` declaration.

## Repo conventions to follow

- Every color used must be an existing CSS custom property already defined in
  `core/app_Gestor/static/css/cert_manager.css`'s `:root` (`--danger-bg`, `--danger-hover`,
  `--success-bg`, `--success-hover`, `--warn-bg`, `--warn-hover`, `--info-bg`,
  `--info-hover` all already exist — confirmed present). Do not introduce a new hex value
  or a new custom property.
- `--secondary` / `--tertiary` / `--quaternary` stay untouched — DESIGN.md documents them
  as reserved and asks not to reach for them ad hoc. This plan doesn't touch them.
- Exemplar to imitate: `.btn-secondary:hover` and `.btn-outline:hover`/`.btn-edit:hover`
  (`core/app_Gestor/static/css/components/buttons.css:85-88` and `:100-103`) — both
  explicitly re-declare `background` in their `:hover` rule rather than relying on
  `.btn:hover`'s fallback. Follow that same explicit-redeclaration pattern.
- Radius (7px), no `box-shadow`, and press scale (`0.96`) are untouched by this plan — this
  is a background-color-only fix.

## Steps

1. In `core/app_Gestor/static/css/components/buttons.css`, replace the `.btn-danger:hover`
   rule (currently lines 141-144) with:
   ```css
   .btn-danger:hover {
     background: color-mix(in srgb, var(--danger-bg) 70%, var(--danger-hover) 30%);
     color: var(--danger-hover);
     border-color: var(--danger-hover);
   }
   ```
2. Replace the `.btn-success:hover` rule (currently lines 152-155) with:
   ```css
   .btn-success:hover {
     background: color-mix(in srgb, var(--success-bg) 70%, var(--success-hover) 30%);
     color: var(--success-hover);
     border-color: var(--success-hover);
   }
   ```
3. Replace the `.btn-warn:hover` rule (currently lines 163-166) with:
   ```css
   .btn-warn:hover {
     background: color-mix(in srgb, var(--warn-bg) 70%, var(--warn-hover) 30%);
     color: var(--warn-hover);
     border-color: var(--warn-hover);
   }
   ```
4. Replace the `.btn-info:hover` rule (currently lines 174-177) with:
   ```css
   .btn-info:hover {
     background: color-mix(in srgb, var(--info-bg) 70%, var(--info-hover) 30%);
     color: var(--info-hover);
     border-color: var(--info-hover);
   }
   ```

## Boundaries

- Do NOT touch `.btn`, `.btn-primary`, `.btn-secondary`, `.btn-outline`/`.btn-edit`,
  `.btn-ghost`, `.btn-sm`, `.btn-lg`, `.btn-block`, the loading state, or the hit-area
  expansion block in this same file — they are already correct.
- Do NOT touch `core/app_Gestor/static/css/cert_manager.css` or any template/JS file — no
  markup currently uses `.btn-danger`/`.btn-success`/`.btn-warn`/`.btn-info`, so this is a
  CSS-only fix with nothing to wire up.
- Do NOT change the `-bg`/`-hover` mix ratio per-variant — keep all four at 70%/30% so the
  family stays one consistent token-driven rule (Cohesion & tokens).
- Do NOT add `box-shadow`, change `border-radius`, or change the transition duration/easing
  — this plan is a background-color value fix only.
- If the current code at any of the four cited line ranges doesn't match what's quoted
  above (drift since commit `0508474`), STOP and report instead of guessing which rule to
  replace.

## Verification

- **Mechanical**: none — this is a static CSS file served directly by Django's
  `AppDirectoriesFinder` (`core/app_Gestor/static/css/components/buttons.css`), no build
  step. Confirm the file still parses as valid CSS (matched braces, no stray commas) by
  reading it back after the edit.
- **Feel check**: since none of these classes are wired into markup yet, temporarily add
  `<button class="btn btn-danger">Test</button>`, `<button class="btn btn-success">Test</button>`,
  `<button class="btn btn-warn">Test</button>`, and `<button class="btn btn-info">Test</button>`
  to any template that extends `cert_manager.css` (e.g. `dashboard.html`), load the page,
  and hover each button. Confirm:
  - The background visibly deepens toward the variant's own color family (red/green/amber/blue)
    — it must NOT flip to neutral gray.
  - The transition is smooth over ~150ms, not an instant snap (DevTools Animations panel,
    playback at 10%, confirm the background-color interpolates rather than jump-cutting).
  - Text and border still darken together with the background, so all three properties read
    as one cohesive "this button just got more serious" state, not three separate motions.
  - Remove the temporary test buttons after verifying.
- **Done when**: all four `:hover` rules explicitly declare `background` via the
  `color-mix()` expressions above, and a hovered `.btn-danger`/`.btn-success`/`.btn-warn`/
  `.btn-info` button visibly stays within its own color family instead of graying out.
