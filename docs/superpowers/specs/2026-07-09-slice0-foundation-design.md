# Slice 0 — Foundation — Design Spec

**Date:** 2026-07-09
**Status:** Approved for planning
**Parent:** `P2P_BRD.md` Phase 1 (foundation-first decomposition)
**Requirement IDs:** PLT-01, PLT-02, PLT-06 (infra), PLT-07, NFR-OPS-01, NFR-SEC-01/05, NFR-DATA-01, NFR-I18N-01

---

## 1. Purpose & Scope

Slice 0 is the architectural skeleton that every later feature slice (ORG → VEN → PO → APR) plugs into. It delivers no business modules. It proves the end-to-end shape of the system — a self-hostable stack where a seeded Admin can authenticate through the React UI, manage users under server-side RBAC, and have every mutation recorded in an append-only audit log — so that subsequent slices only add domain modules against stable foundations.

### In scope

- Monorepo scaffolding: `/backend`, `/frontend`, `/docs`, `/docker`, `/samples`.
- Docker Compose stack: `postgres`, `redis`, `api`, `worker`, `frontend`, optional `minio` (compose profile).
- Async database layer (SQLAlchemy 2.x async) + Alembic migrations (async env).
- Base model mixin: UUID pk, `created_at`, `updated_at` (all `timestamptz`, UTC).
- **Auth (PLT-01):** email+password login, argon2id hashing, JWT access (15 min) + refresh (7 d) with refresh-token rotation, logout, password-reset via email token (token generation + verification; SMTP send stubbed/logged in Slice 0).
- **RBAC (NFR-SEC-01):** the 8 BRD roles seeded; `require_roles(...)` dependency enforced server-side on every protected route; User↔Role many-to-many.
- **User management (PLT-02):** Admin invites users by email, assigns/removes roles, deactivates. No self-signup.
- **Audit log infrastructure (PLT-06):** append-only `audit_log` table + `AuditWriter` service + request-scoped actor/IP context. No update/delete paths. Login, logout, and all user-management actions write entries in Slice 0.
- **Health/ops (PLT-07):** `/health` (liveness), `/health/ready` (DB, Redis, storage checks); structured JSON logging.
- **Storage interface:** `StorageBackend` ABC + `LocalStorage` implementation; config-driven (`STORAGE_BACKEND=local|s3`). S3 impl deferred (interface only + local).
- **Worker skeleton:** ARQ worker process with one example idempotent task and a health check; wiring for later email/extraction/matching workers.
- **Error format:** RFC 7807 problem+json for all error responses.
- **Frontend shell:** Vite + React 18 + TS, Tailwind + shadcn/ui, React Router, TanStack Query, react-i18next. Login page, auth context (token storage + silent refresh), protected-route wrapper, app layout shell, stub authenticated landing page showing current user + roles.
- **Tooling:** Makefile (`up`, `migrate`, `seed-demo`, `test`, `lint`), `.env.example`, ruff + mypy (backend), Vitest + RTL (frontend), pytest + httpx (backend).
- **Seed script:** `make seed-demo` seeds the 8 roles + one Admin user.

### Out of scope (deferred to later slices)

- Settings UI (PLT-03), dashboard (PLT-05), notifications (PLT-04).
- All business modules: cost centers/GL accounts (ORG), vendors (VEN), purchase orders (PO), approval engine (APR).
- S3 storage implementation, real SMTP delivery (stub/log only), OCR/extraction/LLM, ERP export.
- TOTP 2FA (Phase 4).

---

## 2. Backend Architecture (modular / feature-based)

```
backend/
  app/
    core/
      config.py       pydantic-settings; 12-factor env; typed Settings
      db.py           async engine, async_sessionmaker, get_session dependency
      security.py     argon2id hash/verify; JWT encode/decode; token models
      rbac.py         Role enum/constants; require_roles(...) dependency factory
      audit.py        AuditWriter service; request-scoped actor/IP context
      storage.py      StorageBackend ABC + LocalStorage impl; get_storage factory
      logging.py      structured JSON logging config
      errors.py       RFC 7807 problem+json exception handlers + ProblemException
      deps.py         get_current_user, get_current_active_user
    models/
      base.py         Base (DeclarativeBase) + UUIDAuditMixin (id, created_at, updated_at)
    modules/
      auth/
        router.py     POST /auth/login | /refresh | /logout | /password-reset[/confirm]
        schemas.py    Pydantic v2 request/response models
        service.py    authenticate, issue tokens, rotate refresh, reset flow
        models.py     RefreshToken (for rotation/revocation), PasswordResetToken
      users/
        router.py     CRUD /users; POST /users/{id}/roles; POST /users/invite; deactivate
        schemas.py
        service.py    business logic; writes audit entries
        models.py     User, Role, user_roles association
    health/
      router.py       /health, /health/ready
    main.py           app factory: settings, routers, middleware, CORS, error handlers
    worker.py         ARQ WorkerSettings; example idempotent task; on_startup checks
  alembic/
    env.py            async migration environment
    versions/         initial migration (users, roles, user_roles, refresh_tokens,
                      password_reset_tokens, audit_log)
  tests/
    conftest.py       ephemeral DB, transactional rollback per test, httpx client,
                      user/role factories, auth-header helper
    test_auth.py, test_users.py, test_rbac.py, test_audit.py, test_health.py
  pyproject.toml      deps + ruff + mypy config
  Dockerfile
```

### 2.1 Key decisions

