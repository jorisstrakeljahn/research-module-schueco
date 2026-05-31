"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";

import {
  fetchRuns,
  fetchTrends,
  MATURITY_META,
  MATURITY_ORDER,
  type Maturity,
  type Run,
  type Trend,
} from "@/lib/api";

type Filter = Maturity | "all";

export default function HomePage() {
  const [trends, setTrends] = useState<Trend[]>([]);
  const [run, setRun] = useState<Run | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState<Filter>("all");

  useEffect(() => {
    Promise.all([fetchTrends(), fetchRuns()])
      .then(([t, runs]) => {
        setTrends(t);
        setRun(runs[0] ?? null);
      })
      .catch((e) => setError(String(e)))
      .finally(() => setLoading(false));
  }, []);

  const counts = useMemo(() => {
    const c: Record<string, number> = {};
    for (const t of trends) if (t.maturity) c[t.maturity] = (c[t.maturity] ?? 0) + 1;
    return c;
  }, [trends]);

  if (loading)
    return <p className="text-sm text-slate-400">Loading trends…</p>;

  if (error)
    return (
      <div className="border-l-2 border-red-300 pl-3 text-sm text-red-700">
        Could not reach the API. Is the backend running on{" "}
        <code className="text-red-600">http://127.0.0.1:8000</code>?
        <div className="mt-1 text-xs text-red-400">{error}</div>
      </div>
    );

  return (
    <div>
      <header className="mb-6">
        <h1 className="text-xl font-semibold tracking-tight text-slate-900">
          Trendradar
        </h1>
        <p className="mt-1 text-sm text-slate-500">
          AI-discovered trends in building-envelope technology, ordered by
          maturity. PESTEL sectors and impact/uncertainty follow in the next
          stage.
        </p>
      </header>

      {/* result count + run provenance */}
      <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
        <p className="text-sm text-slate-500">
          <span className="font-semibold text-slate-900">{trends.length}</span>{" "}
          trends
        </p>
        {run && (
          <p className="font-mono text-xs text-slate-400">
            Run #{run.id} · {run.n_documents} documents · {run.n_topics} topics ·{" "}
            {run.embedder}/{run.topic_model}/{run.describer}
          </p>
        )}
      </div>

      {/* facets */}
      <nav className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-1 border-y border-slate-200 py-2 text-[13px]">
        <FacetButton
          active={filter === "all"}
          onClick={() => setFilter("all")}
          label="All"
          count={trends.length}
        />
        {MATURITY_ORDER.map((m) => (
          <FacetButton
            key={m}
            active={filter === m}
            onClick={() => setFilter(m)}
            label={MATURITY_META[m].label}
            count={counts[m] ?? 0}
            dot={MATURITY_META[m].dot}
          />
        ))}
      </nav>

      {trends.length === 0 ? (
        <p className="mt-8 text-sm text-slate-500">
          No trends yet. Run the pipeline:{" "}
          <code className="text-slate-700">
            uv run trendscout research &quot;adaptive facade&quot;
          </code>
        </p>
      ) : filter === "all" ? (
        <div className="mt-2">
          {MATURITY_ORDER.map((m) => {
            const items = trends
              .filter((t) => t.maturity === m)
              .sort((a, b) => b.size - a.size);
            if (items.length === 0) return null;
            return (
              <section key={m}>
                <SectionHeader maturity={m} count={items.length} />
                <ul>
                  {items.map((t) => (
                    <TrendRow key={t.id} trend={t} />
                  ))}
                </ul>
              </section>
            );
          })}
        </div>
      ) : (
        <ul className="mt-2">
          {trends
            .filter((t) => t.maturity === filter)
            .sort((a, b) => b.size - a.size)
            .map((t) => (
              <TrendRow key={t.id} trend={t} />
            ))}
        </ul>
      )}
    </div>
  );
}

function FacetButton({
  active,
  onClick,
  label,
  count,
  dot,
}: {
  active: boolean;
  onClick: () => void;
  label: string;
  count: number;
  dot?: string;
}) {
  return (
    <button
      onClick={onClick}
      className={`inline-flex items-center gap-1.5 transition-colors ${
        active
          ? "font-semibold text-slate-900"
          : "text-slate-500 hover:text-slate-900"
      }`}
    >
      {dot && <span className={`h-1.5 w-1.5 rounded-full ${dot}`} />}
      {label}
      <span className="text-slate-400">{count}</span>
    </button>
  );
}

function SectionHeader({
  maturity,
  count,
}: {
  maturity: Maturity;
  count: number;
}) {
  const meta = MATURITY_META[maturity];
  return (
    <div className="mt-7 mb-1 flex items-center gap-2">
      <span className={`h-2 w-2 rounded-full ${meta.dot}`} />
      <h2 className="text-xs font-semibold uppercase tracking-wider text-slate-500">
        {meta.label}
      </h2>
      <span className="text-xs text-slate-400">{count}</span>
    </div>
  );
}

function TrendRow({ trend }: { trend: Trend }) {
  return (
    <li className="border-b border-slate-100">
      <Link
        href={`/trends/${trend.id}`}
        className="group -mx-3 block rounded-sm px-3 py-3 transition-colors hover:bg-slate-50"
      >
        <h3 className="text-[15px] font-medium leading-snug text-slate-900 group-hover:text-blue-700">
          {trend.title}
        </h3>
        <div className="mt-1 flex flex-wrap items-center gap-x-2 text-[12.5px] text-slate-500">
          <span>{trend.size} documents</span>
          {trend.keywords.length > 0 && (
            <>
              <span className="text-slate-300">·</span>
              <span className="truncate text-slate-400">
                {trend.keywords.slice(0, 6).join(", ")}
              </span>
            </>
          )}
        </div>
      </Link>
    </li>
  );
}
