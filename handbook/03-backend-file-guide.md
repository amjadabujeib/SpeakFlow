# Backend file guide

This page maps the production backend. Test files are described in
[Testing and quality](10-testing-and-quality.md); training scripts are described
in [ML models and providers](09-ml-and-providers.md).

## Backend root

- **`main.py`** — Executable composition root; wires routers, lifespan, health, and
  runtime callables.

- **`setup.py`** — Cross-platform bootstrap: dependencies, database, migrations, models,
  curriculum, and verification.

- **`pyproject.toml`** — Python package metadata, package discovery, and declared
  top-level modules.

- **`requirements.txt`** — Reproducible runtime/test dependency list used by setup.

- **`alembic.ini`** — Alembic configuration; migration environment is below
  `migrations/`.

Keeping only launch and configuration files here makes the backend root a
navigation surface rather than an implementation package.

## Shared configuration

- **`speakflow/config.py`** — Finds and loads the repository `.env` for the app,
  migrations, setup, and tools, and resolves the backend model root.

## `speakflow/app`

- **`__init__.py`** — Exports application construction functions.

- **`factory.py`** — Creates FastAPI and owns middleware, identity binding, upload
  limits, and rate limits.

- **`health.py`** — Builds the deliberately lightweight `/health` router.

- **`rate_limit.py`** — Process-shared fixed-window rate limiting backed by a small
  SQLite state file.

The app package contains only cross-feature HTTP/process concerns. It must not
become a home for feature rules.

## Authentication feature

- **`features/auth/domain/models.py`** — Immutable `AuthenticatedUser` and
  `IssuedSession` values.

- **`features/auth/application/ports.py`** — Signup/signin/guest command protocols and
  `AuthenticationPort`.

- **`features/auth/application/errors.py`** — Invalid-credential, conflict, and
  unavailable errors.

- **`features/auth/infrastructure/models.py`** — `User` and hashed `AuthSession`
  SQLAlchemy mappings.

- **`features/auth/infrastructure/service.py`** — Password hashing, session issuing,
  pruning, authentication, and signout.

- **`features/auth/presentation/schemas.py`** — Strict Pydantic request/response schemas
  and input normalization.

- **`features/auth/presentation/router.py`** — `/api/auth` endpoints and HTTP error
  mapping.

Package `__init__.py` files mark boundaries and export only intentional public
objects. Authentication is accessed through its feature package rather than
root-level compatibility facades.

## Other feature presentation and persistence files

- **`features/language_tools/presentation/schemas.py`** — Grammar, dictionary, and TTS
  inputs.

- **`features/language_tools/presentation/router.py`** — Router factory for grammar,
  dictionary, chat, TTS, and guide routes.

- **`features/learning_plan/presentation/router.py`** — Profile, generation, active
  plan, attempts, and adaptation routes.

- **`features/news/presentation/router.py`** — Injected news-list and safe-image-proxy
  routes.

- **`features/pronunciation/presentation/router.py`** — Multipart pronunciation and
  guided-speaking routes.

- **`features/roleplay/infrastructure/models.py`** — Roleplay scenario, session, and
  turn ORM tables.

- **`features/roleplay/presentation/router.py`** — Scenario creation, session start,
  history, and transcript REST routes.

- **`features/roleplay/presentation/runtime_router.py`** — Draft, translation,
  finalization, legacy escape, and WebSocket routes.

The short feature/package `__init__.py` files document ownership and export the
router factory or router used by `main.py`.

## Roleplay domain

- **`features/roleplay/domain/catalog.py`** — Reviewed built-in scenarios, objective
  evidence patterns, thresholds, and rubric definitions.

- **`features/roleplay/domain/engine.py`** — Deterministic scenario lookup, objective
  updates, transcript aggregation, and evaluation policy.

## `speakflow/runtime`

- **`models.py`** — Owns lazy global state and locks for WhisperX, GECToR, Kokoro, and
  pronunciation scorer.

- **`grammar_model.py`** — Constructs and loads the self-contained GECToR checkpoint
  without resolving an external base-model path.

- **`language.py`** — Groq client, chat reply, grammar feedback, dictionary lookup, and
  display sanitization.

