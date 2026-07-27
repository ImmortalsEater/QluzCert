---
version: alpha
name: QCert Manager
description: Internal single-page CRM dashboard (Django + vanilla JS) for managing digital certificate (e-CPF/e-CNPJ) sales, clients, partners, pricing, and a Google Sheets-synced sales ledger.
colors:
  palette-name: "Branding Variant-01"

  primary: "#065194"
  primary-hover: "#054170"
  primary-bg: "#c6e7ec"

  secondary: "#1c2a5e"
  secondary-hover: "#14204a"
  secondary-bg: "#dde1f0"

  tertiary: "#b8860b"
  tertiary-hover: "#8f6a08"
  tertiary-bg: "#f4e8c8"

  quaternary: "#b8501f"
  quaternary-hover: "#943f18"
  quaternary-bg: "#f6ddc8"

  bg: "#f4f3ee"
  surface: "#fffdf7"
  surface-alt: "#efe9e0"
  border: "#e4e3e0"
  border-strong: "#c9c1b6"
  text: "#161513"
  muted: "#8b8479"
  muted-strong: "#57544c"

  success: "#3b6d11"
  success-hover: "#2c5209"
  success-bg: "#e7f0d8"

  warn: "#9a4b0a"
  warn-hover: "#7a3b08"
  warn-bg: "#fbe3cb"

  danger: "#c31c1e"
  danger-hover: "#9c1517"
  danger-soft: "#e0555a"
  danger-bg: "#f8e3e1"

  info: "#2e86ab"
  info-hover: "#216c8a"
  info-bg: "#d9edf5"

  teal: "#0f6e56"
  teal-hover: "#0b5643"
  teal-bg: "#e1f5ee"
typography:
  body-md:
    fontFamily: "Inter, Segoe UI, system-ui, sans-serif"
    fontSize: 13px
    fontWeight: 400
  label:
    fontFamily: "Inter, Segoe UI, system-ui, sans-serif"
    fontSize: 11px
    fontWeight: 700
    letterSpacing: 0.5px
  heading-sm:
    fontFamily: "Inter, Segoe UI, system-ui, sans-serif"
    fontSize: 14px
    fontWeight: 600
  heading:
    fontFamily: "Inter, Segoe UI, system-ui, sans-serif"
    fontSize: 15px
    fontWeight: 700
  metric:
    fontFamily: "Bricolage Grotesque, Inter, system-ui, sans-serif"
    fontSize: 24px
    fontWeight: 700
    letterSpacing: -0.01em
  page-title:
    fontFamily: "Bricolage Grotesque, Inter, system-ui, sans-serif"
    fontSize: 16px
    fontWeight: 600
    letterSpacing: -0.01em
  display:
    fontFamily: "Bricolage Grotesque, Inter, system-ui, sans-serif"
    fontSize: 36px
    fontWeight: 800
    letterSpacing: -0.02em
rounded:
  sm: 7px
  md: 8px
  lg: 10px
  xl: 12px
  full: 20px
components:
  button-primary:
    backgroundColor: "{colors.primary}"
    textColor: "#ffffff"
    rounded: "{rounded.sm}"
  button-default:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.text}"
    rounded: "{rounded.sm}"
  card:
    backgroundColor: "{colors.surface}"
    rounded: "{rounded.lg}"
  input:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.text}"
    rounded: "{rounded.sm}"
  nav-item:
    textColor: "{colors.muted}"
    rounded: "{rounded.sm}"
  nav-item-active:
    backgroundColor: "{colors.primary-light}"
    textColor: "{colors.primary}"
    rounded: "{rounded.sm}"
  badge-info:
    backgroundColor: "{colors.info-bg}"
    textColor: "{colors.info}"
    rounded: "{rounded.full}"
  badge-warn:
    backgroundColor: "{colors.warn-bg}"
    textColor: "{colors.warn}"
    rounded: "{rounded.full}"
  badge-purple:
    backgroundColor: "{colors.purple-bg}"
    textColor: "{colors.purple}"
    rounded: "{rounded.full}"
  badge-teal:
    backgroundColor: "{colors.teal-bg}"
    textColor: "{colors.teal}"
    rounded: "{rounded.full}"
  badge-success:
    backgroundColor: "{colors.success-bg}"
    textColor: "{colors.success}"
    rounded: "{rounded.full}"
  badge-danger:
    backgroundColor: "{colors.danger-bg}"
    textColor: "{colors.danger}"
    rounded: "{rounded.full}"
  badge-danger-soft:
    backgroundColor: "{colors.danger-bg}"
    textColor: "{colors.danger-soft}"
    rounded: "{rounded.full}"
