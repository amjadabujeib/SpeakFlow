# ML models and external providers

## Capability map

- **Speech recognition/alignment**
  - **Engine:** WhisperX small.en + align model
  - **Local/external:** local
  - **Runtime owner:** `runtime/models.py`

- **Scripted pronunciation features**
  - **Engine:** XLSR-53 CTC-GOP
  - **Local/external:** local
  - **Runtime owner:** `runtime/pronunciation/gop.py`

- **Phone/word pronunciation scoring**
  - **Engine:** GOPT + Arabic-L1 calibrated models
  - **Local/external:** local
  - **Runtime owner:** `runtime/pronunciation/service.py`

- **Grammar correction**
  - **Engine:** self-contained GECToR RoBERTa
  - **Local/external:** local
  - **Runtime owner:** `runtime/grammar_model.py`

- **Text-to-speech**
  - **Engine:** Kokoro
  - **Local/external:** local
  - **Runtime owner:** `runtime/tts.py`

- **English phone/IPA data**
  - **Engine:** CMUdict, local G2P, WordNet
  - **Local/external:** local
  - **Runtime owner:** `runtime/pronunciation/core.py` / curriculum

- **Explanations, roleplay, weekly surfaces**
  - **Engine:** Groq OpenAI-compatible API
  - **Local/external:** external
  - **Runtime owner:** runtime/PLP generators

- **Curriculum embeddings**
  - **Engine:** Ollama `embeddinggemma`
  - **Local/external:** local service
  - **Runtime owner:** PLP ingestion/retrieval

- **Live articles**
  - **Engine:** NewsAPI-compatible provider
  - **Local/external:** external/optional
  - **Runtime owner:** `runtime/news.py`

## Lazy model loading

ML imports and weights are expensive. `runtime/models.py` owns module-level
state and lock-protected load functions. Startup records availability without
loading weights. The first request for a capability performs the load; later
requests reuse it.

This design keeps backend startup and `/health` fast, avoids allocating GPU/RAM
for unused features, and gives one place to handle CPU/GPU selection.

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

## Target-free roleplay speech

Roleplay has no canonical sentence, so its speech metrics answer different
questions:

- recognition confidence: how certain WhisperX was about the transcript;
- fluency estimate: timing, rate, voiced duration, and long pauses;
- pitch variation: a descriptive vocal-range proxy.

It does not report phone accuracy, completeness, or reference prosody. The UI
keeps these estimates separate from grammar, vocabulary, interaction, and
scenario-goal evidence.

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

## Ollama and curriculum retrieval

Ollama provides fixed-dimension `embeddinggemma` vectors for curriculum
concepts. Snapshot metadata records model identity and dimensions. Import fails
if those do not match configuration.

Retrieval prefers exact reviewed concept matches when the planner already knows
the required skill. Vector retrieval adds grounded candidates; it does not
replace prerequisite or CEFR policy.

## News provider

`NEWSAPI_KEY` is optional. When configured, the backend requests category/page
feeds, filters fields, rewrites text at the learner CEFR, and sends images
through the secure proxy. When absent, the API returns an explicit provider
configuration failure rather than fake articles.

## Training tree

Training is deliberately outside runtime imports:

- **`training/download_speechocean.py`** — Obtains SpeechOcean data used by
  training/evaluation preparation.

- **`training/prepare_l2_arctic.py`** — Normalizes L2-ARCTIC Arabic-speaker corpus
  metadata/audio.

- **`training/prepare_speechocean_ctc.py`** — Prepares SpeechOcean for the CTC pipeline.

- **`training/setup_ctc_model.py`** — Creates/configures the local XLSR-53 CTC
  checkpoint.

- **`training/extract_ctc_gop_batch.py`** — Batch-extracts CTC-GOP features.

- **`training/train_gopt_ctc.py`** — Trains the GOPT model on extracted features.

- **`training/fine_tune_ctc_head_arabic.py`** — Fine-tunes CTC components for the
  Arabic-L1 setup.

- **`training/train_arabic_pronunciation_ctc_v3.py`** — Trains calibrated v3 Arabic
  pronunciation models.

- **`training/pronunciation_data.py`** — General pronunciation dataset records/loaders.

- **`training/pronunciation_training_data.py`** — Training-specific feature/label
  preparation.

- **`training/pronunciation_training_models.py`** — Training model definitions and
  serialization helpers.

- **`training/pronunciation_training_run.py`** — Shared training/evaluation run
  orchestration.

See `backend/training/README.md` for dataset-specific commands. Raw datasets and
derived checkpoints are not application source and must not be committed.