- **`news.py`** — News retrieval, CEFR rewrite cache, batching, URL checks, and
  SSRF-safe image proxy.

- **`tts.py`** — Kokoro synthesis, content-addressed cache, request coalescing, and
  pronunciation guide.

- **`pronunciation_audio.py`** — Speech gate, transcript alignment, completeness, word
  matching, and upload reads.

- **`pronunciation_text.py`** — Transcript comparison, local/Groq coaching,
  placeholders, and feedback wording.

- **`pronunciation_endpoints.py`** — WAV decoding, resampling, guided transcription,
  strict score orchestration, and PLP attempt recording.

- **`chat_delivery.py`** — Target-free fluency/pitch estimates, chat transcription, and
  trusted grammar correction.

- **`roleplay_scenario.py`** — Provider prompts, validated scenario drafts, role
  replies, evidence, and repetition repair.

- **`roleplay_session.py`** — Authenticated WebSocket state machine and per-session turn
  locks.

- **`roleplay_turn.py`** — Atomic turn generation/persistence across workers.

- **`roleplay_evaluation.py`** — Arabic help, final evaluation, TTS delivery, HTTP
  mapping, and disconnect handling.

- **`roleplay_finalize.py`** — Explicit session-finalization endpoint use case.

### `speakflow/runtime/pronunciation`

- **`core.py`** — Canonical phones, G2P, IPA conversion, text normalization, and score
  aggregation.

- **`gop.py`** — Alignment-free CTC-GOP extraction from the local XLSR-53 model.

- **`features.py`** — Stable acoustic and phone-context feature construction and
  normalization.

- **`scoring.py`** — Converts CTC, GOPT, and Arabic-L1 evidence into the strict public
  scoring result.

- **`service.py`** — Loads compatible scoring assets and runs the production scorer.

`gopt_models/gopt.py` retains the stored PyTorch GOPT architecture used by the
runtime scorer and offline training code.

## Shared ORM

`speakflow/shared/orm.py` defines the single SQLAlchemy declarative `Base` and
UTC timestamp helper. Auth, PLP, and roleplay models share this metadata so
migrations and foreign keys describe one modular-monolith database.

## `plp` public surfaces and configuration

- **`__init__.py`** — Lightweight package marker; importing `plp` does not eagerly load
  FastAPI.

- **`config.py`** — Database, embedding, provider, model, lease, and curriculum
  configuration.

- **`standard.py`** — Stable learning-plan architecture, pipeline, and format revision.

- **`database.py`** — Lazy SQLAlchemy engine, transaction context manager, readiness
  check, and disposal.

- **`identity.py`** — Context-local authenticated user binding used by PLP queries.

- **`models.py`** — Learner, curriculum, plan, lesson, job, progress, attempt, evidence,
  and adaptation ORM models.

- **`schemas.py`** — Stable re-export facade for public PLP schemas.

- **`schema_core.py`** — Profiles, plans, activities, attempts, jobs, progress, and
  document contracts.

- **`schema_roleplay.py`** — Roleplay scenario, turn, translation, evaluation, and
  transcript contracts.

- **`service.py`** — Stable `PlpService` facade composed from focused mixins; exports
  `plp_service`.

- **`service_base.py`** — Shared imports, settings, lifecycle, and basic service state.

- **`service_errors.py`** — PLP error hierarchy and operational constants.

## PLP service implementation

- **`service_document.py`** — Profile access and construction of the mobile-safe
  active-plan document.

- **`service_generation.py`** — Generation requests, job queries/retry, and active-plan
  retrieval.

- **`service_generation_worker.py`** — Provider-backed lesson/week generation and atomic
  publication.

- **`service_worker.py`** — Job claiming, leases, stale-job recovery, retry windows, and
  terminal failure.

- **`service_attempts.py`** — Idempotent attempt submission, grading integration, XP,
  completion, and evidence writes.

- **`service_grading.py`** — Answer-key stripping, deterministic graders, pronunciation
  validation, and failure envelopes.

- **`service_progress.py`** — Streak/progress calculation, eligibility, verified
  completion, and adaptation views.

- **`service_identity.py`** — Profile mapping, local-user creation, learner snapshots,
  and safe DB error translation.

