"""Parse the demo snapshot (data/demo.sql) into clean evaluation datasets.

Outputs (written next to this script under ``_out/``):
  * ``chart_data.json`` - the evaluated Run 7 trends joined with their
    assessment scores and cluster sizes, plus distribution summaries.
  * ``corpus.jsonl``     - the document corpus of the snapshot (title + text),
    used as the input for the topic-model comparison.

No database is required. The parser reads the Postgres ``COPY ... FROM stdin``
blocks directly so the evaluation is fully reproducible from the committed
snapshot.
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
SNAPSHOT = REPO_ROOT / "data" / "demo.sql"
OUT_DIR = Path(__file__).resolve().parent / "_out"
EVAL_RUN_ID = 7


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
            columns = [c.strip() for c in cols.split(",")]
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


def build_chart_data(tables: dict[str, list[dict]]) -> dict:
    topics_by_id = {t["id"]: t for t in tables["topic"] if t["run_id"] == str(EVAL_RUN_ID)}
    assessments_by_trend = {a["trend_id"]: a for a in tables["trend_assessment"]}
    timepoints: dict[str, list[dict]] = {}
    for tp in tables.get("topic_timepoint", []):
        timepoints.setdefault(tp["topic_id"], []).append(
            {"period": tp["period"], "doc_count": int(tp["doc_count"])}
        )

    trends = []
    for tr in tables["trend"]:
        if tr["run_id"] != str(EVAL_RUN_ID):
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
                "pestel": assessment.get("pestel"),
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
        "pestel": dict(Counter(t["pestel"] for t in trends)),
        "radar_stage": dict(Counter(t["radar_stage"] for t in trends)),
        "category": dict(Counter(t["category"] for t in trends)),
    }

    run = next(r for r in tables["run"] if r["id"] == str(EVAL_RUN_ID))
    return {
        "run": {
            "id": int(run["id"]),
            "embedder": run["embedder"],
            "topic_model": run["topic_model"],
            "describer": run["describer"],
            "n_documents": int(run["n_documents"]),
            "n_topics": int(run["n_topics"]),
        },
        "n_trends": len(trends),
        "trends": trends,
        "distributions": distributions,
    }


def build_corpus(tables: dict[str, list[dict]]) -> list[dict]:
    corpus = []
    for doc in tables["document"]:
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
            }
        )
    return corpus


def main() -> None:
    sql_text = SNAPSHOT.read_text(encoding="utf-8")
    tables = parse_copy_blocks(sql_text)
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    chart_data = build_chart_data(tables)
    (OUT_DIR / "chart_data.json").write_text(
        json.dumps(chart_data, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    corpus = build_corpus(tables)
    with (OUT_DIR / "corpus.jsonl").open("w", encoding="utf-8") as fh:
        for row in corpus:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")

    print(f"run {chart_data['run']['id']}: "
          f"{chart_data['run']['n_documents']} docs, "
          f"{chart_data['run']['n_topics']} topics")
    print(f"trends parsed: {chart_data['n_trends']}")
    print(f"corpus documents: {len(corpus)}")
    print(f"maturity: {chart_data['distributions']['maturity']}")
    print(f"pestel:   {chart_data['distributions']['pestel']}")
    print(f"radar:    {chart_data['distributions']['radar_stage']}")


if __name__ == "__main__":
    main()
