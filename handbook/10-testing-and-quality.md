# Testing and quality

## Validation commands

Backend, from `backend/`:

```bash
../.venv/bin/python -m pip install -r requirements-dev.txt
../.venv/bin/python -m ruff check .
PYTHONDONTWRITEBYTECODE=1 ../.venv/bin/python -m unittest discover -s tests
../.venv/bin/python -m alembic -c alembic.ini current
../.venv/bin/python -m alembic -c alembic.ini heads
../.venv/bin/python -m alembic -c alembic.ini check
```

Flutter, from `frontend/`:

```bash
dart format --output=none --set-exit-if-changed lib test
flutter analyze
flutter test
```

Operations dashboard, from `admin-dashboard/`:

```bash
npm ci
npm run lint
npm test
npm run build
```

Repository whitespace:

```bash
git diff --check
```

Database integration tests require a migrated local PostgreSQL database. A
connection refusal is an unavailable dependency, not a passing test.

The tracked GitHub Actions workflow runs the same backend lint/tests/migration
drift check, Flutter format/analysis/tests, and dashboard lint/tests/build on
pull requests and pushes to `main`.

Ruff's enforced boundary covers the maintained composition, application,
feature, shared, migration, operational-tool, and test packages. Test support
facades have narrow unused-re-export exceptions; ordinary test modules use
explicit fixture imports, and an architecture test prevents wildcard fixtures
from returning.

## Architecture tests

`backend/tests/app/test_architecture.py` protects:

- application layers from FastAPI/SQLAlchemy/provider dependencies;
- presentation adapters from importing `main.py`;
- one shared ORM metadata registry;
- absence of the retired top-level `plp` and catch-all runtime adapter modules;
- explicit test-fixture imports;
- the unversioned route set, absence of v1 aliases, and route ordering;
- body and rate-limit behavior;
- the 500-line Python source ceiling.

`frontend/test/architecture/architecture_dependencies_test.dart` protects key
dependency directions, provider-owned runtime state, construction seams, and
the production/test asset boundary. `source_size_policy_test.dart` protects the
500-line Dart limit.

Backend architecture tests protect anonymous/ordinary/admin route behavior and
admin rate-limit selection. `test_admin_security.py` covers persisted claims,
short administrator sessions, searchable account pagination, readable audit
history, session invalidation, audited revocation, CLI privilege changes, and
sanitized failure responses. The dashboard's Node tests protect auth headers,
non-admin rejection, directory/audit query parameters, revocation payloads, and
safe failure handling.

## Backend test map

- **`test_multi_user_auth.py`** — registration, guest lifecycle, revocation, session
  cap, and user isolation; requires PostgreSQL.

- **`test_admin_security.py`** — administrator claim, authorization, privilege CLI,
  directory/audit reads, short admin sessions, audited revocation, session
  invalidation, and safe errors; requires PostgreSQL.

- **`test_mission_archetypes.py`** — direct-context relevance, extended-scenario
  evidence contracts, real-world source and simulation boundaries, and distinct
  event operations.

- **`test_roleplay_persistence.py`** — atomic durable scenario/session/turn behavior;
  requires PostgreSQL.

- **`test_roleplay_engine.py`** — deterministic objectives, evidence, rubric, and
  independent evidence-availability and metric-boundary rules.

- **`test_roleplay_api_authority.py`** — absence of client-authored summary authority.

- **`test_runtime_roleplay.py`** — provider drafts/replies, translations, recovery, and
  evidence filtering.

- **`test_roleplay_scenario_draft.py`** — CEFR-aware custom-scenario drafts and the
  reviewable offline fallback.

- **`test_custom_roleplay_lifecycle.py`** — database-backed create, play, evidence,
  completion, edit, immutable history, and delete behavior.

- **`test_runtime_language_audio.py`** — uploads, guided speech, coaching, grammar,
  delivery metrics, TTS coalescing.

- **`test_runtime_news_dictionary.py`** — news/provider failures, category paging,
  rewrite, dictionary pinning, coaching.

- **`test_runtime_pronunciation_scoring.py`** — endpoint gates, transcript alignment,
  lesson recording, and strict scorer use.

- **`test_pronunciation_audio_quality.py`** — silence, clipping, non-finite input,
  stationary tones, VAD rejection, and scorer failure propagation.

- **`test_pronunciation_assessment.py`** — conservative pass/inconclusive/fail
  policy, raw-versus-display phone states, IPA focus, uncertainty, and
  completeness boundaries.

- **`test_pronunciation_service.py`** — G2P/canonicalization, batching, model
  compatibility, and score contract.

- **`test_ctc_gop.py`** — alignment-free feature extraction rules.

- **`test_pronunciation_features.py`** — finite, dimensionally stable context features.

- **`test_gector_runtime.py`** — self-contained grammar checkpoint loading.

- **`test_model_loading.py`** — offline/language-pinned local model behavior.

- **`test_model_bundle.py`** — path safety, split assets, checksums, and fixed
  repository.

- **`tooling/test_setup.py`** — bootstrap decision and command behavior.

- **`test_curriculum_graph.py`** — provenance, CEFR mapping, interests, identity,
  prerequisites, and unsupported-part-of-speech enrichment rejection.

