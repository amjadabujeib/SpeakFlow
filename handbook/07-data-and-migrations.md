# Data and migrations

## Data ownership

PostgreSQL is authoritative for data that must survive devices, enforce user
ownership, participate in transactions, or affect learning outcomes. Flutter
device files are limited to local convenience state.

- **Users, password hashes, session hashes** — PostgreSQL

- **Administrator capability and privileged-action audit** — PostgreSQL

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

- `roleplay_scenarios` stores user-owned custom scenario contracts. Reviewed
  built-ins remain code-owned.
- `roleplay_sessions` freezes the chosen scenario, objective state, status, and
  final evaluation for one user session.
- `roleplay_turns` stores ordered learner/assistant evidence with idempotent turn
  identity and optional speech/grammar metadata.

Replacing or deleting a custom scenario never rewrites a session snapshot, so
active conversations and historical transcripts retain their original roles,
goals, phrases, and rubric.

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

The operations dashboard is the explicit exception: its reporting queries are
global by design, and its revoke operation targets a supplied user UUID. It
can cross learner boundaries only after middleware authenticates the actor and
confirms persisted administrator access. Revocation and its audit row commit
atomically.

`users.is_admin` defaults to false. `admin_audit_events` stores the actor,
target, action, structured detail, and timestamp for privilege changes and
session revocation. User deletion sets actor/target references to null while
retaining the operational record.

## Curriculum snapshot

The private `rag-curriculum-v1.zip` contains a deterministic manifest, source
metadata, concepts, and embeddings. Export sorts and normalizes data so the
same content yields the same archive. Import verifies checksums, version,
embedding model/dimensions, references, and duplicate identities before a
transactional upsert.

The current snapshot's 8,223 records are not 8,223 interchangeable lesson words.
They comprise 7,799 vocabulary records (6,863 distinct case-folded headwords) and
424 grammar records. The 7,227 `prototype_ready` vocabulary rows record successful
lexical enrichment and embeddings; the runtime still applies a stricter teaching
gate. At the current snapshot version, 5,433 rows pass that gate, while the
remainder stay useful for evaluation, audit, or future reviewed enrichment.

The snapshot is a managed model-bundle asset because generated vectors are too
large and environment-specific for source control.

CEFR, headword, part of speech, source definition, pronunciation evidence, and
embeddings remain snapshot/database facts. A separate code-owned review overlay
may add or remove an interest tag only for an exact
`(CEFR, normalized headword, part of speech)` identity. The current overlay has
129 source-backed assignments and removes three known false Technology links
created by a formerly broad “scientific development” mapping. It does not
invent records, rewrite source levels, or mutate the snapshot.

Because the overlay is applied during retrieval and auditing, changing to a
version that contains it requires only a backend restart. Do not reseed,
re-import, or recompute embeddings for that change. A fresh database still
requires the normal reviewed catalog ingest and snapshot import.

## Alembic workflow

### Why the revision history stays in the repository

`migrations/versions/` is an ordered schema history, not a collection of
alternative schemas. Each revision describes how to move a database from one
known version to the next. Alembic follows the `revision`/`down_revision` chain
when upgrading an existing installation, and a deployed database records the
revision it has reached. Removing an older file can therefore make an otherwise
valid database impossible to upgrade.

The directory is deliberately small: the Alembic scaffold and all current
revision source files total about 41 KiB. Any additional `__pycache__` files are
ignored, reproducible interpreter output and are not part of the repository.
Keep the following files:

- `env.py`, which connects Alembic to the application metadata and database;
- `script.py.mako`, which is the revision template;
- every file under `versions/`, which forms the upgrade chain.

Do not combine or delete revisions merely to shorten the directory. A migration
history may be baselined only as an explicit release operation when every
supported database will either be recreated or stamped to a verified equivalent
schema. SpeakFlow has persistent development data and gains no meaningful size
benefit from doing that now.

Before starting a newly updated backend against an existing database:

```bash
cd backend
../.venv/bin/python -m alembic -c alembic.ini current
../.venv/bin/python -m alembic -c alembic.ini heads
../.venv/bin/python -m alembic -c alembic.ini upgrade head
```

`current` reports the database revision. `heads` reports what the checked-out
code expects. They must match after upgrade.

The current head is `20260809_12`. The latest three revisions add:

- the non-null, false-by-default `users.is_admin` capability;
- the indexed `admin_audit_events` table and user foreign keys;
- `roleplay_turns.grammar_evaluated`, which distinguishes an evaluated correct
  turn from a turn for which the local grammar model was unavailable.
- `roleplay_turns.turn_status` plus its check constraint, which prevents
  unclear/off-topic turns from being treated as meaningful evaluation evidence.

## Why a reachable database can still fail

A readiness check such as `SELECT 1` proves that credentials, host, and server
work. It does not prove that every expected column exists. If code maps a new
column but Alembic is one revision behind, SQLAlchemy raises a schema error when
selecting the model. The PLP boundary translates database exceptions to a safe
generic “PostgreSQL unavailable” message.

`/health` also checks the minimum reviewed generation catalog, but it cannot
prove that the schema revision matches the code. Therefore, if it says `ok` but
the app cannot load a plan, compare Alembic revisions and inspect backend logs
before changing URLs or credentials.

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
