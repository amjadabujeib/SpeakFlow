# API, authentication, and security

## Contract families

FastAPI exposes generated OpenAPI documentation at `/docs` when the backend is
running. Learner HTTP feature routes use one unversioned `/api` namespace; the
authenticated operations routes use the separate `/admin` prefix.

- **`/health`**
  - **Purpose:** Minimal database/worker/reviewed-catalog readiness state
  - **Authentication:** public

- **`/api/auth/*`**
  - **Purpose:** signup, signin, guest, current user, signout
  - **Authentication:** mixed by endpoint

- **`/api/learners/local/profile`**
  - **Purpose:** authenticated learner profile
  - **Authentication:** bearer

- **`/api/learners/local`**
  - **Purpose:** learning-data reset
  - **Authentication:** bearer

- **`/api/onboarding/options`, `/api/plp/*`**
  - **Purpose:** options, generation, active plan, attempts, adaptations
  - **Authentication:** bearer

- **`/api/roleplay/*`**
  - **Purpose:** scenarios, authenticated custom-scenario create/edit/delete,
    sessions, and history
  - **Authentication:** bearer

- **`/ws/chat`**
  - **Purpose:** live roleplay session
  - **Authentication:** bearer during WebSocket setup

- **`/api/grammar/check`, `/api/vocabulary/lookup`**
  - **Purpose:** grammar and dictionary tools
  - **Authentication:** bearer

- **`/api/translation/arabic`, `/api/pronunciation/guide`**
  - **Purpose:** language help and canonical guide
  - **Authentication:** bearer

- **`/api/pronunciation`, `/api/speaking/transcribe`**
  - **Purpose:** audio analysis
  - **Authentication:** bearer

- **`/api/news`**
  - **Purpose:** personalized feed
  - **Authentication:** bearer

- **`/api/news/image`**
  - **Purpose:** validated image proxy
  - **Authentication:** public GET, rate limited

- **`/api/tts`**
  - **Purpose:** cached speech
  - **Authentication:** bearer-protected POST

- **`/admin/dashboard`, `/admin/learning`, `/admin/roleplay`, `/admin/errors`**
  - **Purpose:** global operational summaries
  - **Authentication:** bearer plus persisted administrator capability

- **`/admin/users`, `/admin/audit-events`**
  - **Purpose:** paginated account search and immutable privileged-action history
  - **Authentication:** bearer plus persisted administrator capability

- **`/admin/users/{user_id}/revoke`**
  - **Purpose:** audited revocation of active sessions for one user UUID
  - **Authentication:** bearer plus persisted administrator capability

The project has no `/api/v1` aliases. Flutter and FastAPI are released together,
so breaking contract changes are coordinated directly rather than maintained as
parallel API versions.

## Administrator authorization

The middleware explicitly treats `/admin` as protected even though it is
outside the learner `/api` namespace. It authenticates the opaque bearer token,
loads the current user row, rejects non-admin users with 403, stores the actor
on request state, and binds the same identity context used elsewhere.

Public signup cannot request `is_admin`. A local CLI grants or removes the
capability, revokes pre-change sessions, and audits the change. Session
revocation requires a validated reason and atomically records actor, target,
count, and time. The dashboard sends bearer headers with browser credentials
disabled, so authorization does not depend on cookies or CORS.

## Bearer authentication

Registered or guest login returns an opaque random token. The backend stores a
SHA-256 token hash. For a protected request:

1. middleware parses the Bearer scheme;
2. `AuthService.authenticate()` hashes the supplied token;
3. PostgreSQL verifies a non-revoked, non-expired session and active user;
4. middleware binds `user_id` to the request context;
5. the feature service scopes every query/write to that identity.

Flutter persists the raw token only in its application storage for session
restoration and adds it through `ApiClient`.

## Password and session policy

- Passwords use `hashlib.scrypt` with per-password random salt.
- Comparison uses constant-time `hmac.compare_digest`.
- Registered learner sessions last 30 days.
- New administrator sessions last eight hours.
- Guest sessions last seven days.
- Registered accounts retain at most five active sessions.
- Online signout revokes one registered session. If the backend is unreachable,
  Flutter still removes the local credential and reports that server revocation
  could not be confirmed.
- Signing out a guest deletes the unrecoverable guest and owned data.

## Input validation

Pydantic schemas reject unknown fields where contracts are strict, normalize
email/text/list values, and enforce lengths, ranges, enums, and list counts.
Flutter validates for immediate UX, but backend validation is authoritative.

Multipart endpoints impose both declared `Content-Length` and streamed-byte
limits before expensive decoding. Audio code also checks sample finiteness,
duration, clipping, and speech presence.

## Rate limiting

`ProcessSharedRateLimiter` uses a small indexed SQLite-backed fixed window so
multiple backend workers on the same host share counts. Public/authentication
limits are keyed by client address; authenticated expensive paths are keyed by
the persisted user ID so unrelated learners behind one network do not consume
one another's quota. Specific limits cover authentication, PLP generation,
grammar/dictionary/translation providers, scenario drafts, news, TTS, image
proxy, pronunciation, speaking transcription, admin reads, and the stricter
admin revocation command. A limited response is HTTP 429 with `Retry-After`.

Provider rate limits are separate. PLP generation stores the provider reset
time in the durable job and resumes later rather than busy-looping.

## CORS

Production origins come from `CORS_ORIGINS`. When it is absent in local
development, only localhost/127.0.0.1 HTTP origins are matched. Allowed methods
and headers are explicit.

## News image proxy and SSRF

The proxy treats article URLs as hostile:

- only permitted HTTP(S) URLs are accepted;
- DNS results must resolve to public addresses;
- redirects are revalidated;
- the connected peer must be public;
- response type and size are bounded.

This prevents a provider-supplied URL from reading loopback, private network,
cloud metadata, or oversized content through the backend.

## WebSocket authority

The WebSocket uses the same bearer identity as REST and binds to a previously
created learner-owned roleplay session. Each client turn has an idempotent ID.
Locks and database constraints prevent duplicate concurrent processing.

The server owns scenario snapshot, objective state, ordered turns, completion,
and evaluation. Client-authored session summaries are deliberately not exposed.

## Secret and transport policy

- `.env` is ignored and must never be committed.
- Hugging Face tokens remain in the user's local credential cache.
- Release Flutter builds require HTTPS and WSS compile-time URLs.
- Local HTTP is permitted only for development/device forwarding.
- Provider keys and database credentials remain backend-only.

## Public versus private learning content

Compiled lessons contain private grading data. The mobile document sanitizer
removes answer keys and sensitive provenance before response serialization.
Attempt endpoints return the relevant correction after grading; they never let
the client declare success or upload an arbitrary score as mastery.
