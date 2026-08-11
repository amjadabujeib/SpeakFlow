# Runtime flows

These sequences show how major user actions cross files and authority
boundaries.

Before accepting requests, the FastAPI lifespan sequentially warms
WhisperX/alignment, GECToR, Kokoro, and the full pronunciation scorer. A warm-up
report controls readiness, after which the PLP worker starts. The default is
eager; `SPEAKFLOW_MODEL_LOADING=lazy` is an explicit diagnostic opt-out.

## Application startup and first-run routing

Startup proceeds as follows:

1. `main.dart` asks `AuthSessionStore` to restore the saved token and user.
2. Flutter starts `MaterialApp.router`, and the router checks for a session.
3. A signed-out learner is sent to `/auth`.
4. A signed-in learner is sent to `/start`, where `FirstRunGate` requests the
   authenticated profile from FastAPI.
5. FastAPI queries PostgreSQL for that learner's profile.
6. A missing profile opens onboarding.
7. An existing profile triggers active-plan and latest-generation requests.
8. The gate then opens the home screen or displays the current generation
   state.

The gate does not silently enter the app on infrastructure failures. It shows
a retry screen so “no profile” is never confused with “could not query profile.”

## Authentication

1. `AuthScreen` validates visible form fields.
2. `AuthController` calls `AuthApi` through its injected provider.
3. `ApiClient` posts to a public `/api/auth/...` endpoint.
4. the auth router validates a strict Pydantic command;
5. `AuthService` hashes/checks passwords or creates a disposable guest;
6. PostgreSQL stores only the SHA-256 hash of the random bearer token;
7. the response returns the raw token once with a user view;
8. `AuthSessionStore` persists the session and notifies `GoRouter`;
9. the router moves to first-run resolution.

Subsequent protected calls attach `Authorization: Bearer <token>`. Middleware
authenticates it and binds the user UUID before invoking a feature route.

## Profile and learning-plan generation

Plan generation proceeds as follows:

1. Onboarding or settings gives the profile to `PlpRepository`.
2. The repository sends it to the learning-plan router, which asks
   `LearningPlanService` to validate and store it for the authenticated learner.
3. The UI requests plan generation.
4. The planner rotates the profile's selected goals/interests, ranks a matching
   reviewed mission by direct context before broader theme compatibility, and
   uses a stable digest only to choose inside the same relevance tier.
5. `LearningPlanService` stores a pending job and deterministic plan outline, then
   returns the job ID immediately.
6. The PLP worker leases an eligible job from PostgreSQL.
7. The worker retrieves same-level vocabulary through one shared teaching-safety
   policy. Direct and related interest terms rank ahead of a separately limited
   general-context tier; current-revision terms are excluded and older-revision
   terms are deprioritized.
8. Deterministic preparation chooses two terms for the week. A vocabulary lesson
   owns them when present; otherwise the first teaching lesson pre-teaches them.
9. The worker asks Groq for constrained weekly surface text using the
   archetype's real-world evidence contract and level-specific support boundary.
   Recognizable real subjects are preferred, while volatile operational details
   must be dated from supplied evidence or labelled as simulated practice data.
10. The worker parses, validates, compiles, and audits the response.
11. Valid lessons and the final job state are published atomically.
12. Flutter polls through the repository and displays a pending, retry-wait,
   failure, or completed-plan state.

Onboarding generation and manual regeneration intentionally have different
job-reuse rules. Onboarding may reuse the learner's matching in-flight or idle
job while resolving first-run state. Settings sends `regenerate: true`: an
already in-flight manual regeneration is reused idempotently, but an `idle` JIT
job is superseded by a new revision. Flutter keeps the current plan usable,
tracks the returned new job ID, and shows the same generation-state banner used
on first run until the replacement Week 1 is published.

The outline contains all four weeks, but lesson bodies are generated one week
at a time. Week 1 is prepared first. Completing its checkpoint makes Week 2
eligible and queues the same durable generation job; later checkpoints unlock
Weeks 3 and 4 in the same way. The worker also reconciles eligible `idle` jobs
on every poll, so a process stop or a missed older queue transition cannot
leave a completed week permanently stuck. A provider rate limit moves the job
to `waiting_for_model`, and the worker resumes it after the bounded cooldown.

