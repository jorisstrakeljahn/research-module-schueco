"use client";

import { ArrowLeft, ExternalLink, GitCommitHorizontal, UserRound } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import { toast } from "sonner";

import Score from "@/components/Score";
import TrendBadges from "@/components/TrendBadges";
import {
  decidePortfolioTrend,
  fetchPestelAnalysis,
  fetchPortfolioTrend,
  fetchTrendHistory,
  type PestelAnalysis,
  type PestelDimensionAnalysis,
  type PortfolioDecisionInput,
  type PortfolioTrendDetail,
  type Timepoint,
  type TrendDecision,
  type TrendHistory,
  type TrendHistoryPoint,
} from "@/lib/api";
import { useI18n } from "@/lib/i18n";

export default function PortfolioTrendPage() {
  const { t } = useI18n();
  const params = useParams<{ id: string }>();
  const [trend, setTrend] = useState<PortfolioTrendDetail | null>(null);
  const [history, setHistory] = useState<TrendHistory | null>(null);
  const [pestel, setPestel] = useState<PestelAnalysis | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([
      fetchPortfolioTrend(params.id),
      fetchTrendHistory(params.id),
      fetchPestelAnalysis(params.id),
    ])
      .then(([trendData, historyData, pestelData]) => {
        setTrend(trendData);
        setHistory(historyData);
        setPestel(pestelData);
      })
      .catch((e) => setError(String(e)));
  }, [params.id]);

  const evidence = useMemo(() => {
    const all = [...(trend?.evidence ?? []), ...(history?.evidence ?? [])];
    return all.filter(
      (item, index) =>
        all.findIndex((candidate) => candidate.title === item.title && candidate.url === item.url) ===
        index,
    );
  }, [history, trend]);

  if (error) return <div className="p-8 text-sm text-digital">{error}</div>;
  if (!trend || !history || !pestel)
    return <div className="p-8 text-sm text-muted">{t("portfolioDetail.loading")}</div>;

  return (
    <div className="h-full overflow-auto">
      <article className="mx-auto max-w-6xl p-6">
        <Link href="/portfolio" className="inline-flex items-center gap-2 text-sm text-muted hover:text-fg">
          <ArrowLeft className="h-4 w-4" /> {t("portfolioDetail.back")}
        </Link>

        <header className="mt-6 rounded-xl border border-border bg-surface p-6 shadow-sm">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div className="max-w-3xl">
              <TrendBadges trend={trend} />
              <h1 className="mt-4 text-3xl font-semibold tracking-tight text-fg">{trend.title}</h1>
              <p className="mt-3 text-[15px] leading-relaxed text-muted">{trend.summary}</p>
            </div>
            <span className="rounded-full bg-primary/10 px-3 py-1 text-xs font-semibold uppercase tracking-wide text-primary">
              {trend.status}
            </span>
          </div>
          <div className="mt-6 grid max-w-xl grid-cols-3 gap-3">
            <Score label="Impact" value={trend.impact} />
            <Score label="Urgency" value={trend.urgency} />
            <Score label="Uncertainty" value={trend.uncertainty} />
          </div>
          {trend.rationale && (
            <p className="mt-5 border-l-2 border-primary/40 pl-4 text-sm italic leading-relaxed text-muted">
              {trend.rationale}
            </p>
          )}
        </header>

        <div className="mt-6 grid gap-6 xl:grid-cols-[minmax(0,1.45fr)_minmax(0,0.85fr)]">
          <div className="min-w-0 space-y-6">
            <Section title={t("portfolioDetail.pestel")}>
              <p className="-mt-2 mb-5 text-sm leading-relaxed text-muted">
                {t("portfolioDetail.pestelIntro")}
              </p>
              <PestelGrid analysis={pestel} />
            </Section>

            <Section title={t("portfolioDetail.history")}>
              <HistoryChart points={history.points} />
              <div className="mt-5 space-y-0">
                {[...history.points].reverse().map((point) => (
                  <HistoryRow key={`${point.run_id}-${point.occurred_at}`} point={point} />
                ))}
              </div>
            </Section>

            <Section title={t("portfolioDetail.activity")}>
              <ActivityChart points={trend.timeseries} />
            </Section>

            <Section title={t("portfolioDetail.evidence", { n: evidence.length })}>
              {evidence.length === 0 ? (
                <p className="text-sm text-muted">{t("portfolioDetail.noEvidence")}</p>
              ) : (
                <ol className="divide-y divide-border">
                  {evidence.map((item, index) => (
                    <li key={`${item.title}-${index}`} className="flex gap-3 py-3 first:pt-0">
                      <span className="mt-0.5 text-xs tabular-nums text-faint">{index + 1}</span>
                      <div className="min-w-0">
                        {item.url ? (
                          <a
                            href={item.url}
                            target="_blank"
                            rel="noreferrer"
                            className="flex max-w-full items-start gap-1.5 text-sm text-primary hover:underline"
                          >
                            <span className="min-w-0 wrap-break-word">{item.title}</span>
                            <ExternalLink className="mt-0.5 h-3.5 w-3.5 shrink-0" />
                          </a>
                        ) : (
                          <p className="text-sm text-fg">{item.title}</p>
                        )}
                        {(item.source || item.published_at) && (
                          <p className="mt-1 text-xs text-faint">
                            {[item.source, item.published_at].filter(Boolean).join(" · ")}
                          </p>
                        )}
                      </div>
                    </li>
                  ))}
                </ol>
              )}
            </Section>
          </div>

          <div className="min-w-0 space-y-6">
            <Section title={t("portfolioDetail.decisions")}>
              <DecisionList decisions={history.decisions} />
            </Section>
            <DecisionForm
              trendId={trend.id}
              onSaved={(decision) =>
                setHistory((current) =>
                  current ? { ...current, decisions: [decision, ...current.decisions] } : current,
                )
              }
            />
          </div>
        </div>
      </article>
    </div>
  );
}

