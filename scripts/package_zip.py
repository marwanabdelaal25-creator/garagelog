#!/usr/bin/env python3
"""Package garagelog for Silver submission."""

from __future__ import annotations

import os
import sys
import zipfile
from pathlib import Path

PROJECT = "garagelog"
SKIP_DIRS = {"__pycache__", ".pytest_cache", "htmlcov", ".ruff_cache", "build", "dist", ".history_snapshot"}
SKIP_FILES = {".coverage", "coverage_report.txt"}
SKIP_SUFFIXES = (".pyc",)


def package(project_dir: Path, output: Path | None = None) -> Path:
    output = output or project_dir.parent / f"{PROJECT}.zip"
    project_dir = project_dir.resolve()
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        for root, dirs, files in os.walk(project_dir):
            dirs[:] = [d for d in dirs if d not in SKIP_DIRS and not d.endswith(".egg-info")]
            for fname in files:
                if fname in SKIP_FILES or fname.endswith(SKIP_SUFFIXES):
                    continue
                full = Path(root) / fname
                arc = Path(PROJECT) / full.relative_to(project_dir)
                zf.write(full, arc.as_posix())
    return output


def verify(output: Path) -> None:
    prefix = f"{PROJECT}/"
    with zipfile.ZipFile(output) as zf:
        ents = zf.namelist()
    for needle, label in [
        (f"{prefix}.git/", ".git"), (f"{prefix}tests/", "tests"),
        (f"{prefix}.git/HEAD", "HEAD"), (f"{prefix}.git/refs/heads/main", "main ref"),
        (f"{prefix}Dockerfile", "Dockerfile"), (f"{prefix}README.md", "README"),
        (f"{prefix}tests/conftest.py", "conftest"),
    ]:
        ok = any(needle in e for e in ents) if needle.endswith("/") else needle in ents
        if not ok:
            print(f"VERIFY FAIL: {label} missing", file=sys.stderr)
            sys.exit(1)
    size_mb = output.stat().st_size / 1_048_576
    print(f"OK: {len(ents)} entries, {size_mb:.2f} MB compressed")


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    out = package(root)
    print(f"Wrote {out}")
    verify(out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
