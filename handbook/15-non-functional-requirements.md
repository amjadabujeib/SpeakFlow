# Observed non-functional characteristics

## How to use this page

This matrix documents non-functional behavior that exists in the current code
and its validation evidence. It intentionally separates a verified project
property from an unmeasured production service-level objective. SpeakFlow has
not undergone a load test, accessibility certification, penetration test, or
long-running availability measurement, so none of those properties are part of
the documented current behavior.

Status meanings:

- **Implemented and verified** — the repository contains the mechanism and an
  automated check or repeatable validation command.
- **Implemented, partially verified** — the mechanism exists, but validation is
  narrower than a production acceptance exercise.
- **Current limitation** — the repository does not currently implement or
  verify this property.

## Requirement matrix

| ID | Quality | Requirement and acceptance criterion | Evidence | Status |
| --- | --- | --- | --- | --- |
| NFR-SEC-01 | Authentication and authorization | Learner-owned routes must reject missing, invalid, expired, or revoked bearer sessions; every `/admin` route must additionally require persisted administrator access. | Authentication middleware plus multi-user, architecture, and administrator security tests. | Implemented and verified |
| NFR-SEC-02 | Credential protection | Passwords must be salted and scrypt-hashed; the database must store only bearer-token hashes; the mobile client must keep the restorable token in platform secure storage. | Auth service and `flutter_secure_storage` session store. | Implemented and verified |
| NFR-SEC-03 | Transport and exposure | Release mobile builds must use HTTPS/WSS, Android must reject cleartext traffic, and local database/backend ports must bind to loopback by default. | Release URL guard, Android manifest, Compose configuration, and Flutter tests. | Implemented and verified |
| NFR-SEC-04 | Abuse and input control | Expensive/public operations must have bounded request rates and sizes; audio uploads must be rejected above their limits before expensive processing. | Process-shared same-host rate limiter, body middleware, schema constraints, and architecture/runtime tests. | Implemented and verified |
| NFR-SEC-05 | External content safety | Proxied news images must reject unsafe schemes, private/loopback destinations, unsafe redirects, invalid media types, and oversized responses. | News proxy validation and runtime news tests. | Implemented and verified |
| NFR-DATA-01 | Integrity | Persistent learner outcomes must be server-authoritative, user-scoped, transactionally committed, and protected by relevant database constraints. | Shared ORM/session boundary, ownership checks, Alembic constraints, PLP/roleplay/auth integration tests. | Implemented and verified |
| NFR-DATA-02 | Schema evolution | An existing supported database must be upgradeable through an ordered, reviewable migration chain, and CI must reject ORM/schema drift. | Alembic revision history, `upgrade head`, and `alembic check` in CI. | Implemented and verified |
| NFR-REL-01 | Duplicate/retry safety | Retried attempt submissions and roleplay turns must not create duplicate authoritative results; durable PLP jobs must retain retry and lease state. | Idempotency columns/constraints and PLP attempt, worker, roleplay persistence, and socket tests. | Implemented and verified |
| NFR-REL-02 | Dependency failure behavior | Database, model, and provider failures must produce bounded, sanitized client errors rather than fabricated success; provider-limited PLP jobs must remain resumable. | Safe service error mapping, health semantics, worker state, and failure-path tests. | Implemented and verified |
| NFR-AVA-01 | Readiness | `/health` must return 200 only when PostgreSQL, the PLP worker, and minimum reviewed curriculum are ready; otherwise it must return 503 without exposing sensitive diagnostics. | Health implementation, curriculum readiness tests, and operations procedure. | Implemented and verified |
| NFR-PERF-01 | Bounded waiting | Ordinary mobile HTTP calls must time out after 30 seconds, long model calls after 60 seconds, history reads after 8 seconds, and roleplay sockets must close after 120 seconds idle. | Central Flutter API client and roleplay socket policy/tests. These are timeout bounds, not response-time guarantees. | Implemented and verified |
| NFR-PERF-02 | Interactive model readiness | Local speech, pronunciation, grammar, and TTS model families must warm during application startup so the first accepted request does not trigger model initialization. | Lifespan warm-up, readiness state, and model-loading tests. | Implemented, partially verified |
| NFR-PERF-03 | Resource bounds | Repeated TTS work must be coalesced/cached within a 32 MiB cache, provider/network calls must use timeouts, and blocking model work must not run directly on the event loop. | Runtime cache/locks, provider configuration, thread offloading, and runtime tests. | Implemented, partially verified |
| NFR-SCL-01 | Deployment scale | The current deployment supports backend workers on one host with shared PostgreSQL authority and same-host rate counts. Its rate limiter, model state, caches, and locks do not provide a multi-host contract. | SQLite-backed same-host limiter and process-local model/cache design. | Implemented, partially verified |
| NFR-MNT-01 | Maintainability | Hand-written Python and Dart source files must remain at or below 500 lines and key dependency directions must remain enforceable. | Backend/Flutter architecture tests and CI. | Implemented and verified |
| NFR-MNT-02 | Change safety | Every pull request and push to `main` must run backend lint/tests/migration drift, Flutter format/analyze/tests, and dashboard lint/tests/build. | `.github/workflows/quality.yml`. | Implemented and verified |
| NFR-COMP-01 | Mobile layout | Core flows must render without overflow at a 393 x 852 logical test viewport, respect safe insets, and combine system/user text scaling within the supported 0.85–2.0 range. | Flutter widget tests, safe-area layout, and text-scale unit tests. | Implemented, partially verified |
| NFR-ACC-01 | Accessibility | Important interactive content should expose useful semantics and remain usable with increased system text size. | Selected semantic labels and text-scale support. A complete screen-reader, contrast, focus-order, and touch-target audit has not been performed. | Implemented, partially verified |
| NFR-OBS-01 | Operability | Operators must be able to distinguish database, curriculum, worker, and local-model readiness without receiving secrets or raw internal exceptions. | Public minimal health response, authenticated dashboard health/error views, and sanitized admin failures. | Implemented, partially verified |
| NFR-PRIV-01 | Privacy lifecycle | Learner data must remain account-scoped and guest sign-out/reset operations must remove data according to documented semantics. | Ownership tests, guest lifecycle, reset flows, and user-namespaced local stores. The repository has no formal retention/export/account-deletion policy. | Implemented, partially verified |
| NFR-REC-01 | Backup and recovery | The Compose database volume preserves data across container replacement, but the repository contains no automated backup/restore workflow or recovery-time/recovery-point targets. | Compose named volume; no backup/restore exercise is present. | Current limitation |

## Current project-level conclusion

These characteristics are suitable as report evidence when accompanied by
their stated scope. The current code demonstrates security boundaries,
integrity, retry safety, readiness, bounded resource use, maintainability, and
responsive mobile behavior. It does not establish production capacity or a
formal service level.

The repository currently has no measured p50/p95 latency, startup or memory
budget, supported concurrent-user count, complete accessibility audit,
automated database restoration exercise, formal retention/export/account-
deletion policy, structured request tracing, uptime measurement, multi-host
coordination, or independent security assessment.