The provider does not choose prerequisite order, correct answers, or grading.
The deterministic planner and compiler own those decisions.

## Activity attempt

1. a lesson widget collects an answer;
2. `lesson_controller.dart` sends the activity ID, answer/evidence, and unique
   `submission_id` through `PlpRepository`;
3. authentication middleware binds the learner;
4. `PlpAttemptsMixin` verifies ownership and checks whether this submission was
   already processed;
5. deterministic grading uses the private server payload;
6. one transaction stores the attempt, evidence, progress transition, XP, and
   any generation/adaptation consequences;
7. the response includes correctness and safe feedback, not the entire private
   answer key;
8. Flutter updates the activity/lesson state from that response.

Retries are safe because `(user_id, submission_id)` is unique.

## Scripted pronunciation

Pronunciation analysis follows this pipeline:

1. Flutter records WAV audio and uploads it through `PronunciationApi`.
2. FastAPI enforces request-size and audio-duration limits.
3. SoundFile decodes the audio and resamples it to 16 kHz.
4. Quality gates reject non-finite, clipped, silent, or insufficient speech.
5. WhisperX validates the transcript while XLSR-53 CTC-GOP, the Arabic-L1
   models, and GOPT produce acoustic evidence.
6. The backend aligns target words, transcript words, and acoustic evidence.
7. Deterministic logic produces diagnostic scores and a separate conservative
   assessment. Completion requires sufficient transcript/completeness evidence,
   positive XLSR support for the expected phones, and no confirmed red error.
   Orange evidence is advisory when its strongest phone hypothesis still
   matches the expected phone. The learner-facing phone becomes verified green
   while its raw orange acoustic status remains in the response for diagnostics.
   Guidance is generated only for the final orange/red display set, so a phone
   promoted to verified green cannot also receive improvement instructions.
   Final orange produces non-diagnostic practice guidance; red evidence or an
   independent transcript-plus-phone contradiction produces a correction.
   An alternative hypothesis alone is inconclusive; when the word transcript
   also contradicts the target, the phone-identity disagreement becomes a
   correction.
8. For a PLP sound check, the assessment considers only the segmental IPA
   sounds assigned by the activity. Other phones remain visible as feedback but
   cannot block that activity's learning objective. Curriculum validation
   rejects non-segmental targets and any phrase missing an assigned sound.
9. Local logic or constrained Groq output adds coaching, and Flutter renders
   the result.

The response exposes `transcript_relation` separately from
`transcript_verified`, distinguishing exact text, phonetic compatibility,
fuzzy near matches, and mismatches. Only exact or phonetic-compatible single
words count as positive transcript evidence; a fuzzy near match may still be
analyzed but cannot create mastery. `phone_summaries.acoustic` counts raw model
states, while `phone_summaries.learner_facing` counts the final displayed
states. Raw diagnostic lists use the `acoustic_*` prefix. `overall_score` is the
only aggregate acoustic score; the former misleading `gop_score` alias is not
part of the contract.

If this request belongs to a PLP lesson, the backend also validates and records
the trusted acoustic result and reduced per-phone evidence as an activity
attempt. Client-supplied scores are not accepted as mastery evidence. A
transcript disagreement without a confirmed phone error is stored as
inconclusive and does not create mastery evidence. After three inconclusive
recordings of the same target, the target may complete for lesson progression,
but remains explicitly unverified and still creates no mastery evidence.
Lesson progress returns verified and unverified target keys separately, so this
state survives navigation and app reloads. Authoritative lesson and skill scores
use verified-target mastery; the whole-utterance acoustic estimate remains
diagnostic. Each target contributes at most one first-conclusive initial evidence
record, with the activity weight shared across its assigned targets. Pronunciation
skills retain spoken activities in weekly checkpoints.

## Grammar and dictionary

For grammar, Flutter sends text through `LanguageToolsApi`; the runtime obtains
a deterministic GECToR correction and may ask Groq to explain trusted changes.
The provider is not allowed to invent a correction when GECToR found none.