function PestelGrid({ analysis }: { analysis: PestelAnalysis }) {
  const { t } = useI18n();
  return (
    <div>
      <div className="grid gap-3 md:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
        {analysis.dimensions.map((dimension) => (
          <PestelDimension key={dimension.dimension} dimension={dimension} />
        ))}
      </div>
      <p className="mt-4 text-xs text-faint">
        {t("portfolioDetail.pestelRun")}
      </p>
    </div>
  );
}

function PestelDimension({ dimension }: { dimension: PestelDimensionAnalysis }) {
  const { t } = useI18n();
  return (
    <article className="min-w-0 rounded-lg border border-border bg-bg p-4">
      <div className="flex items-center justify-between gap-3">
        <h3 className="text-sm font-semibold text-fg">{t(`pestel.${dimension.dimension}`)}</h3>
        <span className="text-xs font-semibold tabular-nums text-primary">
          {dimension.relevance.toFixed(1)}/10
        </span>
      </div>
      <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-border">
        <div
          className="h-full rounded-full bg-primary"
          style={{ width: `${dimension.relevance * 10}%` }}
        />
      </div>
      <ul className="mt-3 space-y-1.5 wrap-break-word text-xs leading-relaxed text-muted">
        <li>
          {t("portfolioDetail.pestelCoverage", {
            matched: dimension.matched_documents,
            total: dimension.total_documents,
          })}
        </li>
        <li>
          {dimension.signal_terms.length
            ? t("portfolioDetail.pestelTerms", { terms: dimension.signal_terms.join(", ") })
            : t("portfolioDetail.pestelNoTerms")}
        </li>
        {dimension.evidence.slice(0, 2).map((item) => (
          <li key={`${dimension.dimension}-${item.title}`} className="text-fg">
            {item.title}
          </li>
        ))}
      </ul>
    </article>
  );
}

