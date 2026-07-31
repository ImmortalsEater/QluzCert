# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Response style rules

- Short sentences only (8-10 words max)
- No filler, no preamble, no pleasantries
- Tool first. Result first. No explain unless asked.
- Code stays normal. English and Portuguese gets compressed.

## Commands

```
python manage.py runserver              # dev server, http://127.0.0.1:8000/
python manage.py test core.app_Gestor.tests            # full suite
python manage.py test core.app_Gestor.tests.test_views  # single test module
python manage.py test core.app_Gestor.tests.test_views.ClassName.test_method  # single test
python manage.py migrate
python manage.py create_sheets_user <usuario> <senha> [--admin]  # creates/updates a row in the Usuarios sheet tab; the actual login mechanism
python manage.py collectstatic           # required before serving with DJANGO_DEBUG=False
```

CI (`.github/workflows/tests.yml`) runs `python manage.py test core.app_Gestor.tests` on push/PR with `DJANGO_SECRET_KEY=ci-test-secret-key`. No lint step configured.

`credentials.json` (Google service account) must exist at repo root for anything touching Sheets or Drive — most tests mock `sheets_repository`/`drive_repository`, but scripts under `scripts/` hit the real API.

## Architecture

**Google Sheets is the live source of truth**, not a batch sync target. Clientes, Parceiros, Precos, Contatos, Usuarios (login credentials) and Documentos (client file metadata) all read/write straight through to a Google Sheet on every request — there is no local cache table for this data, only a short in-memory TTL cache (see below). This shapes almost everything else in the app.

