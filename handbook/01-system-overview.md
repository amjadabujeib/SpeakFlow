# System overview

## Product responsibilities

SpeakFlow is an English-learning application with six connected capabilities:

- account registration, login, guest access, and learner isolation;
- a durable four-week personalized learning plan;
- scripted pronunciation practice and feedback;
- grammar correction, dictionary lookup, and text-to-speech;
- goal-driven roleplay over text or speech;
- CEFR-adapted news reading.

It also includes a separate operations dashboard for inspecting aggregate
users, sessions, learning-plan jobs, roleplay activity, runtime-model state, and
recent PLP failures. This dashboard is an operator tool, not a learner feature.

The features share identity and learner profile data, but they do not share a
single undifferentiated service or UI file. Each feature owns its contracts and
presentation, while composition roots connect the parts.

## System context

The system communicates in this order:

1. The learner interacts with the Flutter Android client.
2. Flutter sends JSON requests over HTTP/HTTPS and opens an authenticated
   WebSocket for live roleplay.
3. An operator may separately open the React dashboard, whose Vite development
   server proxies `/api/auth` and `/admin` requests to FastAPI.
4. FastAPI authenticates learner `/api` requests and coordinates the requested
   feature; it separately requires persisted administrator access for every
   `/admin` request.
5. FastAPI reads and writes authoritative data in PostgreSQL with pgvector.
6. When a feature needs them, FastAPI calls the local ML bundle, Groq, Ollama,
   or the optional news provider.

In local Android development, ADB reverses device port 8000 to the host backend.
The Flutter client therefore uses `http://localhost:8000` while the FastAPI
process listens on `127.0.0.1:8000` by default.

## Runtime processes

- **Flutter app**
  - **Responsibility:** UI, navigation, input capture, local caches
  - **Persistent state:** app documents directory

- **React operations dashboard**
  - **Responsibility:** authenticated aggregate diagnostics and audited session revocation
  - **Persistent state:** session storage; active-tab responses live in browser memory

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
application, infrastructure, and presentation layers. The larger learning-plan
implementation is feature-owned under `features/learning_plan/engine`; narrow
application services separate its production callers from the private
transactional composition.

## Design patterns used

### Composition root

`backend/main.py` selects concrete routers and runtime functions. It does not
implement feature behavior. `frontend/lib/app/providers.dart` creates and
shares the learner client-side API adapters.
`admin-dashboard/src/components/Dashboard.jsx` is the smaller dashboard
composition point for tab polling.

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

`LearningPlanEngine` composes focused persistence behaviors behind narrow
learning-plan, lifecycle, pronunciation-assignment, and roleplay services.
`speakflow.features.learning_plan.engine.schemas`, `speakflow.features.learning_plan.engine.weekly_mission`, and similar modules expose deliberate
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

The operations dashboard deliberately crosses learner boundaries to show
global aggregates. Backend middleware authenticates its bearer token, checks
the current `is_admin` database value, rate-limits the request, and attributes
privileged writes to that administrator. CORS or hidden UI controls are not
used as authorization boundaries.

## Why not microservices

Independent services would add deployment, networking, authentication, tracing,
and consistency costs without providing a useful academic or operational
benefit. Feature boundaries inside one process demonstrate the same separation
of concerns while remaining easy to run and explain.