function ActivityChart({ points }: { points: Timepoint[] }) {
  const { t } = useI18n();
  if (points.length === 0) return <p className="text-sm text-muted">{t("portfolioDetail.noHistory")}</p>;
  const maximum = Math.max(...points.map((point) => point.doc_count), 1);
  const axisPoints = points.filter(
    (_, index) => index % 4 === 0 || index === points.length - 1,
  );
  return (
    <div>
      <div className="flex h-40 items-end gap-2 border-b border-border px-1">
        {points.map((point) => (
          <div key={point.period} className="flex h-full min-w-0 flex-1 flex-col justify-end">
            {point.doc_count > 0 && (
              <span className="mb-1 text-center text-[10px] tabular-nums text-faint">
                {point.doc_count}
              </span>
            )}
            <div
              className="min-h-1 rounded-t bg-primary/70"
              style={{ height: `${Math.max(4, (point.doc_count / maximum) * 118)}px` }}
              title={`${point.period}: ${point.doc_count}`}
            />
          </div>
        ))}
      </div>
      <div className="mt-2 flex justify-between px-1">
        {axisPoints.map((point) => (
          <span key={point.period} className="text-[10px] text-faint">
            {point.period.slice(0, 4)}
          </span>
        ))}
      </div>
      <p className="mt-3 text-xs text-faint">{t("portfolioDetail.activityUnit")}</p>
    </div>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="rounded-xl border border-border bg-surface p-5 shadow-sm">
      <h2 className="mb-5 text-sm font-semibold text-fg">{title}</h2>
      {children}
    </section>
  );
}

function HistoryChart({ points }: { points: TrendHistoryPoint[] }) {
  const { t } = useI18n();
  if (points.length === 0) return <p className="text-sm text-muted">{t("portfolioDetail.noHistory")}</p>;
  const metrics = [
    { key: "impact" as const, color: "#00a651", label: "Impact" },
    { key: "urgency" as const, color: "#2ba8e0", label: "Urgency" },
    { key: "uncertainty" as const, color: "#f5a623", label: "Uncertainty" },
  ];
  const width = 640;
  const height = 150;
  const x = (index: number) => (points.length === 1 ? width / 2 : (index / (points.length - 1)) * width);
  const y = (value: number) => height - (Math.max(0, Math.min(10, value)) / 10) * height;

  return (
    <div>
      <div className="flex flex-wrap gap-4 text-xs text-muted">
        {metrics.map((metric) => (
          <span key={metric.key} className="flex items-center gap-1.5">
            <span className="h-2 w-2 rounded-full" style={{ backgroundColor: metric.color }} />
            {metric.label}
          </span>
        ))}
      </div>
      <svg viewBox={`-8 -8 ${width + 16} ${height + 28}`} className="mt-3 w-full overflow-visible">
        {[0, 5, 10].map((tick) => (
          <line
            key={tick}
            x1={0}
            x2={width}
            y1={y(tick)}
            y2={y(tick)}
            stroke="var(--border)"
            strokeWidth={1}
          />
        ))}
        {metrics.map((metric) => {
          const available = points
            .map((point, index) => ({ value: point[metric.key], index }))
            .filter((item): item is { value: number; index: number } => item.value != null);
          return (
            <g key={metric.key}>
              <polyline
                fill="none"
                stroke={metric.color}
                strokeWidth={2.5}
                points={available.map((item) => `${x(item.index)},${y(item.value)}`).join(" ")}
              />
              {available.map((item) => (
                <circle
                  key={item.index}
                  cx={x(item.index)}
                  cy={y(item.value)}
                  r={3.5}
                  fill={metric.color}
                />
              ))}
            </g>
          );
        })}
      </svg>
    </div>
  );
}

function HistoryRow({ point }: { point: TrendHistoryPoint }) {
  const { t } = useI18n();
  return (
    <div className="relative flex gap-3 border-l border-border pb-5 pl-5 last:pb-0">
      <GitCommitHorizontal className="absolute -left-2 top-0 h-4 w-4 bg-surface text-primary" />
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <span className="text-sm font-medium text-fg">
            {t("portfolioDetail.run", {
              date: point.occurred_at ? formatDate(point.occurred_at) : "—",
            })}
          </span>
        </div>
        <p className="mt-1 text-xs text-muted">
          {point.maturity ? t(`maturity.${point.maturity}`) : "—"}
          {point.change_type ? ` · ${t(`diff.${point.change_type}`)}` : ""}
        </p>
      </div>
    </div>
  );
}

