#!/usr/bin/env python3
"""Build data/demo.sql for onboarding: trends/UI tables only, no vector payloads.

The UI reads runs, topics, trends, assessments and timepoints — not chunk
embeddings. Stripping vectors lets ``trendscout seed-demo`` work with the default
``EMBEDDING_DIM=384`` from ``backend/.env.example``.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "demo.sql"
CONTAINER = "trendscout-db"

# Tables required for Dashboard / Newsfeed / Trendradar / detail pages.
KEEP_TABLES = frozenset(
    {
        "source",
        "document",
        "run",
        "run_event",
        "run_document",
        "topic",
        "topic_timepoint",
        "trend",
        "trend_assessment",
        "expert_feedback",
        "reference_trend",
        "trend_translation",
        "canonical_trend",
        "trend_occurrence",
        "trend_decision",
        "baseline_snapshot",
        "baseline_trend",
    }
)

VECTOR_RE = re.compile(r"\[[^\]]+\]")


def _null_topic_centroid(line: str) -> str:
    """Replace topic.centroid vector with NULL; leave other columns untouched."""
    parts = line.split("\t")
    if len(parts) != 9:
        return line
    if parts[6].startswith("["):
        parts[6] = "\\N"
    return "\t".join(parts)


def _filter_dump(raw: str) -> str:
    out: list[str] = []
    i = 0
    lines = raw.splitlines(keepends=True)
    while i < len(lines):
        line = lines[i]
        if line.startswith("COPY public."):
            table = line.split("COPY public.", 1)[1].split(" ", 1)[0]
            if table not in KEEP_TABLES:
                i += 1
                while i < len(lines) and not lines[i].startswith("\\.\n") and lines[i] != "\\.\n":
                    i += 1
                if i < len(lines):
                    i += 1
                continue
            out.append(line)
            i += 1
            while i < len(lines) and not lines[i].startswith("\\.\n") and lines[i] != "\\.\n":
                row = lines[i]
                if table == "topic":
                    row = _null_topic_centroid(row)
                out.append(row)
                i += 1
            if i < len(lines):
                out.append(lines[i])
                i += 1
            continue
        out.append(line)
        i += 1
    return "".join(out)


def _dump_from_docker() -> str:
    proc = subprocess.run(
        [
            "docker",
            "exec",
            CONTAINER,
            "pg_dump",
            "-U",
            "trendscout",
            "-d",
            "trendscout",
            "--data-only",
            "--no-owner",
            "--no-privileges",
        ],
        capture_output=True,
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.decode() or "pg_dump failed")
    return proc.stdout.decode()


def main() -> int:
    source = sys.argv[1] if len(sys.argv) > 1 else None
    if source:
        raw = Path(source).read_text(encoding="utf-8")
    else:
        raw = _dump_from_docker()
    filtered = _filter_dump(raw)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(filtered, encoding="utf-8")
    print(f"Wrote {OUT} ({OUT.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
