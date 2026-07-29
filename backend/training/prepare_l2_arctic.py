"""Prepare Arabic L2-ARCTIC annotations and deterministic noisy copies."""

from __future__ import annotations

import argparse
import io
import json
import math
import re
import shutil
from collections import defaultdict
from pathlib import Path

import cmudict
import numpy as np
import pyarrow.parquet as pq
import soundfile as sf

from training.pronunciation_data import DEFAULT_ARABIC_DATASET, DEFAULT_MANUAL_DATASET


VALID_PHONES = {
    "W", "IY", "K", "AO", "L", "IH", "T", "B", "EH", "R", "Z",
    "OW", "TH", "F", "AY", "V", "AH", "N", "UW", "S", "G", "AA",
    "M", "P", "NG", "HH", "EY", "SH", "AE", "D", "UH", "AW", "DH",
    "ER", "Y", "JH", "CH", "OY", "ZH",
}
WORD_RE = re.compile(r"[A-Za-z]+(?:'[A-Za-z]+)?")


def pure(phone: str) -> str:
    return re.sub(r"[012]$", "", phone.upper())


def edit_distance(left: tuple[str, ...], right: tuple[str, ...]) -> int:
    previous = list(range(len(right) + 1))
    for i, a in enumerate(left, start=1):
        current = [i]
        for j, b in enumerate(right, start=1):
            current.append(min(current[-1] + 1, previous[j] + 1, previous[j - 1] + (a != b)))
        previous = current
    return previous[-1]


def segment_by_words(text: str, phones: tuple[str, ...], dictionary) -> tuple[tuple[str, ...], tuple[tuple[str, ...], ...]]:
    words = tuple(match.group(0).upper() for match in WORD_RE.finditer(text))
    if not words or len(words) > len(phones):
        raise ValueError("could not derive non-empty word boundaries")

    candidates = []
    for word in words:
        variants = dictionary.get(word.lower())
        if variants:
            candidates.append([tuple(pure(phone) for phone in variant) for variant in variants])
        else:
            candidates.append([])

    # Dynamic programming assigns every manually annotated canonical phone to
    # exactly one transcript word while preferring CMU pronunciation lengths.
    states = {0: (0.0, [])}
    total = len(phones)
    for word_index, variants in enumerate(candidates):
        remaining_words = len(words) - word_index - 1
        next_states = {}
        for start, (base_cost, groups) in states.items():
            max_end = total - remaining_words
            for end in range(start + 1, max_end + 1):
                segment = tuple(pure(phone) for phone in phones[start:end])
                if variants:
                    distance = min(edit_distance(segment, variant) for variant in variants)
                    expected = min(abs(len(segment) - len(variant)) for variant in variants)
                    cost = base_cost + distance + (0.05 * expected)
                else:
                    expected_length = max(1, round(len(words[word_index]) * 0.65))
                    cost = base_cost + 1.0 + (0.15 * abs(len(segment) - expected_length))
                old = next_states.get(end)
                if old is None or cost < old[0]:
                    next_states[end] = (cost, groups + [(start, end)])
        states = next_states

    if total not in states:
        raise ValueError("word-boundary alignment did not consume all phones")
    spans = states[total][1]
    return words, tuple(tuple(phones[start:end]) for start, end in spans)


def marked_phones(phones: tuple[str, ...]) -> tuple[str, ...]:
    if len(phones) == 1:
        return (phones[0] + "_S",)
    return tuple(
        phone + ("_B" if index == 0 else "_E" if index == len(phones) - 1 else "_I")
        for index, phone in enumerate(phones)
    )


def canonical_phone(event: dict) -> str:
    raw = re.sub(r"[^A-Z0-2]", "", (event.get("canonical_raw") or "").upper())
    normalized = (event.get("canonical_phoneme") or "").upper()
    if pure(raw) == normalized and normalized in VALID_PHONES:
        return raw
    if normalized in VALID_PHONES:
        return normalized
    raise ValueError(f"unsupported canonical phone {event.get('canonical_raw')!r}")


def phone_label(event: dict) -> float:
    error_type = event["error_type"]
    if error_type == "correct":
        return 2.0
    if error_type == "substitution":
        canonical = event.get("canonical_phoneme")
        perceived = event.get("perceived_phoneme")
        return 1.0 if canonical and canonical == perceived else 0.0
    if error_type == "deletion":
        return 0.0
    raise ValueError(f"unsupported canonical event type {error_type}")


def realized_phone(event: dict) -> str | None:
    """Return the human-perceived phone used to evaluate substitutions."""
    if event["error_type"] == "deletion":
        return None
    if event["error_type"] == "correct":
        return pure(canonical_phone(event))
    perceived = (event.get("perceived_phoneme") or "").upper()
    perceived = pure(perceived)
    return perceived if perceived in VALID_PHONES else None


def add_noise(clean: np.ndarray, partner: np.ndarray, rng: np.random.Generator) -> tuple[np.ndarray, float]:
    if len(partner) < len(clean):
        repeats = math.ceil(len(clean) / max(1, len(partner)))
        partner = np.tile(partner, repeats)
    start = int(rng.integers(0, max(1, len(partner) - len(clean) + 1)))
    background = partner[start:start + len(clean)].astype(np.float32, copy=True)
    background += rng.normal(0, 0.02, size=len(clean)).astype(np.float32)

    snr_db = float(rng.choice([8.0, 12.0, 16.0, 20.0]))
    signal_rms = float(np.sqrt(np.mean(clean ** 2)) + 1e-8)
    noise_rms = float(np.sqrt(np.mean(background ** 2)) + 1e-8)
    background *= signal_rms / (noise_rms * (10 ** (snr_db / 20.0)))
    mixed = clean + background

    # Two quiet echoes approximate an ordinary untreated room without hiding
    # the target speech or changing its labels.
    if rng.random() < 0.5:
        for delay_seconds, gain in ((0.032, 0.12), (0.071, 0.06)):
            delay = int(16000 * delay_seconds)
            mixed[delay:] += gain * clean[:-delay]
    peak = float(np.max(np.abs(mixed)))
    if peak > 0.98:
        mixed *= 0.98 / peak
    return mixed.astype(np.float32), snr_db