function DecisionList({ decisions }: { decisions: TrendDecision[] }) {
  const { t } = useI18n();
  if (decisions.length === 0)
    return <p className="text-sm text-muted">{t("portfolioDetail.noDecisions")}</p>;
  return (
    <div className="space-y-4">
      {decisions.map((decision) => (
        <div key={decision.id} className="border-l-2 border-primary/30 pl-3">
          <div className="flex items-center justify-between gap-2">
            <span className="text-xs font-semibold uppercase tracking-wide text-primary">
              {decision.action}
            </span>
            <span className="text-[11px] text-faint">{formatDate(decision.created_at)}</span>
          </div>
          {decision.reason && <p className="mt-1 text-sm leading-relaxed text-fg">{decision.reason}</p>}
          <p className="mt-1 flex items-center gap-1 text-xs text-muted">
            <UserRound className="h-3 w-3" /> {decision.reviewer ?? t("portfolioDetail.system")}
          </p>
        </div>
      ))}
    </div>
  );
}

function DecisionForm({
  trendId,
  onSaved,
}: {
  trendId: string | number;
  onSaved: (decision: TrendDecision) => void;
}) {
  const { t } = useI18n();
  const [action, setAction] = useState<PortfolioDecisionInput["action"]>("confirm");
  const [reviewer, setReviewer] = useState("");
  const [reason, setReason] = useState("");
  const [target, setTarget] = useState("");
  const [saving, setSaving] = useState(false);

  async function submit() {
    if (!reviewer.trim() || !reason.trim()) {
      toast.error(t("review.required"));
      return;
    }
    setSaving(true);
    try {
      const decision = await decidePortfolioTrend(trendId, {
        action,
        reviewer: reviewer.trim(),
        reason: reason.trim(),
        target_trend_id: action === "merge" ? target.trim() : undefined,
      });
      onSaved(decision);
      setReason("");
      toast.success(t("portfolioDetail.saved"));
    } catch (e) {
      toast.error(t("portfolioDetail.saveError"), { description: String(e) });
    } finally {
      setSaving(false);
    }
  }

  return (
    <section className="rounded-xl border border-border bg-surface p-5 shadow-sm">
      <h2 className="text-sm font-semibold text-fg">{t("portfolioDetail.addDecision")}</h2>
      <div className="mt-4 grid gap-3">
        <select
          value={action}
          onChange={(event) => setAction(event.target.value as PortfolioDecisionInput["action"])}
          className="h-10 rounded-md border border-border bg-bg px-3 text-sm text-fg"
        >
          {(["confirm", "correct", "reject", "restore", "merge"] as const).map((value) => (
            <option key={value} value={value}>
              {t(`decision.${value}`)}
            </option>
          ))}
        </select>
        <input
          value={reviewer}
          onChange={(event) => setReviewer(event.target.value)}
          placeholder={t("review.reviewer")}
          className="h-10 rounded-md border border-border bg-bg px-3 text-sm text-fg outline-none focus:border-primary"
        />
        <textarea
          value={reason}
          onChange={(event) => setReason(event.target.value)}
          placeholder={t("review.reason")}
          rows={3}
          className="rounded-md border border-border bg-bg px-3 py-2 text-sm text-fg outline-none focus:border-primary"
        />
        {action === "merge" && (
          <input
            value={target}
            onChange={(event) => setTarget(event.target.value)}
            placeholder={t("review.target")}
            className="h-10 rounded-md border border-border bg-bg px-3 text-sm text-fg outline-none focus:border-primary"
          />
        )}
        <button
          onClick={submit}
          disabled={saving}
          className="h-10 rounded-md bg-primary text-sm font-medium text-white hover:bg-primary-bright disabled:opacity-50"
        >
          {saving ? t("review.saving") : t("portfolioDetail.save")}
        </button>
      </div>
    </section>
  );
}

function formatDate(value: string) {
  return new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" }).format(
    new Date(value),
  );
}
