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

For a physical Android device:

```bash
adb devices
adb reverse tcp:8000 tcp:8000
cd frontend
flutter run
```

## Health semantics

`GET /health` is intentionally lightweight. It reports:

- process status;
- whether local model packages/assets are available;
- whether each expensive model is currently loaded;
- whether Groq is configured;
- PLP database reachability and worker state.

It must not load models. Database “ready” proves a basic query succeeds; it
does not prove the schema revision matches the code.

## Migration check

```bash
cd backend
../.venv/bin/python -m alembic -c alembic.ini current
../.venv/bin/python -m alembic -c alembic.ini heads
```

If the values differ, run `upgrade head` before retrying the app. The expected
head for this revision is `20260802_09`.

## Learning-plan database error

Symptom: Flutter shows “Could not check your learning plan” and a generic PLP
PostgreSQL message.

Check in this order:

1. `ss -ltnp` or `docker compose ps`: is port 5432 listening?
2. `/health`: can the backend reach the configured database?
3. `alembic current` versus `alembic heads`: is the schema current?
4. backend terminal: is the underlying error connection, authentication,
   missing relation/column, constraint, or provider worker failure?
5. after correcting the cause, tap “Try again.”

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

Verify `GROQ_API_KEY`, worker state in `/health`, PostgreSQL time/connectivity,
and provider reset information before manually editing rows.

## Model problems

- A first request can be slow because models load lazily.
- Missing asset/checksum errors: rerun `backend/setup.py`; do not download an
  arbitrary replacement manually.
- GPU memory issue: set `FORCE_CPU=1` and restart.
- Runtime tries to access Hugging Face: verify the managed local paths; runtime
  is intentionally offline.
- Pronunciation asset versions disagree: reinstall the complete verified bundle
  because partial compatibility is not accepted.

## Ollama/curriculum problems

- Verify `ollama serve` or its systemd service.
- Verify `embeddinggemma` appears in `/api/tags`.
- Inspect the curriculum snapshot with the snapshot CLI.
- Run curriculum audit tools rather than re-ingesting blindly.
- Snapshot model/dimension mismatch requires the matching versioned snapshot,
  not a metadata edit.

## News and TTS

- News provider missing: set `NEWSAPI_KEY` and restart; the app does not invent
  live articles.
- Broken article image: check backend proxy validation; private/unsafe URLs are
  rejected intentionally.
- TTS first request slow: Kokoro loads lazily.
- Concurrent identical TTS requests should share synthesis and then use cache.

## Logs and observability

The development backend currently logs to its terminal. Keep the startup
terminal visible when reproducing an error. Correlate:

- Flutter-visible message and route;
- HTTP status/body;
- backend exception type;
- Alembic revision;
- provider/job state;
- model loaded flags from `/health`.

Avoid printing bearer tokens, passwords, provider keys, or full `.env` values.

## Safe cleanup

Generated Python `__pycache__`, Flutter build output, `.dart_tool`, downloaded
weights, and temporary audio/cache files are reproducible. Database volumes,
`.env`, Hugging Face credentials, and learner exports are not interchangeable
with caches. Resolve exact targets before deleting anything.
