# Flutter architecture

## Application startup

`frontend/lib/main.dart` is the Flutter composition entrypoint:

1. initialize Flutter bindings;
2. reject insecure backend URLs in release builds;
3. restore the authenticated session from device storage;
4. restore UI preferences;
5. register learner-state reset behavior for signout;
6. lock the app to portrait orientations;
7. run a Riverpod `ProviderScope` containing `SpeakFlowApp`.

`SpeakFlowApp` builds a dark `MaterialApp.router`. An `AnimatedBuilder` applies
the selected text scale through `MediaQuery` without rebuilding the router
configuration.

## Feature-first layout

```text
lib/
  app/                 dependency composition and routes
  core/                app-wide auth, network, data, state, and theme
  features/
    auth/
    chat/
    home/
    learning_plan/
      data/
      domain/
      presentation/
    news/
    practice/
    shell/
  shared/widgets/      widgets genuinely reused across features
```

A feature owns its data adapters and UI. Code moves to `core` only when it is
application-wide and to `shared` only when multiple features genuinely use it.

## Dependency composition

`app/providers.dart` creates one `AppDependencies` object around one
authenticated `ApiClient`. It constructs focused adapters for authentication,
roleplay, language tools, news, pronunciation, and learning plans, then exposes
them through Riverpod providers.

This gives tests and future controllers a stable injection point without
requiring screens to know URL construction, authorization headers, or JSON
error parsing.

## Routing

`app/router.dart` uses `go_router`.

- `/auth` is guarded by `AuthGate`.
- `/start` checks whether the learner already has a profile/plan.
- `/onboarding` and `/loading` implement first account setup.
- `/home`, `/practice`, `/chat`, and `/news` share `MainShell`.
- roleplay, feedback, history, grammar, dictionary, PLP onboarding, lessons,
  and pronunciation are full-screen routes outside or beyond the shell.

`AuthSessionStore` is the router refresh listener. If no session exists, any
protected location redirects to `/auth`.

The shell receives `state.uri.path`; this route location is the single source
of truth for the highlighted bottom-navigation item. Programmatic navigation
and deep links therefore cannot leave a stale selected tab.

## State categories

SpeakFlow separates state by lifetime and authority.

- **Authentication**
  - **Owner:** `AuthSessionStore`
  - **Examples:** token, user UUID, guest flag

- **App UI/profile snapshot**
  - **Owner:** `AppState`
  - **Examples:** font scale, native language, CEFR, interests, plan refresh token

- **Feature workflow**
  - **Owner:** screen/controller state
  - **Examples:** loading, recording, selected lesson, chat messages

- **Shared dependencies**
  - **Owner:** Riverpod providers
  - **Examples:** API adapters

- **Device persistence**
  - **Owner:** focused stores
  - **Examples:** practice words, phoneme history, session, preferences

- **Server authority**
  - **Owner:** backend/PostgreSQL
  - **Examples:** plan, attempts, XP, roleplay history

`AppState` returns immutable interest lists, ignores unchanged assignments,
clamps font scale, and serializes preference writes so rapid slider updates do
not race each other.

## Networking

`core/network/api_client.dart` owns:

- API origin and `/api` path construction;
- bearer-token headers;
- JSON encoding/decoding;
- request timeout behavior;
- consistent error extraction;
- session invalidation on unauthorized responses.

Feature APIs express operations in the language of their feature. Screens
should call `AuthApi.signIn`, `RoleplayApi.startSession`, or
`PlpRepository.loadActivePlan`, not build HTTP requests themselves.

## Learning-plan internal architecture

The learning-plan feature is the most explicit Flutter layering:

- `features/learning_plan/data/learning_plan_api.dart` is the low-level
  application dependency adapter;
- `features/learning_plan/data/plp_repository.dart` defines the screen-facing
  repository contract and HTTP implementation;
- `features/learning_plan/domain/plp_models.dart` is the public library for
  immutable parsed models;
- domain `part` files divide lesson, plan, progress, and validation models;
- presentation files divide gate, onboarding, plan state, weeks, lessons, and
  generation UI;
- `presentation/lesson` divides controller and activity-specific widgets.

Repository injection lets widget tests provide deterministic fake plans and
generation states without a running backend.

## Dart `part` files

Several large screens are split with Dart's `part` mechanism. A library file
owns imports, private symbols, and main state; related part files own focused
widgets/controllers. This preserves private collaboration while keeping each
source file under 500 lines.

Use a part when components are tightly coupled to one private screen state.
Use a normal importable file when a component has an independent public
contract or is shared by another feature.

## UI authority rules

- The UI may optimistically show progress but must display the server result.
- Correct answers are not embedded in the public plan payload.
- Pronunciation launches with a target and returns trusted backend evidence.
- Roleplay feedback distinguishes text categories, spoken delivery estimates,
  and recognition uncertainty.
- Signout clears learner-specific singleton and file state before another user
  can see it.

## Error and retry behavior

Feature screens catch adapter exceptions and map them to loading, empty,
retryable, or fatal view states. `FirstRunGate` distinguishes missing profile
from infrastructure failure: missing profile opens onboarding; a database/API
failure stays on an explicit retry screen.

The client must not infer that a generic database message means the server is
offline. Operational diagnosis belongs to backend health, logs, and Alembic
revision checks.