- `core.app_Gestor` — the only active app. Every view, template, and static file goes here. Routed from `core/urls.py`.
  - `sheets_repository.py` — the single access layer to the sheet (`list_rows`/`get_row`/`create_row`/`update_row`/`delete_row`). Handles: retry-with-backoff on 429/5xx, an in-memory read cache (`GOOGLE_SHEETS_CACHE_TTL_SECONDS`, default 20s) keyed per tab, optimistic-concurrency checks via the `atualizado_em` column (`update_row` raises `ConcurrencyError` if it changed since read), and auto-generated `id`/`atualizado_em` columns per tab (id prefixes: CLI/PAR/PRC/CTT/USR/DOC). All Sheets access must go through this module — never call the Sheets API directly from views.
  - `drive_repository.py` — the single access layer to Google Drive (`get_or_create_client_folder`/`upload_file`/`download_file`/`delete_file`). Same `credentials.json`, separate `drive` scope (needs full `drive`, not `drive.file` — the root folder is shared manually, not created by the app). Requires `GOOGLE_DRIVE_ROOT_FOLDER_ID` (settings, env var) pointing at a folder inside a **Shared Drive** — Workspace-only, confirmed live 2026-07-29. A regular folder shared as Editor lets the service account create subfolders (free) but `upload_file` fails with `storageQuotaExceeded` (service accounts have zero storage quota; only Shared Drive storage isn't tied to an individual account). A personal Gmail account cannot host this feature at all, dev or prod. Retry-with-backoff mirrors `sheets_repository`'s, duplicated rather than shared — the two modules stay independent on purpose.
  - `parsing.py` — shared parsers (`parse_date`, `parse_decimal`, `bool_from`) for interpreting sheet cell values, which always arrive as text.
  - `auth_backends.py` — `SheetsBackend`, a Django auth backend that checks credentials against the Usuarios tab instead of the local `auth_user` table (no persistent disk to trust between deploys). It mirrors into a local `auth.User` row via `get_or_create` purely to satisfy Django's `request.user` contract; that local row's password is always unusable, so real auth only ever happens through `SheetsBackend.authenticate`. `is_superuser`/`is_staff` are resynced from the sheet's `tipo` column on every login, not just creation.
- `core.app` — no URLs of its own. Exists only to keep the legacy `PlanilhaRegistro`/`Colaborador` models alive for a possible future migration to a server with a shared database. Don't add views/templates/statics here.
- `preview_login/` — static design mockups only. The actual served pages (`/preview/login/`, `/preview/cadastro/`, `/preview/recuperar-senha/`) are separate Django templates in `core/app_Gestor/templates/` — don't confuse the two when asked to change login-page design.

### Documentos (client files on Drive)

Client documents (RG/CNH, contrato social, etc.) live as files in a per-client Drive folder, with metadata in the `Documentos` sheet tab — not the local `DocumentoCliente` SQLite model (kept in `models.py` for now, but the document views in `views.py` no longer read/write it).

- `Documentos` tab header (manual setup, same requirement as `perm_*`/Contatos): `id, cliente_ref, nome_cliente, nome_original, tipo_documento, tamanho_bytes, observacao, drive_file_id, drive_view_url, atualizado_em`.
- Clientes tab needs an extra `drive_folder_id` column (manual setup too).
- The per-client folder is created lazily, on the client's *first* document upload (`views._get_or_create_cliente_drive_folder`) — not at client creation — so leads that never upload anything don't leave empty folders. The folder id is then cached back onto the Clientes row.
- Downloads are proxied server-side (`views.download_documento` calls `drive_repository.download_file`, never redirects to the Drive link directly) — this is what preserves the `cliente_ref == pk` IDOR check; a bare Drive link wouldn't have it.
- `cliente_excluir` deletes the client's Drive folder (and its contents) and the matching `Documentos` rows, best-effort (logged, not fatal to the request) — same pattern as the old `PagamentoCliente` cleanup.
- Two upload entry points, not duplicates: `documentos_cliente` (`/planilha/<pk>/documentos/`) is the real one, opened from the client modal via `openDocumentosCliente()` in `cert_manager.documentos.js` — scoped to one client, lists/deletes its documents. `upload_documento` (`/documentos/upload/`) is a standalone quick-upload form (free-text client id, no delete UI, last-20-across-all-clients list) for front-desk intake before opening a specific client record; linked from the dashboard sidebar ("Upload de Documentos", Operacional section) as of 2026-07-29 — it was previously an orphaned route with no UI link anywhere.

### Data model split

Sheets-backed (live, no local persistence): Clientes, Parceiros, Precos, Contatos, Usuarios, Documentos.
SQLite-backed local models (`core/app_Gestor/models.py`) — **not reliable if the deploy has no persistent disk**: `AppState`, `PagamentoCliente` (Mercado Pago PIX/boleto payment records), plus the legacy `app.PlanilhaRegistro`/`Colaborador`. `DocumentoCliente` also still exists here (unused by current views, kept to avoid a destructive migration) — don't build new features on it. These haven't been migrated to the sheet yet; treat any feature depending on them as fragile in a non-persistent-disk deployment.

### Permissions

Base role comes from the `tipo` column in the Usuarios sheet: `admin` = full access (bypasses every granular permission below), anything else (including empty) = `vendedor`. Vendedor's extra abilities are five independent booleans, columns `perm_parceiros`, `perm_precos`, `perm_pagamentos`, `perm_excluir_cliente`, `perm_excluir_documento` (`Sim`/`Não`, empty = restricted) — these must exist in the Usuarios sheet header before use, same manual-setup requirement as the Contatos tab.

`SheetsBackend.authenticate` (`core/app_Gestor/auth_backends.py`) syncs both `is_superuser`/`is_staff` and, for non-admins, a `request.session['perms']` dict from the `perm_*` columns on every login — session-based (signed cookie) rather than a local model field, consistent with the no-persistent-disk constraint. `PERM_KEYS` (`core/app_Gestor/parsing.py`) is the shared list of the five keys.

Enforced server-side via two decorators in `core/app_Gestor/views.py`: `admin_required` (superuser-only, non-delegable — reserved for the user-management page) and `permission_required(perm_key)` (superuser OR the matching session perm) wrapping `parceiro_*`/`preco_*` (`parceiros`/`precos`), `cliente_excluir` (`excluir_cliente`), `excluir_documento` (`excluir_documento`) — both return 403/JSON error, not just a hidden menu item. `dashboard.html` mirrors the same checks (`user.is_superuser or perms.<key>`) to hide nav sections, and `window.PERMS` (parallel to `window.IS_ADMIN`) gates the equivalent JS-rendered buttons in `cert_manager.core.js`/`cert_manager.documentos.js` — but hiding the menu/button client-side is cosmetic only; never rely on it as the actual check.

An admin edits an existing user's `tipo`/`perm_*` at `/usuarios/` (`usuarios_gestao`/`usuarios_atualizar` views, admin-only). Creating a new user or resetting a password stays out of that page — still only via `create_sheets_user` (append-only; errors if the username already exists) or manual sheet editing.

### Sessions

`SESSION_ENGINE = signed_cookies` — session state lives entirely in a signed browser cookie, not the `django_session` table, so it survives redeploys without persistent disk. Depends on `DJANGO_SECRET_KEY` staying stable across restarts.

### Concurrency pattern

Edit flows pass the row's last-seen `atualizado_em` back on save; `sheets_repository.update_row` compares it against the current sheet value and raises `ConcurrencyError` (surfaced as 409) on mismatch, instead of silently overwriting a concurrent edit.

## Known limitations (see README "Limitações conhecidas" for detail)

- No self-service signup/password-reset; users are created/updated only via `create_sheets_user`.
- No persistent disk assumed anywhere — this is why auth and core business data live in the sheet instead of SQLite.
