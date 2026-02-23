#!/usr/bin/env python3
"""Launcher script for the Swimming Results Database."""

import os
import subprocess
import sys
from pathlib import Path


def main() -> None:
    project_root = Path(__file__).resolve().parents[2]
    app_file = project_root / "src" / "swimming_app" / "streamlit_app.py"
    env_data_path = os.getenv("SWIM_DATA_PATH", "").strip()
    candidates = []
    if env_data_path:
        candidates.append(Path(env_data_path))
    candidates.append(project_root / "CSV" / "swim_data.csv")
    candidates.append(project_root / "CSV" / "swim_data.sample.csv")
    csv_file = next((p for p in candidates if p.exists()), candidates[0])

    if not app_file.exists():
        print(f"Error: {app_file} not found")
        print("Run this command from the project root.")
        sys.exit(1)

    if not csv_file.exists():
        print("Error: data CSV not found.")
        print("Set SWIM_DATA_PATH or provide CSV/swim_data.csv (or CSV/swim_data.sample.csv).")

        sys.exit(1)

    with csv_file.open("r", encoding="utf-8") as f:
        row_count = sum(1 for _ in f) - 1

    print(f"Using data file: {csv_file}")
    print(f"Found {row_count} data rows")

    print("Starting Streamlit app at http://localhost:8501")

    try:
        subprocess.run(
            [
                sys.executable,
                "-m",
                "streamlit",
                "run",
                str(app_file),
                "--server.port",
                "8501",
                "--server.address",
                "localhost",
            ],
            cwd=str(project_root),
            check=False,
        )
    except KeyboardInterrupt:
        print("Stopped")


if __name__ == "__main__":
    main()
