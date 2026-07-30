# SpeakFlow

Flutter English-learning client with a FastAPI backend. Registered accounts
and disposable guests have separate plans, progress, practice data, roleplay
history, and custom scenarios. The app combines roleplay chat, strict scripted
pronunciation assessment, target-free spoken delivery feedback, grammar
support, news, and a durable four-week personalized learning plan (PLP).

## Repository layout

```text
frontend/   Flutter client, Android project, assets, and widget tests
backend/    FastAPI application, migrations, ML services, and tests
```

Downloaded model weights are runtime assets rather than source files. They stay
under ignored backend directories, while the small configuration and vocabulary
resources needed by the application remain tracked.

## Installation requirements

The supported development environments are Ubuntu 24.04 and Windows 11 with
WSL2 Ubuntu 24.04. The backend is pinned to Python 3.12. The Android client
requires Flutter 3.35 or newer, an Android SDK, JDK 21, and ADB.

Allow at least 15 GiB of free space for the Python environment, Docker data,
Ollama, and the approximately 2.8 GiB private model bundle. Android Studio and
its SDK need additional space. A machine with 16 GiB of RAM is recommended.
An NVIDIA GPU is optional; add `FORCE_CPU=1` to `.env` to force CPU inference.

Before setup, obtain:

- access to the private `speakflow/randomModels` Hugging Face repository and a
  Hugging Face read token;
- a `GROQ_API_KEY`;
- an optional `NEWSAPI_KEY` if live news categories are required;
- access to this private source repository.

The bootstrap command installs Python dependencies, authenticates with Hugging
Face when necessary, downloads and verifies the model bundle, starts
PostgreSQL 16 with pgvector, pulls Ollama's `embeddinggemma` model, applies
database migrations, ingests the 28 reviewed teaching objects, and restores
the versioned 8,223-concept RAG vocabulary snapshot with its 7,227 embeddings.

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
3. run `.venv/bin/python backend/setup.py` as shown below and paste the token
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
GROQ_API_KEY=gsk_your_key
NEWSAPI_KEY=
```

Do not commit `.env`. It is ignored by Git and loaded automatically by the
backend, migrations, and curriculum tools.

#### 4. Create the backend environment

```bash
python3.12 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python backend/setup.py
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
should be healthy. Heavy speech, grammar, and TTS models load lazily when their
features are first used.

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
GROQ_API_KEY=gsk_your_key
NEWSAPI_KEY=
```

Then create the Linux virtual environment and run setup:

```bash
python3.12 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python backend/setup.py
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
3. ensure Ollama is running;
4. start the backend with `.venv/bin/python backend/main.py` from the repository
   root;
5. run `adb reverse tcp:8000 tcp:8000`;
6. run `flutter run` from `frontend/`.

The PostgreSQL container uses a named Docker volume, so normal container
restarts do not erase learner data.

### Verification and common failures

Run backend checks from the repository root:

```bash
cd backend
../.venv/bin/python -m alembic -c alembic.ini current
PYTHONPATH=. ../.venv/bin/python -m unittest discover -s tests -p 'test_*.py'
```

Run frontend checks:

```bash
cd frontend
flutter test
flutter analyze
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
- **Groq features fail:** ensure `GROQ_API_KEY` is populated in the root `.env`
  without quotes or extra spaces, then restart the backend.

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
PYTHONPATH=backend .venv/bin/python -m plp.curriculum_snapshot export
.venv/bin/python backend/model_bundle.py inventory
.venv/bin/python backend/model_bundle.py upload
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

Runtime data is stored outside Git. Downloaded runtime model weights live under
the ignored `backend/.models/` directory.

The RAG curriculum has two reproducible layers:

- 28 project-authored reviewed teaching objects covering seven domains at
  A1–B2, ingested from `backend/plp/seed.py`;
- a versioned private snapshot containing 8,223 source-attributed CEFR-J
  concepts, including 7,227 retrieval-ready vocabulary records enriched with
  Words-CEFR frequency, WordNet definitions, CMUdict IPA, and the exact
  `embeddinggemma:latest` 768D vectors.

The snapshot is restored into PostgreSQL's `curriculum_concepts` table during
setup. It is part of the private Hugging Face bundle rather than Git because it
contains about 21 MiB of generated metadata and embeddings. A missing,
modified, wrong-version, or wrong-embedding-model snapshot fails setup instead
of silently creating an incomplete learning plan.

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
