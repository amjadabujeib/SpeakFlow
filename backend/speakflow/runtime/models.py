"""Loading and ownership of speech, grammar, TTS, and Practice model state."""

from __future__ import annotations

import asyncio
import os
import threading
import time
from dataclasses import dataclass
from pathlib import Path

import torch

from speakflow.features.pronunciation.infrastructure.acoustic.core import (
    LocalG2pCanonicalizer,
    arpabet_to_ipa,
)
from speakflow.features.pronunciation.infrastructure.acoustic.service import Wav2Vec2GoptScorer

try:
    import whisperx
    WHISPER_AVAILABLE = True
except ImportError:
    whisperx = None
    WHISPER_AVAILABLE = False

try:
    from kokoro import KModel, KPipeline
    KOKORO_AVAILABLE = True
except ImportError:
    KModel = KPipeline = None
    KOKORO_AVAILABLE = False

try:
    from gector import load_verb_dict
    from transformers import AutoTokenizer

    from speakflow.features.language_tools.infrastructure.grammar_model import load_self_contained_gector
    GECTOR_AVAILABLE = True
except ImportError:
    AutoTokenizer = load_self_contained_gector = load_verb_dict = None
    GECTOR_AVAILABLE = False

# --- Global Model Initialization ---

def _select_torch_device():
    if os.environ.get("FORCE_CPU", "").lower() in {"1", "true", "yes"}:
        print("FORCE_CPU is set; using CPU for all models.")
        return "cpu", "int8"

    if not torch.cuda.is_available():
        return "cpu", "int8"

    try:
        if torch.cuda.device_count() < 1:
            raise RuntimeError("torch reports CUDA available but no CUDA devices are visible")
        torch.cuda.set_device(0)
        torch.empty(1, device="cuda")
        return "cuda", "float16"
    except Exception as e:
        print(f"Warning: CUDA is not usable in this process ({e}). Falling back to CPU.")
        return "cpu", "int8"

device, compute_type = _select_torch_device()

whisper_model = None
align_model = None
align_metadata = None
kokoro_pipeline = None

gector_model = None
gector_tokenizer = None
gector_encode = None
gector_decode = None
grammar_pipeline = None

pronunciation_scorer = None
pronunciation_guide_canonicalizer = None
_model_load_lock = threading.RLock()
_kokoro_inference_lock = threading.Lock()
_failed_model_loads: set[str] = set()
_chat_inference_lock = asyncio.Lock()
_backend_root = Path(__file__).resolve().parents[2]
_gector_model_root = _backend_root / ".models" / "gector"
_gector_resource_root = _backend_root / "resources" / "gector"
_runtime_model_root = _backend_root / ".models" / "runtime"
_whisper_model_root = _runtime_model_root / "whisperx-small-en"
_whisper_align_root = _runtime_model_root / "whisperx-align"
_kokoro_model_root = _runtime_model_root / "kokoro"
_kokoro_voice_path = _kokoro_model_root / "voices" / "af_heart.pt"


@dataclass(frozen=True)
class RuntimeModelLoadReport:
    """Result of the blocking startup warm-up for every local model family."""

    models: dict[str, bool]
    duration_seconds: float

    @property
    def ready(self) -> bool:
        return all(self.models.values())

    @property
    def unavailable(self) -> tuple[str, ...]:
        return tuple(name for name, loaded in self.models.items() if not loaded)


def model_loading_mode() -> str:
    """Return the configured startup policy; eager is the project default."""
    value = os.environ.get("SPEAKFLOW_MODEL_LOADING", "eager").strip().lower()
    if value not in {"eager", "lazy"}:
        raise ValueError("SPEAKFLOW_MODEL_LOADING must be 'eager' or 'lazy'")
    return value


def _load_gector_model() -> bool:
    """Load the grammar correction model once."""
    global gector_model, gector_tokenizer, gector_encode, gector_decode
    if gector_model is not None and gector_tokenizer is not None:
        return True
    if not GECTOR_AVAILABLE or "gector" in _failed_model_loads:
        return False
    with _model_load_lock:
        if gector_model is not None and gector_tokenizer is not None:
            return True
        try:
            print("Loading GECToR RoBERTa grammar model...")
            model_id = str(_gector_model_root / "gector-roberta-base-5k")
            gector_tokenizer = AutoTokenizer.from_pretrained(
                model_id,
                local_files_only=True,
            )
            gector_model = load_self_contained_gector(model_id)
            gector_model.to(device)
            gector_model.eval()
            gector_encode, gector_decode = load_verb_dict(
                str(_gector_resource_root / "verb-form-vocab.txt")
            )
            print("GECToR loaded successfully!")
            return True
        except Exception as exc:
            print(f"Warning: Failed to load GECToR model: {exc}")
            gector_model = None
            gector_tokenizer = None
            _failed_model_loads.add("gector")
            return False


