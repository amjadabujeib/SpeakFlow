# Testing and quality

## Validation commands

Backend, from `backend/`:

```bash
PYTHONDONTWRITEBYTECODE=1 ../.venv/bin/python -m unittest discover -s tests
../.venv/bin/python -m alembic -c alembic.ini current
../.venv/bin/python -m alembic -c alembic.ini heads
```

Flutter, from `frontend/`:

```bash
dart format --output=none --set-exit-if-changed lib test
flutter analyze
flutter test
```

Repository whitespace:

```bash
git diff --check
```

Database integration tests require a migrated local PostgreSQL database. A
connection refusal is an unavailable dependency, not a passing test.

## Architecture tests

`backend/tests/test_architecture.py` protects:

- application layers from FastAPI/SQLAlchemy/provider dependencies;
- presentation adapters from importing `main.py`;
- one shared ORM metadata registry;
- the unversioned route set, absence of v1 aliases, and route ordering;
- body and rate-limit behavior;
- the 500-line Python source ceiling.

`frontend/test/architecture_dependencies_test.dart` protects key dependency
directions and construction seams. `source_size_policy_test.dart` protects the
500-line Dart limit.

## Backend test map

- **`test_multi_user_auth.py`** — registration, guest lifecycle, revocation, session
  cap, and user isolation; requires PostgreSQL.

- **`test_roleplay_persistence.py`** — atomic durable scenario/session/turn behavior;
  requires PostgreSQL.

- **`test_roleplay_engine.py`** — deterministic objectives, evidence, rubric, and
  provisional score rules.

- **`test_roleplay_api_authority.py`** — absence of client-authored summary authority.

- **`test_runtime_roleplay.py`** — provider drafts/replies, translations, recovery, and
  evidence filtering.

- **`test_runtime_language_audio.py`** — uploads, guided speech, coaching, grammar,
  delivery metrics, TTS coalescing.

- **`test_runtime_news_dictionary.py`** — news/provider failures, category paging,
  rewrite, dictionary pinning, coaching.

- **`test_runtime_pronunciation_scoring.py`** — endpoint gates, transcript alignment,
  lesson recording, and strict scorer use.

- **`test_pronunciation_service.py`** — G2P/canonicalization, batching, model
  compatibility, and score contract.

- **`test_ctc_gop.py`** — alignment-free feature extraction rules.

- **`test_pronunciation_features.py`** — finite, dimensionally stable context features.

- **`test_gector_runtime.py`** — self-contained grammar checkpoint loading.

- **`test_model_loading.py`** — offline/language-pinned local model behavior.

- **`test_model_bundle.py`** — path safety, split assets, checksums, and fixed
  repository.

- **`test_setup.py`** — bootstrap decision and command behavior.

- **`test_curriculum_graph.py`** — provenance, CEFR mapping, interests, identity, and
  prerequisites.

- **`test_curriculum_snapshot.py`** — deterministic archive, checksums, references, and
  round trip.

- **`test_plp_retrieval.py`** — local PostgreSQL/embedding retrieval integration when
  available.

PLP tests are split into focused modules:

- `test_plp_contract_content.py` — public/private content and profile rules;
- `test_plp_contract_attempts.py` — grading, idempotency, evidence, and lesson
  completion;
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

`*_test_support.py` modules provide shared fixtures and import surfaces to the
focused suites.

## Flutter test map

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
  provisional display.

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

Do not make code cryptic merely to reduce line count.

## Definition of done

A change is complete only when:

- behavior is implemented at the correct authority boundary;
- new/changed contracts have tests;
- static analysis and formatting pass;
- database changes have an Alembic revision;
- source files respect the size ceiling;
- README/handbook paths, commands, routes, and migration head remain current;
- no generated caches, weights, secrets, or raw datasets are added to Git.