---

## Overview

QCert Manager is an internal, single-page operations dashboard used by a small digital-certificate sales team to track clients, partners, pricing, renewals, and payments, with a Google Sheets-backed sales ledger. It is built as one Django template driven by vanilla JavaScript — no CSS or component framework.

The interface is built for an operator scanning dense tables and status badges all day, not for a marketing surface: flat, bordered panels; a warm off-white neutral base; and a single confident blue accent ("Branding Variant-01") reserved for primary actions and the active navigation state. Shadows are avoided almost everywhere and appear only on floating overlays. Typography splits by role rather than by screen: **Inter** (self-hosted `woff2`, Segoe UI stack as fallback) for every scanned piece of UI — tables, labels, nav, forms — and **Bricolage Grotesque** for glance-once headline text — the auth screens' `<h1>`, the Dashboard's KPI numbers, and the topbar page title. Operator-facing density still comes from size and weight within Inter; the second face is reserved for the handful of places a user reads a value once rather than scans it.

## Colors

The palette follows **Branding Variant-01**: a confident blue brand color, a cool-neutral gray scale, and a three-step red ladder used to grade the severity of overdue/urgent states. Every color role now also carries a `-hover` step (`--success-hover`, `--warn-hover`, `--danger-hover`, `--info-hover`, `--teal-hover`), even where nothing currently hovers over that color yet, for consistency with `--accent-hover`.

