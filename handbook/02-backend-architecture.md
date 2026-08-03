# Backend architecture

## Startup and composition

`backend/main.py` is the executable composition root. Startup follows this
order:

1. `speakflow.config.load_runtime_env()` loads the root `.env` consistently.
2. Offline/cache environment variables are set before ML libraries import.
3. feature routers and concrete runtime functions are imported;
4. `create_application()` creates FastAPI and installs cross-cutting middleware;
5. routers receive their required callables and are included;
6. Uvicorn runs `main:app` when the file is executed directly.

The application lifespan starts the PLP worker. Shutdown stops the worker,
closes the service/database pool when safe, and releases provider sessions.

The runtime dependency chain is straightforward:

1. `main.py` calls `speakflow/app/factory.py` to construct FastAPI.
2. `main.py` supplies the feature routers and concrete runtime adapters.
3. Routers delegate work to the authentication service, PLP service, or
   roleplay engine.
4. Services use SQLAlchemy to access PostgreSQL.
5. Runtime adapters isolate local models and external providers from the route
   layer.

## Application shell

`speakflow/app/factory.py` owns behavior that applies across features:

- CORS configuration;
- streamed upload body limits;
- fixed-window rate-limit selection;
- bearer-token authentication middleware;
- binding the authenticated UUID to the PLP identity context;
- enforcing the single `/api` authentication and transport policy.

This logic belongs outside feature routers because every protected feature
needs the same identity and transport policy.

## Feature boundaries

### Authentication

Authentication is the clearest Clean Architecture example:

- `speakflow/features/auth/domain/models.py` defines framework-free
  authenticated-user/session values;
- `speakflow/features/auth/application/ports.py` defines command and service
  protocols;
- `speakflow/features/auth/application/errors.py` defines errors meaningful to
  callers;
- `speakflow/features/auth/infrastructure/models.py` maps users and token hashes
  to SQLAlchemy;
- `speakflow/features/auth/infrastructure/service.py` implements signup,
  signin, guest, validation, and revocation;
- `speakflow/features/auth/presentation/schemas.py` validates HTTP payloads;
- `speakflow/features/auth/presentation/router.py` maps routes and errors to
  HTTP.

### Learning plan

The feature presentation router owns HTTP. The mature engine remains under
`plp/` and is divided by responsibility: models, schemas, planning, retrieval,
generation, grading, progress, attempts, roleplay persistence, and worker
leasing. `PlpService` composes focused mixins and is the router-facing facade.

### Roleplay

Feature infrastructure owns roleplay ORM models. The REST router owns scenario
and history contracts. The runtime router injects scenario generation,
translation, finalization, and WebSocket functions from `speakflow/runtime`.
Deterministic scenario catalog and evaluation policy live under
`speakflow/features/roleplay/domain`.

### Language tools, news, and pronunciation

These presentation routers are router factories. `main.py` injects concrete
functions from runtime modules, so a router does not import the executable
entrypoint or own heavyweight model state.

## The runtime adapter package

`speakflow/runtime` contains operations that touch local models, provider SDKs,
audio libraries, network sessions, or complex WebSocket orchestration. It is
not a second domain layer. Its purpose is to keep those unstable dependencies
out of `main.py` and out of simple feature contracts.

Model ownership is centralized in `runtime/models.py`. Global model references
begin as `None`; lock-protected loaders initialize them only on first use.
Health checks inspect state without causing model loads.

## Learning-plan service composition

`plp/service.py` defines `PlpService` by combining small mixins:

- base configuration and lifecycle;
- profile/document behavior;
- generation submission and retrieval;
- attempts and server-side grading;
- progress/adaptation views;
- roleplay persistence;
- worker leasing, retry, and failure transitions.

The mixins share the same configured service instance but keep source files
within the project size policy. Private helper modules own identity conversion,
grading, generation-worker details, and failure envelopes.

## Database transaction boundary

`plp.database.session_scope()` is the standard synchronous transaction
boundary. It commits on success, rolls back on exceptions, and closes the
session. Services catch SQLAlchemy errors at a boundary and convert them to
feature errors. FastAPI routers then convert feature errors into appropriate
HTTP responses.

Roleplay turn generation uses explicit cross-worker coordination so the same
client session/turn cannot be persisted twice. Activity attempts use a
`submission_id` uniqueness contract for the same reason.

## API surface

HTTP routers expose one unversioned `/api/...` contract. Live roleplay uses
`/ws/chat`. The project intentionally does not clone routes under `/api/v1`:
the Flutter application and backend are updated together, so duplicate aliases
would add maintenance and test surface without supporting an independent
consumer.

Tests reject versioned aliases and ensure static generation routes are
registered before dynamic `{job_id}` routes.

## Contract standard

The application has one supported learning-plan contract. Plans identify the
`weekly_mission` architecture and expose `format_revision: 1`; they do not carry
separate prompt, planner, generator, or compiler versions. Generated content
uses canonical hashes for identity. Alembic revisions, dependency pins, source
releases, and ML manifest revisions remain separate because each protects a
real persistence or asset boundary rather than an alternate application API.

## Error translation

Errors are translated in layers:

1. provider/SQL/audio/model exception occurs;
2. service/runtime code classifies it and preserves safe detail;
3. the feature router returns an HTTP status and public message;
4. `ApiClient` throws a Dart exception containing that message;
5. the screen chooses retry, onboarding, or failure UI.

The learning-plan database message is intentionally safe but broad. Therefore
operations should compare Alembic revisions when PostgreSQL is reachable but a
PLP query fails.

## Dependency rules

- Feature presentation must never import `main.py`.
- Domain and application modules must not depend on FastAPI or SQLAlchemy.
- Runtime/provider modules may depend on frameworks but should expose focused
  functions to routers.
- ORM metadata is shared through `speakflow.shared.orm.Base` so Alembic sees one
  registry.
- A new cross-cutting middleware belongs in `speakflow/app`, not in a feature.
- A feature-specific contract belongs beside that feature, not in a generic
  shared utility module.
