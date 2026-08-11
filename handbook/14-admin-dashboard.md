# Operations dashboard

## Purpose and boundary

`admin-dashboard/` is the authenticated React/Vite client for operational
visibility. It is independent of the Flutter learner client and reads the
backend route family owned by `speakflow.features.admin`.

The dashboard reports process/provider state, account/session totals, PLP
lesson and job aggregates, roleplay aggregates, and sanitized PLP generation
failures. It is a focused diagnostic interface rather than a complete metrics,
logging, or tracing system.

## Runtime shape

In development, Vite proxies authentication and administrative requests to the
loopback FastAPI listener:

```text
Browser -> Vite -> /api/auth proxy -> FastAPI -> PostgreSQL
                -> /admin proxy ---->         -> PLP worker state
                                              -> Ollama health probe
                                              -> in-process model references
```

`App.jsx` restores an administrator session from `sessionStorage` or shows the
sign-in form. `Dashboard.jsx` owns the selected tab and polls operational
summary tabs every ten seconds. Searchable users and paginated audit history
load on demand. A failed refresh shows an error and retry action. It never
substitutes mock statistics; previously loaded live data can remain visible
while marked by the error banner.

## Administrator identity

Administrator status is a persisted Boolean on a registered `users` row.
Public signup always creates a non-admin account. The local command below is the
only supported privilege-management path:

```bash
cd backend
../.venv/bin/python -m speakflow.features.admin.cli grant admin@example.com
../.venv/bin/python -m speakflow.features.admin.cli remove admin@example.com
```

Both operations lock the target user, change `is_admin`, revoke every existing
session, and create an `admin_audit_events` row with source `local_cli`. Revoking
sessions prevents a bearer token issued before promotion from silently gaining
administrator power.

The dashboard signs in through the ordinary `/api/auth/signin` endpoint and
checks the returned `user.is_admin` claim. This UI check improves feedback, but
the actual boundary is backend middleware: every `/admin` request is
authenticated again and rejected with 403 unless the current database record
is an administrator. The middleware attaches that identity to `request.state`
for audit attribution.

## Backend route contract

- `GET /admin/dashboard` verifies PostgreSQL, performs a two-second Ollama tags
  probe, reports Groq configuration and worker state, inspects process-local
  eagerly warmed model references, and returns account/session/job aggregates.
- `GET /admin/learning` groups all plan lessons by content status/type and all
  generation jobs by status.
- `GET /admin/roleplay` aggregates all roleplay sessions, converts stored
  alignment coverage from a 0–1 fraction to a percentage, and returns ten
  recent sessions.
- `GET /admin/errors` maps the last 20 failed generation jobs to safe failure
  categories/messages. Raw exception text remains in protected backend storage
  and logs.
- `GET /admin/users` returns a bounded page of accounts and supports search by
  email, display name, or exact UUID. Each row includes its active-session count.
- `GET /admin/audit-events` returns a bounded, newest-first page of immutable
  privileged-action records.
- `POST /admin/users/{user_id}/revoke` requires a 3–200-character reason,
  revokes the target's non-expired active sessions, and atomically records the
  actor, target, reason, count, action, and timestamp in `admin_audit_events`.

All responses use strict Pydantic models. Database failures are logged with
detail on the server and returned as a safe HTTP 503; empty databases still
return valid zero counts. Administrative reads and revocation have explicit
fixed-window rate limits.

## Health semantics

- PostgreSQL is healthy only after the database check and aggregate queries
  succeed.
- Ollama is healthy only when its configured `/api/tags` endpoint returns a
  successful response within two seconds.
- Groq is `configured` or `missing`; the dashboard does not claim to know
  provider quota.
- worker count reflects the current FastAPI process.
- model flags say whether a model object is loaded in that process; they do not
  trigger loading or inference.
- overall state becomes `warning` when Ollama is unavailable, Groq is missing,
  or the PLP worker is not alive. PostgreSQL failure makes the request 503.

## Persistence and migration

Migration `20260808_10` adds:

- non-null `users.is_admin`, defaulting to false;
- `admin_audit_events` with nullable actor/target foreign keys using `SET NULL`
  on user deletion, action/detail fields, and query indexes.

Audit rows survive account deletion without retaining a dangling foreign key.
The authenticated read endpoint is paginated; no endpoint edits or deletes
audit events. The current retention policy is indefinite: events remain for the
lifetime of the PostgreSQL volume. Operators can export the paginated JSON
response through the authenticated API before normal database backup or
retention changes.

## Network and browser security

FastAPI defaults to `127.0.0.1`, configurable through `SPEAKFLOW_HOST` and
`SPEAKFLOW_PORT`. Docker Compose publishes PostgreSQL only on
`127.0.0.1:${POSTGRES_PORT}`. These defaults contain local development services
but do not replace production controls.

New administrator sign-ins receive an eight-hour session rather than the
30-day learner lifetime. The dashboard uses an Authorization bearer header with `credentials: omit`, so
state-changing requests do not rely on cookies. CORS is still configured for
browser isolation, but authorization is enforced independently. A remote
deployment must use HTTPS, a trusted reverse proxy, deliberate allowed origins,
firewall rules, and access-controlled logs. Avoid third-party scripts because
the dashboard session lives in `sessionStorage` and is therefore sensitive to
same-origin script execution.

## Validation

```bash
cd admin-dashboard
npm ci
npm run lint
npm test
npm run build
```

Backend coverage verifies anonymous rejection, ordinary-user rejection,
administrator access, revocation, privilege-change session invalidation, audit
records, safe error feeds, and rate-limit selection. The production `dist/`
directory is ignored and must be served separately with `/api/auth` and
`/admin` reverse-proxied to FastAPI.

## Change map

- Admin transport/security policy: `speakflow/app/factory.py`.
- Operational schemas and handlers: `speakflow/features/admin/`.
- Privilege CLI: `speakflow/features/admin/cli.py`.
- Persistence: admin/auth infrastructure models and Alembic migrations.
- Browser auth/transport: `adminApi.js`, `App.jsx`, and `AdminLogin.jsx`.
- Polling/presentation: `Dashboard.jsx`, `UserDirectory.jsx`, `AuditLog.jsx`, and
  focused panels.
- Contract/security tests: `backend/tests/admin/test_admin_security.py`,
  `backend/tests/app/test_architecture.py`, and
  `admin-dashboard/test/adminApi.test.js`.
