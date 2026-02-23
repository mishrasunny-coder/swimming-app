# PDF Parser Script Explanation

## What This Script Does
The parser (`src/swimming_app/pdf_parser.py`) reads one swim-meet PDF, extracts results, and converts them into normalized CSV rows with this schema:

- `Meet_Name`
- `Meet_Date`
- `Name`
- `Age`
- `Rank`
- `Time`
- `Team`
- `Notes`
- `Event_Type`

It is designed to support multiple PDF layouts used across different meets.

## Core Idea: Family-Based Parsing
Not all PDFs have the same structure. The script first **detects a format family**, then uses the matching parser logic for that family.

Current families:

- `A`: `#<event>` style dual-meet PDFs.
- `B`: `Event <n>` compact-token PDFs.
- `C1`: older HY-TEK style with `Age TeamName Finals Time` tables.
- `C2`: compact dual-meet variant under C-family.
- `D1`: `AgeName Team Finals TimeSeed Time` style with place/seed compact tails.
- `D2`: variant of D with different individual/relay row shape.
- `E`: `Event <n>` style with separate relay and individual patterns.
- `F`: Team Manager “Individual Meet Results” style (`Event # ...`).
- `G`: Be Smartt/HY-TEK style with plain event titles (no `Event n` headers).

If no family matches, parse is blocked as `unsupported_format`.

## What Happens in One Run
1. Backup is refreshed from active CSV.
2. PDF text is extracted.
3. Family is detected.
4. Family parser builds candidate rows.
5. Validation gates run (structure, events, relay integrity, required fields).
6. If validation passes:
   - Existing rows for that meet are replaced.
   - New rows are appended.
   - Active CSV is atomically written.
7. Report JSON and candidate CSV are generated for traceability.

## Strict vs Lenient
- `strict`: hard validation blocks append on issues.
- `lenient`: allows warning-level issues while still blocking true structural failures.

## How to Run
```bash
python3 scripts/robust_pdf_to_csv.py \
  --pdf-path "PDF/<file>.pdf" \
  --active-csv-path "CSV/swim_data.csv" \
  --backup-csv-path "codex/swim_data_backup.csv" \
  --mode lenient
```

## Output Files
For each run, script writes:

- Parse report: `codex/<pdf_stem>_parse_report.json`
- Candidate rows: `codex/<pdf_stem>_candidate.csv`
- Active CSV update only if validation passes.

## Team/Event Uniforming
A separate post-processing step can standardize team aliases and event naming (for reporting consistency). This is intentionally kept separate from raw parsing logic.

## If a New PDF Fails
Typical process:
1. Inspect report and extracted row shape.
2. Decide whether to:
   - extend an existing family parser, or
   - add a new family.
3. Re-run regression checks on previously supported PDFs.

This keeps new support from breaking older formats.
