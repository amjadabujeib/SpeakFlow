# Arabic-L1 Pronunciation Training

The current reproducible training path is deliberately small:

- `prepare_l2_arctic.py` prepares manually annotated Arabic L2-ARCTIC speech,
  deterministic noise variants, manifests, and a Kaldi batch job.
- `extract_gop_batch.sh` runs the prepared job with `custom-kaldi`.
- `pronunciation_data.py` strictly joins manifests to extracted GOP vectors.
- `train_arabic_pronunciation_v2.py` performs four-speaker LOSO evaluation,
  cross-fitted calibration, model selection, final training, and metadata output.

Data lives outside the repository:

```text
/home/amjad/english_learning_app_data/
├── l2_arctic_manual/
└── l2_arctic_arabic/
```

Prepare the dataset only when rebuilding it from the manual source:

```bash
PYTHONPATH=backend /home/amjad/whisperx-env/bin/python \
  backend/training/prepare_l2_arctic.py
```

Extract Kaldi GOP features:

```bash
docker run --rm \
  --mount type=bind,src=/home/amjad/english_learning_app_data/l2_arctic_arabic,dst=/training \
  custom-kaldi bash /training/extract_gop_batch.sh /training 4
```

Train a candidate without overwriting production:

```bash
PYTHONPATH=backend /home/amjad/whisperx-env/bin/python \
  backend/training/train_arabic_pronunciation_v2.py \
  --output /home/amjad/pronunciation_v2_candidate \
  --oof-output /home/amjad/pronunciation_v2_oof.npz
```

The script defaults to the external prepared-data path. Its default output is
the live `backend/pretrained_models/arabic_pronunciation_v2/` directory, so use
an explicit candidate output unless intentionally promoting a verified model.
