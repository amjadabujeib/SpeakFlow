"""Local XLSR-53 CTC pronunciation features.

The feature definition follows the alignment-free vector GOP described in
Frank et al. (Interspeech 2024): each canonical phone receives the utterance
CTC negative log-likelihood followed by likelihood-ratio features for deleting
that phone and replacing it with each of the 39 English phones.

Unlike the paper's reference script, the dynamic program is evaluated by
PyTorch's log-space CTC implementation and counterfactual targets are batched.
This avoids probability-domain underflow on ordinary sentence-length audio.
"""

from __future__ import annotations

import json
import math
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

import numpy as np
import soundfile as sf
import torch
import torch.nn.functional as functional
from scipy.signal import resample_poly
from transformers import AutoFeatureExtractor, Wav2Vec2ForCTC


CTC_SAMPLE_RATE = 16_000
CTC_BLANK_ID = 0
CTC_PHONE_TO_ID = {
    phone: index
    for index, phone in enumerate(
        (
            "AA", "AE", "AH", "AO", "AW", "AY", "B", "CH", "D", "DH",
            "EH", "ER", "EY", "F", "G", "HH", "IH", "IY", "JH", "K",
            "L", "M", "N", "NG", "OW", "OY", "P", "R", "S", "SH",
            "T", "TH", "UH", "UW", "V", "W", "Y", "Z", "ZH",
        ),
        start=1,
    )
}
CTC_ID_TO_PHONE = {phone_id: phone for phone, phone_id in CTC_PHONE_TO_ID.items()}
CTC_CLASS_COUNT = 40
CTC_GOP_FEATURE_DIM = 41
CTC_SCHEMA_FILENAME = "ctc_gop_schema.json"
CTC_SCHEMA_VERSION = 1


class CtcGopError(RuntimeError):
    """Raised when the acoustic model cannot produce trustworthy features."""


@dataclass(frozen=True)
class CtcGopResult:
    features: np.ndarray
    likely_phones: tuple[str | None, ...]
    likely_phone_probabilities: np.ndarray
    deletion_probabilities: np.ndarray


def _ctc_losses(
    log_probabilities: torch.Tensor,
    targets: Sequence[torch.Tensor],
    *,
    blank_id: int = CTC_BLANK_ID,
    batch_size: int = 128,
) -> torch.Tensor:
    """Return one summed CTC NLL per target without leaving log space."""
    if log_probabilities.ndim != 2:
        raise ValueError("CTC log probabilities must have shape frames x classes")
    if not targets:
        return torch.empty(0, dtype=torch.float32, device=log_probabilities.device)
    frame_count, class_count = log_probabilities.shape
    if class_count != CTC_CLASS_COUNT:
        raise ValueError(
            f"CTC logits contain {class_count} classes, expected {CTC_CLASS_COUNT}"
        )
    if frame_count <= 0:
        raise ValueError("CTC logits contain no frames")

    losses: list[torch.Tensor] = []
    for start in range(0, len(targets), batch_size):
        target_batch = targets[start : start + batch_size]
        target_lengths = torch.as_tensor(
            [target.numel() for target in target_batch],
            dtype=torch.long,
            device=log_probabilities.device,
        )
        if any(target.ndim != 1 for target in target_batch):
            raise ValueError("each CTC target must be one-dimensional")
        if any(
            target.numel()
            and (
                int(torch.min(target).item()) <= blank_id
                or int(torch.max(target).item()) >= class_count
            )
            for target in target_batch
        ):
            raise ValueError("CTC targets must contain supported non-blank phone ids")
        concatenated = (
            torch.cat(target_batch)
            if int(target_lengths.sum().item())
            else torch.empty(0, dtype=torch.long, device=log_probabilities.device)
        )
        current_batch_size = len(target_batch)
        repeated = (
            log_probabilities[:, None, :]
            .expand(frame_count, current_batch_size, class_count)
            .contiguous()
        )
        input_lengths = torch.full(
            (current_batch_size,),
            frame_count,
            dtype=torch.long,
            device=log_probabilities.device,
        )
        losses.append(
            functional.ctc_loss(
                repeated,
                concatenated,
                input_lengths,
                target_lengths,
                blank=blank_id,
                reduction="none",
                zero_infinity=False,
            )
        )
    return torch.cat(losses)


