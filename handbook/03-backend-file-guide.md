# Backend file guide

This page maps the production backend. Test files are described in
[Testing and quality](10-testing-and-quality.md); training scripts are described
in [ML models and providers](09-ml-and-providers.md).

## Backend root

- **`main.py`** — Executable composition root; wires routers, lifespan, health, and
  runtime callables.

- **`tools/setup_backend.py`** — Cross-platform bootstrap: dependencies, database, migrations, models,
  curriculum, and verification.

- **`pyproject.toml`** — Python package metadata, package discovery, and declared
  top-level modules.

- **`requirements.txt`** — Reproducible runtime/test dependency list used by setup.

- **`requirements-dev.txt`** — Pinned Ruff version for the maintained backend lint
  boundary and CI.

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

- **`features/admin/presentation.py`** — Thin `/admin` HTTP routing and safe error
  translation.

- **`features/admin/schemas.py`** — Strict response models and the validated
  revocation-reason command.

- **`features/admin/cli.py`** — Local grant/remove workflow that revokes existing
  sessions and audits privilege changes.

- **`features/admin/infrastructure/models.py`** — Privileged-action audit mapping.

- **`features/admin/infrastructure/reporting.py`** — Operational aggregates, provider
  health, account search, audit history, and audited session revocation.

- **`features/admin/__init__.py`** — Marks the operations feature boundary.

- **`features/language_tools/contracts.py`** — Grammar, dictionary, and TTS
  inputs.

- **`features/language_tools/presentation/router.py`** — Router factory for grammar,
  dictionary, chat, TTS, and guide routes.

- **`features/learning_plan/presentation/router.py`** — Profile, generation, active
  plan, attempts, and adaptation routes.

- **`features/news/presentation/router.py`** — Injected news-list and safe-image-proxy
  routes.

- **`features/pronunciation/presentation/router.py`** — Multipart pronunciation and
  guided-speaking routes.

- **`features/pronunciation/domain/assessment.py`** — Versioned conservative
  pass/inconclusive/error policy based on completeness, transcript verification,
  assigned IPA focus, and positive CTC phone support.

- **`features/roleplay/infrastructure/models.py`** — Roleplay scenario, session, and
  turn ORM tables.

- **`features/roleplay/presentation/router.py`** — Scenario creation, session start,
  history, and transcript REST routes.

- **`features/roleplay/presentation/runtime_router.py`** — Draft, translation,
  finalization, legacy escape, and WebSocket routes.

The short feature/package `__init__.py` files document ownership and export the
router factory or router used by `main.py`.

The admin router reads auth, PLP, and roleplay mappings directly because it is
an operational reporting adapter. Middleware owns administrator authorization;
the admin feature owns only its contracts, audit persistence, and operations.

## Roleplay domain

- **`features/roleplay/domain/catalog.py`** — Reviewed built-in scenarios, objective
  evidence patterns, thresholds, and rubric definitions.

- **`features/roleplay/domain/engine.py`** — Deterministic scenario lookup, objective
  updates, transcript aggregation, and evaluation policy.

- **`features/roleplay/domain/evaluation.py`** — Trusted correction-summary policy
  shared by explicit and disconnect finalization.

## Runtime ownership

- **`speakflow/runtime/models.py`** — Owns eager startup warm-up, global state, readiness reports, and
  locks for WhisperX, GECToR, Kokoro, and the pronunciation scorer.

- **`features/language_tools/infrastructure/grammar_model.py`** — Constructs and loads the self-contained GECToR checkpoint
  without resolving an external base-model path.

- **`features/language_tools/infrastructure/language.py`** — Groq client, grammar feedback, dictionary lookup, and
  display sanitization.

- **`features/news/infrastructure/provider.py`** — News retrieval, CEFR rewrite cache, batching, URL checks, and
  SSRF-safe image proxy.

- **`features/language_tools/infrastructure/tts.py`** — Kokoro synthesis, content-addressed cache, request coalescing, and
  pronunciation guide.

- **`features/pronunciation/infrastructure/pronunciation_audio.py`** — WAV decoding/resampling, speech gate, transcript
  alignment, completeness, word matching, and upload reads.

