# SpeakFlow project handbook

This handbook explains SpeakFlow from the outside in. It is intended for a new
developer, reviewer, or college examiner who needs to understand not only what
the application does, but why the code is arranged as it is and how a user
action travels through the system.

The repository README remains the installation and quick-start reference. This
handbook records the architecture and provides a maintainer-oriented map of the
current implementation.

## Recommended reading order

1. [System overview](01-system-overview.md) — product scope, processes,
   dependencies, and design patterns.
2. [Backend architecture](02-backend-architecture.md) — FastAPI composition,
   feature boundaries, application services, and runtime adapters.
3. [Backend file guide](03-backend-file-guide.md) — responsibility of each
   production backend file and major test group.
4. [Flutter architecture](04-flutter-architecture.md) — routing, state,
   feature-first layout, networking, and widget decomposition.
5. [Flutter file guide](05-flutter-file-guide.md) — responsibility of each
   file under `frontend/lib`.
6. [Runtime flows](06-runtime-flows.md) — end-to-end sequences for startup,
   authentication, learning plans, pronunciation, roleplay, and news.
7. [Data and migrations](07-data-and-migrations.md) — PostgreSQL ownership,
   tables, transactions, pgvector, local device files, and Alembic.
8. [API, authentication, and security](08-api-auth-security.md) — route
   families, bearer identity, middleware, rate limits, and trust boundaries.
9. [ML models and providers](09-ml-and-providers.md) — local models, Groq,
   Ollama, NewsAPI, model loading, and score authority.
10. [Testing and quality](10-testing-and-quality.md) — test suites,
    architecture checks, the 500-line policy, and validation commands.
11. [Operations and troubleshooting](11-operations.md) — daily startup,
    health, migrations, logs, and common failure diagnosis.
12. [Changing the system safely](12-change-guide.md) — where new code belongs
    and the checks required for common changes.
13. [Repository and configuration guide](13-repository-config-guide.md) — root
    files, Flutter/Android scaffolding, assets, generated paths, and secrets.

## Architectural summary

SpeakFlow is a feature-oriented Clean Architecture modular monolith:

- one Flutter application presents the user interface;
- one FastAPI process exposes REST and WebSocket contracts;
- one PostgreSQL 16 database with pgvector stores authoritative shared data;
- local ML models provide speech, pronunciation, grammar, and TTS capabilities;
- external providers supply constrained language generation, embeddings, and
  optional live news.

“Modular monolith” means the backend deploys as one process but its code is
owned by business features. “Clean Architecture” means dependencies should
point toward business contracts, while FastAPI, SQLAlchemy, files, provider
SDKs, and model runtimes stay at the edges.

## Sources of truth

When documentation and implementation disagree, use this order:

1. executable behavior and automated tests;
2. migration files and Pydantic/Dart contract models;
3. this handbook and the repository README.

Update the relevant handbook page in the same change whenever a route, file
owner, migration head, startup command, or major runtime flow changes.

## Important invariants

- PostgreSQL is authoritative for accounts, plans, attempts, generation jobs,
  roleplay sessions, and reviewed curriculum.
- Device files hold only user-namespaced local practice lists, phoneme progress,
  auth-session restoration, and UI preferences.
- Answers and completion decisions are server-authoritative.
- Scripted pronunciation uses target-dependent acoustic evidence; roleplay
  delivery metrics never pretend to be reference pronunciation scores.
- Expensive models load lazily, not during `/health` or module import.
- Every hand-written Python and Dart source file must remain at or below 500
  lines; 100–300 lines is the preferred range.
- `alembic current` must match `alembic heads` before running a new backend
  revision against an existing database.