def build_example(row: dict, dictionary) -> dict:
    canonical_events = [event for event in row["manual_events"] if event.get("canonical_phoneme") is not None]
    phones = tuple(canonical_phone(event) for event in canonical_events)
    if len(phones) > 50:
        raise ValueError("more than 50 canonical phones")
    labels = tuple(phone_label(event) for event in canonical_events)
    realized = tuple(realized_phone(event) for event in canonical_events)
    words, word_phones = segment_by_words(row["transcript"], phones, dictionary)

    phone_to_word = []
    for word_index, group in enumerate(word_phones):
        phone_to_word.extend([word_index] * len(group))
    addition_counts = [0] * len(words)
    canonical_midpoints = [0.5 * (event["start"] + event["end"]) for event in canonical_events]
    for event in row["manual_events"]:
        if event["error_type"] != "addition":
            continue
        midpoint = 0.5 * (event["start"] + event["end"])
        nearest = min(range(len(canonical_midpoints)), key=lambda index: abs(canonical_midpoints[index] - midpoint))
        addition_counts[phone_to_word[nearest]] += 1

    word_labels = []
    offset = 0
    for group, additions in zip(word_phones, addition_counts):
        length = len(group)
        word_labels.append(sum(labels[offset:offset + length]) / (length + additions))
        offset += length
    utterance_accuracy = sum(labels) / (len(labels) + sum(addition_counts))

    return {
        "speaker": row["speaker_id"],
        "split": row["corpus_split"],
        "utterance": row["utterance_id"],
        "transcript": " ".join(words),
        "words": list(words),
        "word_phones": [list(group) for group in word_phones],
        "phones": list(phones),
        "pure_phones": [pure(phone) for phone in phones],
        "phone_labels": list(labels),
        "realized_phones": list(realized),
        "word_labels": word_labels,
        "addition_counts": addition_counts,
        "utterance_accuracy": utterance_accuracy,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, default=DEFAULT_MANUAL_DATASET)
    parser.add_argument("--output", type=Path, default=DEFAULT_ARABIC_DATASET)
    parser.add_argument("--seed", type=int, default=20260714)
    args = parser.parse_args()

    dictionary = cmudict.dict()
    rows = []
    for parquet_path in sorted((args.source / "data").glob("*.parquet")):
        for row in pq.read_table(parquet_path).to_pylist():
            if row["native_language"] == "Arabic" and row["corpus_split"] in {"train", "validation", "test"}:
                rows.append(row)

    if args.output.exists():
        shutil.rmtree(args.output)
    audio_root = args.output / "audio"
    audio_root.mkdir(parents=True)

    examples = []
    skipped = defaultdict(int)
    for row in rows:
        try:
            example = build_example(row, dictionary)
        except ValueError as exc:
            skipped[str(exc)] += 1
            continue
        audio, sample_rate = sf.read(io.BytesIO(row["audio"]["bytes"]), dtype="float32")
        if sample_rate != 16000:
            raise RuntimeError(f"unexpected sample rate {sample_rate}")
        if audio.ndim > 1:
            audio = audio.mean(axis=1)
        utterance_id = f"{example['speaker']}_{example['utterance']}"
        relative_path = Path("audio") / example["split"] / f"{utterance_id}.wav"
        (args.output / relative_path).parent.mkdir(parents=True, exist_ok=True)
        sf.write(args.output / relative_path, audio, 16000, subtype="PCM_16")
        example.update({"id": utterance_id, "variant": "clean", "audio": relative_path.as_posix()})
        examples.append(example)

    clean_examples = list(examples)
    rng = np.random.default_rng(args.seed)
    for index, example in enumerate(clean_examples):
        same_split = [
            candidate for candidate in clean_examples
            if candidate["split"] == example["split"] and candidate["id"] != example["id"]
        ]
        different_speaker = [
            candidate for candidate in same_split if candidate["speaker"] != example["speaker"]
        ]
        candidates = different_speaker or same_split
        partner = candidates[int(rng.integers(0, len(candidates)))]
        clean, _ = sf.read(args.output / example["audio"], dtype="float32")
        background, _ = sf.read(args.output / partner["audio"], dtype="float32")
        noisy, snr_db = add_noise(clean, background, rng)
        noisy_example = dict(example)
        noisy_example["id"] = example["id"] + "_noise"
        noisy_example["variant"] = "noise"
        noisy_example["snr_db"] = snr_db
        relative_path = Path("audio") / example["split"] / f"{noisy_example['id']}.wav"
        sf.write(args.output / relative_path, noisy, 16000, subtype="PCM_16")
        noisy_example["audio"] = relative_path.as_posix()
        examples.append(noisy_example)

    examples.sort(key=lambda item: item["id"])
    with (args.output / "manifest.jsonl").open("w", encoding="utf-8") as handle:
        for example in examples:
            handle.write(json.dumps(example, ensure_ascii=False) + "\n")

    counts = defaultdict(int)
    for example in examples:
        counts[(example["split"], example["variant"])] += 1
    print(json.dumps({"prepared": {str(key): value for key, value in counts.items()}, "skipped": skipped}, indent=2))


if __name__ == "__main__":
    main()
