# Arabic-L1 Pronunciation Training

The current reproducible training path is deliberately small:

- `prepare_l2_arctic.py` prepares manually annotated Arabic L2-ARCTIC speech,
  deterministic noise variants, and manifests.
- `setup_ctc_model.py` downloads and verifies the pinned CMU39 XLSR-53 CTC
  checkpoint published with the Interspeech 2024 method.
- `extract_ctc_gop_batch.py` writes resumable 41D alignment-free CTC-GOP rows.
- `fine_tune_ctc_head_arabic.py` optionally adapts only the 40-class CTC head
  with speaker-held-out Arabic-L1 supervision on low-memory GPUs.
- `pronunciation_data.py` strictly joins manifests to extracted CTC-GOP rows.
- `download_speechocean.py`, `prepare_speechocean_ctc.py`, and
  `train_gopt_ctc.py` rebuild GOPT with the same 41D feature schema.
- `train_arabic_pronunciation_ctc_v3.py` performs four-speaker LOSO evaluation,
  cross-fitted calibration, model selection, final training, and metadata output.

Data lives outside the repository:

```text
/home/amjad/english_learning_app_data/
├── l2_arctic_manual/
└── l2_arctic_arabic_ctc/   # CTC-GOP preparation
```

Prepare the dataset only when rebuilding it from the manual source:

```bash
PYTHONPATH=backend /home/amjad/whisperx-env/bin/python \
  backend/training/prepare_l2_arctic.py
```

Install the pinned acoustic checkpoint (the 1.26 GB weight remains outside Git):

```bash
PYTHONPATH=backend /home/amjad/whisperx-env/bin/python \
  backend/training/setup_ctc_model.py
```

Extract CTC-GOP features:

```bash
PYTHONPATH=backend /home/amjad/whisperx-env/bin/python \
  backend/training/extract_ctc_gop_batch.py
```

Download SpeechOcean762's two parquet files, prepare them, extract features
with the same command and `--data` path, then train CTC-GOPT:

```bash
PYTHONPATH=backend /home/amjad/whisperx-env/bin/python \
  backend/training/download_speechocean.py
PYTHONPATH=backend /home/amjad/whisperx-env/bin/python \
  backend/training/prepare_speechocean_ctc.py
PYTHONPATH=backend /home/amjad/whisperx-env/bin/python \
  backend/training/extract_ctc_gop_batch.py \
  --data /home/amjad/english_learning_app_data/speechocean762_ctc
PYTHONPATH=backend /home/amjad/whisperx-env/bin/python \
  backend/training/train_gopt_ctc.py
```

SpeechOcean762 is published by OpenSLR under CC BY 4.0. The pinned CTC weight
repository does not declare a license; confirm redistribution rights before
shipping that weight commercially.

Train a candidate without overwriting production:

```bash
PYTHONPATH=backend /home/amjad/whisperx-env/bin/python \
  backend/training/train_arabic_pronunciation_ctc_v3.py \
  --output /home/amjad/pronunciation_ctc_v3_candidate \
  --oof-output /home/amjad/pronunciation_ctc_v3_oof.npz
```

The script defaults to the external prepared-data path. Its default output is
the live `backend/pretrained_models/arabic_pronunciation_ctc_v3/` directory, so use
an explicit candidate output unless intentionally promoting a verified model.

The production runtime always uses the local XLSR-53 CTC checkpoint,
`backend/pretrained_models/gopt_ctc/`, and
`backend/pretrained_models/arabic_pronunciation_ctc_v3/`. Held-out results
from the pinned July 2026 rebuild were AP 0.343 and ROC-AUC 0.798 for
Arabic-L1 phone-error ranking, plus SpeechOcean phone PCC 0.641 and prosody
PCC 0.733 for CTC-GOPT.
