## GECToR resources

`verb-form-vocab.txt` is the compact verb transformation vocabulary used by
the local GECToR grammar checker. It comes from
[`gotutiyan/gector`](https://github.com/gotutiyan/gector) and retains that
project's MIT license.

The runtime model weights are intentionally not stored here or committed to
Git. The private model bundle installs `gotutiyan/gector-roberta-base-5k`
under `backend/.models/gector/gector-roberta-base-5k/` as described in the
root README. Its safetensors checkpoint contains the complete RoBERTa encoder
and correction heads. `backend/gector_runtime.py` constructs the architecture
locally, so no separate `roberta-base` checkout or runtime download is needed.