- **Primary (`#065194`, CSS var `--accent`):** The single brand accent. Used for the active sidebar item, primary buttons, links, focus rings, and the "current" step in progress indicators.
- **Primary-hover (`#054170`, `--accent-hover`):** A manually darkened step of primary (no darker blue swatch exists in the source palette) used only for `.btn-primary:hover`, so filled buttons keep enough contrast when pressed.
- **Primary-bg (`#c6e7ec`, CSS var `--accent-light` — named `primary-bg` in the token list for consistency with every other role's `-bg` suffix, kept as `--accent-light` in code to avoid an unrelated rename):** The palette's pale cyan tint, used as a background for hover/active/focus states (active nav item, focused form fields, selected triagem option).
- **Info (`#2e86ab`, `--info` / `--info-hover` `#216c8a` / `--info-bg` `#d9edf5`):** The "Novo Lead" badge. Previously reused the primary blue directly; now its own distinct teal-blue role, separate from `--accent`.
- **Neutral scale:** `bg` (`#f4f3ee`, page background), `surface` (`#ffffff`, cards/tables/sidebar/topbar/modals), `surface-alt` (`#f1f5f8`, table header strips, nav-item hover, generic button hover, distinguishing "hovered/secondary surface" from the plain page background), `border` (`#e4e3e0`, derived light tint for the default 1px divider — the palette has no dedicated hairline-border swatch), `border-strong` (`#c9c1b6`, the palette's mid tone, used where a hover/focus needs a more visible outline than the default border), `text` (`#161513`), `muted` (`#8b8479`, secondary/meta text: labels, captions, timestamps), `muted-strong` (`#57544c`, slightly stronger secondary text — table header labels).

> **Deviation from the token list:** the frontmatter's `surface` (`#fffdf7`) and `surface-alt` (`#efe9e0`) are a warm cream/tan pair; in the live UI this read as yellowish rather than neutral, so the implementation keeps the previous pure-white `surface` and cool blue-gray `surface-alt` instead. Everything else in the neutral scale (and the rest of the palette) follows the frontmatter values as written.
- **Danger is a three-step ladder**, all from the palette's red family, used to grade urgency rather than a single flat red: `danger` (`#c31c1e` / hover `#9c1517`, deepest red — already-overdue states, e.g. the "Vencido" badge), `danger-soft` (`#e0555a`, medium red — due-soon-but-not-yet-overdue states, e.g. the "X dias" badge), both paired with the same pale `danger-bg` (`#f8e3e1`) background so only the text color signals severity.
- **Other status colors**, unchanged from the previous system since Branding Variant-01 doesn't define them: `success` (green, "Emitido" status, paid states), `warn` (amber, "Documentação Pendente", warning alerts), `purple` ("Aguardando Pagamento" badge, partner tags — kept as-is; the current Branding Variant-01 pass dropped `purple` from the named palette without a replacement, so it stays an unmapped legacy color like `teal`), `teal` ("Agendado para Vídeo" badge, the Kit Soluti panel).
- **Reserved (not yet wired to any component):** `secondary` (`#1c2a5e` / hover `#14204a` / bg `#dde1f0`), `tertiary` (`#b8860b` / hover `#8f6a08` / bg `#f4e8c8`), `quaternary` (`#b8501f` / hover `#943f18` / bg `#f6ddc8`) — three new brand roles added to the palette with no assigned UI role yet. Defined as CSS custom properties for when a use is picked; don't reach for them ad hoc in the meantime — `purple` and `teal` already cover the app's "extra status color" needs.

> **Note on source fidelity:** the reference image includes a dark-navy swatch mislabeled `#FF3D00` (a copy-paste artifact — that hex is the coral primary from the palette's orange family, not a navy). Rather than guess at the intended value, it was left out of the implementation. The orange family itself (`#ff3d00`/`#ff6e40`/`#ff9e7f`/`#ffcebf`) remains documented here but unused and undefined as a token — a separate, older candidate from the one covered by the `secondary`/`tertiary`/`quaternary` reserve above; the two aren't the same swatches and shouldn't be conflated.

## Typography

Two font families, split by role rather than by screen: **Inter** for everything scanned — table cells, labels, nav, form fields — and **Bricolage Grotesque** for headline-scale text a user reads once at a glance rather than scans (page titles, KPI numbers, the auth screens' `<h1>`). Both are self-hosted `@font-face` in `cert_manager.css` (Inter 400/600/700, Bricolage Grotesque 600/700/800; `static/fonts/inter/*.woff2` and `static/fonts/bricolage-grotesque/*.woff2`), with `Segoe UI, system-ui, sans-serif` kept as the fallback stack so the app still renders correctly before the webfonts load or if they fail to.

- **`display`** (36px/800, `Bricolage Grotesque`, -0.02em letter-spacing): the single `<h1>` on the login, cadastro, and recuperar-senha screens (`static/css/login.css`). The largest, most expressive use of the face — these are the only pre-auth surfaces in the product.
- **`metric`** (24px/700, `Bricolage Grotesque`, -0.01em letter-spacing): the large KPI numbers on the Dashboard cards (Total de Clientes, Emitidos, etc. — `.metric-val`). The biggest number on any given screen; a glance-once value rather than something scanned character-by-character, so the display face's personality reads as a feature, not a legibility cost.
- **`page-title`** (16px/600, `Bricolage Grotesque`, -0.01em letter-spacing): the topbar page title (`.topbar-title` — "Dashboard", "Clientes", etc.), one per screen. Same reasoning as `metric`: read once on arrival, not scanned.
- **`heading`** (15px/700, `Inter`): modal dialog titles (`.modal-head h2`), shared by every modal in the app.
- **`heading-sm`** (14px/600, `Inter`): table/section header titles (`.table-header h3`), shared by every table panel.
- **`label`** (11px/700, `Inter`, uppercase, 0.5px letter-spacing): the recurring "quiet caption" style — metric card labels, table column headers, Kanban column headers, form fieldset legends, detail-panel section titles. This is the most-reused text role in the product.
- **`body-md`** (13px/400, `Inter`): the default size for table cells, form inputs, buttons, and alert/detail copy — the working size for nearly all UI text (the unstyled HTML default is 14px, but almost every component explicitly sets 13px).

**Don't** apply `Bricolage Grotesque` below ~16px or to anything repeated/scanned (table headers, labels, nav items, form fields) — those stay `Inter` because operators read them densely all day, and the display face's character shapes cost legibility at small sizes without adding anything a user would notice mid-scan. The boundary is glance-once vs. scanned, not "dashboard vs. auth."

## Layout

Fixed two-column app shell: a 220px sidebar and a 52px topbar, with the content area scrolling independently underneath. There is no responsive collapse of this shell above 700px; below that breakpoint the sidebar hides entirely (mobile is a secondary target, not a primary layout mode).

Content-area grids are role-specific rather than following one global grid: the Dashboard metrics row is a 4-column grid (2 columns under 700px), the Kanban board is a 5-column grid (2 columns under 700px), and forms use a 2-column `.form-grid` (1 column under 700px). Tables that overflow their container scroll horizontally within their own `.table-scroll` wrapper rather than compressing columns, keeping a sticky, shadow-separated "Ações" column pinned on the right.

## Elevation & Depth

Depth is conveyed almost entirely through a single 1px `border` — in-flow surfaces (cards, tables, sidebar, topbar, kanban cards) never use `box-shadow`. Shadows are reserved for elements that float above the page: the modal dialog (`0 20px 60px rgba(0,0,0,.2)`), toast notifications (`0 8px 24px rgba(0,0,0,.16)`), and the export-in-progress overlay. The one exception is a directional shadow used on the sticky last table column, which exists only to visually separate it from content scrolling underneath it, not to imply general elevation.

## Shapes

Corner rounding is assigned by container role rather than by a single global radius:

- **`sm` (7px):** interactive controls — buttons, form inputs, the search box.
- **`md` (8px):** small contained surfaces — Kanban cards, alert list items, triagem option buttons, the contact-log panel.
- **`lg` (10px):** primary content containers — metric cards, table panels, the triagem card.
- **`xl` (12px):** the modal dialog, the largest and most prominent surface.
- **`full` (20px):** pill shapes — status badges and partner/type tags.

## Components

- **Buttons:** `.btn` is the base for every button and button-styled link (`<a class="btn">`), and explicitly sets `font-family: inherit` so anchors and `<button>` elements render identically. `button-primary` uses the primary color solid-filled; the default button is a bordered `surface`-colored control; a pressed button scales to 0.96. Icon-only and small buttons keep a minimum 40×40px hit area via a `::after` pseudo-element sized independently of the visible control, so compact buttons stay easy to tap without visually growing.
- **Navigation items:** sidebar links (`nav-item`) are quiet by default (`muted` text, no fill) and use `surface-alt` on hover; the active item (`nav-item-active`) is the only place besides buttons and focus rings where `primary`/`primary-light` appear together as a filled state.
- **Badges:** small pill shapes (`rounded.full`) pairing a status color with its `-bg` tint (e.g. `badge-success` = `success` text on `success-bg`). One variant per status color (`badge-info`, `badge-warn`, `badge-purple`, `badge-teal`, `badge-success`), covering funnel status (Novo Lead → Emitido). Overdue/renewal alerts use two danger variants sharing one background — `badge-danger` (deep red, already overdue) and `badge-danger-soft` (medium red, due soon) — so severity is legible without adding a new background tint per level.
- **Tables:** header row uses the `label` typography (uppercase, `muted-strong`, letter-spaced) on a `surface-alt`-colored strip (distinct from the page `bg`); body rows are separated by `border` only, with a subtle background change on hover. Wide tables scroll horizontally with the last "Ações" column pinned via `position: sticky`.
- **Modals:** a full-screen dim overlay (fades in/out) containing a centered `surface` panel that scales from 0.95→1 while fading in. Every modal shares the same head/body/foot structure (`heading` title, scrollable body, right-aligned action buttons in the foot).
- **Toasts:** bottom-right stacked notifications, color-coded by type (success/error/warning/info) with a matching icon, auto-dismissing after a duration proportional to how critical the message is (errors linger longer than confirmations).
- **Forms:** labeled fields in a 2-column grid, `muted` uppercase labels, and a `primary-light` focus ring on the active input.

## Do's and Don'ts

- Do set `font-family: inherit` on any new button-like control (button or anchor) — this was fixed historically after `<button>` and `<a class="btn">` rendered with different fonts.
- Do give icon-only or otherwise small buttons a 40×40px minimum hit area via pseudo-element expansion rather than enlarging the visible control.
- Don't add `box-shadow` to in-flow panels (cards, tables, sidebar sections) — separate them with the 1px `border` token; reserve shadows for floating overlays (modals, toasts).
- Do use the `danger`/`danger-soft` pairing to grade urgency (overdue vs. due-soon) instead of introducing a new hue — it's a deliberate two-step ladder off one background tint, not two unrelated colors.
- Don't reuse `#1d5c8f`/`#185fa5` (the pre-Variant-01 blue) as the primary/accent color — primary is `#065194`, the blue from the Variant-01 palette itself, not the older ad-hoc blue.
- Do reference `--success`/`--danger`/`--info`/`--warn` for toast notification colors (`.toast.success/.error/.info/.warning` in `dashboard.html`) — previously hardcoded gradients independent of the tokens above, now resolved to flat token-backed fills.
