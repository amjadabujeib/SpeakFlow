# SpeakFlow

English-learning platform with a Flutter Android client, a FastAPI backend,
and a React operations dashboard. Registered accounts
and disposable guests have separate plans, progress, practice data, roleplay
history, and custom scenarios. The app combines roleplay chat, strict scripted
pronunciation assessment, target-free spoken delivery feedback, grammar
support, news, and a durable four-week personalized learning plan (PLP).

## Repository layout

```text
frontend/          Flutter client, Android project, assets, and widget tests
backend/           FastAPI application, migrations, ML services, and tests
admin-dashboard/   React/Vite operations dashboard
handbook/          Architecture, file maps, runtime flows, and maintenance guides
```

The runtime follows a feature-oriented Clean Architecture modular monolith.
Backend feature boundaries and application ports live under
`backend/speakflow/`; Flutter transport adapters live with their features and
are wired through Riverpod in `frontend/lib/app/providers.dart`. The dashboard
polls a separate `/admin` backend surface for system-wide operational data. See
the [backend architecture](handbook/02-backend-architecture.md) and
[Flutter architecture](handbook/04-flutter-architecture.md) guides for the
dependency rules and rationale.

For a ground-up explanation of the system, including file-by-file maps,
request flows, database ownership, ML boundaries, tests, and safe extension
guides, start with the [project handbook](handbook/README.md).

The backend and Flutter application share release `1.0.0`. Learning-plan JSON
uses one compatibility marker, `format_revision: 1`, and one stable
architecture name, `weekly_mission`. Internal prompt, planner, generator, and
compiler counters are intentionally not exposed or persisted. Database
revisions and verified ML asset formats remain independent because they protect
different compatibility boundaries.

Downloaded model weights are runtime assets rather than source files. They stay
under ignored backend directories, while the small configuration and vocabulary
resources needed by the application remain tracked.

## Installation requirements

The supported development environments are Ubuntu 24.04 and Windows 11 with
WSL2 Ubuntu 24.04. The backend is pinned to Python 3.12. The Android client
requires Flutter 3.35 or newer, an Android SDK, JDK 21, and ADB. Running the
optional operations dashboard requires Node.js `^20.19.0` or `>=22.12.0` and
npm.

Allow at least 15 GiB of free space for the Python environment, Docker data,
Ollama, and the approximately 2.8 GiB private model bundle. Android Studio and
its SDK need additional space. A machine with 16 GiB of RAM is recommended.
An NVIDIA GPU is optional; add `FORCE_CPU=1` to `.env` to force CPU inference.

Before setup, obtain:

- access to the private `speakflow/randomModels` Hugging Face repository and a
  Hugging Face read token;
- one or more Groq API keys authorized for this application;
- an optional `NEWSAPI_KEY` if live news categories are required;
- access to this private source repository.

The bootstrap command installs Python dependencies, authenticates with Hugging
Face when necessary, downloads and verifies the model bundle, starts
PostgreSQL 16 with pgvector, pulls Ollama's `embeddinggemma` model, applies
database migrations, ingests the 28 reviewed teaching objects, and restores
the versioned 8,223-concept RAG curriculum snapshot with its 7,227 embeddings.

### Private model access and automatic download