- **`features/pronunciation/infrastructure/pronunciation_text.py`** — Transcript comparison, local/Groq coaching,
  placeholders, and feedback wording.

- **`features/pronunciation/infrastructure/pronunciation_endpoints.py`** — Validated multipart contracts, guided
  transcription, strict score orchestration, and PLP attempt recording.

- **`features/roleplay/application/chat_delivery.py`** — Target-free fluency/pitch estimates, chat transcription, and
  trusted grammar correction.

- **`features/roleplay/application/roleplay_scenario.py`** — Provider prompts, validated scenario drafts, role
  replies, evidence, and repetition repair.

- **`features/roleplay/presentation/websocket_session.py`** — Authenticated WebSocket state machine and per-session turn
  locks.

- **`features/roleplay/application/roleplay_socket_policy.py`** — One-session socket binding and safe public
  turn-error classification.

- **`features/roleplay/application/roleplay_turn.py`** — Atomic turn generation/persistence across workers.

- **`features/roleplay/presentation/evaluation.py`** — Arabic help, final evaluation, TTS delivery, HTTP
  mapping, and disconnect handling.

- **`features/roleplay/presentation/finalize.py`** — Explicit session-finalization endpoint.

### `speakflow/features/pronunciation/infrastructure/acoustic`

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

## Learning-plan engine surfaces and configuration

- **`features/learning_plan/application/services.py`** — Narrow production-facing
  learning-plan, lifecycle, and pronunciation-assignment services.

- **`config.py`** — Database, embedding, provider, model, lease, and curriculum
  configuration.

- **`standard.py`** — Stable learning-plan architecture, pipeline, and format revision.

- **`database.py`** — Lazy SQLAlchemy engine, transaction context manager, readiness
  check, and disposal.

- **`identity.py`** — Context-local authenticated user binding used by PLP queries.

- **`models.py`** — Learner, curriculum, plan, lesson, job, progress, attempt, evidence,
  and adaptation ORM models.

- **`schemas.py`** — Stable re-export facade for public PLP schemas.

- **`schema_core.py`** — Profiles, plans, activities, lesson content, and generation
  contracts.

- **`schema_progress.py`** — Progress, activity-attempt, pronunciation target-state,
  document, and adaptation contracts.

- **`schema_roleplay.py`** — Roleplay scenario, turn, translation, evaluation, and
  transcript contracts.

- **`service.py`** — Private `LearningPlanEngine` composition and shared engine instance.

- **`service_base.py`** — Shared lifecycle, stale-roleplay cleanup, catalog-aware
  readiness, and learner-profile behavior.

- **`service_errors.py`** — PLP error hierarchy and operational constants.

## Learning-plan engine implementation

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

- **`pronunciation_attempt_policy.py`** — Reduced phone-evidence persistence and the
  bounded inconclusive-retry, per-target first-conclusive-evidence, and normalized
  multi-target weighting policies.

- **`service_pronunciation.py`** — Server-side authorization of assigned PLP
  pronunciation targets before acoustic scoring.

- **`service_grading.py`** — Answer-key stripping, deterministic graders, pronunciation
  validation, and failure envelopes.

- **`service_progress.py`** — Streak/progress calculation, target-scoped pronunciation
  mastery scores, durable verified/unverified target state, eligibility, and
  adaptation views.

- **`service_identity.py`** — Profile mapping, local-user creation, learner snapshots,
  and safe DB error translation.

- **`features/roleplay/infrastructure/persistence.py`** — Roleplay session/turn
  persistence, finalization state, and transcript queries.

- **`features/roleplay/infrastructure/scenario_repository.py`** — User-owned custom
  scenario list, create, replacement edit, and delete lifecycle.

- **`features/roleplay/infrastructure/persistence_policy.py`** — Roleplay idempotency,
  objective-evidence agreement, and database-safe final metric bounds.

## Curriculum and planning

- **`seed.py`** — The reviewed project-authored curriculum source, skills,
  prerequisites, and chunks.

- **`ingest.py`** — Validates and idempotently inserts reviewed seed records.

