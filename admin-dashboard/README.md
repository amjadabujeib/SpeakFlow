# SpeakFlow operations dashboard

Authenticated React 19 and Vite 8 dashboard for inspecting the SpeakFlow
backend. It shows system/model state, searchable account/session data,
learning-plan generation, roleplay activity, sanitized PLP failure categories,
and immutable administrator audit history. An administrator can revoke a
user's active sessions with a recorded reason.

This is an operational surface, separate from the Flutter learner application.
Its backend routes live in
`backend/speakflow/features/admin/presentation.py`.

## Security model

Every `/admin` request requires an opaque SpeakFlow bearer session. FastAPI
authenticates the session and then requires the persisted `users.is_admin`
flag; anonymous requests receive 401 and ordinary learner accounts receive
403. The dashboard stores its session in browser `sessionStorage`, sends it in
the `Authorization` header, and clears it on sign-out or authorization failure.
It uses bearer headers rather than cookies, so the admin command surface does
not rely on browser cookies or CORS for authorization.

Administrator access cannot be requested through public signup. Register the
account normally, migrate the database, and grant access using the local CLI:

```bash
cd backend
../.venv/bin/python -m alembic -c alembic.ini upgrade head
../.venv/bin/python -m speakflow.features.admin.cli grant admin@example.com
```

Use `remove` instead of `grant` to remove access. Both commands revoke all
existing sessions for the account and write an audit event, so the operator
must sign in again afterward.

The backend and PostgreSQL bind to loopback by default. A remote deployment
still requires HTTPS, a trusted reverse proxy, deliberately configured CORS,
network/firewall controls, and protected backend logs.

## Requirements

- a SpeakFlow PostgreSQL database migrated to the repository's Alembic head;
- a registered user granted administrator access;
- Node.js `^20.19.0` or `>=22.12.0`;
- npm, using the committed `package-lock.json`.

## Local development

Start FastAPI from the repository root:

```bash
.venv/bin/python backend/main.py
```

In another terminal:

```bash
cd admin-dashboard
npm ci
npm run dev
```

Open the Vite URL, normally `http://localhost:5173`, and sign in with the
administrator account. Vite proxies `/api/auth/*` and `/admin/*` to
`http://127.0.0.1:8000`. Operational summary tabs load immediately and refresh
every ten seconds. User searches and audit pages load on demand.

Failed requests never produce fabricated statistics. The dashboard shows an
explicit error and retry action; if previously loaded live data exists, it
remains visible as stale data until a later successful refresh.

## Backend endpoints

| Method | Path | Dashboard use |
| --- | --- | --- |
| `GET` | `/admin/dashboard` | Database/provider summary, lazy-model state, user/session totals, five recent users |
| `GET` | `/admin/users` | Paginated account directory with email, display-name, or UUID search |
| `GET` | `/admin/audit-events` | Paginated immutable privileged-action history |
| `GET` | `/admin/learning` | Lesson content counts, generation-job statuses, lesson-type counts |
| `GET` | `/admin/roleplay` | Global session counts, nullable score averages, ten recent sessions |
| `GET` | `/admin/errors` | Up to 20 sanitized failed-PLP categories; never raw exception text |
| `POST` | `/admin/users/{user_id}/revoke` | Revoke active sessions with a required reason and audit event |

Read endpoints aggregate all learners, which is why backend administrator
authorization is mandatory. Database failures return HTTP 503 rather than
zero-like data. Ollama health performs a bounded `/api/tags` probe; Groq status
means configured or missing, not remaining quota. Model flags mean “loaded in
this FastAPI process,” not a full inference test. The error feed is limited to
PLP generation failures and exposes safe categories/messages only.
Audit events are retained indefinitely in PostgreSQL; the paginated endpoint
also provides a machine-readable JSON export surface.

## Project map

- `src/adminApi.js` — authenticated transport and safe HTTP errors.
- `src/components/AdminLogin.jsx` — administrator sign-in form.
- `src/components/Dashboard.jsx` — tab state, polling, retry, and stale-data behavior.
- `src/components/SystemHealth.jsx` — backend/provider/model summary.
- `src/components/UserManagement.jsx` — totals and confirmed, reasoned revocation.
- `src/components/UserDirectory.jsx` — searchable/paginated account operations.
- `src/components/AuditLog.jsx` — paginated privileged-action history.
- `src/components/LearningPanel.jsx` — lesson and generation-job aggregates.
- `src/components/RoleplayPanel.jsx` — session aggregates and recent sessions.
- `src/components/ErrorFeed.jsx` — sanitized failed-generation categories.
- `vite.config.js` — React plugin and local auth/admin proxies.
- API requests abort after eight seconds so a stalled backend cannot accumulate
  overlapping dashboard polls.
- `test/adminApi.test.js` — authentication, authorization, transport, and error tests.

## Checks and production build

```bash
npm run lint
npm test
npm run build
```

`npm run build` writes ignored static assets to `dist/`. FastAPI does not serve
that directory. A deployment must serve `dist/` separately and proxy both
`/api/auth` and `/admin` to FastAPI on the same HTTPS origin. `npm run preview`
does not inherit the development proxy and therefore needs an equivalent
external reverse proxy for live data.

For system-wide architecture and operations, see the
[project handbook](../handbook/README.md) and
[dashboard guide](../handbook/14-admin-dashboard.md).
