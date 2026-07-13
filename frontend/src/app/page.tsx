"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { toast } from "sonner";

import PageHeader from "@/components/PageHeader";
import TrendSearch from "@/components/TrendSearch";
import {
  fetchPortfolioTrends,
  fetchRuns,
  MATURITY_META,
  MATURITY_ORDER,
  PESTEL_SECTORS,
  type PortfolioTrend,
  type Run,
} from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import { useRunProgress } from "@/lib/run-progress";

export default function DashboardPage() {
  const { t, lang } = useI18n();
  const { startRun, completedCount } = useRunProgress();
  const [trends, setTrends] = useState<PortfolioTrend[]>([]);
  const [run, setRun] = useState<Run | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([
      fetchPortfolioTrends("active", lang, { includePending: true }),
      fetchRuns(),
    ])
      .then(([trendList, runs]) => {
        setTrends(trendList);
        setRun(runs[0] ?? null);
        setError(null);
      })
      .catch((e) => setError(String(e)))
      .finally(() => setLoading(false));
  }, [lang, completedCount]);

  const active = useMemo(
    () => trends.filter((trend) => !isPendingNew(trend)),
    [trends],
  );
  const pendingNew = useMemo(
    () => trends.filter((trend) => isPendingNew(trend)),
    [trends],
  );
  const pendingTotal = useMemo(
    () => trends.filter((trend) => trend.pending_review).length,
    [trends],
  );
  const pendingRunId = useMemo(
    () =>
      trends.reduce<number | null>(
        (latest, trend) =>
          trend.pending_run_id != null &&
          (latest == null || trend.pending_run_id > latest)
            ? trend.pending_run_id
            : latest,
        null,
      ),
    [trends],
  );

  const maturityCounts = useMemo(() => {
    const c: Record<string, number> = {};
    for (const t of active) if (t.maturity) c[t.maturity] = (c[t.maturity] ?? 0) + 1;
    return c;
  }, [active]);

  const pestelCounts = useMemo(() => {
    const c: Record<string, number> = {};
    for (const t of active) for (const p of t.pestel ?? []) c[p] = (c[p] ?? 0) + 1;
    return c;
  }, [active]);

  const actCount = active.filter((t) => t.radar_stage === "act").length;
  // Unreviewed candidates that would land in the "act" ring once approved.
  const pendingActCount = pendingNew.filter((t) => t.radar_stage === "act").length;

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
              onStarted={startRun}
              onError={(message) =>
                toast.error(t("search.toastErrorTitle"), { description: message })
              }
            />

            {pendingTotal > 0 && pendingRunId != null && (
              <Link
                href={`/runs/${pendingRunId}`}
                className="flex items-center justify-between gap-3 rounded-xl border border-pending/40 bg-pending/10 px-5 py-3.5 transition-colors hover:bg-pending/15"
              >
                <span className="text-sm text-fg">
                  {t("dashboard.pendingBanner", { n: pendingTotal })}
                </span>
                <span className="shrink-0 text-sm font-medium text-pending">
                  {t("dashboard.pendingBannerCta")} →
                </span>
              </Link>
            )}

      <div className="grid grid-cols-2 gap-4">
        <KpiCard
          value={active.length}
          label={t("dashboard.kpi.total")}
          badge={
            pendingNew.length > 0
              ? t("dashboard.kpi.pendingNew", { n: pendingNew.length })
              : undefined
          }
        />
        <KpiCard
          value={actCount}
          label={t("dashboard.kpi.act")}
          accent
          badge={
            pendingActCount > 0
              ? t("dashboard.kpi.pendingAct", { n: pendingActCount })
              : undefined
          }
        />
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <Panel title={t("dashboard.panel.maturity")}>
          {MATURITY_ORDER.map((m) => (
            <Bar
              key={m}
              label={t(`maturity.${m}`)}
              count={maturityCounts[m] ?? 0}
              total={active.length}
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
              total={active.length}
              color="#00a651"
            />
          ))}
        </Panel>
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
    </div>
  );
}

function isPendingNew(trend: PortfolioTrend): boolean {
  return Boolean(trend.pending_review) && String(trend.id).startsWith("pending-");
}

function KpiCard({
  value,
  label,
  accent,
  badge,
}: {
  value: number;
  label: string;
  accent?: boolean;
  badge?: string;
}) {
  return (
    <div className="rounded-xl border border-border bg-surface p-5 shadow-sm">
      <div className="flex items-baseline gap-2">
        <span
          className={`text-3xl font-semibold ${accent ? "text-primary" : "text-fg"}`}
        >
          {value}
        </span>
        {badge && (
          <span className="rounded-full bg-pending/15 px-2 py-0.5 text-xs font-medium text-pending">
            {badge}
          </span>
        )}
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
