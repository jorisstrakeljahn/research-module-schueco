"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { toast } from "sonner";

import PageHeader from "@/components/PageHeader";
import SearchProgressModal, {
  SearchProgressPill,
} from "@/components/SearchProgressModal";
import TrendSearch from "@/components/TrendSearch";
import {
  fetchPortfolioTrends,
  fetchRunDiff,
  fetchRunProgress,
  fetchRuns,
  MATURITY_META,
  MATURITY_ORDER,
  PESTEL_SECTORS,
  type Run,
  type RunDiff,
  type RunMode,
  type RunProgress,
  type Trend,
} from "@/lib/api";
import { useI18n } from "@/lib/i18n";

export default function DashboardPage() {
  const { t, lang } = useI18n();
  const [trends, setTrends] = useState<Trend[]>([]);
  const [run, setRun] = useState<Run | null>(null);
  const [runDiff, setRunDiff] = useState<RunDiff | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeRunId, setActiveRunId] = useState<number | null>(null);
  const [activeQuery, setActiveQuery] = useState("");
  const [activeMode, setActiveMode] = useState<RunMode>("deep_research");
  const [runProgress, setRunProgress] = useState<RunProgress | null>(null);
  const [activeDiff, setActiveDiff] = useState<RunDiff | null>(null);
  const [progressOpen, setProgressOpen] = useState(false);
  const terminalHandledRef = useRef<number | null>(null);

  const reload = useCallback(() => {
    fetchPortfolioTrends("active").then(setTrends).catch((e) => setError(String(e)));
    fetchRuns()
      .then((runs) => {
        const latest = runs[0] ?? null;
        setRun(latest);
        if (latest) fetchRunDiff(latest.id).then(setRunDiff).catch(() => setRunDiff(null));
      })
      .catch(() => setRun(null));
  }, []);

  useEffect(() => {
    Promise.all([fetchPortfolioTrends("active"), fetchRuns()])
      .then(([trendList, runs]) => {
        setTrends(trendList);
        const latest = runs[0] ?? null;
        setRun(latest);
        if (latest) fetchRunDiff(latest.id).then(setRunDiff).catch(() => setRunDiff(null));
      })
      .catch((e) => setError(String(e)))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    if (activeRunId == null) return;
    const runId = activeRunId;
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout> | null = null;

    async function poll() {
      try {
        const next = await fetchRunProgress(runId);
        if (cancelled) return;
        setRunProgress(next);
        const terminal = next.status === "completed" || next.status === "failed";
        if (terminal) {
          if (terminalHandledRef.current !== runId) {
            terminalHandledRef.current = runId;
            if (next.status === "completed") {
              const diff = await fetchRunDiff(runId);
              if (cancelled) return;
              setActiveDiff(diff);
              reload();
              toast.success(t("search.toastDoneTitle"), {
                description: t("search.toastDoneDesc", {
                  topics: next.n_topics,
                  docs: next.n_documents,
                }),
              });
            } else {
              toast.error(t("search.toastFailedTitle"), {
                description: next.error ?? "",
              });
            }
          }
          return;
        }
      } catch {
        /* transient API failure; keep polling the background run */
      }
      if (!cancelled) timer = setTimeout(poll, 1200);
    }

    poll();
    return () => {
      cancelled = true;
      if (timer) clearTimeout(timer);
    };
  }, [activeRunId, reload, t]);

  function handleStarted(result: {
    run_id: number;
    query: string;
    mode: RunMode;
  }) {
    terminalHandledRef.current = null;
    setActiveRunId(result.run_id);
    setActiveQuery(result.query);
    setActiveMode(result.mode);
    setActiveDiff(null);
    setRunProgress({
      run_id: result.run_id,
      status: "running",
      phase: "queued",
      progress: 2,
      message: "",
      n_documents: 0,
      n_topics: 0,
      error: null,
      events: [],
    });
    setProgressOpen(true);
    toast.success(t("search.toastStartTitle"), {
      description: t("search.toastStartDesc", { query: result.query }),
    });
  }

  const maturityCounts = useMemo(() => {
    const c: Record<string, number> = {};
    for (const t of trends) if (t.maturity) c[t.maturity] = (c[t.maturity] ?? 0) + 1;
    return c;
  }, [trends]);

  const pestelCounts = useMemo(() => {
    const c: Record<string, number> = {};
    for (const t of trends) for (const p of t.pestel ?? []) c[p] = (c[p] ?? 0) + 1;
    return c;
  }, [trends]);

  const actCount = trends.filter((t) => t.radar_stage === "act").length;

  return (
    <div className="flex h-full min-w-0 flex-col overflow-hidden">
      <PageHeader title={t("dashboard.title")} subtitle={t("dashboard.subtitle")} />
      {loading ? (
        <p className="p-6 text-sm text-muted">{t("dashboard.loading")}</p>
      ) : error ? (
        <p className="p-6 text-sm">
          <span className="text-digital">{t("dashboard.apiError")}</span>{" "}
          <span className="text-faint">{error}</span>
        </p>
      ) : (
        <div className="flex-1 overflow-auto">
          <div className="mx-auto max-w-5xl space-y-6 p-6">
            <TrendSearch
              onStarted={handleStarted}
              onError={(message) =>
                toast.error(t("search.toastErrorTitle"), { description: message })
              }
            />

      <div className="grid grid-cols-2 gap-4">
        <KpiCard value={trends.length} label={t("dashboard.kpi.total")} />
        <KpiCard value={actCount} label={t("dashboard.kpi.act")} accent />
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <Panel title={t("dashboard.panel.maturity")}>
          {MATURITY_ORDER.map((m) => (
            <Bar
              key={m}
              label={t(`maturity.${m}`)}
              count={maturityCounts[m] ?? 0}
              total={trends.length}
              color={MATURITY_META[m].color}
            />
          ))}
        </Panel>
        <Panel title={t("dashboard.panel.pestel")}>
          {PESTEL_SECTORS.map((s) => (
            <Bar
              key={s.key}
              label={s.label}
              count={pestelCounts[s.key] ?? 0}
              total={trends.length}
              color="#00a651"
            />
          ))}
        </Panel>
      </div>

      {runDiff && (
        <Panel title={t("dashboard.panel.lastDiff")}>
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            {(["new", "updated", "unchanged", "review"] as const).map((kind) => (
              <Link
                key={kind}
                href={`/runs/${runDiff.run_id}`}
                className="rounded-lg bg-surface-2 p-3 transition-colors hover:bg-hover"
              >
                <div className="text-xl font-semibold tabular-nums text-fg">
                  {runDiff.counts[kind] ?? 0}
                </div>
                <div className="mt-1 text-xs text-muted">{t(`diff.${kind}`)}</div>
              </Link>
            ))}
          </div>
        </Panel>
      )}

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        <QuickLink
          href="/newsfeed"
          title={t("nav.newsfeed")}
          desc={t("dashboard.quick.newsfeedDesc")}
          open={t("dashboard.open")}
        />
        <QuickLink
          href="/radar"
          title={t("nav.radar")}
          desc={t("dashboard.quick.radarDesc")}
          open={t("dashboard.open")}
        />
      </div>

            {run && (
              <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-faint">
                <span>
                  {t("dashboard.runMeta", {
                    date: new Intl.DateTimeFormat(lang, {
                      dateStyle: "medium",
                      timeStyle: "short",
                    }).format(new Date(run.started_at)),
                  })}
                </span>
                <span>
                  {t("dashboard.runStats", {
                    docs: run.n_documents,
                    topics: run.n_topics,
                  })}
                </span>
              </div>
            )}
          </div>
        </div>
      )}
      {runProgress && (
        <>
          <SearchProgressModal
            open={progressOpen}
            query={activeQuery}
            mode={activeMode}
            progress={runProgress}
            diff={activeDiff}
            onClose={() => setProgressOpen(false)}
          />
          {!progressOpen && (
            <SearchProgressPill
              progress={runProgress}
              onClick={() => setProgressOpen(true)}
            />
          )}
        </>
      )}
    </div>
  );
}