The model bundle is stored in the private
[`speakflow/randomModels`](https://huggingface.co/speakflow/randomModels)
Hugging Face repository. Before running setup:

1. sign in with a Hugging Face account that has read access to
   `speakflow/randomModels`; organization administrators can provide this
   access by adding the account to the `speakflow` organization;
2. create a personal
   [Hugging Face access token](https://huggingface.co/settings/tokens) with the
   **Read** role. Write access is not required;
3. run `.venv/bin/python backend/tools/setup_backend.py` as shown below and paste the token
   when prompted.

The token must not be shared, committed, or added to `.env`. Hugging Face saves
the login in the current Linux user's local cache, so authentication is normally
required only once per machine or WSL distribution. A Windows Hugging Face
login does not authenticate the separate Ubuntu environment inside WSL.

No model files need to be selected or downloaded manually. Setup downloads the
approximately 2.8 GiB bundle from the fixed repository, reconstructs chunked
large files, verifies every file's size and SHA-256 digest, and installs each
asset into its expected backend path. If setup is interrupted, run the same
command again; already verified files are retained.

### Linux installation (Ubuntu 24.04)

#### 1. Install Linux packages

```bash
sudo apt update
sudo apt install -y \
  build-essential ca-certificates curl ffmpeg git libsndfile1 \
  python3.12 python3.12-dev python3.12-venv
```

Install [Docker Engine with the Compose
plugin](https://docs.docker.com/engine/install/ubuntu/). Then allow the current
user to run Docker and verify both commands:

```bash
sudo usermod -aG docker "$USER"
newgrp docker
docker --version
docker compose version
```

Install [Ollama for Linux](https://ollama.com/download/linux), start its
service, and verify that it responds:

```bash
curl -fsSL https://ollama.com/install.sh | sh
sudo systemctl enable --now ollama
curl http://127.0.0.1:11434/api/tags
```

If the machine does not use systemd, run `ollama serve` in a separate terminal
instead.

#### 2. Install Flutter and Android tooling

Follow Flutter's [Android setup
guide](https://docs.flutter.dev/platform-integration/android/setup) to install
Flutter 3.35 or newer, Android Studio, the Android SDK, and the required SDK
command-line tools. Use Android Studio's bundled JDK 21 or configure another
JDK 21 installation.

Accept the Android licenses and resolve every required item reported by
Flutter:

```bash
flutter doctor
flutter doctor --android-licenses
```

For a physical Android phone, enable Developer options and USB debugging,
connect the phone, accept its authorization prompt, and confirm that ADB sees
it:

```bash
adb devices
```

An Android emulator can be used instead.

#### 3. Clone and configure SpeakFlow

```bash
git clone https://github.com/amjadabujeib/SpeakFlow.git SpeakFlow
cd SpeakFlow
cp .env.example .env
nano .env
```

At minimum, set a Groq key in the root `.env`:

```dotenv
GROQ_API_KEYS=gsk_your_key
NEWSAPI_KEY=
```

Do not commit `.env`. It is ignored by Git and loaded automatically by the
backend, migrations, and curriculum tools.

For an explicitly approved development key pool, add credentials to the same
variable in the order they should be selected:

```dotenv
GROQ_API_KEYS=gsk_primary,gsk_approved_secondary
```

`GROQ_API_KEYS` accepts any positive number of comma-separated keys, removes
duplicates, and preserves their order. Interactive Groq features use the first
key. PLP generation distributes requests round-robin; when one key returns HTTP
429, that key follows its provider `retry-after` cooldown and the same request
tries the next available key. The PLP job enters its durable cooldown only when
no configured key can currently accept the request. Never commit, print, or
share the resulting `.env`. Return production to one account-owned key in
`GROQ_API_KEYS` when the temporary approved pool is no longer needed.

#### 4. Create the backend environment

```bash
python3.12 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python backend/tools/setup_backend.py
```

At the Hugging Face prompt, use the personal read token described in
[Private model access and automatic download](#private-model-access-and-automatic-download).
The model repository is fixed in code; no model-repository environment
variable is needed.

#### 5. Start and verify the backend

```bash
.venv/bin/python backend/main.py
```

Keep that terminal open. In another terminal:

```bash
curl http://127.0.0.1:8000/health
docker compose ps
```

The health response should contain `"status":"ok"`, and the `postgres` service
should be healthy. The backend prints progress while eagerly loading its local
speech, grammar, TTS, and pronunciation models; health becomes ready after the
warm-up succeeds.

#### 6. Start the Android client

```bash
adb reverse tcp:8000 tcp:8000
cd frontend
flutter pub get
flutter run
```

`adb reverse` lets the Android app reach the backend through
`http://localhost:8000`. Run it again whenever the device reconnects or
restarts.

#### 7. Start the operations dashboard (optional)

First register the account that will administer the system, then grant it
administrator access from the backend environment:

```bash
cd backend
../.venv/bin/python -m speakflow.features.admin.cli grant admin@example.com
cd ..
```

Granting or removing administrator access revokes that account's existing
sessions, so sign in again through the dashboard. With the backend still
running:

```bash
cd admin-dashboard
npm ci
npm run dev
```

Open the URL printed by Vite, normally `http://localhost:5173`. The development
server proxies relative `/admin` requests to `http://127.0.0.1:8000`.
The dashboard signs in through `/api/auth/signin`; every `/admin` request then
requires that bearer session to belong to a registered user whose persisted
`is_admin` flag is true. Session revocations require a reason and create an
`admin_audit_events` record. See the
[operations dashboard guide](handbook/14-admin-dashboard.md).

### Windows installation with WSL2

Use Windows for Flutter, Android Studio, the emulator or USB phone, and ADB.
Use Ubuntu inside WSL2 for Python, Docker commands, Ollama, PostgreSQL, and the
FastAPI backend. This avoids maintaining a second Windows Python/ML
environment.

#### 1. Install WSL2 and Ubuntu

Open PowerShell as Administrator:

```powershell
wsl --install -d Ubuntu-24.04
wsl --update
```

Restart Windows if requested, launch Ubuntu, and create the Linux username and
password. Confirm that the distribution uses WSL2:

```powershell
wsl --list --verbose
```

If Ubuntu shows version 1, convert it:

```powershell
wsl --set-version Ubuntu-24.04 2
```

See Microsoft's [WSL installation
guide](https://learn.microsoft.com/windows/wsl/install) if the distribution
name differs or WSL is already installed.

#### 2. Install Windows-side tools

Install:

- Git for Windows;
- Flutter 3.35 or newer;
- Android Studio with the Android SDK, SDK command-line tools, and bundled
  JDK 21.

Open an ordinary Windows PowerShell terminal and verify the Android toolchain:

```powershell
flutter doctor
flutter doctor --android-licenses
adb devices
```

For a physical phone, enable Developer options and USB debugging and accept the
authorization prompt. Alternatively, start an Android emulator from Android
Studio.

#### 3. Clone once on the Windows filesystem

Keeping one checkout under `C:\dev` lets native Windows Flutter and WSL share
the same files:

```powershell
New-Item -ItemType Directory -Force C:\dev
git clone https://github.com/amjadabujeib/SpeakFlow.git C:\dev\SpeakFlow
cd C:\dev\SpeakFlow
```

Do not create a Windows Python virtual environment. The backend environment
will be Linux-based inside WSL.

#### 4. Install WSL backend prerequisites

Open Ubuntu and enter the repository checkout:

```bash
cd /mnt/c/dev/SpeakFlow
sudo apt update
sudo apt install -y \
  build-essential ca-certificates curl ffmpeg git libsndfile1 \
  python3.12 python3.12-dev python3.12-venv
```

Docker Desktop is not required. Install [Docker Engine and the Docker Compose
plugin](https://docs.docker.com/engine/install/ubuntu/) directly inside the
Ubuntu distribution. Enable the service, give the current Linux user access,
and verify the installation:

```bash
sudo systemctl enable --now docker
sudo usermod -aG docker "$USER"
newgrp docker
docker --version
docker compose version
docker run --rm hello-world
```

Current Ubuntu installations created by `wsl --install` use `systemd` by
default. If `systemctl` reports that the system was not booted with systemd,
create or edit `/etc/wsl.conf`:

```ini
[boot]
systemd=true
```

Then close Ubuntu, restart WSL from PowerShell, and reopen Ubuntu:

```powershell
wsl --shutdown
```

Do not install Docker Engine inside this Ubuntu distribution and also enable
Docker Desktop integration for it. Choose one Docker provider to avoid daemon,
socket, and CLI conflicts. Docker Desktop remains an optional alternative. If
Docker Desktop is used, do not install Docker Engine inside Ubuntu; follow
Docker's [WSL integration guide](https://docs.docker.com/desktop/features/wsl/)
instead.

Install Ollama inside WSL so the backend can consistently reach it at
`127.0.0.1:11434`:

```bash
curl -fsSL https://ollama.com/install.sh | sh
sudo systemctl enable --now ollama
curl http://127.0.0.1:11434/api/tags
```

If `systemctl` is unavailable, update WSL and restart it with `wsl --shutdown`
from PowerShell. As a temporary alternative, run `ollama serve` in a separate
Ubuntu terminal.

#### 5. Configure and bootstrap the backend in WSL

Still inside `/mnt/c/dev/SpeakFlow`:

```bash
cp .env.example .env
nano .env
```

Set at least:

```dotenv
GROQ_API_KEYS=gsk_your_key
NEWSAPI_KEY=
```

Then create the Linux virtual environment and run setup:

```bash
python3.12 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python backend/tools/setup_backend.py
```

At the Hugging Face prompt, use the personal read token described in
[Private model access and automatic download](#private-model-access-and-automatic-download).

#### 6. Start the backend in WSL

```bash
cd /mnt/c/dev/SpeakFlow
.venv/bin/python backend/main.py
```

Keep Ubuntu open. Verify WSL networking from a separate Windows PowerShell
terminal:

```powershell
curl.exe http://localhost:8000/health
```

Current WSL2 versions forward Windows `localhost` to services bound inside WSL.
If this check fails, run `wsl --update`, then `wsl --shutdown`, reopen Ubuntu,
and restart the backend.

#### 7. Start Flutter from Windows

In Windows PowerShell:

```powershell
cd C:\dev\SpeakFlow\frontend
flutter pub get
adb devices
adb reverse tcp:8000 tcp:8000
flutter run
```

Flutter and ADB run on Windows; only the backend commands run in Ubuntu. The
Android app still uses `localhost:8000`, so the PowerShell health check and ADB
reverse must both succeed.

### Daily startup

After the one-time installation:

1. on Windows, open Ubuntu in WSL so its systemd-managed Docker Engine and
   Ollama services start; on native Linux, ensure those services are running;
2. from the repository root, run `docker compose up -d postgres`;
3. apply any migrations with
   `cd backend && ../.venv/bin/python -m alembic -c alembic.ini upgrade head`;
4. ensure Ollama is running;
5. start the backend with `.venv/bin/python backend/main.py` from the repository
   root;
6. run `adb reverse tcp:8000 tcp:8000`;
7. run `flutter run` from `frontend/`.

When operational visibility is needed, also run `npm run dev` from
`admin-dashboard/`. It refreshes the selected dashboard tab every ten seconds.

The PostgreSQL container uses a named Docker volume, so normal container
restarts do not erase learner data.

Backend startup eagerly initializes WhisperX/alignment, GECToR, Kokoro, and the
complete XLSR/GOPT pronunciation scorer before Uvicorn reports the application
ready. Wait for the `All local runtime models are ready` message; subsequent
speech, grammar, TTS, and Practice requests reuse those instances. For a
deliberately lightweight diagnostic process only, set
`SPEAKFLOW_MODEL_LOADING=lazy`.

### Verification and common failures

Run backend checks from the repository root:

```bash
cd backend
../.venv/bin/python -m pip install -r requirements-dev.txt
../.venv/bin/python -m ruff check .
../.venv/bin/python -m alembic -c alembic.ini current
../.venv/bin/python -m alembic -c alembic.ini heads
PYTHONPATH=. ../.venv/bin/python -m unittest discover -s tests -p 'test_*.py'
```

Run frontend checks:

```bash
cd frontend
flutter test
flutter analyze
```

Run dashboard checks:

```bash
cd admin-dashboard
npm ci
npm run lint
npm test
npm run build
```

Common setup failures:

- **Hugging Face returns 401 or 403:** confirm organization access, then run
  `.venv/bin/hf auth login` and rerun setup.
- **`docker` is unavailable in WSL:** confirm Docker Engine was installed
  inside Ubuntu, then run `sudo systemctl enable --now docker`. If the service
  cannot use systemd, enable systemd in `/etc/wsl.conf`, run `wsl --shutdown`
  from PowerShell, and reopen Ubuntu.
- **Port 5432 is already occupied:** stop the other PostgreSQL service, or
  change both `POSTGRES_PORT` and the port in `DATABASE_URL` inside `.env`.
- **Ollama cannot be reached:** start `ollama serve` and verify
  `http://127.0.0.1:11434/api/tags`.
- **ADB reports no devices:** unlock the phone, accept USB debugging, check the
  cable, or start the Android emulator.
- **The app cannot reach the backend:** verify `/health`, then rerun
  `adb reverse tcp:8000 tcp:8000`.
- **`/health` returns HTTP 503 with `degraded`:** verify PostgreSQL and the PLP
  worker, then restore the reviewed catalog with `python -m speakflow.features.learning_plan.engine.ingest` and
  import the verified curriculum snapshot. The probe checks catalog readiness
  without loading embedding or generation models.
- **The learning-plan screen says PostgreSQL is unavailable while `/health`
  says `ok`:** compare `alembic current` with `alembic heads`, run
  `alembic upgrade head`, and retry. Health cannot prove that every expected
  schema revision has been applied.
- **Groq features fail:** ensure `GROQ_API_KEYS` contains at least one key in the
  root `.env` without quotes or extra spaces, then restart the backend. In a
  pool, invalid credentials are not treated as rate limits: fix or remove the
  invalid key instead of expecting rotation to hide it.

## Private model bundle

The bundle contains only assets used by the current application:

```text
backend/pretrained_models/wav2vec2_xlsr53_cmu39_ctc/
backend/pretrained_models/gopt_ctc/
backend/pretrained_models/arabic_pronunciation_ctc_v3/
backend/.models/gector/gector-roberta-base-5k/
backend/.models/runtime/whisperx-small-en/
backend/.models/runtime/whisperx-align/
backend/.models/runtime/kokoro/
backend/.models/nltk_data/
backend/.models/curriculum/rag-curriculum-v1.zip
```

It is approximately 2.8 GiB. Every downloaded file is checked against the
bundle's size and SHA-256 manifest before it is promoted into the runtime path.
The bundled GECToR safetensors file contains both the RoBERTa encoder and its
grammar-correction heads. SpeakFlow constructs the architecture locally, so a
separate `roberta-base` checkout or Hugging Face runtime download is not
required.

To publish or update the model bundle, a repository maintainer with write
access runs:

```bash
hf auth login
PYTHONPATH=backend .venv/bin/python -m speakflow.features.learning_plan.engine.curriculum_snapshot export
PYTHONPATH=backend .venv/bin/python -m tools.model_bundle inventory
PYTHONPATH=backend .venv/bin/python -m tools.model_bundle upload
```

Runtime authentication and download are covered in
[Private model access and automatic download](#private-model-access-and-automatic-download).
Setup restores the RAG snapshot transactionally and idempotently, so rerunning
it neither duplicates words nor recomputes their embeddings. Local training
source and raw datasets are intentionally not part of the application
repository.

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
  feedback means uncertainty and may receive non-diagnostic practice guidance;
  only conservative red phones or independent transcript-plus-phone
  contradictions are corrections.
  Likely substitutions are reported only after the separate CTC
  counterfactual-confidence gate passes.
- Acoustic quality numbers are diagnostic estimates, not calibrated pass/fail
  probabilities. Free Practice accepts a complete, transcript-verified target
  only when XLSR's strongest hypothesis independently supports each expected
  phone and no phone has a conservative red diagnosis. Learning-plan sound
  checks apply that policy only to the IPA sound assigned by the activity, so
  an uncertain vowel cannot block a `/p/` lesson. An orange `/p/` can pass when
  XLSR still identifies `/p/`; the UI then shows the cross-model verification
  as green while retaining the raw orange acoustic status for diagnostics. An
  alternative phone from only one recognizer is inconclusive. When the word
  recognizer also disagrees, the two-model contradiction is shown as a
  correction.
- Assessed PLP pronunciation targets are segmental IPA phones that occur in
  every assigned phrase. Bare stress, rhythm, prominence, reduction, and
  aspiration claims are not treated as verified mastery because the current
  pass policy has no calibrated authority for those properties. Contrast drills
  declare every assessed phone, such as `/p/ and /b/`.
- PLP pronunciation scores mean verified assigned-target mastery: a verified
  target contributes 100 and an unverified or failed target contributes 0.
  Whole-utterance acoustic quality remains a separately labelled diagnostic
  score and never becomes skill evidence. Weekly pronunciation checkpoints keep
  an actual recorded pronunciation activity. Each assigned target can create
  evidence once on its first conclusive initial result; a drill's normal evidence
  weight is divided across its targets so longer word lists are not over-weighted.
- A PLP target that remains inconclusive for three recordings is allowed to
  complete for progression, but it is explicitly returned in durable lesson
  progress as unverified and creates no pronunciation-mastery evidence. This
  prevents model uncertainty from permanently locking a learner out of the rest
  of a lesson without making the target appear verified after reopening it.

## Personalized learning plan

Onboarding stores CEFR level, native language, one learning goal, and up to
three interests. PostgreSQL is the source of truth. A deterministic planner and
reviewed curriculum own sequence, prerequisites, activities, grading, and
answers. A constrained Groq call using `openai/gpt-oss-120b` supplies weekly
scenario wording; the local compiler validates and atomically publishes all
five lessons in a week.
The reviewed mission catalog distinguishes a scenario's direct context family
from broader interests that can merely theme it. Direct goal-and-context
matches rank first. Each CEFR outcome must retain the source evidence needed to
complete the task even as instructional scaffolding fades at higher levels.
Mission subjects prefer recognizable real places, works, sports, tools,
institutions, and natural phenomena. Every assessed fact remains in the lesson
input; changing prices, schedules, availability, entry requirements, service
incidents, and similar details are dated from supplied evidence or explicitly
labelled as simulated practice data.
Answers remain server-side until an attempt is graded, and completion/XP are
server-authoritative. Groq supplies roleplay responses, trusted-correction
explanations, news rewriting, pronunciation drill wording, and the constrained
weekly PLP surface language. Rate-limited PLP jobs wait for Groq's reported
token-window reset and resume automatically. Credentials and provider settings
remain in the ignored `.env`.

Runtime data is stored outside Git. Downloaded runtime model weights live under
the ignored `backend/.models/` directory.

The RAG curriculum has two reproducible layers:

- 28 project-authored reviewed teaching objects covering seven domains at
  A1–B2, ingested from `backend/speakflow/features/learning_plan/engine/seed.py`;
- a versioned private snapshot containing 8,223 source-attributed CEFR-J
  concepts: 7,799 vocabulary records representing 6,863 distinct case-folded
  headwords, plus 424 grammar records. Of those records, 7,227 vocabulary rows
  have lexical enrichment and the exact `embeddinggemma:latest` 768D vector;
  enrichment is candidate evidence, not by itself permission to teach the row.

A code-owned review overlay links 129 exact existing vocabulary concepts to
previously sparse learner interests. Each link is keyed by CEFR level,
headword, and part of speech, so it cannot silently change the source's level
or attach every sense of a word. The current managed snapshot plus this review
provides at least eight directly relevant, pronounceable, definition-safe terms
for every supported A1–B2 and interest combination (44 cells). A shared runtime
policy then requires a supported lexical part of speech, CMUdict pronunciation,
and a short non-circular definition anchored to the source meaning. The current
snapshot contains 5,433 rows that pass those teaching checks: 1,398 topical and
4,035 untagged general-context candidates. Exact-interest terms are retrieved
before broader related themes; related Music/History themes only fill a remaining
shortage. An untagged general word is eligible only when its embedding is strongly
relevant to the current weekly scenario, and it receives a separate quota so it
cannot displace all topical vocabulary. Reviewed learner glosses protect ambiguous
dictionary entries while retaining the original lexical source in provenance.

Every successfully generated week teaches exactly two safe source-backed terms, even when the
planner did not schedule a dedicated vocabulary-domain lesson; in that case the
terms are pre-taught at the start of the first teaching lesson. Terms already used
in the current revision are excluded, while terms from an older revision of the
same plan are retained only as lower-priority review candidates. Given the audited
minimum of eight safe direct terms per supported level/interest cell, a four-week
plan can introduce eight distinct terms without fabricating new vocabulary.

The overlay is application code, not a database seed. Existing installations
pick it up after a backend restart; they do not need to re-import or re-embed
the curriculum. Fresh installations still restore the normal snapshot during
setup.

CEFR, interest, and goal have deliberately different responsibilities. CEFR is
a hard vocabulary eligibility filter. Interest supplies topical retrieval tags.
The learner goal selects and orders missions, scenarios, and lesson domains; it
is not copied onto thousands of dictionary records as a vocabulary label. The
weekly scenario query is the controlled bridge from that goal/context to safe
untagged general vocabulary. Runtime eligibility and ranking changes are code,
so an existing healthy snapshot needs only a backend restart, not reseeding.

The snapshot is restored into PostgreSQL's `curriculum_concepts` table during
setup. It is part of the private Hugging Face bundle rather than Git because it
contains about 21 MiB of generated metadata and embeddings. A missing,
modified, wrong-version, or wrong-embedding-model snapshot fails setup instead
of silently creating an incomplete learning plan.

## Accounts and data ownership

Email/password registration uses scrypt password hashes. Login returns an
opaque random bearer token; only its SHA-256 hash is stored in PostgreSQL.
Registered learner sessions last 30 days; administrator sign-ins last eight
hours. Sessions can be revoked independently. Guest
sessions last seven days, receive their own user UUID, and are deleted with
their learning data when the guest signs out. Expired abandoned guests are
pruned when a new guest is created.

All learner-owned backend reads and writes are scoped to the authenticated
`users.id`, including indirect generation-job and adaptation IDs. Roleplay
session IDs are unique per user rather than globally. The WebSocket uses the
same bearer identity as REST. Device-local practice words and phoneme progress
are stored in user-namespaced files. Resetting learning data preserves a
registered account and its login; signing out does not erase registered data.

Administrator access is a separate persisted capability on a registered user.
It can be granted or removed only through the local backend CLI, which revokes
existing sessions and records the privilege change. `/admin` routes reject
missing sessions with 401 and non-admin sessions with 403. Operational error
responses are sanitized; detailed exceptions remain in backend logs.

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
before the scenario is persisted. Saved custom scenarios can later be edited or
deleted. Edits affect only future sessions; active and historical sessions keep
the immutable scenario snapshot with which they started.

Typed roleplay turns must contain Latin-script English text. Flutter rejects
Arabic/non-Latin input immediately, and the WebSocket repeats the same check
before grammar correction, provider generation, or persistence. Learners can
use Language Help to translate Arabic into an English option before sending.
The backend also rejects unmistakable structural nonsense locally before a
provider call. This conservative gate covers malformed tokens, keyboard runs,
and function-word-only fragments while preserving names, acronyms, normal short
answers, and context-dependent phrases. Ambiguous plausible English still goes
through the contextual dialogue classifier; objective evidence is accepted only
when it is explicitly grounded in the learner's turn.

Final feedback reports task achievement, each scenario-specific criterion,
interaction, grammar, vocabulary, free-speech fluency, and
pitch variation, and recognition-confidence clarity as independent scores.
Pitch variation is a descriptive vocal-range proxy, not a reference-based
prosody or intonation diagnosis. The roleplay system does not combine
unlike learning dimensions into an overall number. Spoken categories appear
only when spoken evidence exists. Task progress remains visible from exact
objective evidence, while language scores stay absent until the conversation
meets the turn/word minimum. Grammar is scored only when the local corrector
actually evaluated sufficient transcript coverage; a model outage never becomes
a perfect score. Delivery categories require their separate spoken-evidence
minimums. The summary shows evidence status, scenario-specific rubric evidence,
and trusted grammar refinements. Recognition uncertainty is
presented as a word to verify in scripted pronunciation practice, not as a
diagnosed pronunciation error. Zero-turn sessions are abandoned; completed or
interrupted sessions retain their turn evidence in PostgreSQL. Turn and session
idempotency keys reject changed content, repeated turns reuse the stored reply,
and finalization shares the cross-worker session lease with turn generation.
Starting over
deletes learner-owned PLP and roleplay data through database cascades while
preserving reviewed curriculum. The current migration head is `20260809_12`.
