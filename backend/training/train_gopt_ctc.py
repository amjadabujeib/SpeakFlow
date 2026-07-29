"""Train the 41-input GOPT model on SpeechOcean762 CTC-GOP features."""

from __future__ import annotations

import argparse
import json
import random
from pathlib import Path

import numpy as np
import torch
from torch.utils.data import DataLoader, Dataset

from gopt_models.gopt import GOPT
from pronunciation_features import GOP_FEATURE_DIM
from pronunciation_core import GOPT_PHONE_TO_ID, MAX_GOPT_PHONES


DEFAULT_DATA = (
    Path.home()
    / "english_learning_app_data"
    / "speechocean762_ctc"
)


class GoptDataset(Dataset):
    def __init__(
        self,
        rows: list[dict],
        feature_root: Path,
        mean: np.ndarray,
        std: np.ndarray,
    ):
        self.items = []
        for row in rows:
            raw = np.load(
                feature_root / f"{row['id']}.npy",
                allow_pickle=False,
            ).astype(np.float32, copy=False)
            count = len(row["pure_phones"])
            if raw.shape != (count, GOP_FEATURE_DIM):
                raise ValueError(
                    f"{row['id']}: feature shape {raw.shape} is incompatible"
                )
            features = np.zeros(
                (MAX_GOPT_PHONES, GOP_FEATURE_DIM),
                dtype=np.float32,
            )
            features[:count] = (raw - mean) / std
            phone_ids = np.full(MAX_GOPT_PHONES, -1, dtype=np.int64)
            phone_ids[:count] = [
                GOPT_PHONE_TO_ID[phone] for phone in row["pure_phones"]
            ]
            phone_labels = np.full(MAX_GOPT_PHONES, -1.0, dtype=np.float32)
            phone_labels[:count] = np.asarray(
                row["phone_labels"],
                dtype=np.float32,
            )
            word_labels = np.full(
                (MAX_GOPT_PHONES, 3),
                -1.0,
                dtype=np.float32,
            )
            offset = 0
            for word_length, labels in zip(
                row["word_lengths"],
                row["word_labels"],
            ):
                word_labels[offset : offset + word_length] = labels
                offset += word_length
            if offset != count:
                raise ValueError(
                    f"{row['id']}: word labels do not cover every phone"
                )
            utterance_labels = np.asarray(
                row["utterance_labels"],
                dtype=np.float32,
            )
            if utterance_labels.shape != (5,):
                raise ValueError(
                    f"{row['id']}: utterance labels are malformed"
                )
            self.items.append(
                (
                    features,
                    phone_ids,
                    phone_labels,
                    word_labels,
                    utterance_labels,
                )
            )

    def __len__(self) -> int:
        return len(self.items)

    def __getitem__(self, index: int):
        return tuple(torch.from_numpy(value) for value in self.items[index])


def _training_normalization(
    rows: list[dict],
    feature_root: Path,
) -> tuple[np.ndarray, np.ndarray]:
    features = [
        np.load(feature_root / f"{row['id']}.npy", allow_pickle=False)
        for row in rows
    ]
    stacked = np.concatenate(features).astype(np.float64, copy=False)
    mean = np.mean(stacked, axis=0)
    std = np.std(stacked, axis=0)
    std = np.maximum(std, 1e-5)
    if (
        mean.shape != (GOP_FEATURE_DIM,)
        or std.shape != (GOP_FEATURE_DIM,)
        or not np.isfinite(mean).all()
        or not np.isfinite(std).all()
    ):
        raise ValueError("training normalization is malformed")
    return mean.astype(np.float32), std.astype(np.float32)


def _masked_mse(
    prediction: torch.Tensor,
    target: torch.Tensor,
) -> torch.Tensor:
    mask = target >= 0
    return torch.mean((prediction[mask] - target[mask]) ** 2)


