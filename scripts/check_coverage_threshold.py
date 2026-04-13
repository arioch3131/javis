#!/usr/bin/env python3
"""Fail if per-file coverage is below a required threshold."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Validate per-file coverage from a coverage JSON report "
            "and fail when files are below the required threshold."
        )
    )
    parser.add_argument(
        "--report",
        type=Path,
        default=Path("coverage.json"),
        help="Path to coverage JSON report (default: coverage.json).",
    )
    parser.add_argument(
        "--min-percent",
        type=float,
        default=80.0,
        help="Minimum coverage percentage required per file (default: 80).",
    )
    parser.add_argument(
        "--exclude-prefix",
        action="append",
        default=["src/ai_content_classifier/views/"],
        help=(
            "Path prefix to exclude from per-file validation. "
            "Can be provided multiple times."
        ),
    )
    return parser.parse_args()


def _to_posix(path: str) -> str:
    return path.replace("\\", "/")


def _is_excluded(path: str, excluded_prefixes: list[str]) -> bool:
    normalized = _to_posix(path)
    return any(normalized.startswith(_to_posix(prefix)) for prefix in excluded_prefixes)


def main() -> int:
    args = parse_args()
    if not args.report.exists():
        print(f"Coverage report not found: {args.report}", file=sys.stderr)
        return 2

    data = json.loads(args.report.read_text(encoding="utf-8"))
    files = data.get("files", {})

    if not files:
        print("Coverage report contains no file entries.", file=sys.stderr)
        return 2

    below_threshold: list[tuple[str, float]] = []

    for file_path, file_data in files.items():
        if _is_excluded(file_path, args.exclude_prefix):
            continue

        summary = file_data.get("summary", {})
        percent = summary.get("percent_covered")
        if percent is None:
            continue

        if float(percent) < args.min_percent:
            below_threshold.append((file_path, float(percent)))

    if below_threshold:
        below_threshold.sort(key=lambda item: item[1])
        print(
            f"Per-file coverage gate failed: {len(below_threshold)} file(s) "
            f"below {args.min_percent:.1f}%."
        )
        for file_path, percent in below_threshold:
            print(f"- {file_path}: {percent:.1f}%")
        return 1

    print(
        f"Per-file coverage gate passed: all non-excluded files are "
        f">= {args.min_percent:.1f}%."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
