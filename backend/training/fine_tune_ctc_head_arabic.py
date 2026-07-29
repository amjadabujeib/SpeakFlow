"""Adapt only the XLSR-53 CTC phone head to human-perceived Arabic-L1 speech.

The wav2vec2 encoder stays frozen. This keeps training feasible on a 4 GB GPU
and avoids overfitting hundreds of millions of parameters to four speakers.
For honest evaluation, pass --held-out-speaker and train one head per LOSO
fold; the held-out speaker is never used for training or checkpoint selection.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
from pathlib import Path

import numpy as np
import torch
import torch.nn.functional as functional
from transformers import AutoFeatureExtractor, Wav2Vec2ForCTC

from ctc_gop import (
    CTC_BLANK_ID,
    CTC_PHONE_TO_ID,
    Wav2Vec2CtcGopExtractor,
)
from training.pronunciation_data import DEFAULT_ARABIC_DATASET


DEFAULT_MODEL = (
    Path(__file__).resolve().parents[1]
    / "pretrained_models"
    / "wav2vec2_xlsr53_cmu39_ctc"
)


def _rows(data: Path, held_out_speaker: str | None) -> list[dict]:
    rows = [
        json.loads(line)
        for line in (data / "manifest.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    clean = [row for row in rows if row["variant"] == "clean"]
    if held_out_speaker is not None:
        clean = [
            row for row in clean
            if row["speaker"] != held_out_speaker
        ]
    for row in clean:
        realized = [
            phone for phone in row["realized_phones"] if phone is not None
        ]
        if not realized:
            raise ValueError(f"{row['id']}: realized phone sequence is empty")
        if any(phone not in CTC_PHONE_TO_ID for phone in realized):
            raise ValueError(f"{row['id']}: realized phone sequence is unsupported")
    return clean


def _loss(
    model: Wav2Vec2ForCTC,
    feature_extractor,
    audio: np.ndarray,
    target_ids: list[int],
    device: torch.device,
) -> torch.Tensor:
    inputs = feature_extractor(
        audio,
        sampling_rate=16_000,
        return_tensors="pt",
    )
    input_values = inputs.input_values.to(
        device=device,
        dtype=torch.float32,
    )
    with torch.no_grad():
        hidden = model.wav2vec2(input_values).last_hidden_state
    hidden = functional.dropout(
        hidden.float(),
        p=float(model.config.final_dropout),
        training=model.training,
    )
    logits = model.lm_head(hidden)
    log_probabilities = functional.log_softmax(logits.float(), dim=-1)
    targets = torch.as_tensor(target_ids, dtype=torch.long, device=device)
    input_lengths = torch.as_tensor(
        [log_probabilities.shape[1]],
        dtype=torch.long,
        device=device,
    )
    target_lengths = torch.as_tensor(
        [len(target_ids)],
        dtype=torch.long,
        device=device,
    )
    return functional.ctc_loss(
        log_probabilities.transpose(0, 1),
        targets,
        input_lengths,
        target_lengths,
        blank=CTC_BLANK_ID,
        reduction="mean",
        zero_infinity=True,
    )


def _mean_loss(
    model: Wav2Vec2ForCTC,
    feature_extractor,
    rows: list[dict],
    data: Path,
    device: torch.device,
) -> float:
    values = []
    model.eval()
    with torch.inference_mode():
        for row in rows:
            audio = Wav2Vec2CtcGopExtractor._read_audio(data / row["audio"])
            targets = [
                CTC_PHONE_TO_ID[phone]
                for phone in row["realized_phones"]
                if phone is not None
            ]
            values.append(
                float(
                    _loss(
                        model,
                        feature_extractor,
                        audio,
                        targets,
                        device,
                    ).cpu()
                )
            )
    return float(np.mean(values))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", type=Path, default=DEFAULT_ARABIC_DATASET)
    parser.add_argument("--model", type=Path, default=DEFAULT_MODEL)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--held-out-speaker")
    parser.add_argument("--epochs", type=int, default=4)
    parser.add_argument("--learning-rate", type=float, default=5e-5)
    parser.add_argument("--gradient-accumulation", type=int, default=8)
    parser.add_argument("--validation-fraction", type=float, default=0.10)
    parser.add_argument("--seed", type=int, default=20260729)
    args = parser.parse_args()

    if not torch.cuda.is_available():
        raise RuntimeError("CTC head adaptation requires CUDA")
    if args.epochs <= 0 or args.gradient_accumulation <= 0:
        raise ValueError("epochs and gradient accumulation must be positive")
    if not 0.0 < args.validation_fraction < 0.5:
        raise ValueError("validation fraction must be between zero and 0.5")

    random.seed(args.seed)
    np.random.seed(args.seed)
    torch.manual_seed(args.seed)
    rows = _rows(args.data, args.held_out_speaker)
    split = list(rows)
    random.Random(args.seed).shuffle(split)
    validation_count = max(1, round(len(split) * args.validation_fraction))
    validation_rows = split[:validation_count]
    train_rows = split[validation_count:]

    feature_extractor = AutoFeatureExtractor.from_pretrained(
        args.model,
        local_files_only=True,
    )
    model = Wav2Vec2ForCTC.from_pretrained(
        args.model,
        local_files_only=True,
    )
    for parameter in model.parameters():
        parameter.requires_grad = False
    for parameter in model.lm_head.parameters():
        parameter.requires_grad = True
    device = torch.device("cuda")
    model.float().to(device)
    optimizer = torch.optim.AdamW(
        model.lm_head.parameters(),
        lr=args.learning_rate,
        weight_decay=0.01,
    )

    best_validation_loss = float("inf")
    best_state = None
    history = []
    initial_validation_loss = _mean_loss(
        model,
        feature_extractor,
        validation_rows,
        args.data,
        device,
    )
    if not np.isfinite(initial_validation_loss):
        raise RuntimeError("base CTC head produced a non-finite validation loss")
    print(
        json.dumps(
            {"epoch": -1, "validation_loss": initial_validation_loss},
            sort_keys=True,
        ),
        flush=True,
    )
    for epoch in range(args.epochs):
        model.train()
        shuffled = list(train_rows)
        random.Random(args.seed + epoch).shuffle(shuffled)
        optimizer.zero_grad(set_to_none=True)
        running_loss = 0.0
        for index, row in enumerate(shuffled, start=1):
            audio = Wav2Vec2CtcGopExtractor._read_audio(
                args.data / row["audio"]
            )
            targets = [
                CTC_PHONE_TO_ID[phone]
                for phone in row["realized_phones"]
                if phone is not None
            ]
            loss = _loss(
                model,
                feature_extractor,
                audio,
                targets,
                device,
            )
            if not torch.isfinite(loss):
                raise RuntimeError(
                    f"{row['id']}: adapted CTC loss became non-finite"
                )
            (loss / args.gradient_accumulation).backward()
            running_loss += float(loss.detach().cpu())
            if (
                index % args.gradient_accumulation == 0
                or index == len(shuffled)
            ):
                torch.nn.utils.clip_grad_norm_(
                    model.lm_head.parameters(),
                    max_norm=1.0,
                )
                optimizer.step()
                optimizer.zero_grad(set_to_none=True)
        validation_loss = _mean_loss(
            model,
            feature_extractor,
            validation_rows,
            args.data,
            device,
        )
        current = {
            "epoch": epoch,
            "train_loss": running_loss / len(shuffled),
            "validation_loss": validation_loss,
        }
        history.append(current)
        print(json.dumps(current, sort_keys=True), flush=True)
        if validation_loss < best_validation_loss:
            best_validation_loss = validation_loss
            best_state = {
                key: value.detach().float().cpu().clone()
                for key, value in model.lm_head.state_dict().items()
            }

    if best_state is None:
        raise RuntimeError("CTC head adaptation did not produce a checkpoint")
    args.output.mkdir(parents=True, exist_ok=True)
    head_path = args.output / "ctc_head.pt"
    torch.save(best_state, head_path)
    metadata = {
        "version": 1,
        "base_model": str(args.model.resolve()),
        "held_out_speaker": args.held_out_speaker,
        "trained_speakers": sorted({row["speaker"] for row in rows}),
        "train_utterances": len(train_rows),
        "validation_utterances": len(validation_rows),
        "epochs": args.epochs,
        "learning_rate": args.learning_rate,
        "seed": args.seed,
        "best_validation_loss": best_validation_loss,
        "initial_validation_loss": initial_validation_loss,
        "history": history,
        "head_sha256": hashlib.sha256(head_path.read_bytes()).hexdigest(),
    }
    (args.output / "metadata.json").write_text(
        json.dumps(metadata, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(f"saved adapted CTC head to {args.output}")


if __name__ == "__main__":
    main()
