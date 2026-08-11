# ML models and external providers

## Capability map

- **Speech recognition/alignment**
  - **Engine:** WhisperX small.en + align model
  - **Local/external:** local
  - **Runtime owner:** `runtime/models.py`

- **Scripted pronunciation features**
  - **Engine:** XLSR-53 CTC-GOP
  - **Local/external:** local
  - **Runtime owner:** `features/pronunciation/infrastructure/acoustic/gop.py`

- **Phone/word pronunciation scoring**
  - **Engine:** GOPT + Arabic-L1 calibrated models
  - **Local/external:** local
  - **Runtime owner:** `features/pronunciation/infrastructure/acoustic/service.py`

- **Grammar correction**
  - **Engine:** self-contained GECToR RoBERTa
  - **Local/external:** local
  - **Runtime owner:** `runtime/grammar_model.py`

- **Text-to-speech**
  - **Engine:** Kokoro
  - **Local/external:** local
  - **Runtime owner:** `features/language_tools/infrastructure/tts.py`

- **English phone/IPA data**
  - **Engine:** CMUdict, local G2P, WordNet
  - **Local/external:** local
  - **Runtime owner:** `features/pronunciation/infrastructure/acoustic/core.py` / curriculum

- **Explanations, roleplay, weekly surfaces**
  - **Engine:** Groq OpenAI-compatible API
  - **Local/external:** external
  - **Runtime owner:** runtime/PLP generators

- **Curriculum embeddings**
  - **Engine:** Ollama `embeddinggemma`
  - **Local/external:** local service
  - **Runtime owner:** PLP ingestion/retrieval

Weekly vocabulary keeps the source-attributed curriculum definition as its
semantic authority. Exact reviewed interest links are applied only to an
existing CEFR/headword/part-of-speech identity. One shared local policy requires
a noun, verb, adjective, or adverb with pronunciation evidence and a safe
learner definition. This prevents an untyped WordNet lookup from promoting
function words under an unrelated abbreviation or scientific sense.

Direct interest vocabulary is a hard retrieval tier; broader
Culture/Entertainment/Education themes may fill a genuine Music/History shortage
but cannot displace a direct term. Untagged vocabulary forms a separate general
context tier and must exceed a calibrated semantic threshold against the weekly
scenario. Its quota is capped at half the retrieved palette, preserving topical
grounding. A reviewed project gloss protects known ambiguous entries. Otherwise,
a Groq simplification is used only when local checks confirm that it is short,
non-circular, and anchored to the source meaning.

Retrieval over-fetches 24 safe candidates, and deterministic preparation teaches
two terms per week. The pair prefers one topical and one context-general term
when both exist, then fills from safe topical terms. A missing vocabulary-domain
lesson is not a missing vocabulary week: the compiler prepends the two sourced
cards to the first teaching lesson. Current-revision terms are excluded; older
revision terms are deprioritized so they can support deliberate review only when
fresh candidates are exhausted.

These controls are intentionally orthogonal: CEFR is a hard level filter,
interest is a topical classification, and the learning goal shapes mission and
scenario selection. A goal is not bulk-written onto lexical records. Instead,
the scenario-aware semantic query may admit an otherwise untagged general word
only when it is safe and strongly relevant to that week's task.

- **Live articles**
  - **Engine:** NewsAPI-compatible provider
  - **Local/external:** external/optional
  - **Runtime owner:** `features/news/infrastructure/provider.py`

## Eager model loading

ML imports and weights are expensive. `runtime/models.py` owns module-level
state and lock-protected load functions. The FastAPI lifespan invokes every
local loader sequentially and waits for WhisperX/alignment, GECToR, Kokoro, and
the pronunciation scorer before startup completes. Later requests reuse those
instances.

This intentionally trades a slower development startup and immediate GPU/RAM
allocation for predictable first-request latency. If any eager load fails, the
server can expose diagnostics but `/health` remains degraded. The explicit
`SPEAKFLOW_MODEL_LOADING=lazy` opt-out is intended for lightweight diagnostics
and isolated tests, not the normal app workflow.

The operations dashboard reads the same in-process model references. A
“Loaded” label means an object has been initialized in that FastAPI process; the
dashboard does not load a model, verify its assets, or run an inference probe.

`HF_HUB_OFFLINE=1` and `TRANSFORMERS_OFFLINE=1` ensure runtime behavior does
not silently download a different model. The verified private bundle is the
source of model assets.

## Model bundle

`backend/.models/speakflow-model-bundle.json` lists every managed asset with
destination, byte size, and SHA-256. Large source files may be split in the
private repository and reconstructed locally. A staged file is promoted only
after verification. The small pronunciation metadata contracts are tracked by
Git instead, so older bundles cannot replace them with machine-specific
training paths.

Managed runtime locations include:

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

These directories are runtime assets, not normal source files, and are ignored
by Git.

## Scripted pronunciation authority

Scripted practice has a known target. Its pipeline can therefore compare
expected and observed evidence:

1. decode and normalize to mono 16 kHz;
2. reject malformed, silent, clipped, or non-speech audio;
3. use WhisperX as a transcript/completeness guard;
4. canonicalize target text into CMU phones and IPA;
5. extract alignment-free 41-dimensional CTC-GOP features;
6. construct stable phone/context features;
7. run compatible GOPT and calibrated Arabic-L1 models;
8. apply deterministic thresholds and overall aggregation;
9. report a likely substitution only if independent counterfactual evidence is
   confident enough.

