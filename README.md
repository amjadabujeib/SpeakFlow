# SpeakFlow

Flutter English-learning client with a FastAPI backend. Registered accounts
and disposable guests have separate plans, progress, practice data, roleplay
history, and custom scenarios. The app combines roleplay chat, strict scripted
pronunciation assessment, target-free spoken delivery feedback, grammar
support, news, and a durable four-week personalized learning plan (PLP).

## Run locally

1. Copy `.env.example` to `.env` and configure the constrained PLP writer.
2. Ensure the local PostgreSQL and pronunciation model assets described below are installed.
3. Start the complete Android development stack:

```bash
./start_dev.sh
```

The launcher starts the user-owned PostgreSQL cluster, configures ADB reverse
port forwarding, starts FastAPI with the local WhisperX environment, and runs
Flutter. Heavy speech, grammar, and TTS models load lazily.

Useful checks:

```bash
cd backend
/home/amjad/whisperx-env/bin/alembic -c alembic.ini current
PYTHONPATH=. /home/amjad/whisperx-env/bin/python -m unittest \
  test_ctc_gop test_pronunciation_features test_pronunciation_service \
  test_pronunciation_endpoint test_plp test_weekly_mission \
  test_plp_v3_service test_curriculum_graph test_roleplay_engine \
  test_roleplay_persistence test_multi_user_auth

cd ..
flutter test
flutter analyze
```

## Speech scoring boundary

- Scripted words/sentences use audio gates, local WhisperX validation, local
  G2P, XLSR-53 alignment-free 41D CTC-GOP, calibrated Arabic-L1 phone
  models, GOPT, and deterministic aggregation. CTC is the only pronunciation
  engine; invalid or incompatible evidence returns an error.
- Free roleplay speech has no known target. It therefore reports nullable
  WhisperX recognition confidence and separately labelled timing/pause
  fluency and pitch-variation estimates. It does not claim phone accuracy or
  completeness.
- The Arabic-L1 phone models were evaluated on four L2-ARCTIC speakers. Orange
  feedback means uncertainty; only conservative red phones are diagnoses.
  Likely substitutions are reported only after the separate CTC
  counterfactual-confidence gate passes.

## Personalized learning plan

Onboarding stores CEFR level, native language, one learning goal, and up to
three interests. PostgreSQL is the source of truth. A deterministic planner and
reviewed curriculum own sequence, prerequisites, activities, grading, and
answers. A constrained Groq call using `openai/gpt-oss-120b` supplies weekly
scenario wording; the local compiler validates and atomically publishes all
five lessons in a week.
Answers remain server-side until an attempt is graded, and completion/XP are
server-authoritative. Groq supplies roleplay responses, trusted-correction
explanations, news rewriting, pronunciation drill wording, and the constrained
weekly PLP surface language. Rate-limited PLP jobs wait for Groq's reported
token-window reset and resume automatically. Credentials and provider settings
remain in the ignored `.env`.

Runtime data is stored outside Git under
`/home/amjad/english_learning_app_data`. The local database helper is
`scripts/plp_postgres.sh`.

## Accounts and data ownership

Email/password registration uses scrypt password hashes. Login returns an
opaque random bearer token; only its SHA-256 hash is stored in PostgreSQL.
Registered sessions last 30 days and can be revoked independently. Guest
sessions last seven days, receive their own user UUID, and are deleted with
their learning data when the guest signs out. Expired abandoned guests are
pruned when a new guest is created.

All learner-owned backend reads and writes are scoped to the authenticated
`users.id`, including indirect generation-job and adaptation IDs. Roleplay
session IDs are unique per user rather than globally. The WebSocket uses the
same bearer identity as REST. Device-local practice words and phoneme progress
are stored in user-namespaced files. Resetting learning data preserves a
registered account and its login; signing out does not erase registered data.

## Roleplay sessions

The backend owns the scenario catalog, frozen scenario snapshot, objective
state, ordered turns, completion status, and final evaluation. The client binds
the WebSocket to a REST-created session and every turn has an idempotent ID.
Groq receives the scenario contract plus recent conversation history and
returns a short in-role reply and exact-text objective evidence. Unsupported
evidence is rejected before it can affect progress.

The learner's stored CEFR level is supplied to turn generation and final
interaction, vocabulary, and scenario-rubric evaluation. Custom-scenario
creation uses the same level to generate an editable draft containing roles,
an opening, observable goals, useful sentence starters, and situation-specific
evaluation criteria. The learner reviews and can edit these fields and weights
for conversation goals before the versioned scenario is persisted.

Final feedback reports task achievement, each scenario-specific criterion,
interaction, grammar, vocabulary, free-speech fluency, and
pitch variation, and recognition-confidence clarity as independent scores.
Pitch variation is a descriptive vocal-range proxy, not a reference-based
prosody or intonation diagnosis. The roleplay system does not combine
unlike learning dimensions into an overall number. Spoken categories appear
only when spoken evidence exists, and the summary labels category scores as
provisional until the evidence minimum is met. Recognition uncertainty is
presented as a word to verify in scripted pronunciation practice, not as a
diagnosed pronunciation error. Zero-turn sessions are abandoned; completed or
interrupted sessions retain their turn evidence in PostgreSQL. Starting over
deletes learner-owned PLP and roleplay data through database cascades while
preserving reviewed curriculum. The current migration head is `20260726_07`.