- **`service_roleplay.py`** — Learner-owned scenario/session/turn persistence and
  transcript queries.

## Curriculum and planning

- **`seed.py`** — The reviewed project-authored curriculum source, skills,
  prerequisites, and chunks.

- **`ingest.py`** — Validates and idempotently inserts reviewed seed records.

- **`external_curriculum.py`** — Stable retrieval/enrichment facade and lexical helpers.

- **`external_curriculum_ingest.py`** — CEFR-J/Words-CEFR source loading and database
  upsert CLI.

- **`retrieval.py`** — Exact and vector curriculum retrieval with source/provenance
  checks.

- **`planner.py`** — Builds the deterministic four-week outline from profile and
  curriculum.

- **`planner_models.py`** — Planner constants and immutable planning structures.

- **`planner_support.py`** — Domain priority, prerequisites, role assignment, review
  spacing, and titles.

- **`mission_catalog.py`** — Normalizes goals/interests and selects rotating weekly
  missions.

- **`mission_catalog_models.py`** — Typed goal, interest, archetype, lesson-role, and
  mission definitions.

- **`mission_archetypes.py`** — Reviewed scenario archetype catalog used by mission
  selection.

- **`curated_lessons.py`** — Reviewed fallback/anchor lesson templates.

- **`learner_glosses.py`** — Reviewed learner-friendly definition overrides.

- **`lesson_quality.py`** — Semantic quality rules for generated and curated activities.

## Generation and weekly compilation

- **`generation_support.py`** — Shared provider-response parsing, retry timing, token
  usage, and validation utilities.

- **`generator.py`** — Single-lesson writer strategy and strict lesson validation.

- **`weekly_mission.py`** — Stable public weekly-generation imports.

- **`weekly_mission_models.py`** — Strict weekly draft models, request records, prepared
  week, and JSON schema.

- **`weekly_mission_prepare.py`** — Deterministically prepares five lesson anchors and
  provider requests.

- **`weekly_mission_generator.py`** — Makes the constrained one-call weekly provider
  request.

- **`weekly_mission_validation.py`** — Parses output and enforces IDs, uniqueness,
  meaning, and answer consistency.

- **`weekly_mission_content.py`** — Combines reviewed anchors with approved surface
  realizations.

- **`weekly_mission_compile.py`** — Compiles validated weekly output into complete
  private lesson payloads.

- **`weekly_mission_payload.py`** — Adds provenance, usage metadata, and safe failure
  serialization.

The preparation/compiler split is essential: the model supplies constrained
surface wording, while deterministic code retains curriculum sequence, correct
answers, skills, and completion rules.

## Curriculum snapshots and audits

- **`curriculum_snapshot.py`** — Deterministic ZIP format, checksums, manifest
  validation, export, and read.

- **`curriculum_snapshot_store.py`** — Transactional database import/inspection CLI for
  a validated snapshot.

- **`audit_curriculum.py`** — Checks stored sources, concepts, embeddings, and
  curriculum integrity.

- **`audit_generation.py`** — Generates/audits a representative lesson for a
  level/domain.

- **`audit_weekly.py`** — Audits the weekly preparation/provider/compilation pipeline.

`backend/tools/audit_*.py` are thin operational entrypoints that call these
package-owned audit functions. `backend/tools/README.md` documents their use.
`backend/tools/model_bundle.py` inventories, verifies, reconstructs, downloads,
and uploads managed private model assets.

## Migrations

`migrations/env.py` loads runtime configuration and the shared ORM metadata.
`migrations/script.py.mako` is Alembic's revision template. Ordered revision
files own schema evolution:

- **`20260716_01`** — Initial PLP tables.

- **`20260721_02`** — External curriculum concepts.

- **`20260724_03`** — Durable roleplay sessions/turns.

- **`20260724_04`** — Integrity constraints.

- **`20260726_05`** — Concept embeddings/pgvector.

- **`20260726_06`** — Server-authoritative roleplay persistence.

- **`20260726_07`** — Multi-user authentication and ownership.

- **`20260801_08`** — Profile timezone, one active plan per user, and idempotent
  attempts.

- **`20260802_09`** — Standard learning-plan and roleplay contracts without redundant
  labels.