function KpiCard({
  value,
  label,
  accent,
}: {
  value: number;
  label: string;
  accent?: boolean;
}) {
  return (
    <div className="rounded-xl border border-border bg-surface p-5 shadow-sm">
      <div className={`text-3xl font-semibold ${accent ? "text-primary" : "text-fg"}`}>
        {value}
      </div>
      <div className="mt-1 text-sm text-muted">{label}</div>
    </div>
  );
}

function Panel({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="rounded-xl border border-border bg-surface shadow-sm">
      <h3 className="border-b border-border px-5 py-3 text-sm font-medium text-fg">
        {title}
      </h3>
      <div className="space-y-2.5 p-5">{children}</div>
    </div>
  );
}

function Bar({
  label,
  count,
  total,
  color,
}: {
  label: string;
  count: number;
  total: number;
  color: string;
}) {
  const pct = total > 0 ? (count / total) * 100 : 0;
  return (
    <div className="flex items-center gap-3">
      <span className="w-36 shrink-0 truncate text-sm text-muted">{label}</span>
      <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-surface-2">
        <div
          className="h-full rounded-full"
          style={{ width: `${pct}%`, backgroundColor: color }}
        />
      </div>
      <span className="w-5 shrink-0 text-right text-sm tabular-nums text-fg">{count}</span>
    </div>
  );
}

function QuickLink({
  href,
  title,
  desc,
  open,
}: {
  href: string;
  title: string;
  desc: string;
  open: string;
}) {
  return (
    <Link
      href={href}
      className="group rounded-xl border border-border bg-surface p-5 shadow-sm transition-colors hover:bg-surface-2"
    >
      <h3 className="text-base font-medium text-fg">{title}</h3>
      <p className="mt-1 text-sm text-muted">{desc}</p>
      <span className="mt-3 inline-block text-sm text-primary">{open}</span>
    </Link>
  );
}
