# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project status: greenfield

There is **no application code yet** — only `P2P_BRD.md` (the full spec) and a stub `README.md`. `P2P_BRD.md` is the authoritative source of truth for scope, tech stack, domain model, API surface, and the phased delivery plan. Read it before starting any implementation work. The sections below distill the constraints that are easy to violate and expensive to walk back; everything else lives in the BRD.

## What this system is (and is not)

OpenP2P is a self-hostable Procure-to-Pay front-end that runs **alongside** an existing ERP, not as a replacement. It owns the workflow half of the cycle — vendor onboarding, POs, approvals, goods receipt, invoice capture/matching — then exports ERP-ready payment data.

**Hard non-goals — do not build these:**
- **No payment execution.** The system never moves money, stores executable payment instructions, or touches banks/payment rails. Payment happens in the ERP.
- No accounting ledger (ERP is the system of record for financials), no sourcing/RFQ, no contract or inventory management, no punchout catalogs.
- **v1 is single-tenant.** Do not add `tenant_id` / multi-tenancy complexity now — but don't make architectural choices that would make it impossible later.

## Fixed tech stack (do not substitute)

Backend: **Python 3.12+ / FastAPI** (async, Pydantic v2), **SQLAlchemy 2.x async + Alembic**, **PostgreSQL 15+** (use JSONB for flexible schemas — extraction payloads, rule conditions). Frontend: **React 18+ / Vite / TypeScript**, React Router, TanStack Query, **shadcn/ui + Tailwind**. **Redis** for cache + queue. Job queue: **ARQ** (async-native; only switch to Celery on a hard blocker). Testing: **pytest + httpx** (backend), **Vitest / React Testing Library** (frontend). Deployment: Docker Compose.

Monorepo layout (per BRD §2): `/backend` (FastAPI app, workers, alembic), `/frontend`, `/docs` (architecture + ERP export template specs), `/docker`, `/samples` (sample invoices, export files, seed data).

## Intended commands (targets — do not exist until built)

Per BRD NFR-OPS-01, a clean clone must reach a working seeded system via:
```
docker compose up        # api, worker, frontend, postgres, redis, optional minio
make seed-demo           # seeded demo data (Admin, cost centers, GL accounts, vendor, approval rule)
```
Backend tests use `pytest`; frontend uses Vitest. When you build these, keep the one-command self-host promise intact.

## Non-negotiable implementation rules

These come from BRD §4/§5 and the NFRs. They shape the schema and service layer, so honor them from the first commit:

- **State machines in code, not scattered string updates.** Every entity with a status (PO, vendor, invoice, approval step, match) has one authoritative set of allowed transitions defined in code. Reject invalid transitions with **HTTP 409**. Status enums are enumerated authoritatively in BRD §5.2.
- **Audit log is append-only.** Every create/update/delete/state-transition/approval/login/export writes an `audit_log` row (actor, action, object, before/after JSONB, timestamp, IP). No update/delete endpoints for it may exist.
- **Money is never a float.** `NUMERIC(15,2)` + ISO-4217 `currency` everywhere. All timestamps `timestamptz` in UTC; timezone applied in the frontend only.
- **All tables get** UUID `id` pk, `created_at`, `updated_at`.
- **Workers are idempotent.** Jobs take IDs, re-read state, and are safe to retry; poison messages go to a visible dead-letter state (PLT-07).
- **RBAC enforced server-side on every endpoint**, including object-level checks (e.g. requesters see only their own drafts) in the query layer — the frontend only hides affordances.
- **Bank details are fraud-critical (VEN-06):** never overwrite. Any change creates a new *versioned* `pending` record requiring dual control (approval by a *different* internal user). Account numbers encrypted at rest (AES-GCM via `SECRET_ENCRYPTION_KEY`); store only last-4 in plaintext. Never log secrets or full bank numbers.
- **Vendor portal is isolated (NFR-SEC-02):** separate router, token-scoped access to one vendor's onboarding resources only, aggressive rate limiting, no enumeration (constant-time check, 404 on invalid token).
- **Extraction and ERP export are plugin interfaces** — the intended community contribution surface. Keep them behind clean abstractions (`StorageBackend`, extraction strategy chain, `ERPConnector` ABC). LLM extraction is **off by default** and never receives documents unless an Admin explicitly enables it.
- **Approval engine is object-agnostic** (`object_type`, `object_id`) — v1 drives POs but must extend to invoices/vendors without schema changes. On submission, snapshot the resolved approver chain so later rule edits don't affect in-flight approvals; first matching rule (by priority) wins.

## Conventions

- **Requirement IDs are stable and referenceable.** Cite them in commits, tests, and PRs — e.g. `feat(VEN-03): vendor review queue`. Every requirement ID in BRD §6 must have at least one test referencing it (NFR-QUA-01: ≥80% coverage on business logic — approval engine, matching, state machines, export mapping).
- REST API under `/api/v1`; errors as RFC 7807 problem+json; list endpoints paginated (default 25, max 200) with DB indexes on every filter column.
- Build in **vertical slices by phase** (BRD §9): Phase 1 foundation/PO core → Phase 2 vendor portal/receiving → Phase 3 invoice inbox/matching/ERP export (the differentiating phase) → Phase 4 hardening/API connectors. Each phase must end demo-able with seed data and its acceptance criteria met.
