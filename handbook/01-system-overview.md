# System overview

## Product responsibilities

SpeakFlow is an English-learning application with six connected capabilities:

- account registration, login, guest access, and learner isolation;
- a durable four-week personalized learning plan;
- scripted pronunciation practice and feedback;
- grammar correction, dictionary lookup, and text-to-speech;
- goal-driven roleplay over text or speech;
- CEFR-adapted news reading.

The features share identity and learner profile data, but they do not share a
single undifferentiated service or UI file. Each feature owns its contracts and
presentation, while composition roots connect the parts.

## System context

The system communicates in this order:

1. The learner interacts with the Flutter Android client.
2. Flutter sends JSON requests over HTTP/HTTPS and opens an authenticated
   WebSocket for live roleplay.
3. FastAPI authenticates the learner and coordinates the requested feature.
4. FastAPI reads and writes authoritative data in PostgreSQL with pgvector.
5. When a feature needs them, FastAPI calls the local ML bundle, Groq, Ollama,
   or the optional news provider.

In local Android development, ADB reverses device port 8000 to the host backend.
The Flutter client therefore uses `http://localhost:8000` while the FastAPI
process listens on `0.0.0.0:8000`.

## Runtime processes

- **Flutter app**
  - **Responsibility:** UI, navigation, input capture, local caches
  - **Persistent state:** app documents directory

- **FastAPI process**
  - **Responsibility:** contracts, authorization, orchestration, scoring
  - **Persistent state:** none outside configured caches

- **PLP worker thread**
  - **Responsibility:** leases and completes generation jobs
  - **Persistent state:** PostgreSQL

- **PostgreSQL**
  - **Responsibility:** authoritative learner and curriculum data
  - **Persistent state:** Docker volume or configured cluster

- **Ollama**
  - **Responsibility:** curriculum embeddings during ingestion/query support
  - **Persistent state:** Ollama model store

- **External providers**
  - **Responsibility:** constrained generation and news
  - **Persistent state:** provider-owned

## Architectural style

The main style is a feature-oriented modular monolith with Clean Architecture
dependency direction.

Dependencies point inward:

1. Presentation code calls an application or service boundary.
2. Infrastructure code implements the interfaces required by that boundary.
3. Application code uses domain contracts and rules without depending on the
   web framework, database, or user interface.
4. Composition roots select the concrete presentation and infrastructure
   implementations and connect them at startup.

The codebase is intentionally pragmatic. Authentication has explicit domain,
application, infrastructure, and presentation layers. The older and much
larger learning-plan engine remains a cohesive `plp` package while its FastAPI
router lives in the learning-plan feature. This keeps stable persistence and
migration imports intact without returning orchestration to `main.py`.

## Design patterns used

### Composition root

`backend/main.py` selects concrete routers and runtime functions. It does not
implement feature behavior. `frontend/lib/app/providers.dart` creates and
shares the client-side API adapters.

### Repository

Flutter learning-plan screens depend on `PlpRepository`. The HTTP repository
is replaceable with fakes in widget tests. Other feature APIs similarly hide
JSON transport behind focused classes.

### Adapter

FastAPI routers adapt HTTP/WebSocket requests to Python calls. Runtime modules
adapt Groq, local models, NewsAPI, files, and audio libraries. Flutter data
classes adapt API responses to domain/view models.

### Strategy and policy

The planner, generation compiler, scoring helpers, and provider-backed writer
separate deterministic policy from variable provider output. Provider text is
validated before publication.

### Facade

`PlpService` composes focused mixins behind one stable service instance.
`plp.schemas`, `plp.weekly_mission`, and similar modules expose deliberate
public import surfaces while implementation is split into smaller files.

### Observer

Flutter `ChangeNotifier`, Riverpod providers, and router refresh listeners
propagate session and UI state changes. The route location—not a duplicate
integer—is the source of truth for the selected navigation tab.

### Background worker and lease

The PLP worker claims durable jobs with database leases. This allows recovery
from process interruption and prevents multiple workers from publishing the
same job concurrently.

## Trust and authority boundaries

The client may request an action and display a result, but it does not decide:

- whether an authenticated token owns a resource;
- whether an activity answer is correct;
- whether a lesson is complete or XP is earned;
- whether a pronunciation result has sufficient acoustic evidence;
- whether roleplay objectives were supported by the current turn;
- whether generated learning content is valid enough to publish.

These decisions remain in backend services and deterministic validators.

## Why not microservices

Independent services would add deployment, networking, authentication, tracing,
and consistency costs without providing a useful academic or operational
benefit. Feature boundaries inside one process demonstrate the same separation
of concerns while remaining easy to run and explain.
