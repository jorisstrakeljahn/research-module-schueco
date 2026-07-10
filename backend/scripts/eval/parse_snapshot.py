"""Export one explicitly materialized run from ``data/demo.sql``.

Unlike the legacy evaluator, this module never guesses run membership from the
global document table. A corpus is exportable only when ``run_document`` records
its exact membership. This prevents the former 540-vs-280 document mismatch.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
SNAPSHOT = REPO_ROOT / "data" / "demo.sql"
OUT_DIR = Path(__file__).resolve().parent / "_out"


def _unescape(value: str) -> str:
    return (
        value.replace("\\t", "\t")
        .replace("\\n", "\n")
        .replace("\\r", "\r")
        .replace("\\\\", "\\")
    )


def parse_copy_blocks(sql_text: str) -> dict[str, list[dict]]:
    """Return {table_name: [row_dict, ...]} for every COPY block in the dump."""
    tables: dict[str, list[dict]] = {}
    lines = sql_text.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]
        if line.startswith("COPY public."):
            header = line[len("COPY public.") :]
            table = header.split(" ", 1)[0]
            cols = header[header.index("(") + 1 : header.index(")")]
            columns = [c.strip().strip('"') for c in cols.split(",")]
            rows: list[dict] = []
            i += 1
            while i < len(lines) and lines[i] != "\\.":
                raw = lines[i].split("\t")
                row = {}
                for col, val in zip(columns, raw, strict=False):
                    row[col] = None if val == "\\N" else _unescape(val)
                rows.append(row)
                i += 1
            tables[table] = rows
        i += 1
    return tables


def _to_float(value: str | None) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except ValueError:
        return None


def _run_row(tables: dict[str, list[dict]], run_id: int) -> dict:
    try:
        return next(row for row in tables["run"] if row["id"] == str(run_id))
    except StopIteration as exc:
        raise ValueError(f"Run {run_id} does not exist in the snapshot") from exc


def runs_with_materialized_corpus(tables: dict[str, list[dict]]) -> list[int]:
    return sorted({int(row["run_id"]) for row in tables.get("run_document", [])})


def resolve_run_id(tables: dict[str, list[dict]], requested: int | None) -> int:
    available = runs_with_materialized_corpus(tables)
    if requested is not None:
        if requested not in available:
            raise ValueError(
                f"Run {requested} has no materialized run_document corpus; "
                f"available runs: {available or 'none'}"
            )
        return requested
    if not available:
        raise ValueError(
            "The snapshot contains no materialized run corpus. Run a new pipeline "
            "after the portfolio migration before generating evaluation artifacts."
        )
    completed = {
        int(row["id"])
        for row in tables.get("run", [])
        if row.get("status") == "completed"
    }
    candidates = [run_id for run_id in available if run_id in completed]
    if not candidates:
        raise ValueError("No completed run has a materialized corpus")
    return max(candidates)


def build_chart_data(tables: dict[str, list[dict]], run_id: int) -> dict:
    topics_by_id = {
        t["id"]: t for t in tables["topic"] if t["run_id"] == str(run_id)
    }
    assessments_by_trend = {a["trend_id"]: a for a in tables["trend_assessment"]}
    timepoints: dict[str, list[dict]] = {}
    for tp in tables.get("topic_timepoint", []):
        timepoints.setdefault(tp["topic_id"], []).append(
            {"period": tp["period"], "doc_count": int(tp["doc_count"])}
        )

    trends = []
    for tr in tables["trend"]:
        if tr["run_id"] != str(run_id):
            continue
        assessment = assessments_by_trend.get(tr["id"], {})
        topic = topics_by_id.get(tr["topic_id"], {})
        tps = sorted(timepoints.get(tr["topic_id"], []), key=lambda x: x["period"])
        trends.append(
            {
                "trend_id": int(tr["id"]),
                "topic_id": int(tr["topic_id"]),
                "title": tr["title"],
                "maturity": tr["maturity"],
                "emergence": _to_float(tr["emergence"]),
                "size": int(topic["size"]) if topic.get("size") else None,
                "label": topic.get("label"),
                "pestel": _json_value(assessment.get("pestel")),
                "category": assessment.get("category"),
                "impact": _to_float(assessment.get("impact")),
                "uncertainty": _to_float(assessment.get("uncertainty")),
                "urgency": _to_float(assessment.get("urgency")),
                "radar_stage": assessment.get("radar_stage"),
                "timepoints": tps,
            }
        )

    trends.sort(key=lambda t: (-(t["impact"] or 0), -(t["uncertainty"] or 0)))

    distributions = {
        "maturity": dict(Counter(t["maturity"] for t in trends)),
        "pestel": dict(
            Counter(
                category
                for trend in trends
                for category in (
                    trend["pestel"]
                    if isinstance(trend["pestel"], list)
                    else [trend["pestel"]]
                )
                if category
            )
        ),
        "radar_stage": dict(Counter(t["radar_stage"] for t in trends)),
        "category": dict(Counter(t["category"] for t in trends)),
    }

    run = _run_row(tables, run_id)
    return {
        "run": {
            "id": int(run["id"]),
            "embedder": run["embedder"],
            "topic_model": run["topic_model"],
            "describer": run["describer"],
            "classifier": run.get("classifier"),
            "n_documents": int(run["n_documents"]),
            "n_topics": int(run["n_topics"]),
            "corpus_hash": run.get("corpus_hash"),
            "component_manifest": _json_value(run.get("component_manifest")),
        },
        "n_trends": len(trends),
        "trends": trends,
        "distributions": distributions,
    }


def _json_value(value: str | None):
    if value is None:
        return None
    try:
        return json.loads(value)
    except (TypeError, json.JSONDecodeError):
        return value


def build_corpus(tables: dict[str, list[dict]], run_id: int) -> list[dict]:
    documents = {row["id"]: row for row in tables["document"]}
    memberships = sorted(
        (
            row
            for row in tables.get("run_document", [])
            if row["run_id"] == str(run_id)
        ),
        key=lambda row: int(row["position"]),
    )
    if not memberships:
        raise ValueError(f"Run {run_id} has no materialized corpus")
    corpus = []
    for membership in memberships:
        doc = documents[membership["document_id"]]
        title = doc.get("title") or ""
        text = doc.get("text") or ""
        if not (title or text).strip():
            continue
        corpus.append(
            {
                "id": int(doc["id"]),
                "title": title,
                "text": text,
                "published_at": doc.get("published_at"),
                "source_id": int(doc["source_id"]) if doc.get("source_id") else None,
                "content_hash": doc.get("content_hash"),
                "provenance": membership.get("provenance"),
                "topic_index": (
                    int(membership["topic_index"])
                    if membership.get("topic_index") is not None
                    else None
                ),
                "is_outlier": membership.get("is_outlier") == "t",
            }
        )
    return corpus


def build_manifest(
    tables: dict[str, list[dict]], run_id: int, corpus: list[dict]
) -> dict:
    run = _run_row(tables, run_id)
    source_names = {
        row["id"]: row.get("name") or "unknown" for row in tables.get("source", [])
    }
    source_distribution = Counter(
        source_names.get(str(row["source_id"]), "unknown")
        for row in corpus
        if row.get("source_id") is not None
    )
    occurrences = [
        row
        for row in tables.get("trend_occurrence", [])
        if row["run_id"] == str(run_id)
    ]
    return {
        "run_id": run_id,
        "corpus_hash": run.get("corpus_hash"),
        "n_documents": len(corpus),
        "n_new_documents": sum(row["provenance"] == "new" for row in corpus),
        "n_carried_forward": sum(
            row["provenance"] == "carried_forward" for row in corpus
        ),
        "source_distribution": dict(source_distribution),
        "funnel": {
            "topics": int(run.get("n_topics") or 0),
            "new": sum(row.get("change_type") == "new" for row in occurrences),
            "updated": sum(row.get("change_type") == "updated" for row in occurrences),
            "unchanged": sum(
                row.get("change_type") == "unchanged" for row in occurrences
            ),
            "review": sum(row.get("change_type") == "review" for row in occurrences),
        },
        "configuration": {
            "embedder": run.get("embedder"),
            "embedder_revision": run.get("embedder_revision"),
            "topic_model": run.get("topic_model"),
            "topic_model_revision": run.get("topic_model_revision"),
            "random_seed": int(run.get("random_seed") or 42),
            "component_manifest": _json_value(run.get("component_manifest")),
            "prompt_manifest": _json_value(run.get("prompt_manifest")),
            "git_revision": run.get("git_revision"),
        },
    }


def export_run(
    tables: dict[str, list[dict]], run_id: int, out_dir: Path = OUT_DIR
) -> tuple[Path, Path, Path]:
    chart_data = build_chart_data(tables, run_id)
    corpus = build_corpus(tables, run_id)
    manifest = build_manifest(tables, run_id, corpus)
    out_dir.mkdir(parents=True, exist_ok=True)
    chart_path = out_dir / f"chart_data_run_{run_id}.json"
    corpus_path = out_dir / f"corpus_run_{run_id}.jsonl"
    manifest_path = out_dir / f"manifest_run_{run_id}.json"
    chart_path.write_text(
        json.dumps(chart_data, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    with corpus_path.open("w", encoding="utf-8") as handle:
        for row in corpus:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    manifest_path.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return chart_path, corpus_path, manifest_path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", type=int)
    parser.add_argument("--snapshot", type=Path, default=SNAPSHOT)
    args = parser.parse_args()
    sql_text = args.snapshot.read_text(encoding="utf-8")
    tables = parse_copy_blocks(sql_text)
    run_id = resolve_run_id(tables, args.run_id)
    paths = export_run(tables, run_id)
    print(f"exported run {run_id}: {', '.join(str(path) for path in paths)}")


if __name__ == "__main__":
    main()