There is no legacy fallback scorer. Missing/incompatible assets fail closed so
the UI cannot display invented certainty.

The continuous accuracy and overall values are diagnostic quality estimates;
they are not treated as calibrated pass probabilities. The versioned
assessment contract separately checks utterance completeness, transcript
verification, positive XLSR support for every evaluated phone, and conservative
red phone diagnoses. Orange is advisory when the strongest XLSR hypothesis is
still the expected phone. The API preserves that raw orange status but exposes a
separate verified-green display status when transcript and phone identity agree.
Only phones that remain orange or red after that verification are eligible for
learner-facing guidance. Orange guidance remains explicitly non-diagnostic;
red evidence or independent transcript-plus-phone disagreement is a correction.
Another hypothesis is inconclusive unless the transcript independently
contradicts the target too. PLP drills scope blocking errors to their assigned
IPA target rather than failing `/p/` practice because of an uncertain vowel
elsewhere in a word.

The assessment authority is segmental. It does not certify contrastive stress,
rhythm, prominence, vowel reduction, or aspiration/VOT. Reviewed PLP drills must
declare one or more segmental IPA targets, and every assigned phrase must contain
each target in the canonical G2P sequence. Acoustic `overall_score`, accuracy,
fluency, and prosody remain diagnostic. PLP lesson scores and `skill_evidence`
instead use verified assigned-target mastery, preventing unrelated phones from
weakening an otherwise verified target.

The API keeps raw and learner-facing namespaces explicit:
`acoustic_flagged_phones`, `acoustic_uncertain_phones`, and the acoustic summary
describe model output; `learner_attention_phones` and the learner-facing summary
describe the final display decision. The device Phoneme Map averages acoustic
quality only from transcript-verified recordings and is labelled as diagnostic,
not as correctness or mastery.

Operational progression is deliberately separate from mastery: three
inconclusive recordings of the same PLP target unlock progression without
marking the pronunciation correct or writing skill evidence. Verified and
progress-only target sets are returned separately in durable lesson progress.
Weekly checkpoints use a recorded pronunciation drill for pronunciation skills
rather than treating a multiple-choice pronunciation fact as sound mastery.

## Target-free roleplay speech

Roleplay has no canonical sentence, so its speech metrics answer different
questions:

- recognition confidence: how certain WhisperX was about the transcript;
- fluency estimate: timing, rate, voiced duration, and long pauses;
- pitch variation: a descriptive vocal-range proxy.

It does not report phone accuracy, completeness, or reference prosody. The UI
keeps these estimates separate from grammar, vocabulary, interaction, and
scenario-goal evidence. Delivery scores require sufficient spoken turns, words,
voiced time, and alignment. General language scores require sufficient
conversation evidence. Grammar coverage is recorded independently so a missing
GECToR evaluation produces no grammar score rather than an invented 100.

## Grammar correction

The bundled GECToR checkpoint contains both its encoder and correction heads.
`runtime/grammar_model.py` constructs the local architecture and loads it
without an external base-model path. Groq may explain a trusted correction,
but it cannot create a correction if the deterministic/local pass found none.

## Groq boundaries

Groq is used where natural language variation is useful:

- concise chat and grammar explanations;
- dictionary/translation wording;
- roleplay drafts, replies, and evidence-aware evaluations;
- CEFR news rewrites;
- pronunciation coaching wording;
- constrained weekly learning-plan surface text.

Every high-authority use adds deterministic constraints afterward. Roleplay
objective evidence must match the current learner turn. Weekly output must use
exact requested IDs and pass semantic validation. News and dictionary output
is normalized and pinned to source material.

`GROQ_API_KEYS` is the sole credential contract and accepts one or more ordered,
comma-separated keys. The first key remains the credential for interactive
runtime features. The PLP writer round-robins the pool, places an individual
key into the provider-reported cooldown after HTTP 429, and tries another
available key without exposing credential material in logs or generation
metadata. Other provider failures remain visible and do not trigger credential
rotation.

News rewriting currently turns each selected source summary into a
four-to-six-sentence paragraph with explicit A1–B2 vocabulary and sentence
complexity rules. The provider is instructed to preserve facts, and the input
is treated as untrusted data.

## Ollama and curriculum retrieval

Ollama provides fixed-dimension `embeddinggemma` vectors for curriculum
concepts. Snapshot metadata records model identity and dimensions. Import fails
if those do not match configuration.

Retrieval prefers exact reviewed concept matches when the planner already knows
the required skill. Vector retrieval adds grounded candidates; it does not
replace prerequisite or CEFR policy.

The curriculum audit separately reports catalog composition, runtime lexical
roles, direct coverage, and teachable coverage. With the managed snapshot
currently used by the project, every one of the 44 supported A1–B2/interest cells
has at least eight direct terms that also have IPA and a safe learner definition.
That minimum supports two distinct terms in each of four weeks even when no
general-context term passes the stricter scenario threshold.

## News provider

`NEWSAPI_KEY` is optional. When configured, the backend requests category/page
feeds, filters fields, rewrites text at the learner CEFR, and sends images
through the secure proxy. When absent, the API returns an explicit provider
configuration failure rather than fake articles.