def _loss(
    outputs: tuple[torch.Tensor, ...],
    phone_labels: torch.Tensor,
    word_labels: torch.Tensor,
    utterance_labels: torch.Tensor,
) -> tuple[torch.Tensor, dict[str, float]]:
    utterance_prediction = torch.cat(outputs[:5], dim=1)
    phone_prediction = outputs[5].squeeze(-1)
    word_prediction = torch.cat(outputs[6:9], dim=2)
    phone_loss = _masked_mse(phone_prediction, phone_labels)
    word_loss = _masked_mse(word_prediction, word_labels)
    utterance_loss = torch.mean(
        (utterance_prediction - utterance_labels) ** 2
    )
    total = phone_loss + word_loss + utterance_loss
    return total, {
        "phone": float(phone_loss.detach().cpu()),
        "word": float(word_loss.detach().cpu()),
        "utterance": float(utterance_loss.detach().cpu()),
        "total": float(total.detach().cpu()),
    }


def _validate(
    model: GOPT,
    loader: DataLoader,
    device: torch.device,
) -> dict[str, float]:
    totals = {"phone": 0.0, "word": 0.0, "utterance": 0.0, "total": 0.0}
    phone_predictions: list[np.ndarray] = []
    phone_targets: list[np.ndarray] = []
    word_predictions: list[np.ndarray] = []
    word_targets: list[np.ndarray] = []
    utterance_predictions: list[np.ndarray] = []
    utterance_targets: list[np.ndarray] = []
    count = 0
    model.eval()
    with torch.inference_mode():
        for features, phone_ids, phone_labels, word_labels, utterance_labels in loader:
            features = features.to(device)
            phone_ids = phone_ids.to(device)
            phone_labels = phone_labels.to(device)
            word_labels = word_labels.to(device)
            utterance_labels = utterance_labels.to(device)
            outputs = model(features, phone_ids)
            _, metrics = _loss(
                outputs,
                phone_labels,
                word_labels,
                utterance_labels,
            )
            current_phone_prediction = outputs[5].squeeze(-1)
            phone_mask = phone_labels >= 0
            phone_predictions.append(
                current_phone_prediction[phone_mask].detach().cpu().numpy()
            )
            phone_targets.append(
                phone_labels[phone_mask].detach().cpu().numpy()
            )
            current_word_prediction = torch.cat(outputs[6:9], dim=2)
            word_mask = word_labels >= 0
            word_predictions.append(
                current_word_prediction[word_mask].detach().cpu().numpy()
            )
            word_targets.append(
                word_labels[word_mask].detach().cpu().numpy()
            )
            utterance_predictions.append(
                torch.cat(outputs[:5], dim=1).detach().cpu().numpy()
            )
            utterance_targets.append(utterance_labels.detach().cpu().numpy())
            batch = len(features)
            for name in totals:
                totals[name] += metrics[name] * batch
            count += batch
    report = {name: value / count for name, value in totals.items()}
    flat_phone_predictions = np.concatenate(phone_predictions)
    flat_phone_targets = np.concatenate(phone_targets)
    report["phone_pcc"] = (
        0.0
        if np.std(flat_phone_predictions) == 0
        or np.std(flat_phone_targets) == 0
        else float(np.corrcoef(flat_phone_predictions, flat_phone_targets)[0, 1])
    )
    flat_word_predictions = np.concatenate(word_predictions)
    flat_word_targets = np.concatenate(word_targets)
    report["word_pcc"] = (
        0.0
        if np.std(flat_word_predictions) == 0
        or np.std(flat_word_targets) == 0
        else float(np.corrcoef(flat_word_predictions, flat_word_targets)[0, 1])
    )
    predictions = np.concatenate(utterance_predictions)
    targets = np.concatenate(utterance_targets)
    for index, aspect in enumerate(
        ("accuracy", "completeness", "fluency", "prosody", "total")
    ):
        if np.std(predictions[:, index]) == 0 or np.std(targets[:, index]) == 0:
            correlation = 0.0
        else:
            correlation = float(
                np.corrcoef(predictions[:, index], targets[:, index])[0, 1]
            )
        report[f"{aspect}_pcc"] = correlation
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", type=Path, default=DEFAULT_DATA)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("backend/pretrained_models/gopt_ctc"),
    )
    parser.add_argument("--epochs", type=int, default=100)
    parser.add_argument("--batch-size", type=int, default=25)
    parser.add_argument("--learning-rate", type=float, default=1e-3)
    parser.add_argument("--seed", type=int, default=20260729)
    args = parser.parse_args()

    random.seed(args.seed)
    np.random.seed(args.seed)
    torch.manual_seed(args.seed)
    rows = [
        json.loads(line)
        for line in (args.data / "manifest.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
        if line.strip()
    ]
    official_train_rows = [row for row in rows if row["split"] == "train"]
    test_rows = [row for row in rows if row["split"] == "test"]
    if len(official_train_rows) != 2_500 or len(test_rows) != 2_500:
        raise ValueError("SpeechOcean762 must contain its fixed 2500/2500 split")
    speakers = sorted({row["speaker"] for row in official_train_rows})
    split_rng = random.Random(args.seed)
    split_rng.shuffle(speakers)
    validation_speaker_count = max(1, round(len(speakers) * 0.20))
    validation_speakers = set(speakers[:validation_speaker_count])
    train_rows = [
        row
        for row in official_train_rows
        if row["speaker"] not in validation_speakers
    ]
    validation_rows = [
        row
        for row in official_train_rows
        if row["speaker"] in validation_speakers
    ]
    feature_root = args.data / "ctc_gop_output"
    mean, std = _training_normalization(train_rows, feature_root)
    train_dataset = GoptDataset(train_rows, feature_root, mean, std)
    validation_dataset = GoptDataset(
        validation_rows,
        feature_root,
        mean,
        std,
    )
    test_dataset = GoptDataset(test_rows, feature_root, mean, std)
    generator = torch.Generator().manual_seed(args.seed)
    train_loader = DataLoader(
        train_dataset,
        batch_size=args.batch_size,
        shuffle=True,
        generator=generator,
    )
    validation_loader = DataLoader(
        validation_dataset,
        batch_size=args.batch_size * 4,
        shuffle=False,
    )
    test_loader = DataLoader(
        test_dataset,
        batch_size=args.batch_size * 4,
        shuffle=False,
    )

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model = GOPT(
        embed_dim=24,
        num_heads=1,
        depth=3,
        input_dim=GOP_FEATURE_DIM,
    ).to(device)
    optimizer = torch.optim.Adam(
        model.parameters(),
        lr=args.learning_rate,
        weight_decay=5e-7,
        betas=(0.95, 0.999),
    )
    scheduler = torch.optim.lr_scheduler.MultiStepLR(
        optimizer,
        milestones=list(range(20, 100, 5)),
        gamma=0.5,
    )
    best_loss = float("inf")
    best_state = None
    history = []
    for epoch in range(args.epochs):
        model.train()
        for features, phone_ids, phone_labels, word_labels, utterance_labels in train_loader:
            features = features.to(device)
            phone_ids = phone_ids.to(device)
            phone_labels = phone_labels.to(device)
            word_labels = word_labels.to(device)
            utterance_labels = utterance_labels.to(device)
            loss, _ = _loss(
                model(features, phone_ids),
                phone_labels,
                word_labels,
                utterance_labels,
            )
            optimizer.zero_grad(set_to_none=True)
            loss.backward()
            optimizer.step()
        validation = _validate(model, validation_loader, device)
        validation["epoch"] = epoch
        history.append(validation)
        print(json.dumps(validation, sort_keys=True), flush=True)
        if validation["total"] < best_loss:
            best_loss = validation["total"]
            best_state = {
                key: value.detach().cpu().clone()
                for key, value in model.state_dict().items()
            }
        scheduler.step()
    if best_state is None:
        raise RuntimeError("GOPT training did not produce a checkpoint")
    model.load_state_dict(best_state)
    test_report = _validate(model, test_loader, device)

    args.output.mkdir(parents=True, exist_ok=True)
    torch.save(best_state, args.output / "best_audio_model.pth")
    metadata = {
        "version": 1,
        "input_dim": GOP_FEATURE_DIM,
        "phone_to_id": GOPT_PHONE_TO_ID,
        "normalization": {
            "mean": mean.tolist(),
            "std": std.tolist(),
        },
        "training": {
            "data": str(args.data),
            "seed": args.seed,
            "epochs": args.epochs,
            "best_validation_loss": best_loss,
            "selection_split": (
                "speaker-disjoint 20% of the official SpeechOcean762 train split"
            ),
            "validation_speakers": sorted(validation_speakers),
            "held_out_test": test_report,
            "history": history,
        },
    }
    (args.output / "metadata.json").write_text(
        json.dumps(metadata, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(f"saved CTC-GOPT assets to {args.output}")


if __name__ == "__main__":
    main()
