#!/usr/bin/env python3
"""Launcher script for the Swimming Results Database."""

import subprocess
import sys
from pathlib import Path


def main() -> None:
    project_root = Path(__file__).resolve().parents[2]
    app_file = project_root / "src" / "swimming_app" / "streamlit_app.py"
    csv_file = project_root / "CSV" / "swim_data.csv"

    if not app_file.exists():
        print(f"Error: {app_file} not found")
        print("Run this command from the project root.")
        sys.exit(1)

    if not csv_file.exists():
        print(f"Error: {csv_file} not found")
        print("Ensure swim_data.csv exists in CSV/.")
        sys.exit(1)

    with csv_file.open("r", encoding="utf-8") as f:
        row_count = sum(1 for _ in f) - 1

    print(f"Found CSV/swim_data.csv with {row_count} data rows")
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
