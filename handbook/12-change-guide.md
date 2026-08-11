# Changing the system safely

## Add a FastAPI endpoint

1. Decide which business feature owns the contract.
2. Add/extend a Pydantic schema in that feature's presentation package or in
   the stable PLP schema package.
3. Put deterministic behavior in a service/domain module.
4. Put provider/model/network behavior in an infrastructure/runtime adapter.
5. Add the route to the feature router; use a router factory when a concrete
   callable should be injected.
6. Wire the adapter in `main.py` only if composition is required.
7. Confirm the `/api` path and static-before-dynamic route ordering; do not add
   a duplicate `/api/v1` alias.
8. Add contract, authority, error, and authentication tests.

Do not implement the use case directly in `main.py`.

## Add a Flutter feature or screen

1. Create `lib/features/<feature>/`.
2. Put HTTP/filesystem access in `data/` with a focused adapter.
3. Put framework-light parsed values in `domain/` when the feature has a rich
   model.
4. Put screens/controllers/widgets in `presentation/` or the feature root,
   depending on feature size.
5. Register shared dependencies in `app/providers.dart`.
6. Add a route in `app/router.dart` if it is navigable.
7. Pass typed route arguments; handle missing extras safely.
8. Add widget/model tests with a fake adapter.

Do not put a feature-only widget in `shared` or make a new global service.

## Change the operations dashboard

1. Decide whether the change is a backend aggregate/command, dashboard
   presentation, or both.
2. Update `features/admin/presentation.py` and the matching React component in
   the same contract change.
3. Keep authentication/transport in `adminApi.js` and polling/error behavior in
   `Dashboard.jsx`; never introduce fabricated operational fallback data.
4. Keep authorization in backend middleware and audit every privileged write.
5. Add backend contract/authorization tests and frontend transport coverage.
6. Run `npm run lint`, `npm test`, and `npm run build` from `admin-dashboard/`.
7. Update the dashboard README plus API/security and operations guides when
   paths, proxying, health semantics, or deployment change.

Every new `/admin` route must retain bearer authentication, current database
administrator checks, safe response schemas, rate limits where appropriate,
and server-side authorization. A hidden button, CORS rule, or private-looking
URL is not an authorization boundary.

## Add an API operation to Flutter

1. Add it to the owning feature API/repository.
2. Use `ApiClient` for base URL, bearer headers, JSON, and errors.
3. Parse responses into a domain/view model, not untyped maps in widgets.
4. Keep server error detail available for a retryable UI state.
5. Add adapter parsing and widget behavior tests.

## Change the database

1. Update the shared-registry ORM mapping.
2. Create a new Alembic revision after the current head.
3. Plan defaults/backfills and constraints for existing rows.
4. Update Pydantic/Dart contracts if the field crosses the API.
5. Upgrade a database from the previous revision and run integration tests.
6. Update README, data handbook, operations expected head, and setup behavior.

Never rely on an empty database test alone.

## Change a learning-plan rule

Classify the change first:

- prerequisite/schedule/skill choice → planner/catalog;
- provider wording contract → weekly models/generator;
- semantic acceptance → weekly validation/lesson quality;
- content assembly/answer ownership → compiler/content;
- grading/completion/XP → service grading/attempts;
- retry/lease/rate limit → worker/generation support;
- mobile visibility → document sanitizer/schema/Flutter model.

Add a deterministic test at the same authority boundary. Provider prompt-only
changes are insufficient for rules that affect learning correctness.

## Add or revise a weekly mission archetype

Treat an archetype as a reviewed evidence contract, not just a topic prompt:

1. keep its ID stable once persisted plans may reference it;
2. choose one primary `context_family` and use `compatible_interest_ids` only
   for themes the scenario can genuinely support;
3. make each A1–B2 can-do progression increase linguistic independence rather
   than simply adding abstract difficulty;
4. name every fact, limitation, obstacle, disagreement, or edge case required
   by an outcome in the premise or `setting_slots`;
5. reduce models, phrase banks, and cues at higher levels without removing the
   map, dataset, source text, rules, or case evidence needed to answer;
6. use real-world subjects with supplied evidence; date or explicitly simulate
   volatile travel details, and ground cultural material in respectful public
   or community-authored sources without exposing restricted knowledge;
7. avoid grading personal opinions or experiences as having one correct answer;
8. check overlap with existing archetypes and give the new scenario a distinct
   communicative product;
9. add relevance and evidence-contract coverage in
   `tests/learning_plan/generation/test_mission_archetypes.py`, then run planner
   and weekly compiler tests.

The selector ranks goal plus direct interest-context matches above scenarios
that merely list the interest as a theme. Stable hashing chooses only within a
relevance tier, so catalog additions provide variety without routinely
displacing a more direct scenario.

## Add a roleplay scenario field

Update the reviewed catalog/custom draft schema, persistence snapshot,
Pydantic response, Flutter model, builder UI, runtime prompt, deterministic
validation, evaluation if relevant, and migration if stored in a new column.
When a persisted shape must change, add an Alembic data migration and update
the single supported `format_revision`; do not accumulate alternate parsers.

## Change pronunciation scoring

Treat scoring as a scientific compatibility contract:

1. define the evidence or calibration reason;
2. update feature dimensions/metadata together;
3. train/evaluate without importing training code at runtime;
4. update the model bundle manifest;
5. keep audio/transcript gates independent of model confidence;
6. add regression fixtures for green/warning/red states and false certainty;
7. document what the metric can and cannot claim.

Do not add a silent fallback to a weaker scorer.

## Split a file approaching 500 lines

Choose a semantic seam:

- UI state versus widgets;
- public facade versus implementation;
- deterministic policy versus provider adapter;
- model definitions versus service behavior;
- preparation versus validation versus compilation;
- shared fixture versus focused tests.

For Dart private screen components, a `part` file is acceptable. For reusable
public contracts, use normal imports. For Python, retain a small facade only
when it provides a deliberate stable import surface.

## Remove code safely

1. Search imports, symbol references, routes, providers, tests, and docs.
2. Distinguish reflection/ORM registration/public re-export from dead code.
3. Remove callers and configuration entries with the implementation.
4. Run import smoke tests and full static analysis.
5. Confirm no stale generated `.pyc` made a deleted module appear available.
6. Update file maps and architecture statements.

Protocol files are not dead merely because no class explicitly inherits from
them; structural typing and parameter contracts can consume them.

## Pre-commit review checklist

- Is there one clear owner for the change?
- Does dependency direction still point inward?
- Is client/server authority unchanged or intentionally tested?
- Are user queries scoped by authenticated UUID?
- Are provider outputs validated before persistence/display?
- Are secrets and raw tokens absent from logs and Git?
- Does `alembic current` match `heads` after upgrade?
- Do Flutter analysis/tests and backend tests pass?
- Are all `.py` and `.dart` files at or below 500 lines?
- Are the README and relevant handbook pages still truthful?
- If `/admin` changed, are authorization, auditability, safe errors, tests, and
  deployment impact still explicit?