def _load_whisper_models() -> bool:
    """Load WhisperX transcription and alignment models once."""
    global whisper_model, align_model, align_metadata
    if whisper_model is not None and align_model is not None:
        return True
    if not WHISPER_AVAILABLE or "whisper" in _failed_model_loads:
        return False
    with _model_load_lock:
        if whisper_model is not None and align_model is not None:
            return True
        try:
            print(f"Loading WhisperX model (small.en) on {device}...")
            whisper_model = whisperx.load_model(
                str(_whisper_model_root),
                device,
                compute_type=compute_type,
                language="en",
                local_files_only=True,
            )
            align_model, align_metadata = whisperx.load_align_model(
                language_code="en",
                device=device,
                model_dir=str(_whisper_align_root),
                model_cache_only=True,
            )
            print("WhisperX loaded successfully!")
            return True
        except Exception as exc:
            print(f"Warning: Failed to load WhisperX on {device}: {exc}")
            if device != "cpu":
                try:
                    print("Retrying WhisperX on CPU...")
                    whisper_model = whisperx.load_model(
                        str(_whisper_model_root),
                        "cpu",
                        compute_type="int8",
                        language="en",
                        local_files_only=True,
                    )
                    align_model, align_metadata = whisperx.load_align_model(
                        language_code="en",
                        device="cpu",
                        model_dir=str(_whisper_align_root),
                        model_cache_only=True,
                    )
                    print("WhisperX loaded successfully on CPU.")
                    return True
                except Exception as cpu_exc:
                    print(f"Warning: Failed to load WhisperX on CPU: {cpu_exc}")
                    whisper_model = None
                    align_model = None
                    align_metadata = None
            whisper_model = None
            align_model = None
            align_metadata = None
            _failed_model_loads.add("whisper")
            return False


def _load_kokoro_pipeline() -> bool:
    """Load the Kokoro text-to-speech pipeline once."""
    global kokoro_pipeline
    if kokoro_pipeline is not None:
        return True
    if not KOKORO_AVAILABLE or "kokoro" in _failed_model_loads:
        return False
    with _model_load_lock:
        if kokoro_pipeline is not None:
            return True
        try:
            model = KModel(
                repo_id="hexgrad/Kokoro-82M",
                config=str(_kokoro_model_root / "config.json"),
                model=str(_kokoro_model_root / "kokoro-v1_0.pth"),
            ).to(device).eval()
            try:
                print(f"Loading Kokoro TTS pipeline on {device}...")
                kokoro_pipeline = KPipeline(
                    lang_code="a",
                    repo_id="hexgrad/Kokoro-82M",
                    model=model,
                    device=device,
                )
            except TypeError:
                kokoro_pipeline = KPipeline(
                    lang_code="a",
                    repo_id="hexgrad/Kokoro-82M",
                    model=model,
                )
                if hasattr(kokoro_pipeline, "model"):
                    kokoro_pipeline.model.to(device)
            kokoro_pipeline.load_voice(str(_kokoro_voice_path))
            print("Kokoro loaded successfully!")
            return True
        except Exception as exc:
            kokoro_pipeline = None
            _failed_model_loads.add("kokoro")
            print(f"Warning: Failed to load Kokoro: {exc}")
            return False


def _load_pronunciation_scorer() -> bool:
    """Load the complete local pronunciation scorer once."""
    global pronunciation_scorer
    if pronunciation_scorer is not None:
        return True
    if "pronunciation" in _failed_model_loads:
        return False
    with _model_load_lock:
        if pronunciation_scorer is not None:
            return True
        try:
            pronunciation_scorer = Wav2Vec2GoptScorer()
            print("XLSR-53 CTC-GOP + GOPT pronunciation scorer loaded successfully!")
            return True
        except Exception as exc:
            pronunciation_scorer = None
            _failed_model_loads.add("pronunciation")
            print(f"Error loading the production pronunciation scorer: {exc}")
            return False


def runtime_model_state() -> dict[str, bool]:
    """Return model availability without triggering any loading."""
    return {
        "whisperx": whisper_model is not None and align_model is not None,
        "grammar": gector_model is not None and gector_tokenizer is not None,
        "tts": kokoro_pipeline is not None,
        "pronunciation": pronunciation_scorer is not None,
    }


def eager_load_runtime_models() -> RuntimeModelLoadReport:
    """Synchronously warm every local inference capability during startup.

    Loading is intentionally sequential. The models share accelerator memory and
    the underlying libraries are safer to initialize one at a time. Individual
    loaders remain idempotent so endpoint-level calls are harmless fallbacks.
    """
    started = time.monotonic()
    print("Eagerly loading all local runtime models...")
    results = {
        "whisperx": _load_whisper_models(),
        "grammar": _load_gector_model(),
        "tts": _load_kokoro_pipeline(),
        "pronunciation": _load_pronunciation_scorer(),
    }
    report = RuntimeModelLoadReport(
        models=results,
        duration_seconds=time.monotonic() - started,
    )
    if report.ready:
        print(
            "All local runtime models are ready "
            f"({report.duration_seconds:.1f}s)."
        )
    else:
        print(
            "Warning: runtime model warm-up finished with unavailable models: "
            + ", ".join(report.unavailable)
        )
    return report


def pronunciation_guide(text: str) -> dict:
    """Return the same canonical phones later used by the strict scorer."""
    global pronunciation_guide_canonicalizer
    with _model_load_lock:
        if pronunciation_guide_canonicalizer is None:
            pronunciation_guide_canonicalizer = LocalG2pCanonicalizer()
        canonicalizer = pronunciation_guide_canonicalizer

    pronunciation = canonicalizer.canonicalize(text)
    words = [
        {
            "word": word.lower(),
            "ipa": "".join(arpabet_to_ipa(phone) for phone in phones),
            "phonemes": [arpabet_to_ipa(phone) for phone in phones],
        }
        for word, phones in zip(pronunciation.words, pronunciation.word_phones)
    ]
    return {
        "target": text.strip(),
        "ipa": " ".join(word["ipa"] for word in words),
        "phonemes": list(pronunciation.ipa_phones),
        "words": words,
    }
