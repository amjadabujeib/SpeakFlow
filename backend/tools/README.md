# Backend tools

Operational commands live in this package rather than in runtime feature
modules. Run them from `backend/` with the backend Python environment:

```bash
python -m tools.audit_curriculum
python -m tools.audit_generation --domain grammar --level B1
python -m tools.audit_weekly
python -m tools.model_bundle inventory
```

Publishing the private model bundle additionally requires Hugging Face write
access and uses `python -m tools.model_bundle upload`.

The audit commands delegate to the feature-owned learning-plan engine. The
bootstrap command is `python tools/setup_backend.py` from `backend/`, or
`.venv/bin/python backend/tools/setup_backend.py` from the repository root.
