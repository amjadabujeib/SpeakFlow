# Operations and troubleshooting

## Daily startup

From the repository root:

```bash
docker compose up -d postgres
cd backend
../.venv/bin/python -m alembic -c alembic.ini upgrade head
cd ..
.venv/bin/python backend/main.py
```

In another terminal, verify:

```bash
curl http://127.0.0.1:8000/health
docker compose ps
curl http://127.0.0.1:11434/api/tags
```

The backend blocks startup while loading all four local model families. Wait
for `All local runtime models are ready`; `/health` remains degraded when eager
warm-up reports an unavailable model.

For a physical Android device:

```bash
adb devices
adb reverse tcp:8000 tcp:8000
cd frontend
flutter run
```

For the optional local operations dashboard:

```bash
cd backend
../.venv/bin/python -m speakflow.features.admin.cli grant admin@example.com
cd ../admin-dashboard
npm ci
npm run dev
```

Open the Vite URL, normally `http://localhost:5173`. Its development proxy
expects FastAPI at `http://127.0.0.1:8000`.

## Health semantics

`GET /health` is intentionally lightweight. It reports:

- HTTP 200 with `ok` when PostgreSQL is reachable, the PLP worker is alive,
  and every supported level has enough active skills with reviewed curriculum;
- HTTP 503 with `degraded` otherwise.

It must not load models or expose provider/model details. An `ok` response
also proves the database contains the minimum generation catalog, but it does
not prove the schema revision matches the code.

The authenticated dashboard owns detailed diagnostics: it performs a bounded
Ollama tags probe, labels Groq only as configured/missing, and reports
process-local loaded-model flags. Database/query failures return HTTP 503
instead of zero-like data. Use backend logs for the detailed exception.

## Migration check

```bash
cd backend
../.venv/bin/python -m alembic -c alembic.ini current
../.venv/bin/python -m alembic -c alembic.ini heads
```

If the values differ, run `upgrade head` before retrying the app. The expected
head for this revision is `20260809_12`.

## Learning-plan database error

Symptom: Flutter shows “Could not check your learning plan” and a generic PLP
PostgreSQL message.

Check in this order:

1. `ss -ltnp` or `docker compose ps`: is port 5432 listening?
2. `/health`: can the backend reach the database, run its worker, and find the
   reviewed generation catalog?
3. `alembic current` versus `alembic heads`: is the schema current?
4. backend terminal: is the underlying error connection, authentication,
   missing relation/column, constraint, or provider worker failure?
5. after correcting the cause, tap “Try again.”

If `/health` is degraded while PostgreSQL and the worker are available, restore
the idempotent reviewed catalog with `python -m speakflow.features.learning_plan.engine.ingest`, then import the
verified curriculum snapshot as described by the root setup flow. Generation
returns HTTP 503 with the same actionable ingestion guidance while the catalog
is unavailable instead of exposing an internal traceback.

Do not delete the database volume as a first response. Migrations normally
preserve existing learner/curriculum data.

## App cannot reach backend

- Verify `curl http://127.0.0.1:8000/health` on the host.
- Verify `adb devices` shows an authorized device.
- Re-run `adb reverse tcp:8000 tcp:8000` after reconnect/reboot.
- Confirm debug builds use the expected `SPEAKFLOW_API_URL` and WebSocket URL.
- In WSL, verify Windows can reach WSL `localhost:8000` before involving ADB.

## Authentication failures

- HTTP 401 “bearer token required”: request did not include a session.
- HTTP 401 invalid/expired: sign in again; device state may hold an old token.
- HTTP 503 auth database unavailable: inspect PostgreSQL and migrations.
- Duplicate email: sign in rather than creating another account.
- Guest session lost after signout: expected; guests are intentionally
  unrecoverable.

## PLP generation states

- `pending`: worker has not claimed the job yet.
- `generating`: worker holds an active lease.
- provider rate-limit wait: job remains resumable until the recorded reset.
- `failed`: inspect the safe failure envelope and backend log, then use retry if
  allowed.
- stale generating job: worker recovery can reclaim it after the lease expires.

Verify `GROQ_API_KEYS`, worker state in the authenticated dashboard, PostgreSQL
time/connectivity, and provider reset information before manually editing rows.
With a configured pool, a PLP job reaches its durable rate-limit wait only after
the writer has no non-cooling key available. The dashboard reports only whether
credentials exist; it never returns key values.

## Model problems

- Slow startup is expected because all local models load eagerly; first requests
  should not pay model initialization cost.
- Missing asset/checksum errors: rerun `backend/tools/setup_backend.py`; do not download an
  arbitrary replacement manually.
- GPU memory issue: set `FORCE_CPU=1` and restart.
- Runtime tries to access Hugging Face: verify the managed local paths; runtime
  is intentionally offline.
- Pronunciation asset versions disagree: reinstall the complete verified bundle
  because partial compatibility is not accepted.

## Ollama/curriculum problems

- Verify `ollama serve` or its systemd service.
- Verify `embeddinggemma` appears in `/api/tags`.
- Inspect the default `backend/.models/curriculum/rag-curriculum-v1.zip` with
  the snapshot CLI.
- Run `python -m tools.audit_curriculum` from `backend/` rather than
  re-ingesting blindly. It reports the 8,223-record catalog's vocabulary/grammar
  composition, runtime-safe topical/general/excluded roles, reviewed-interest
  assignment integrity, and direct/teachable coverage for every CEFR/interest
  cell.
- Interest-review changes are application code and need only a backend restart;
  do not reseed or re-embed an existing healthy snapshot for them.
- Snapshot model/dimension mismatch requires the matching versioned snapshot,
  not a metadata edit.

## News and TTS

- News provider missing: set `NEWSAPI_KEY` and restart; the app does not invent
  live articles.
- Broken article image: check backend proxy validation; private/unsafe URLs are
  rejected intentionally.
- TTS first request slow after a successful eager warm-up: inspect synthesis and
  audio-cache logs rather than model-loading state.
- Concurrent identical TTS requests should share synthesis and then use cache.

## Logs and observability

The development backend currently logs to its terminal. Keep the startup
terminal visible when reproducing an error. Correlate:

- Flutter-visible message and route;
- HTTP status/body;
- backend exception type;
- Alembic revision;
- provider/job state;
- model loaded flags from the authenticated dashboard.

Avoid printing bearer tokens, passwords, provider keys, or full `.env` values.
The dashboard receives only categorized generation failures; raw detail remains
in access-controlled backend logs and storage.

## Dashboard operations

- HTTP 401: the bearer session is missing/expired; sign in again.
- HTTP 403: the account is not currently an administrator; grant it locally or
  use another account.
- Privilege grant/remove revokes existing sessions by design.
- Every session revocation requires a reason and returns its audit event ID.
- A Vite production build creates static `dist/` assets only; proxy both
  `/api/auth` and `/admin` to FastAPI over HTTPS.
- FastAPI and Compose PostgreSQL bind to loopback by default. Deliberately
  configure a trusted reverse proxy/firewall before remote exposure.

## Safe cleanup

Generated Python `__pycache__`, Flutter build output, `.dart_tool`, downloaded
weights, and temporary audio/cache files are reproducible. Database volumes,
`.env`, Hugging Face credentials, and learner exports are not interchangeable
with caches. Resolve exact targets before deleting anything.