- **`curriculum_readiness.py`** — Verifies that every supported level has enough
  active skills and reviewed chunk coverage without loading models or embeddings.

- **`external_curriculum.py`** — Source parsing and lexical enrichment. Only nouns,
  verbs, adjectives, and adverbs can be promoted with WordNet evidence; unsupported
  source parts of speech remain evaluation-only.

- **`external_curriculum_ingest.py`** — CEFR-J/Words-CEFR source loading and database
  upsert CLI.

- **`interest_vocabulary.py`** — Reviewed exact CEFR/headword/part-of-speech links
  between existing source vocabulary and learner interests, plus narrow removal
  of known broad-taxonomy false positives.

- **`lexical_definition_policy.py`** — Low-level, provider-independent checks for
  short, non-circular learner definitions anchored to their source meaning.

- **`lexical_policy.py`** — One runtime authority for supported lexical parts of
  speech, CEFR definition limits, reviewed gloss resolution, and teachability.

- **`lexical_retrieval.py`** — Vocabulary-specific filtering, semantic ranking,
  direct/related/general quotas, term deduplication, and prior-exposure priority.

- **`retrieval.py`** — Exact/vector curriculum retrieval facade and local embedding
  client. Direct interest evidence is a hard tier; related themes can fill a
  shortage, while an untagged general term needs a calibrated scenario match.

- **`planner.py`** — Builds the deterministic four-week outline from profile and
  curriculum.

- **`planner_models.py`** — Planner constants and immutable planning structures.

- **`planner_support.py`** — Domain priority, prerequisites, role assignment, review
  spacing, and titles.

- **`mission_catalog.py`** — Normalizes goals/interests and selects rotating weekly
  missions. Goal plus direct interest-context matches outrank scenarios that can
  only be themed with the interest; a stable digest breaks ties inside a relevance
  tier.

- **`mission_catalog_models.py`** — Typed goal, interest, archetype, lesson-role, and
  mission definitions.

- **`mission_archetypes.py`** — Stable combined archetype-catalog facade.

- **`mission_archetypes_core.py`** and **`mission_archetypes_extended.py`** — Reviewed
  scenario records split along a catalog boundary to satisfy the source-size policy.
  Their CEFR outcomes name an observable product and preserve required map, source,
  dataset, rule, or case evidence while support is progressively reduced. User-facing
  contracts prefer real subjects and distinguish sourced facts from simulated practice
  details; legacy IDs containing `fictional` remain stable for persisted plans.

- **`curated_lessons.py`** — Reviewed fallback/anchor lesson templates.

- **`learner_glosses.py`** — Reviewed WordNet sense selection and learner-friendly
  definition overrides for ambiguous or overly technical lexical-source entries.

- **`lesson_quality.py`** — Semantic quality rules for generated and curated activities.

## Generation and weekly compilation

- **`generation_support.py`** — Shared provider-response parsing, retry timing, token
  usage, and validation utilities.

- **`generator.py`** — Single-lesson writer strategy and strict lesson validation.

- **`weekly_mission.py`** — Stable public weekly-generation imports.

- **`weekly_mission_models.py`** — Strict weekly draft models, request records, prepared
  week, and JSON schema.

- **`weekly_mission_prepare.py`** — Deterministically prepares five lesson anchors,
  provider requests, and exactly two safe weekly vocabulary targets. A week without
  a vocabulary-domain lesson pre-teaches those targets in its first teaching lesson.

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

- **`audit_curriculum.py`** — Checks stored sources, catalog composition, embeddings,
  runtime lexical roles, reviewed interest assignments, direct interest coverage,
  teachable interest coverage, and curriculum integrity. The database/snapshot
  audit remains usable after
  the optional raw import files have been removed: it reports local-source
  comparison fields as unavailable rather than treating their absence as a
  runtime failure.

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

- **`20260808_10`** — Administrator capability and privileged-action audit records.

- **`20260809_11`** — Per-turn grammar-evaluation availability for trustworthy
  roleplay grammar scores.

- **`20260809_12`** — Persisted meaningful/unclear/off-topic roleplay-turn
  grounding status.
