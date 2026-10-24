# Data Snapshot Workflow

Commands for updating the `data-latest` branch after a pipeline run, or restoring data after a fresh clone. See `README.md` for why this exists.

## After running the pipeline

```bash
python3 scripts/run_pipeline.py
./scripts/publish_data_snapshot.sh
git push --force origin data-latest
```

## Restore data files (fresh clone, or after losing local `data/`)

```bash
./scripts/fetch_data_snapshot.sh
```
