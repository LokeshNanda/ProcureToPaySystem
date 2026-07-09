# Slice 1 — ORG (Cost Centers & GL Accounts) — Design Spec

**Date:** 2026-07-09
**Status:** Approved for planning
**Parent:** `P2P_BRD.md` Phase 1 (ORG module); builds on Slice 0 foundation
**Requirement IDs:** ORG-01, ORG-02, ORG-03; NFR-SEC-01, PLT-06 (audit), NFR-I18N-01

---

## 1. Purpose & Scope

Deliver the organizational master data that PO line coding and the approval engine depend on later: **cost centers** and **GL accounts**, both Admin-managed, with a referential-safety lifecycle (deactivate, never delete). This slice plugs into the Slice 0 foundation (auth/RBAC/audit/migrations/React shell) and adds a new backend module plus Admin UI pages.

### In scope
- `cost_centers` and `gl_accounts` models + Alembic migration `0002`.
- Admin-only REST CRUD (no hard delete), deactivate/reactivate, and CSV bulk import for both.
- Referential-safety design (ORG-03): deactivate-only lifecycle + an extensible `is_in_use` hook (returns `False` this slice; Slice 3 registers PO references).
- Admin UI pages (Cost Centers, GL Accounts) in the React shell, i18n, Admin-gated sidebar nav.
- Audit entries for every mutation.
- Backend + frontend tests.

### Out of scope (deferred)
- Any enforcement of "in use" against real references (no PO/po_line tables until Slice 3).
- Non-Admin roles managing this data.
- Hard delete of cost centers / GL accounts (never — deactivate is the lifecycle).

---

## 2. Data Model

Both tables use the Slice 0 `UUIDAuditMixin` (UUID `id`, `created_at`, `updated_at` timestamptz).

| Table | Columns |
|---|---|
| `cost_centers` | `code` (String, unique, indexed, immutable after create), `name` (String, not null), `owner_id` (nullable FK → `users.id`, `ON DELETE SET NULL`), `is_active` (bool, default true, not null) |
| `gl_accounts` | `code` (String, unique, indexed, immutable), `name` (String, not null), `is_active` (bool, default true, not null) |

`owner_id` is the user used by the approval engine's "cost center owner" step (APR, later slice); nullable so a cost center can exist before an owner is assigned.

---

## 3. API Surface

All under `/api/v1`, **Admin-only** (`require_roles(Roles.ADMIN)`), all mutations audited, errors RFC 7807.

```
# Cost centers
GET    /cost-centers?active=true|false|all&page=&page_size=   # paginated {data, meta}
POST   /cost-centers                 # {code, name, owner_id?} -> 201; 409 on dup code
GET    /cost-centers/{id}            # 404 if missing
PATCH  /cost-centers/{id}            # {name?, owner_id?} only; code is immutable
POST   /cost-centers/{id}/deactivate # is_active=false (idempotent)
POST   /cost-centers/{id}/reactivate # is_active=true
POST   /cost-centers/import          # multipart CSV -> ImportResult

# GL accounts (identical, no owner)
GET    /gl-accounts?active=&page=&page_size=
POST   /gl-accounts                  # {code, name}
GET    /gl-accounts/{id}
PATCH  /gl-accounts/{id}             # {name?}
POST   /gl-accounts/{id}/deactivate | /reactivate
POST   /gl-accounts/import
```

**No DELETE endpoints exist** (ORG-03).

### Behaviors
- **Uniqueness:** `code` unique per table; duplicate create → `409`. Codes are trimmed; comparison is case-sensitive as stored (document that codes are stored verbatim).
- **Immutability:** `PATCH` cannot change `code` (ignored/rejected); only `name` (and `owner_id` for cost centers).
- **Pagination:** `page` (≥1), `page_size` (1..200, default 25); response `{data:[...], meta:{page,page_size,total}}` — same shape as Slice 0 users.
- **Active filter:** `active=true` (default view for pickers), `active=false`, or `all`.
- **Referential safety (ORG-03):** module exposes `is_in_use(db, kind, id) -> bool` returning `False` this slice. Deactivate/reactivate flips `is_active`; deactivated rows remain readable and valid on historical records but are excluded from `active=true` listings (the filter PO forms will use). When Slice 3 lands, it registers PO/po_line reference checks into this hook and (if desired) blocks deactivation-with-cleanup policies then — no schema change required.

### CSV import (`ImportResult`)
- Multipart file upload (`text/csv`), max size reuse of the platform upload limit.
- Columns: cost centers `code,name,owner_email?,active?`; GL accounts `code,name,active?`. Header row required.
- **Upsert by `code`:** unknown code → create; existing code → update `name` (+ `owner` for cost centers) and, if `active` column present, its state. `owner_email` resolved to a user; unknown email → row error (not fatal to the batch).
- Per-row validation; the batch is best-effort: valid rows apply, invalid rows are reported.
- Response: `{ "created": int, "updated": int, "errors": [ {"row": int, "code": str|null, "reason": str} ] }`.
- One audit entry per import with `{created, updated, error_count}` (no row PII in the audit payload).

---

## 4. Frontend (Admin UI)

- Sidebar nav gains **Cost Centers** and **GL Accounts**, rendered only when the current user holds `Admin` (roles already available from `/users/me/profile`).
- Each page: paginated table (code, name, [owner], active badge), an active/inactive/all filter, a **Create** and per-row **Edit** modal, **Deactivate/Reactivate** action, and a **CSV import** control that surfaces the `ImportResult` (created/updated + a per-row error list).
- All user-facing strings via `react-i18next` (NFR-I18N-01); English bundle extended.
- Data fetching via TanStack Query; mutations invalidate the list query.
- Non-Admins never see the nav; the API also enforces 403 (defense in depth).

---

## 5. Testing

**Backend** (pytest + httpx, real Postgres test DB):
- Service + HTTP: create, list (pagination + active filter), get (404), patch (name/owner; code immutable), deactivate/reactivate, duplicate-code → 409.
- CSV import: all-valid file (created/updated counts), mixed file (valid rows apply, invalid rows reported with row numbers), unknown `owner_email` → row error, malformed/missing header → clear error.
- RBAC: non-Admin token → 403 on every endpoint.
- Audit: each mutation (create/patch/deactivate/reactivate/import) writes an `audit_log` row; import payload carries counts, not row PII.
- `is_in_use` returns `False` (guard placeholder test).
- Migration smoke test still passes with `0002` applied.

**Frontend** (Vitest + RTL): smoke tests that the Cost Centers and GL Accounts pages render their table + create control; nav hidden for non-Admin.

**Acceptance:** From the running app, an Admin creates/edits/deactivates/reactivates cost centers and GL accounts through the UI; a duplicate code returns 409; a mixed-validity CSV import returns per-row results; a non-Admin receives 403; every mutation appears in `audit_log`; `make test` is green and `make migrate` applies `0002` cleanly.

---

## 6. Non-Goals / Explicit Deferrals

No hard delete; no enforcement against real references (Slice 3 wires PO/po_line into `is_in_use`); no non-Admin management; no bulk export (only import) this slice.