For dictionary lookup, the backend normalizes a single requested English word,
collects local lexical/pronunciation evidence, and uses constrained provider
text for learner-facing explanation/translation. It pins the response to the
requested word to prevent prompt drift.

## Roleplay session

A roleplay session proceeds as follows:

1. `ChatScreen` asks the REST API to start a selected scenario.
2. The backend freezes the scenario and initial objectives in PostgreSQL and
   returns a client session ID.
3. Flutter opens an authenticated WebSocket for that session.
   One socket cannot be rebound to a different session, and startup maintenance
   marks active sessions older than the six-hour persistence bound as timed-out
   abandonments after an interrupted process or failed socket bind.
4. Each learner turn carries a unique turn ID and text or audio. Flutter keeps
   typed Arabic/non-Latin text in the composer and directs the learner to
   Language Help instead of opening a provider turn.
5. The WebSocket authoritatively requires typed turns to contain Latin-script
   English before grammar correction, persistence, or Groq. A conservative
   local semantic gate also rejects unmistakable structural nonsense, such as
   function-word fragments, keyboard runs, impossible consonant runs, and
   repeated-character tokens. It deliberately preserves names, acronyms,
   ordinary short answers, and ambiguous but plausible English for contextual
   model classification. Audio is transcribed through the English recognizer.
   Valid input then receives an in-role reply using recent history and a strict
   evidence contract.
6. The backend rejects unsupported evidence and repairs repetitive replies.
7. Learner and assistant turns, objective state, and evidence are saved
   atomically before the reply reaches Flutter. A replayed turn ID returns the
   stored pair without another provider call; changed content conflicts.
8. Finalization takes the same user/session advisory lease as turn generation,
   recovers a stale `finalizing` marker left by a crashed worker, creates an
   evidence-aware evaluation, and stores one terminal result.

Audio roleplay uses target-free recognition confidence, pause/rate fluency, and
pitch variation. It does not reuse scripted phone-accuracy/completeness scores.
Task progress is available from persisted objective evidence. Language and
delivery scores remain nullable until their independent evidence thresholds are
met, and grammar remains nullable when GECToR did not evaluate enough transcript.

## News

1. `NewsTab` chooses a category/page and calls `NewsApi`.
2. the backend loads the authenticated learner profile for CEFR/interests;
3. `features/news/infrastructure/provider.py` asks the provider for up to ten candidates, removes
   removed/thin/truncated items, and keeps up to five useful articles;
4. Groq expands and adapts the selected summaries into four-to-six-sentence
   CEFR paragraphs without changing facts, and the backend caches the rewrites;
5. image URLs are not fetched directly by the app: the backend proxy validates
   scheme, DNS resolution, redirect target, peer IP, size, and content type;
6. Flutter renders articles and can request cached TTS.

## Settings, regeneration, reset, and signout

- A font change updates `AppState` and serializes a local preference write.
- Profile changes save to PostgreSQL before a new generation job starts.
- Regeneration saves the profile, requests an explicit manual regeneration,
  stores its returned job ID, and increments the plan refresh token. The shell
  remounts the active plan subtree so polling starts cleanly and visibly. An
  existing active plan stays available until the new Week 1 publishes.
- Reset deletes learner-owned learning/roleplay state through backend cascades
  while preserving a registered account.
- Registered signout revokes only the session. Guest signout deletes the
  unrecoverable guest and owned data.
- Session loss resets shared learner UI state and user-namespaced local stores
  prevent data from leaking between accounts.

## Operations dashboard polling and revocation

1. Vite proxies administrator sign-in to `/api/auth/signin`.
2. The dashboard accepts only a response whose user has `is_admin: true`, keeps
   the bearer session in `sessionStorage`, and sends it on every `/admin` call.
3. Middleware authenticates the token against PostgreSQL and rechecks current
   administrator status before the route runs.
4. `Dashboard.jsx` fetches operational summary tabs immediately and every ten
   seconds; user search and audit pages load on demand.
   Failures show a retryable error; no mock operational data is substituted.
5. Revocation requires a reason and confirmation. The backend locks the target,
   timestamps non-expired active sessions, and writes an audit row with actor,
   target, reason, count, and time in the same transaction.
6. A 401/403 clears the browser session and returns to administrator sign-in.