- **Language/runtime:** Python 3.12+, FastAPI (async), Pydantic v2.
- **Password hashing:** argon2id (via `argon2-cffi`).
- **JWT:** `PyJWT`. Access token TTL 15 min, refresh 7 d. Refresh tokens are persisted (`refresh_tokens` table) to support **rotation** (on refresh, old token is revoked and a new one issued) and logout revocation. Access tokens carry `sub` (user id), `roles`, `exp`, `jti`.
- **RBAC:** the 8 roles are constants (Admin, ProcurementManager, Requester, Approver, APClerk, Receiver, Auditor, Vendor). `require_roles(*roles)` returns a dependency that 403s if the current user holds none of the required roles. Enforced on every protected route; object-level checks live in service/query layer (relevant from VEN/PO onward, not Slice 0).
- **Audit log:** `audit_log` is append-only at the application level — only an insert path exists; no update/delete endpoints or ORM flows. `AuditWriter.record(actor_id, action, object_type, object_id, before, after)` reads actor + IP from a request-scoped context set by middleware. `before`/`after` stored as JSONB.
- **Storage:** `StorageBackend` ABC (`save`, `open`, `delete`, `url_for`); `LocalStorage` writes under a configured root with random keys (never user-supplied filenames). Selected by `STORAGE_BACKEND` env.
- **Money/time (NFR-DATA-01):** no monetary columns in Slice 0, but the base conventions are set — all timestamps `timestamptz`, UTC in the DB/API, timezone applied only in the frontend.

### 2.2 Data model (Slice 0 tables)

| Table | Columns (beyond id/created_at/updated_at) |
|---|---|
| `users` | email (unique, citext-lower), password_hash, full_name, is_active, last_login_at |
| `roles` | name (unique), description |
| `user_roles` | user_id (fk), role_id (fk), pk(user_id, role_id) |
| `refresh_tokens` | user_id (fk), jti (unique), expires_at, revoked_at (nullable) |
| `password_reset_tokens` | user_id (fk), token_hash (unique), expires_at, used_at (nullable) |
| `audit_log` | actor_id (nullable fk), action, object_type, object_id (nullable), before (JSONB), after (JSONB), ip, at (timestamptz) — **append-only** |

All fk-filtered/list columns indexed. `audit_log` indexed on (object_type, object_id) and (actor_id) and (at).

---

## 3. Frontend Shell

- **Stack:** Vite + React 18 + TypeScript, Tailwind + shadcn/ui, React Router v6, TanStack Query, react-i18next.
- **Auth flow:** `AuthContext` holds the access token in memory and the refresh token in localStorage. A fetch wrapper attaches the access token, and on 401 performs a single silent refresh (rotating the refresh token) then retries; on refresh failure it clears state and redirects to login.
- **Routing:** public `/login`; everything else behind a `<ProtectedRoute>` that redirects unauthenticated users to `/login`.
- **Layout:** app shell with top bar (app name, current user, logout) and a sidebar placeholder (feature nav added by later slices).
- **Landing page:** authenticated stub page rendering the current user's name, email, and roles (proves the whole auth loop).
- **i18n (NFR-I18N-01):** all user-facing strings go through `react-i18next` from day one; English-only bundle in Slice 0; currency/date display locale-aware helpers stubbed.
- **Testing:** Vitest + React Testing Library configured; one smoke test (login form renders and submits).

---

## 4. Infrastructure, Tooling & Seed

- **docker-compose** (`docker/docker-compose.yml`): services `postgres` (15), `redis`, `api` (uvicorn), `worker` (arq), `frontend` (vite dev / static build). `minio` under an optional `storage` compose profile. Healthchecks on postgres/redis; `api`/`worker` wait for them.
- **Config:** 12-factor via env; `.env.example` maintained with every variable (DB URL, Redis URL, `SECRET_KEY`, JWT TTLs, `SECRET_ENCRYPTION_KEY` placeholder, `STORAGE_BACKEND`, `FRONTEND_ORIGIN`, SMTP/IMAP placeholders). CORS locked to `FRONTEND_ORIGIN`; standard security headers.
- **Makefile:** `make up` (compose up), `make migrate` (alembic upgrade head), `make seed-demo`, `make test` (backend+frontend), `make lint` (ruff+mypy+eslint).
- **Seed (`make seed-demo`):** idempotent; inserts the 8 roles if absent and one Admin user (`admin@example.com`, password from env or default `admin`, flagged to change) with the Admin role. Later slices extend this script.
- **Backend tests:** pytest + httpx; ephemeral Postgres with per-test transactional rollback; factories for users/roles; helper to mint auth headers for a role set.

---

## 5. Acceptance Criteria (Slice 0)

From a clean clone:

1. `docker compose up` starts postgres, redis, api, worker, frontend without manual steps.
2. `make migrate && make seed-demo` creates the schema, seeds the 8 roles and the Admin user; re-running `seed-demo` is a no-op (idempotent).
3. The seeded Admin logs in through the React UI and lands on the authenticated stub page showing their email and `Admin` role.
4. Via API: an Admin creates a user, assigns roles, and deactivates a user; a token lacking the required role receives **403**; an invalid/expired refresh token is rejected and cannot be reused after rotation.
5. Each of the actions in (4) plus login/logout writes an `audit_log` row with actor, action, object, before/after, and IP; there is no code path that updates or deletes `audit_log`.
6. `GET /health` returns liveness; `GET /health/ready` reports DB, Redis, and storage health, returning non-200 if any dependency is down.
7. `make test` passes (backend pytest + frontend Vitest); `make lint` is clean.
8. All error responses conform to RFC 7807 problem+json.

---

## 6. Non-Goals / Explicit Deferrals

No business modules, no settings/dashboard/notifications UI, no S3 storage, no real SMTP send (stub/log), no OCR/extraction/LLM, no ERP export, no 2FA. These are named here so the implementation plan does not accidentally pull them in.
