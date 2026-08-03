# Runtime flows

These sequences show how major user actions cross files and authority
boundaries.

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
   `PlpService` to validate and store it for the authenticated learner.
3. The UI requests plan generation.
4. `PlpService` stores a pending job and deterministic plan outline, then
   returns the job ID immediately.
5. The PLP worker leases an eligible job from PostgreSQL.
6. The worker asks Groq for constrained weekly surface text.
7. The worker parses, validates, compiles, and audits the response.
8. Valid lessons and the final job state are published atomically.
9. Flutter polls through the repository and displays a pending, retry-wait,
   failure, or completed-plan state.

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
7. Deterministic logic produces scores and evidence.
8. Local logic or constrained Groq output adds coaching, and Flutter renders
   the result.

If this request belongs to a PLP lesson, the backend also validates and records
the trusted acoustic result as an activity attempt. Client-supplied scores are
not accepted as mastery evidence.

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
4. Each learner turn carries a unique turn ID and text or audio.
5. The runtime transcribes audio when needed, checks language, and asks Groq
   for an in-role reply using recent history and a strict evidence contract.
6. The backend rejects unsupported evidence and repairs repetitive replies.
7. Learner and assistant turns, objective state, and evidence are saved
   atomically before the reply reaches Flutter.
8. When Flutter requests finalization, the backend creates an evidence-aware
   evaluation, stores the terminal state, and returns category feedback.

Audio roleplay uses target-free recognition confidence, pause/rate fluency, and
pitch variation. It does not reuse scripted phone-accuracy/completeness scores.

## News

1. `NewsTab` chooses a category/page and calls `NewsApi`.
2. the backend loads the authenticated learner profile for CEFR/interests;
3. `runtime/news.py` calls the configured provider and caches safe rewrites;
4. Groq simplifies batches to the learner level without changing facts;
5. image URLs are not fetched directly by the app: the backend proxy validates
   scheme, DNS resolution, redirect target, peer IP, size, and content type;
6. Flutter renders articles and can request cached TTS.

## Settings, regeneration, reset, and signout

- A font change updates `AppState` and serializes a local preference write.
- Profile changes save to PostgreSQL before a new generation job starts.
- Regeneration stores the job ID and increments the plan refresh token; the
  shell remounts the active plan subtree so polling starts cleanly.
- Reset deletes learner-owned learning/roleplay state through backend cascades
  while preserving a registered account.
- Registered signout revokes only the session. Guest signout deletes the
  unrecoverable guest and owned data.
- Session loss resets shared learner UI state and user-namespaced local stores
  prevent data from leaking between accounts.
