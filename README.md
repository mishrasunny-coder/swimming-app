# swimming-app
Swimming results app with:
- PDF-to-CSV parser for meet files
- Streamlit UI to search swimmers, events, teams, and trends
- env-based data path so private CSV data stays local

## Project structure
- `src/swimming_app/streamlit_app.py`: main Streamlit application
- `src/swimming_app/pdf_parser.py`: robust PDF-to-CSV parser
- `src/swimming_app/run_app.py`: local launcher
- `CSV/swim_data.sample.csv`: safe sample dataset committed to repo

## Prerequisites
- Python 3.12+
- Poetry
- Docker (optional)

## Install
```bash
make install
```
If Poetry is missing:
```bash
make install-poetry
```

## Run app locally
```bash
make run
```
Open: `http://localhost:8501`

Use private local data (recommended):
```bash
cp .env.example .env
export SWIM_DATA_PATH=CSV/swim_data.csv
make run
```
## Parse a PDF
```bash
python3 src/swimming_app/pdf_parser.py \
  --pdf-path "PDF/<file>.pdf" \
  --active-csv-path "${SWIM_DATA_PATH:-CSV/swim_data.csv}" \
  --backup-csv-path "codex/swim_data_backup.csv" \
  --mode lenient
```

## Run with Docker
```bash
make docker-build
make docker-run
```
`make docker-run` mounts local `CSV/` into the container and sets `SWIM_DATA_PATH=/app/CSV/swim_data.csv`.
CSV edits on your machine are reflected immediately in the container app.

## Data privacy
- Real datasets are intentionally ignored by git.
- Keep private data in local files (for example `CSV/swim_data.csv`) and use `SWIM_DATA_PATH`.
- Share only `CSV/swim_data.sample.csv` in public branches/PRs.

## Useful commands
```bash
make help
make check
make lint
make format
make pre-push
make docker-stop
```

## Code Quality Gate (Required Before Push)
Run this before opening or updating a PR:
```bash
make pre-push
```
This runs formatting checks, lint checks, and syntax checks. Fix any issues before push.