- **`test_interest_vocabulary.py`** — exact reviewed interest links, broad-taxonomy
  exclusions, direct-before-related retrieval, safe general-context admission,
  repeat deprioritization, runtime part-of-speech filtering, and managed-snapshot
  coverage of every CEFR/interest cell when that runtime asset is installed.

- **`test_curriculum_snapshot.py`** — deterministic archive, checksums, references, and
  round trip.

- **`test_plp_retrieval.py`** — local PostgreSQL/embedding retrieval integration when
  available.

PLP tests are split into focused modules:

- `weekly_missions/test_weekly_vocabulary_policy.py` — verifies that weeks without
  a dedicated vocabulary domain still compile exactly two sourced vocabulary
  cards into the first teaching lesson;

- `test_plp_contract_content.py` — public/private content and profile rules;
- `test_plp_contract_attempts.py` — grading, idempotency, evidence, and lesson
  completion;
- `test_plp_activity_grading.py` — normalized answer grading, invalid choice
  rejection, score denominators, and checkpoint evidence scope;
- `test_plp_contract_generation.py` — generation audit, reset, XP, and initial
  progress;
- `test_plp_planner.py` — schedule, prerequisites, review spacing, and mission
  rotation;
- `test_plp_generator.py` — strict provider schema, repair, quality, and limits;
- `test_plp_worker.py` — job leasing, reclaim, resume, and eligible generation;
- `test_plp_document_grounding.py`, `test_weekly_mission_retrieval.py`, and
  `test_weekly_mission_worker.py` — document grounding and weekly worker rules;
- `test_weekly_mission_compilation.py` and
  `test_weekly_mission_validation.py` — preparation, schema, uniqueness,
  semantic checks, compilation, and failure envelopes.

The `learning_plan/support/*_test_support.py` modules and
`runtime/runtime_test_support.py` provide shared fixtures and import surfaces
to the focused suites.

## Suite structure and ownership

Backend tests are grouped into `admin/`, `app/`, `auth/`, `curriculum/`,
`learning_plan/`, `models/`, `pronunciation/`, `roleplay/`, `runtime/`, and
`tooling/`. Each directory is an importable Python package, so standard
`unittest` discovery traverses the complete hierarchy. Support modules contain
reusable fixtures and are not collected as tests.

The larger `learning_plan/` package is divided into `contracts/`, `generation/`,
`weekly_missions/`, and `support/`, reflecting its current test responsibilities.

The verified baseline on 2026-08-11 is 349 backend tests, 76 Flutter tests, and
7 dashboard tests (432 total). Backend test function names are unique. This, the feature
map above, and the CI gates make the suite purposeful rather than a set of
unowned examples.

Backend suites use explicit support imports, and the architecture policy keeps
production and test source files at or below the 500-line ceiling. These checks keep
fixture ownership visible and prevent large catch-all modules from returning.

## Flutter test map

Flutter tests mirror production ownership under `app/`, `architecture/`,
`core/`, and `features/{chat,learning_plan,news,practice}/`. The learning-plan
test parts remain beside their owning `learning_plan_screen_test.dart` library.

- **`architecture_dependencies_test.dart`** — API adapter injection and dependency
  direction.

- **`source_size_policy_test.dart`** — Dart source ceiling.

- **`learning_plan_screen_test.dart` and parts** — onboarding, generation, active plan,
  retry, reset, and lesson flows.

- **`plp_models_test.dart`** — strict domain JSON parsing and repository contracts.

- **`settings_regeneration_test.dart`** — profile save, changed interests, and new
  generation.

- **`phoneme_progress_store_test.dart`** — measured-only progress, persistence, and
  shell lifecycle.

- **`news_category_test.dart`** — category selection and refresh request correctness.

- **`dictionary_screen_test.dart`** — result fields and one-word validation.

- **`roleplay_history_screen_test.dart`** — read-only stored conversation UI.

- **`roleplay_session_summary_screen_test.dart`** — evidence-aware useful feedback and
  rubric/correction display with unavailable scores omitted.

## Test types

- Unit tests exercise deterministic functions and model parsing.
- Contract tests protect public payload and authority boundaries.
- Characterization tests preserve behavior while large files are split.
- Widget tests exercise visible Flutter state with fake adapters.
- Integration tests exercise actual PostgreSQL/pgvector and migrations.
- Architecture tests prevent structural regression.

## File-size policy

Hand-written `.py` and `.dart` files must be no longer than 500 lines. Prefer
100–300 lines. Split by responsibility, not arbitrary line ranges:

- extract data/domain models;
- extract a controller or service mixin;
- extract tightly related private widgets into a Dart `part`;
- extract provider/persistence adapters;
- retain a small stable facade when external imports need continuity.

Do not make code cryptic merely to reduce line count. The scenario archetype
catalog demonstrates the intended approach: a tiny public facade combines
focused core and extended catalog modules.

## Definition of done

A change is complete only when:

- behavior is implemented at the correct authority boundary;
- new/changed contracts have tests;
- static analysis and formatting pass;
- the dashboard tests, lints, and bundles when its source or `/admin` contract changes;
- database changes have an Alembic revision;
- source files respect the size ceiling;
- README/handbook paths, commands, routes, and migration head remain current;
- no generated caches, weights, secrets, or raw datasets are added to Git.
