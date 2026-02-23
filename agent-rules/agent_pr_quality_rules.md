# Agent PR Quality Rules

These rules are mandatory for any agent working on this repository.

## Required Before Push/PR
- Run: `make pre-push`
- Do not push code if this command fails.
- Fix all lint/format/syntax issues before push.

## Standard Static Analysis
- Formatter: Ruff format
- Linter: Ruff check
- Syntax gate: Python compile check

## Commands
- Auto-fix formatting + safe lint fixes:
  - `make format`
- Validate formatting only:
  - `make format-check`
- Lint only:
  - `make lint`
- Full required gate before push:
  - `make pre-push`

## Scope
- Apply checks to application source under `src/`.
- Data folders (`PDF/`, `CSV/`, `codex/`) are excluded from lint/format.