def alignment_free_ctc_gop(
    logits: torch.Tensor | np.ndarray,
    canonical_phone_ids: Sequence[int],
    *,
    blank_id: int = CTC_BLANK_ID,
    counterfactual_batch_size: int = 128,
) -> CtcGopResult:
    """Build one 41D alignment-free CTC-GOP vector per canonical phone."""
    tensor = torch.as_tensor(logits)
    if tensor.ndim != 2 or tensor.shape[1] != CTC_CLASS_COUNT:
        raise ValueError(
            f"CTC logits must have shape frames x {CTC_CLASS_COUNT}, got {tuple(tensor.shape)}"
        )
    if not tensor.is_floating_point():
        tensor = tensor.float()
    tensor = tensor.float()
    if not torch.isfinite(tensor).all():
        raise ValueError("CTC logits contain non-finite values")

    canonical = torch.as_tensor(
        tuple(int(phone_id) for phone_id in canonical_phone_ids),
        dtype=torch.long,
        device=tensor.device,
    )
    if canonical.ndim != 1 or canonical.numel() == 0:
        raise ValueError("the canonical phone sequence must not be empty")
    if int(torch.min(canonical).item()) <= blank_id or int(
        torch.max(canonical).item()
    ) >= CTC_CLASS_COUNT:
        raise ValueError("the canonical sequence contains an unsupported phone id")

    log_probabilities = torch.log_softmax(tensor, dim=-1)
    baseline_nll = _ctc_losses(
        log_probabilities,
        (canonical,),
        blank_id=blank_id,
        batch_size=1,
    )[0]

    alternatives: list[torch.Tensor] = []
    for position in range(canonical.numel()):
        alternatives.append(torch.cat((canonical[:position], canonical[position + 1 :])))
        for replacement_id in range(1, CTC_CLASS_COUNT):
            replacement = canonical.clone()
            replacement[position] = replacement_id
            alternatives.append(replacement)

    alternative_nll = _ctc_losses(
        log_probabilities,
        alternatives,
        blank_id=blank_id,
        batch_size=counterfactual_batch_size,
    ).reshape(canonical.numel(), CTC_CLASS_COUNT)
    ratios = alternative_nll - baseline_nll
    baseline_column = baseline_nll.expand(canonical.numel(), 1)
    features = torch.cat((baseline_column, ratios), dim=1)
    if not torch.isfinite(features).all():
        raise CtcGopError(
            "CTC could not align the canonical phone sequence to this recording"
        )

    # These conditional probabilities compare the deletion and 39 replacement
    # hypotheses at one canonical position while holding the rest fixed.
    hypothesis_probability = torch.softmax(-alternative_nll, dim=1)
    best_hypothesis = torch.argmax(hypothesis_probability, dim=1)
    likely_phones: list[str | None] = []
    likely_probabilities: list[float] = []
    deletion_probabilities: list[float] = []
    for row, hypothesis_id in zip(
        hypothesis_probability, best_hypothesis.tolist()
    ):
        likely_phones.append(CTC_ID_TO_PHONE.get(int(hypothesis_id)))
        likely_probabilities.append(float(row[hypothesis_id].item()))
        deletion_probabilities.append(float(row[CTC_BLANK_ID].item()))

    return CtcGopResult(
        features=features.detach().cpu().numpy().astype(np.float32, copy=False),
        likely_phones=tuple(likely_phones),
        likely_phone_probabilities=np.asarray(likely_probabilities, dtype=np.float32),
        deletion_probabilities=np.asarray(deletion_probabilities, dtype=np.float32),
    )


def _load_schema(model_dir: Path) -> dict:
    schema_path = model_dir / CTC_SCHEMA_FILENAME
    if not schema_path.is_file():
        raise CtcGopError(f"CTC-GOP model schema is missing: {schema_path}")
    try:
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        if int(schema["schema_version"]) != CTC_SCHEMA_VERSION:
            raise ValueError("unsupported schema version")
        if int(schema["feature_dim"]) != CTC_GOP_FEATURE_DIM:
            raise ValueError("feature dimension does not match runtime")
        if int(schema["blank_id"]) != CTC_BLANK_ID:
            raise ValueError("blank id does not match runtime")
        phone_to_id = {
            str(phone): int(phone_id)
            for phone, phone_id in schema["phone_to_id"].items()
        }
        if phone_to_id != CTC_PHONE_TO_ID:
            raise ValueError("phone inventory does not match runtime")
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise CtcGopError(f"CTC-GOP model schema is malformed: {schema_path}") from exc
    return schema


