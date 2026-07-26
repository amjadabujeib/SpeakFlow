"""Strict local pronunciation scoring with Kaldi GOP features and GOPT.

This module intentionally has no alternate scoring path. A request either gets
scores from the validated Kaldi -> GOPT pipeline or fails with an actionable
error.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import threading
import unicodedata
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

import numpy as np
import torch
from g2p_en import G2p
from g2p_en.expand import normalize_numbers
from nltk import pos_tag
from xgboost import XGBClassifier, XGBRegressor

from gopt_models.gopt import GOPT
from pronunciation_features import (
    PHONE_CONTEXT_FEATURE_DIM,
    build_phone_context_features,
)


MAX_GOPT_PHONES = 50
MAX_TARGET_PHONES = 200
GOPT_FEATURE_DIM = 84
GOPT_NORM_MEAN = 3.203
GOPT_NORM_STD = 4.045
KALDI_IMAGE = "custom-kaldi"
KALDI_CONTAINER = "english_tutor_kaldi_gop_v2"
KALDI_SHARED_ROOT = Path("/tmp/english_tutor_kaldi")
# Compatibility constants for older research helpers below. Production v2
# loads its green/severity and shrunken phone-specific red policy from the
# versioned model metadata instead of hard-coding a universal red threshold.
PHONE_ERROR_PROBABILITY_THRESHOLD = 0.30
PHONE_WARNING_PROBABILITY_THRESHOLD = 0.15
PHONE_SCORE_AT_ERROR_THRESHOLD = 60.0
OVERALL_SCORE_WEIGHTS = {
    "accuracy": 0.45,
    "fluency": 0.20,
    "prosody": 0.15,
    "completeness": 0.20,
}
WORD_OVERALL_SCORE_WEIGHTS = {
    "accuracy": 0.80,
    "prosody": 0.20,
}

# Exact first-occurrence ordering produced by GOPT's official
# gen_seq_data_phn.py on the SpeechOcean762 training split.
GOPT_PHONE_TO_ID = {
    phone: index
    for index, phone in enumerate(
        (
            "W", "IY", "K", "AO", "L", "IH", "T", "B", "EH", "R",
            "Z", "OW", "TH", "F", "AY", "V", "AH", "N", "UW", "S",
            "G", "AA", "M", "P", "NG", "HH", "EY", "SH", "AE", "D",
            "UH", "AW", "DH", "ER", "Y", "JH", "CH", "OY", "ZH",
        )
    )
}

ARPABET_TO_IPA = {
    "AA": "ɑ", "AE": "æ", "AH": "ʌ", "AO": "ɔ", "AW": "aʊ",
    "AY": "aɪ", "B": "b", "CH": "tʃ", "D": "d", "DH": "ð",
    "EH": "ɛ", "ER": "ɝ", "EY": "eɪ", "F": "f", "G": "ɡ",
    "HH": "h", "IH": "ɪ", "IY": "i", "JH": "dʒ", "K": "k",
    "L": "l", "M": "m", "N": "n", "NG": "ŋ", "OW": "oʊ",
    "OY": "ɔɪ", "P": "p", "R": "ɹ", "S": "s", "SH": "ʃ",
    "T": "t", "TH": "θ", "UH": "ʊ", "UW": "u", "V": "v",
    "W": "w", "Y": "j", "Z": "z", "ZH": "ʒ",
}


class PronunciationScoringError(RuntimeError):
    """A production scorer error that is safe to expose to the API client."""

    def __init__(self, message: str, status_code: int = 503):
        super().__init__(message)
        self.status_code = status_code


@dataclass(frozen=True)
class CanonicalPronunciation:
    text: str
    words: tuple[str, ...]
    word_phones: tuple[tuple[str, ...], ...]

    @property
    def phones(self) -> tuple[str, ...]:
        return tuple(phone for word in self.word_phones for phone in word)

    @property
    def pure_phones(self) -> tuple[str, ...]:
        return tuple(_pure_phone(phone) for phone in self.phones)

    @property
    def ipa_phones(self) -> tuple[str, ...]:
        return tuple(arpabet_to_ipa(phone) for phone in self.phones)


def _pure_phone(phone: str) -> str:
    return re.sub(r"[012]$", "", phone.upper())


def arpabet_to_ipa(phone: str) -> str:
    phone = phone.upper()
    match = re.fullmatch(r"([A-Z]+)([012])?", phone)
    if not match:
        raise PronunciationScoringError(f"Unsupported canonical phone: {phone}", 422)
    base, stress = match.groups()
    if base not in ARPABET_TO_IPA:
        raise PronunciationScoringError(f"Unsupported canonical phone: {phone}", 422)

    ipa = ARPABET_TO_IPA[base]
    if base == "AH" and stress == "0":
        ipa = "ə"
    elif base == "ER" and stress == "0":
        ipa = "ɚ"
    if stress == "1":
        ipa = "ˈ" + ipa
    elif stress == "2":
        ipa = "ˌ" + ipa
    return ipa


def _normalized_english_tokens(text: str) -> tuple[str, ...]:
    value = unicodedata.normalize("NFD", str(text)).replace("’", "'")
    value = "".join(char for char in value if unicodedata.category(char) != "Mn")
    value = re.sub(r"(?<=[a-z])(?=[A-Z])", " ", value)
    value = re.sub(r"\bi\.e\.", "that is", value, flags=re.IGNORECASE)
    value = re.sub(r"\be\.g\.", "for example", value, flags=re.IGNORECASE)
    value = normalize_numbers(value)
    return tuple(match.group(0) for match in re.finditer(r"[A-Za-z]+(?:'[A-Za-z]+)?", value))


def normalized_english_words(text: str) -> tuple[str, ...]:
    """Normalize written English exactly once for G2P and ASR comparison."""
    return tuple(token.lower() for token in _normalized_english_tokens(text))


def calculate_overall_score(scores: dict) -> int:
    """Combine the four user-facing aspects into the displayed score."""
    weighted = sum(
        float(scores[name]) * weight for name, weight in OVERALL_SCORE_WEIGHTS.items()
    )
    return int(np.clip(round(weighted), 0, 100))


def calculate_word_overall_score(scores: dict) -> int:
    """Weight isolated words by pronunciation rather than sentence fluency."""
    weighted = sum(
        float(scores[name]) * weight
        for name, weight in WORD_OVERALL_SCORE_WEIGHTS.items()
    )
    return int(np.clip(round(weighted), 0, 100))


def phone_quality_scores(error_probability: np.ndarray) -> np.ndarray:
    """Legacy research mapping retained for reproducibility.

    Production v2 never converts class probability into quality; it predicts
    human-label severity directly. Older evaluation scripts still import this
    function, so keep its former deterministic behavior isolated here.
    """
    probability = np.clip(np.asarray(error_probability, dtype=np.float64), 0.0, 1.0)
    below = 100.0 - (
        (100.0 - PHONE_SCORE_AT_ERROR_THRESHOLD)
        * probability
        / PHONE_ERROR_PROBABILITY_THRESHOLD
    )
    above = PHONE_SCORE_AT_ERROR_THRESHOLD * (
        (1.0 - probability) / (1.0 - PHONE_ERROR_PROBABILITY_THRESHOLD)
    )
    return np.clip(
        np.where(probability < PHONE_ERROR_PROBABILITY_THRESHOLD, below, above),
        0.0,
        100.0,
    )


def conservative_phone_aggregate(phone_scores: Sequence[float]) -> int:
    """Legacy weakest-quartile aggregate retained for research comparisons."""
    values = np.asarray(tuple(phone_scores), dtype=np.float64)
    if values.size == 0:
        return 0
    weakest_count = max(1, int(np.ceil(values.size * 0.25)))
    weakest_mean = float(np.mean(np.sort(values)[:weakest_count]))
    score = (0.70 * float(np.mean(values))) + (0.30 * weakest_mean)
    return int(np.clip(round(score), 0, 100))


class LocalG2pCanonicalizer:
    def __init__(self):
        # g2p-en uses CMUdict where a word is known and its local neural model
        # for unseen words. It is the single canonical pronunciation source;
        # there is no eSpeak or network fallback.
        self._g2p = G2p()

    def canonicalize(self, text: str) -> CanonicalPronunciation:
        written_tokens = _normalized_english_tokens(text)
        words = tuple(token.lower() for token in written_tokens)
        if not words:
            raise PronunciationScoringError(
                "Enter an English word or sentence containing letters.", 400
            )

        word_phones: list[tuple[str, ...]] = []
        missing: list[str] = []
        tagged_words = pos_tag(list(words))
        for written, word, (_, part_of_speech) in zip(written_tokens, words, tagged_words):
            if written.isupper() and len(written) > 1 and word not in self._g2p.cmu:
                generated = [
                    phone
                    for letter in written.lower()
                    for phone in self._g2p.cmu[letter][0]
                ]
            elif word in self._g2p.homograph2features:
                first, second, first_pos = self._g2p.homograph2features[word]
                generated = first if part_of_speech.startswith(first_pos) else second
            elif word in self._g2p.cmu:
                generated = self._g2p.cmu[word][0]
            else:
                generated = self._g2p.predict(word.replace("'", ""))
            phones = tuple(str(phone).upper() for phone in generated)
            if not phones or any(_pure_phone(phone) not in GOPT_PHONE_TO_ID for phone in phones):
                missing.append(word)
                continue
            if len(phones) > MAX_GOPT_PHONES:
                raise PronunciationScoringError(
                    f'The target word "{word}" has {len(phones)} phones; a single word supports at most {MAX_GOPT_PHONES}.',
                    422,
                )
            word_phones.append(phones)

        if missing:
            unknown = ", ".join(sorted(set(missing)))
            raise PronunciationScoringError(
                f"The local English G2P model could not pronounce: {unknown}.", 422
            )

        pronunciation = CanonicalPronunciation(
            text=" ".join(word.upper() for word in words),
            words=tuple(word.upper() for word in words),
            word_phones=tuple(word_phones),
        )
        if len(pronunciation.phones) > MAX_TARGET_PHONES:
            raise PronunciationScoringError(
                f"The target has {len(pronunciation.phones)} phones; this scorer supports at most {MAX_TARGET_PHONES}.",
                422,
            )
        return pronunciation


# Retain the old import name for local tests and research scripts. Production
# behavior is the unified CMUdict + neural local G2P canonicalizer above.
CmuCanonicalizer = LocalG2pCanonicalizer


def _position_marked(phones: Sequence[str]) -> tuple[str, ...]:
    if len(phones) == 1:
        return (f"{phones[0]}_S",)
    return tuple(
        f"{phone}_{'B' if index == 0 else 'E' if index == len(phones) - 1 else 'I'}"
        for index, phone in enumerate(phones)
    )


def _parse_kaldi_matrix(path: Path) -> np.ndarray:
    rows: list[list[float]] = []
    inside = False
    current: list[float] = []
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not inside:
            if "[" not in line:
                continue
            line = line.split("[", 1)[1].strip()
            inside = True
            current = []
        if "]" in line:
            line = line.split("]", 1)[0].strip()
            if line:
                current.extend(float(value) for value in line.split())
            rows.append(current)
            inside = False
            current = []
        elif line:
            current.extend(float(value) for value in line.split())

    if inside or not rows:
        raise PronunciationScoringError("Kaldi returned an empty or malformed GOP matrix.")
    matrix = np.asarray(rows, dtype=np.float32)
    if matrix.ndim != 2 or matrix.shape[1] != GOPT_FEATURE_DIM + 1:
        raise PronunciationScoringError(
            f"Kaldi returned GOP shape {tuple(matrix.shape)}; expected N x {GOPT_FEATURE_DIM + 1}."
        )
    if not np.isfinite(matrix).all():
        raise PronunciationScoringError("Kaldi returned non-finite GOP values.")
    return matrix


class KaldiGoptScorer:
    _docker_lock = threading.Lock()

    def __init__(self, backend_dir: Path | None = None):
        self.backend_dir = backend_dir or Path(__file__).resolve().parent
        weights = self.backend_dir / "pretrained_models/gopt_librispeech/best_audio_model.pth"
        if not weights.is_file():
            raise PronunciationScoringError(f"GOPT weights are missing: {weights}")

        model = GOPT(embed_dim=24, num_heads=1, depth=3, input_dim=GOPT_FEATURE_DIM)
        wrapped = torch.nn.DataParallel(model)
        state = torch.load(weights, map_location="cpu", weights_only=True)
        wrapped.load_state_dict(state, strict=True)
        wrapped.float().eval()
        self.model = wrapped

        classifier_dir = self.backend_dir / "pretrained_models/arabic_pronunciation_v2"
        classifier_path = classifier_dir / "phone_error_model.json"
        severe_classifier_path = classifier_dir / "phone_severe_error_model.json"
        severity_path = classifier_dir / "phone_severity_model.json"
        metadata_path = classifier_dir / "metadata.json"
        required_assets = (
            classifier_path,
            severe_classifier_path,
            severity_path,
            metadata_path,
        )
        if not all(path.is_file() for path in required_assets):
            raise PronunciationScoringError(
                f"Arabic pronunciation-v2 assets are missing under: {classifier_dir}"
            )
        phone_classifier = XGBClassifier()
        phone_classifier.load_model(classifier_path)
        self.phone_classifier = phone_classifier
        severe_classifier = XGBClassifier()
        severe_classifier.load_model(severe_classifier_path)
        self.phone_severe_classifier = severe_classifier
        severity_model = XGBRegressor()
        severity_model.load_model(severity_path)
        self.phone_severity_model = severity_model
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        try:
            calibration = metadata["calibration"]
            self.probability_slope = float(calibration["error"]["slope"])
            self.probability_intercept = float(calibration["error"]["intercept"])
            self.severe_probability_slope = float(
                calibration["severe_error"]["slope"]
            )
            self.severe_probability_intercept = float(
                calibration["severe_error"]["intercept"]
            )
            self.severity_slope = float(calibration["phone_severity"]["slope"])
            self.severity_intercept = float(
                calibration["phone_severity"]["intercept"]
            )
            self.quality_severity_regressor_weight = float(
                calibration["quality_severity_regressor_weight"]
            )
            self.global_red_severe_probability = float(
                calibration["global_red_severe_probability"]
            )
            self.red_severe_probability_by_phone_id = {
                int(phone_id): float(threshold)
                for phone_id, threshold in calibration[
                    "red_severe_probability_by_phone_id"
                ].items()
            }
            status_policy = metadata["status_policy"]
            self.warning_probability_threshold = float(
                status_policy["green_max_error_probability"]
            )
            self.warning_severity_threshold = float(
                status_policy["green_max_error_severity"]
            )
            self.red_minimum_severity = float(
                status_policy["red_min_error_severity"]
            )
            feature_schema = metadata["feature_schema"]
            if int(feature_schema["phone_error_legacy"]) != 126:
                raise ValueError("phone-error feature width is not 126")
            if int(feature_schema["phone_context"]) != PHONE_CONTEXT_FEATURE_DIM:
                raise ValueError("phone-context feature width does not match runtime")
            metadata_phone_to_id = {
                str(phone): int(phone_id)
                for phone, phone_id in metadata["phone_to_id"].items()
            }
            if metadata_phone_to_id != GOPT_PHONE_TO_ID:
                raise ValueError("canonical phone mapping does not match runtime")
        except (KeyError, TypeError, ValueError) as exc:
            raise PronunciationScoringError(
                f"Arabic pronunciation-v2 metadata is missing or malformed: {metadata_path}"
            ) from exc

        numeric_policy = (
            self.probability_slope,
            self.probability_intercept,
            self.severe_probability_slope,
            self.severe_probability_intercept,
            self.severity_slope,
            self.severity_intercept,
            self.quality_severity_regressor_weight,
            self.global_red_severe_probability,
            self.warning_probability_threshold,
            self.warning_severity_threshold,
            self.red_minimum_severity,
            *self.red_severe_probability_by_phone_id.values(),
        )
        if not all(np.isfinite(value) for value in numeric_policy):
            raise PronunciationScoringError(
                f"Arabic pronunciation-v2 metadata contains non-finite values: {metadata_path}"
            )
        probability_thresholds = (
            self.global_red_severe_probability,
            self.warning_probability_threshold,
            self.warning_severity_threshold,
            self.red_minimum_severity,
            self.quality_severity_regressor_weight,
            *self.red_severe_probability_by_phone_id.values(),
        )
        if not all(0.0 <= value <= 1.0 for value in probability_thresholds):
            raise PronunciationScoringError(
                f"Arabic pronunciation-v2 thresholds must be between zero and one: {metadata_path}"
            )
        if self.phone_classifier.get_booster().num_features() != 126:
            raise PronunciationScoringError("Phone-error model feature width is incompatible.")
        if (
            self.phone_severe_classifier.get_booster().num_features()
            != PHONE_CONTEXT_FEATURE_DIM
            or self.phone_severity_model.get_booster().num_features()
            != PHONE_CONTEXT_FEATURE_DIM
        ):
            raise PronunciationScoringError("Phone-context model feature width is incompatible.")
        self.canonicalizer = LocalG2pCanonicalizer()
        KALDI_SHARED_ROOT.mkdir(parents=True, exist_ok=True)

    def _ensure_container(self) -> None:
        image = subprocess.run(
            ["docker", "image", "inspect", KALDI_IMAGE], capture_output=True, text=True
        )
        if image.returncode != 0:
            raise PronunciationScoringError(
                "The custom-kaldi Docker image is not built. Run: docker build -t custom-kaldi backend/kaldi_docker"
            )

        inspect = subprocess.run(
            ["docker", "inspect", "-f", "{{.Config.Image}} {{.State.Running}}", KALDI_CONTAINER],
            capture_output=True,
            text=True,
        )
        if inspect.returncode == 0:
            configured_image, running = inspect.stdout.strip().split(maxsplit=1)
            if configured_image != KALDI_IMAGE:
                raise PronunciationScoringError(
                    f"Docker container {KALDI_CONTAINER} uses {configured_image}, not {KALDI_IMAGE}."
                )
            if running != "true":
                started = subprocess.run(
                    ["docker", "start", KALDI_CONTAINER], capture_output=True, text=True
                )
                if started.returncode != 0:
                    raise PronunciationScoringError(
                        f"Could not start the Kaldi container: {started.stderr.strip()}"
                    )
            return

        started = subprocess.run(
            [
                "docker", "run", "-d", "--name", KALDI_CONTAINER,
                "--mount", f"type=bind,src={KALDI_SHARED_ROOT},dst=/shared",
                "--mount", f"type=bind,src={self.backend_dir / 'kaldi_docker/extract_gop.sh'},dst=/usr/local/bin/english-tutor-extract-gop,readonly",
                KALDI_IMAGE, "tail", "-f", "/dev/null",
            ],
            capture_output=True,
            text=True,
        )
        if started.returncode != 0:
            raise PronunciationScoringError(
                f"Could not create the Kaldi container: {started.stderr.strip()}"
            )

    def _write_job(self, job_dir: Path, audio_path: Path, pronunciation: CanonicalPronunciation) -> None:
        shutil.copyfile(audio_path, job_dir / "audio.wav")
        utterance = "practice"
        (job_dir / "wav.scp").write_text(
            f"{utterance} /shared/{job_dir.name}/audio.wav\n", encoding="utf-8"
        )
        (job_dir / "text").write_text(f"{utterance} {pronunciation.text}\n", encoding="utf-8")
        (job_dir / "utt2spk").write_text(f"{utterance} learner\n", encoding="utf-8")
        (job_dir / "spk2utt").write_text(f"learner {utterance}\n", encoding="utf-8")

        lexicon_lines = [
            f"{word} {' '.join(phones)}"
            for word, phones in zip(pronunciation.words, pronunciation.word_phones)
        ]
        (job_dir / "lexicon.txt").write_text(
            "\n".join(sorted(set(lexicon_lines))) + "\n", encoding="utf-8"
        )
        phone_lines = [
            f"{utterance}.{index} {' '.join(_position_marked(phones))}"
            for index, phones in enumerate(pronunciation.word_phones)
        ]
        (job_dir / "text-phone").write_text("\n".join(phone_lines) + "\n", encoding="utf-8")

    def _extract(self, audio_path: Path, pronunciation: CanonicalPronunciation) -> np.ndarray:
        job_dir = KALDI_SHARED_ROOT / uuid.uuid4().hex
        job_dir.mkdir(parents=False)
        try:
            self._write_job(job_dir, audio_path, pronunciation)
            with self._docker_lock:
                self._ensure_container()
                result = subprocess.run(
                    [
                        "docker", "exec", KALDI_CONTAINER,
                        "bash", "/usr/local/bin/english-tutor-extract-gop", job_dir.name,
                    ],
                    capture_output=True,
                    text=True,
                    timeout=180,
                )
            if result.returncode != 0:
                details = (result.stderr or result.stdout).strip()
                raise PronunciationScoringError(f"Kaldi GOP extraction failed: {details[-1200:]}")

            matrix = _parse_kaldi_matrix(job_dir / "features.txt")
            if matrix.shape[0] != len(pronunciation.phones):
                raise PronunciationScoringError(
                    f"Kaldi aligned {matrix.shape[0]} phones, but the target contains {len(pronunciation.phones)}."
                )

            pure_table = {}
            for line in (job_dir / "phones-pure.txt").read_text(encoding="utf-8").splitlines():
                symbol, phone_id = line.split()
                pure_table[int(phone_id)] = symbol
            aligned = tuple(pure_table[int(round(value))] for value in matrix[:, 0])
            if aligned != pronunciation.pure_phones:
                raise PronunciationScoringError(
                    f"Kaldi phone alignment mismatch: expected {' '.join(pronunciation.pure_phones)}, got {' '.join(aligned)}."
                )
            return matrix[:, 1:]
        finally:
            shutil.rmtree(job_dir, ignore_errors=True)

    def score(self, audio_path: str | Path, target_text: str) -> dict:
        pronunciation = self.canonicalizer.canonicalize(target_text)
        raw_features = self._extract(Path(audio_path), pronunciation)

        count = raw_features.shape[0]
        normalized_features = (raw_features - GOPT_NORM_MEAN) / GOPT_NORM_STD
        all_phone_ids = np.asarray(
            [GOPT_PHONE_TO_ID[phone] for phone in pronunciation.pure_phones], dtype=np.int64
        )

        # Keep word boundaries intact when a sentence needs more than one GOPT
        # window. Splitting the middle of a word distorts its contextual
        # representation and the utterance-level fluency/prosody heads.
        chunk_ranges = []
        chunk_start = 0
        chunk_length = 0
        phone_offset = 0
        for word in pronunciation.word_phones:
            word_length = len(word)
            if chunk_length and chunk_length + word_length > MAX_GOPT_PHONES:
                chunk_ranges.append((chunk_start, phone_offset))
                chunk_start = phone_offset
                chunk_length = 0
            chunk_length += word_length
            phone_offset += word_length
        chunk_ranges.append((chunk_start, phone_offset))

        chunk_count = len(chunk_ranges)
        features = np.zeros(
            (chunk_count, MAX_GOPT_PHONES, GOPT_FEATURE_DIM), dtype=np.float32
        )
        phone_ids = np.full((chunk_count, MAX_GOPT_PHONES), -1, dtype=np.int64)
        chunk_lengths = []
        for chunk_index, (start, end) in enumerate(chunk_ranges):
            length = end - start
            features[chunk_index, :length] = normalized_features[start:end]
            phone_ids[chunk_index, :length] = all_phone_ids[start:end]
            chunk_lengths.append(length)

        with torch.inference_mode():
            tensor_features = torch.from_numpy(features)
            tensor_phone_ids = torch.from_numpy(phone_ids)
            base_outputs = self.model(tensor_features, tensor_phone_ids)
        _, _, fluency, prosody, _, _, _, _, _ = base_outputs

        chunk_weights = np.asarray(chunk_lengths, dtype=np.float32)

        def percent(value: torch.Tensor) -> int:
            values = value[:, 0].detach().cpu().numpy()
            if values.shape != (chunk_count,) or not np.isfinite(values).all():
                raise PronunciationScoringError(
                    "GOPT returned malformed fluency/prosody values."
                )
            weighted = float(np.average(values, weights=chunk_weights))
            return int(np.clip(round(weighted * 50.0), 0, 100))

        one_hot = np.eye(40, dtype=np.float32)[all_phone_ids + 1]
        position = np.arange(count, dtype=np.float32)[:, None] / max(1, count - 1)
        length = np.full(
            (count, 1), min(count, MAX_GOPT_PHONES) / MAX_GOPT_PHONES, dtype=np.float32
        )
        classifier_features = np.concatenate(
            (normalized_features, one_hot, position, length), axis=1
        )
        word_lengths = tuple(len(phones) for phones in pronunciation.word_phones)
        context_features = build_phone_context_features(
            raw_features,
            all_phone_ids,
            pronunciation.phones,
            word_lengths,
            normalization_mean=GOPT_NORM_MEAN,
            normalization_std=GOPT_NORM_STD,
        )

        def calibrated_probability(
            raw_probability: np.ndarray,
            slope: float,
            intercept: float,
            name: str,
        ) -> np.ndarray:
            values = np.asarray(raw_probability, dtype=np.float64)
            if values.shape != (count,) or not np.isfinite(values).all():
                raise PronunciationScoringError(
                    f"The {name} model returned malformed probabilities."
                )
            clipped = np.clip(values, 1e-6, 1.0 - 1e-6)
            logits = np.log(clipped / (1.0 - clipped))
            calibrated_logits = np.clip((slope * logits) + intercept, -30.0, 30.0)
            result = 1.0 / (1.0 + np.exp(-calibrated_logits))
            if not np.isfinite(result).all():
                raise PronunciationScoringError(
                    f"The calibrated {name} probabilities are non-finite."
                )
            return result

        error_probability = calibrated_probability(
            self.phone_classifier.predict_proba(classifier_features)[:, 1],
            self.probability_slope,
            self.probability_intercept,
            "phone-error",
        )
        severe_error_probability = calibrated_probability(
            self.phone_severe_classifier.predict_proba(context_features)[:, 1],
            self.severe_probability_slope,
            self.severe_probability_intercept,
            "severe-phone-error",
        )
        raw_severity = np.asarray(
            self.phone_severity_model.predict(context_features), dtype=np.float64
        )
        if raw_severity.shape != (count,) or not np.isfinite(raw_severity).all():
            raise PronunciationScoringError(
                "The phone-severity model returned malformed values."
            )
        regressor_error_severity = np.clip(
            (self.severity_slope * raw_severity) + self.severity_intercept,
            0.0,
            1.0,
        )
        if not np.isfinite(regressor_error_severity).all():
            raise PronunciationScoringError(
                "The calibrated phone-severity values are non-finite."
            )
        error_severity = np.clip(
            self.quality_severity_regressor_weight * regressor_error_severity
            + (1.0 - self.quality_severity_regressor_weight) * error_probability,
            0.0,
            1.0,
        )
        # The displayed quality signal blends the human-label severity regressor
        # with independently calibrated any-error evidence. Both ingredients are
        # also returned separately; no classifier probability is renamed quality.
        phone_scores = np.rint(100.0 * (1.0 - error_severity)).astype(int)
        analysis = []
        mistakes = []
        uncertain = []
        for phone_index, (
            arpabet,
            ipa,
            phone_id,
            score,
            error_chance,
            severe_chance,
            severity,
        ) in enumerate(zip(
            pronunciation.phones,
            pronunciation.ipa_phones,
            all_phone_ids.tolist(),
            phone_scores.tolist(),
            error_probability.tolist(),
            severe_error_probability.tolist(),
            error_severity.tolist(),
        )):
            red_threshold = self.red_severe_probability_by_phone_id.get(
                int(phone_id), self.global_red_severe_probability
            )
            if severe_chance >= red_threshold and severity >= self.red_minimum_severity:
                status = "incorrect"
            elif (
                error_chance > self.warning_probability_threshold + 1e-9
                or severity > self.warning_severity_threshold + 1e-9
            ):
                status = "warning"
            else:
                status = "correct"
            item = {
                "phone_index": phone_index,
                "char": ipa,
                "arpabet": arpabet,
                "status": status,
                "score": score,
                "correct_probability": round((1.0 - error_chance) * 100.0, 1),
                "error_probability": round(error_chance * 100.0, 1),
                "severe_error_probability": round(severe_chance * 100.0, 1),
                "error_severity": round(severity * 100.0, 1),
                "model_error_severity": round(
                    float(regressor_error_severity[phone_index]) * 100.0, 1
                ),
            }
            analysis.append(item)
            evidence = {
                "phone_index": phone_index,
                "phoneme": ipa,
                "arpabet": arpabet,
                "status": status,
                "score": score,
                "error_probability": item["error_probability"],
                "severe_error_probability": item["severe_error_probability"],
                "error_severity": item["error_severity"],
            }
            if status == "incorrect":
                mistakes.append(evidence)
            elif status == "warning":
                uncertain.append(evidence)

        word_scores = []
        offset = 0
        for word, phones in zip(pronunciation.words, pronunciation.word_phones):
            length = len(phones)
            word_phone_scores = phone_scores[offset:offset + length]
            word_severity = float(np.mean(error_severity[offset:offset + length]))
            score = int(np.clip(round(100.0 * (1.0 - word_severity)), 0, 100))
            word_scores.append(
                {
                    "word": word.lower(),
                    "accuracy": score,
                    "weakest_phone_score": int(np.min(word_phone_scores)),
                    "error_severity": round(word_severity * 100.0, 1),
                    "phone_start": offset,
                    "phone_end": offset + length,
                }
            )
            offset += length

        word_lengths = np.asarray(
            [len(phones) for phones in pronunciation.word_phones], dtype=np.float64
        )
        scores = {
            "accuracy": int(round(float(np.average(
                [item["accuracy"] for item in word_scores], weights=word_lengths
            )))),
            # Reaching this point means speech was present and Kaldi aligned
            # every requested phone. Sentence omissions are checked against
            # local WhisperX by the API; pronunciation quality must not be
            # counted a second time as incompleteness.
            "completeness": 100,
            "fluency": percent(fluency),
            "prosody": percent(prosody),
        }
        if len(pronunciation.words) == 1:
            scores["overall_score"] = calculate_word_overall_score(scores)
            overall_weights = WORD_OVERALL_SCORE_WEIGHTS
        else:
            scores["overall_score"] = calculate_overall_score(scores)
            overall_weights = OVERALL_SCORE_WEIGHTS
        # Compatibility alias for the existing Flutter/API contract. This is
        # the weighted overall score, not a raw Kaldi GOP value.
        scores["gop_score"] = scores["overall_score"]
        feedback = "Strong pronunciation across the aligned sounds."
        if mistakes:
            focus = ", ".join(
                f"/{item['phoneme']}/ ({item['status']}, {item['score']}/100)"
                for item in mistakes[:5]
            )
            feedback = "Focus on these sounds: " + focus + "."
        elif uncertain:
            focus = ", ".join(f"/{item['phoneme']}/" for item in uncertain[:5])
            feedback = (
                "The evidence is uncertain for " + focus + ". Repeat the target before treating these as mistakes."
            )
        return {
            "target": target_text.strip(),
            "spoken": None,
            "target_ipa": list(pronunciation.ipa_phones),
            "analysis": analysis,
            "word_scores": word_scores,
            "feedback": feedback,
            "scores": scores,
            "scoring_method": "kaldi_gop_arabic_loso_severity_gopt_v2",
            "flagged_phones": mistakes,
            "uncertain_phones": uncertain,
            "calibration": {
                "green_max_error_probability": round(
                    self.warning_probability_threshold * 100.0, 1
                ),
                "green_max_error_severity": round(
                    self.warning_severity_threshold * 100.0, 1
                ),
                "global_red_severe_probability": round(
                    self.global_red_severe_probability * 100.0, 1
                ),
                "red_minimum_error_severity": round(
                    self.red_minimum_severity * 100.0, 1
                ),
                "orange_means": "uncertain; only red phones receive articulation coaching",
                "quality_scale": "100 minus the calibrated Arabic-L1 severity/error blend",
                "overall_weights": overall_weights,
            },
            "warnings": [],
        }
