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

The existing `plp.*` module paths remain as compatibility entrypoints during
the architectural migration. Model-training programs remain in `training/`
because they are offline workflows and are not imported by the API process.
