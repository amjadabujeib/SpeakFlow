# Data and migrations

## Data ownership

PostgreSQL is authoritative for data that must survive devices, enforce user
ownership, participate in transactions, or affect learning outcomes. Flutter
device files are limited to local convenience state.

- **Users, password hashes, session hashes** — PostgreSQL

- **Learner profile and timezone** — PostgreSQL

- **Curriculum sources/chunks/concepts/embeddings** — PostgreSQL

- **Plans, revisions, lessons, generation jobs** — PostgreSQL

- **Attempts, XP, progress, skill evidence** — PostgreSQL

- **Roleplay scenarios, sessions, turns, evaluations** — PostgreSQL

- **Saved practice word queue** — device file, namespaced by user

- **Measured phoneme history** — device file, namespaced by user

- **Current bearer session restoration** — device file

- **Font scale** — device file

## Shared ORM registry

All ORM mappings inherit from `speakflow.shared.orm.Base`. Alembic imports this
metadata and the model modules. A single registry matters because foreign keys
cross feature packages: PLP and roleplay records belong to auth users.

## Authentication tables

- `users` stores UUID, kind (`registered`, `guest`, or compatible local kind),
  email/display name, scrypt hash when registered, and timestamps.
- `auth_sessions` stores token SHA-256 hash, user UUID, creation/expiry,
  revocation, and last-use information.

Raw passwords and raw bearer tokens are never stored.

## Learning-plan tables

- `learner_profiles` stores CEFR, native/support language, goals, interests,
  internal planning defaults, timezone, and revision.
- `skills` and `skill_prerequisites` define the reviewed learning graph.
- `curriculum_sources`, `curriculum_chunks`, and `curriculum_concepts` hold
  source-attributed teaching/retrieval data and optional vectors.
- `learning_plans` is the user-owned active plan identity. A unique constraint
  permits one plan per user.
- `plan_revisions` preserves each regenerated learner plan and its reason.
- `plan_lessons` stores private compiled content and publication/status data.
- `generation_jobs` is the durable worker queue, retry envelope, and lease.
- `lesson_progress` stores learner status, score, XP, attempts, and timing.
- `activity_attempts` stores answer/evidence/result and idempotent submission ID.
- `skill_evidence` binds trusted attempts to specific skill mastery evidence.
- `study_days` supports streak and daily learning summaries.
- `adaptation_proposals` stores reviewable plan adjustment suggestions.

## Roleplay tables

- `roleplay_scenarios` stores built-in/custom scenario contracts and owner when
  applicable.
- `roleplay_sessions` freezes the chosen scenario, objective state, status, and
  final evaluation for one user session.
- `roleplay_turns` stores ordered learner/assistant evidence with idempotent turn
  identity and optional speech/grammar metadata.

## Transaction rules

`session_scope()` commits only after the whole use case succeeds. Exceptions
roll back all writes. Important multi-record transitions—attempt plus progress,
generation publication, roleplay turn pairs, and reset—must remain atomic.

Do not call `commit()` inside a helper that participates in a larger use case.
Use `flush()` only when a generated primary key or foreign-key parent must exist
before the remaining writes.

## User scoping

Authentication middleware binds the authenticated user UUID to a context-local
identity. Every learner-owned PLP query obtains that identity internally.
Roleplay services explicitly scope scenario/session/turn queries. IDs alone are
never authorization.

## Curriculum snapshot

The private `rag-curriculum-v1.zip` contains a deterministic manifest, source
metadata, concepts, and embeddings. Export sorts and normalizes data so the
same content yields the same archive. Import verifies checksums, version,
embedding model/dimensions, references, and duplicate identities before a
transactional upsert.

The snapshot is a managed model-bundle asset because generated vectors are too
large and environment-specific for source control.

## Alembic workflow

Before starting a newly updated backend against an existing database:

```bash
cd backend
../.venv/bin/python -m alembic -c alembic.ini current
../.venv/bin/python -m alembic -c alembic.ini heads
../.venv/bin/python -m alembic -c alembic.ini upgrade head
```

`current` reports the database revision. `heads` reports what the checked-out
code expects. They must match after upgrade.

The current head is `20260802_09`. It standardizes the runtime contracts by:

- replacing the old architecture label with `weekly_mission`;
- removing unused planner, generator, scenario, and evaluation labels;
- retaining one `format_revision` compatibility boundary for learning plans.

## Why a reachable database can still fail

A readiness check such as `SELECT 1` proves that credentials, host, and server
work. It does not prove that every expected column exists. If code maps a new
column but Alembic is one revision behind, SQLAlchemy raises a schema error when
selecting the model. The PLP boundary translates database exceptions to a safe
generic “PostgreSQL unavailable” message.

Therefore, if `/health` says the database is ready but the app cannot load a
plan, compare Alembic revisions and inspect backend logs before changing URLs or
credentials.

## Creating a migration safely

1. Change the ORM model and associated Pydantic/domain contracts.
2. Add an ordered Alembic revision with correct `down_revision`.
3. Make data backfills/defaults explicit before adding non-null constraints.
4. Add uniqueness/check constraints that encode the business invariant.
5. Test upgrade from the previous head, not only an empty database.
6. Run architecture/unit/integration tests.
7. Update README and this page with the new head and semantic change.

Never use `Base.metadata.create_all()` as a substitute for migrations in an
existing deployment; it cannot express or audit schema evolution reliably.
