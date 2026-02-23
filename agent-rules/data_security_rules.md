# Data Security Rules

These rules are mandatory for agents working in this repository.

## Do Not Commit Sensitive Data
- Never commit real swimmer datasets.
- Never commit raw meet PDFs.
- Keep private files local under `CSV/`, `PDF/`, or `codex/`.

## Use Environment-Based Data Path
- App data path must come from `SWIM_DATA_PATH` (or local fallback).
- For shared/public branches, only use `CSV/swim_data.sample.csv`.

## Before PR/Push
- Confirm `git status` does not include real data files.
- Run `make pre-push` and fix any failures.
