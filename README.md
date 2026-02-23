# swimming-app
Swimming results app with:
- PDF-to-CSV parser for meet files
- Streamlit UI to search swimmers, events, teams, and trends

## Project structure
- `src/swimming_app/streamlit_app.py`: main Streamlit application
- `src/swimming_app/pdf_parser.py`: robust PDF-to-CSV parser
- `src/swimming_app/run_app.py`: local launcher
- `CSV/swim_data.csv`: active dataset
- `PDF/`: source meet PDFs

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

## Parse a PDF
```bash
python3 src/swimming_app/pdf_parser.py \
  --pdf-path "PDF/<file>.pdf" \
  --active-csv-path "CSV/swim_data.csv" \
  --backup-csv-path "codex/swim_data_backup.csv" \
  --mode lenient
```

## Run with Docker
```bash
make docker-build
make docker-run
```
This mounts local `CSV/` into the container at `/app/CSV`, so CSV edits on your machine are reflected immediately.

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