class Wav2Vec2CtcGopExtractor:
    """Strict local-only acoustic feature extractor."""

    _inference_lock = threading.Lock()

    def __init__(
        self,
        model_dir: str | Path,
        *,
        device: str | torch.device | None = None,
        counterfactual_batch_size: int = 128,
        ctc_head_path: str | Path | None = None,
    ):
        self.model_dir = Path(model_dir)
        self.schema = _load_schema(self.model_dir)
        try:
            self.feature_extractor = AutoFeatureExtractor.from_pretrained(
                self.model_dir, local_files_only=True
            )
            self.model = Wav2Vec2ForCTC.from_pretrained(
                self.model_dir, local_files_only=True
            )
        except Exception as exc:
            raise CtcGopError(
                f"Could not load the local XLSR-53 phone CTC model: {self.model_dir}"
            ) from exc
        if int(self.model.config.vocab_size) != CTC_CLASS_COUNT:
            raise CtcGopError(
                f"CTC model has {self.model.config.vocab_size} outputs; expected {CTC_CLASS_COUNT}"
            )
        if int(self.model.config.pad_token_id) != CTC_BLANK_ID:
            raise CtcGopError("CTC model blank/pad id does not match the scoring schema")
        if ctc_head_path is not None:
            head_path = Path(ctc_head_path)
            try:
                state = torch.load(
                    head_path,
                    map_location="cpu",
                    weights_only=True,
                )
                self.model.lm_head.load_state_dict(state, strict=True)
            except Exception as exc:
                raise CtcGopError(
                    f"Could not load the adapted CTC phone head: {head_path}"
                ) from exc
        self.device = torch.device(
            device
            if device is not None
            else ("cuda" if torch.cuda.is_available() else "cpu")
        )
        self.model.to(self.device).eval()
        self.counterfactual_batch_size = int(counterfactual_batch_size)
        if self.counterfactual_batch_size <= 0:
            raise ValueError("counterfactual batch size must be positive")

    @staticmethod
    def _read_audio(audio_path: Path) -> np.ndarray:
        try:
            audio, sample_rate = sf.read(audio_path, dtype="float32", always_2d=False)
        except Exception as exc:
            raise CtcGopError(f"Could not read pronunciation audio: {audio_path}") from exc
        if audio.ndim == 2:
            audio = np.mean(audio, axis=1)
        if audio.ndim != 1 or audio.size == 0:
            raise CtcGopError("Pronunciation audio is empty or malformed")
        if sample_rate != CTC_SAMPLE_RATE:
            common = math.gcd(int(sample_rate), CTC_SAMPLE_RATE)
            audio = resample_poly(
                audio,
                CTC_SAMPLE_RATE // common,
                int(sample_rate) // common,
            ).astype(np.float32, copy=False)
        if not np.isfinite(audio).all():
            raise CtcGopError("Pronunciation audio contains non-finite samples")
        return audio

    def extract(
        self,
        audio_path: str | Path,
        canonical_phones: Sequence[str],
    ) -> CtcGopResult:
        try:
            phone_ids = tuple(
                CTC_PHONE_TO_ID[str(phone).upper()] for phone in canonical_phones
            )
        except KeyError as exc:
            raise CtcGopError(f"Unsupported canonical phone: {exc.args[0]}") from exc
        audio = self._read_audio(Path(audio_path))
        inputs = self.feature_extractor(
            audio,
            sampling_rate=CTC_SAMPLE_RATE,
            return_tensors="pt",
        )
        input_values = inputs.input_values.to(self.device)
        attention_mask = getattr(inputs, "attention_mask", None)
        if attention_mask is not None:
            attention_mask = attention_mask.to(self.device)
        with self._inference_lock, torch.inference_mode():
            logits = self.model(
                input_values,
                attention_mask=attention_mask,
            ).logits[0]
            return alignment_free_ctc_gop(
                logits,
                phone_ids,
                counterfactual_batch_size=self.counterfactual_batch_size,
            )
