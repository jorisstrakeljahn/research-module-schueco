"use client";

import { ArrowLeft, Languages } from "lucide-react";
import Link from "next/link";
import { useParams, useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";
import { toast } from "sonner";

import Score from "@/components/Score";
import TrendBadges from "@/components/TrendBadges";
import {
  fetchTrend,
  PESTEL_SECTORS,
  sendFeedback,
  translateTrend,
  type Maturity,
  type Timepoint,
  type TrendDetail,
} from "@/lib/api";
import { useI18n } from "@/lib/i18n";

type Override = { title: string; summary: string; rationale: string | null };

type BackSource = "newsfeed" | "radar" | "dashboard";

const BACK_BY_SOURCE: Record<
  BackSource,
  { href: string; labelKey: "detail.backNewsfeed" | "detail.backRadar" | "detail.backDashboard" }
> = {
  newsfeed: { href: "/newsfeed", labelKey: "detail.backNewsfeed" },
  radar: { href: "/radar", labelKey: "detail.backRadar" },
  dashboard: { href: "/", labelKey: "detail.backDashboard" },
};

export default function TrendDetailPage() {
  const { t, lang } = useI18n();
  const params = useParams<{ id: string }>();
  const searchParams = useSearchParams();
  const trendId = Number(params.id);
  const from = searchParams.get("from");
  const back =
    from && from in BACK_BY_SOURCE
      ? BACK_BY_SOURCE[from as BackSource]
      : { href: "/radar", labelKey: "detail.back" as const };
  const [trend, setTrend] = useState<TrendDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [override, setOverride] = useState<Override | null>(null);
  const [translating, setTranslating] = useState(false);

  useEffect(() => {
    fetchTrend(trendId)
      .then(setTrend)
      .catch((e) => setError(String(e)));
  }, [trendId]);

  async function doTranslate() {
    if (override) {
      setOverride(null);
      return;
    }
    setTranslating(true);
    try {
      const r = await translateTrend(trendId, lang);
      setOverride({ title: r.title, summary: r.summary, rationale: r.rationale });
    } catch (e) {
      toast.error(t("feedback.toastError"), { description: String(e) });
    } finally {
      setTranslating(false);
    }
  }

  if (error) return <div className="p-8 text-sm text-digital">{error}</div>;
  if (!trend) return <div className="p-8 text-sm text-muted">{t("detail.loading")}</div>;

  const title = override?.title ?? trend.title;
  const summary = override?.summary ?? trend.summary;
  const rationale = override ? override.rationale : trend.rationale;

  return (
    <div className="flex h-full min-w-0 flex-col overflow-hidden">
      <header className="flex h-14 shrink-0 items-center justify-between border-b border-border bg-bg px-6">
        <Link
          href={back.href}
          className="inline-flex items-center gap-1.5 text-sm text-muted transition-colors hover:text-fg"
        >
          <ArrowLeft className="h-4 w-4" /> {t(back.labelKey)}
        </Link>
        <button
          onClick={doTranslate}
          disabled={translating}
          className="inline-flex items-center gap-1.5 rounded-md border border-border px-2.5 py-1 text-xs font-medium text-muted transition-colors hover:bg-hover hover:text-fg disabled:opacity-60"
        >
          <Languages className="h-3.5 w-3.5" />
          {translating
            ? t("detail.translating")
            : override
              ? t("detail.showOriginal")
              : t("detail.translate")}
        </button>
      </header>

      <div className="flex-1 overflow-auto">
        <article className="mx-auto max-w-3xl p-6">
          <TrendBadges trend={trend} />

      <h1 className="mt-3 text-2xl font-semibold tracking-tight text-fg">
        {title}
      </h1>
      {override && (
        <span className="mt-1 inline-block text-[11px] uppercase tracking-wider text-faint">
          {t("detail.translated")}
        </span>
      )}

      <div className="mt-2 flex flex-wrap items-center gap-x-4 text-[13px] text-muted">
        <span>{t("detail.docs", { n: trend.size })}</span>
        {trend.emergence != null && (
          <span title={t("detail.emergenceTip")}>
            {t("detail.emergenceLabel")} {trend.emergence.toFixed(2)}
          </span>
        )}
      </div>

      <Section title={t("detail.section.summary")}>
        <p className="text-[15px] leading-relaxed text-fg/90">{summary}</p>
      </Section>

      <Section title={t("detail.section.assessment")}>
        <div className="mb-4 flex flex-wrap gap-1.5">
          {(trend.pestel ?? []).map((k) => (
            <span
              key={k}
              className="rounded-full border border-border bg-surface px-3 py-1 text-xs text-fg"
            >
              {PESTEL_SECTORS.find((s) => s.key === k)?.label ?? k}
            </span>
          ))}
        </div>
        <div className="grid max-w-md grid-cols-3 gap-3">
          <Score label="Impact" value={trend.impact} />
          <Score label="Urgency" value={trend.urgency} />
          <Score label="Uncertainty" value={trend.uncertainty} />
        </div>
        {rationale && (
          <p className="mt-3 text-[13px] italic leading-relaxed text-muted">
            {rationale}
          </p>
        )}
      </Section>

      <Section title={t("detail.section.activity")}>
        <TimeSeriesChart data={trend.timeseries} />
      </Section>

      <Section title={`${t("detail.section.evidence")} ${trend.evidence.length}`}>
        <ol className="space-y-2 text-[14px]">
          {trend.evidence.map((e, i) => (
            <li key={i} className="flex gap-2.5 leading-snug">
              <span className="w-5 shrink-0 text-right font-mono text-xs text-faint">
                {i + 1}
              </span>
              {e.url ? (
                <a
                  href={e.url}
                  target="_blank"
                  rel="noreferrer"
                  className="text-primary hover:underline"
                >
                  {e.title}
                </a>
              ) : (
                <span className="text-fg/90">{e.title}</span>
              )}
            </li>
          ))}
        </ol>
      </Section>

          <FeedbackPanel trendId={trendId} currentMaturity={trend.maturity} />
        </article>
      </div>
    </div>
  );
}

function Section({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <section className="mt-6 border-t border-border pt-6">
      <h2 className="mb-3 text-xs font-medium uppercase tracking-wider text-faint">
        {title}
      </h2>
      {children}
    </section>
  );
}

function TimeSeriesChart({ data }: { data: Timepoint[] }) {
  const { t } = useI18n();
  if (data.length === 0)
    return <p className="text-sm text-faint">{t("detail.noDated")}</p>;
  const max = Math.max(...data.map((d) => d.doc_count));
  return (
    <div className="flex items-end gap-1.5 overflow-x-auto">
      {data.map((d) => (
        <div key={d.period} className="flex flex-col items-center gap-1">
          <span className="text-[10px] tabular-nums text-faint">{d.doc_count}</span>
          <div
            className="w-7 rounded-t-sm bg-primary/70"
            style={{ height: `${(d.doc_count / max) * 110 + 3}px` }}
            title={`${d.period}: ${d.doc_count}`}
          />
          <span className="mt-0.5 whitespace-nowrap text-[10px] tabular-nums text-faint">
            {d.period}
          </span>
        </div>
      ))}
    </div>
  );
}

function FeedbackPanel({
  trendId,
  currentMaturity,
}: {
  trendId: number;
  currentMaturity: Maturity | null;
}) {
  const { t } = useI18n();
  const [newMaturity, setNewMaturity] = useState("");
  const [comment, setComment] = useState("");

  async function act(action: "confirm" | "correct" | "reject") {
    try {
      await sendFeedback(trendId, {
        action,
        field: action === "correct" ? "maturity" : undefined,
        new_value: action === "correct" ? newMaturity || undefined : undefined,
        comment,
      });
      toast.success(
        action === "confirm"
          ? t("feedback.toastConfirm")
          : action === "reject"
            ? t("feedback.toastReject")
            : t("feedback.toastCorrect"),
      );
    } catch (e) {
      toast.error(t("feedback.toastError"), { description: String(e) });
    }
  }

  return (
    <section className="mt-6 border-t border-border pt-6">
      <h2 className="mb-3 text-xs font-medium uppercase tracking-wider text-faint">
        {t("feedback.title")}
      </h2>
      <div className="flex flex-wrap items-center gap-2 text-sm">
        <button
          onClick={() => act("confirm")}
          className="rounded-md bg-primary px-3 py-1.5 font-medium text-white transition-colors hover:bg-primary-bright"
        >
          {t("feedback.confirm")}
        </button>
        <button
          onClick={() => act("reject")}
          className="rounded-md border border-border px-3 py-1.5 font-medium text-muted transition-colors hover:border-digital/50 hover:text-digital"
        >
          {t("feedback.reject")}
        </button>
        <span className="ml-1 text-faint">{t("feedback.reclassify")}</span>
        <select
          value={newMaturity}
          onChange={(e) => setNewMaturity(e.target.value)}
          className="rounded-md border border-border bg-surface px-2 py-1.5 text-fg"
        >
          <option value="">
            {currentMaturity
              ? t("feedback.current", { v: t(`maturity.${currentMaturity}`) })
              : t("feedback.select")}
          </option>
          <option value="weak_signal">{t("maturity.weak_signal")}</option>
          <option value="emerging">{t("maturity.emerging")}</option>
          <option value="established">{t("maturity.established")}</option>
          <option value="megatrend">{t("maturity.megatrend")}</option>
        </select>
        <button
          onClick={() => act("correct")}
          className="rounded-md border border-border px-3 py-1.5 font-medium text-fg transition-colors hover:bg-hover"
        >
          {t("feedback.save")}
        </button>
      </div>
      <input
        value={comment}
        onChange={(e) => setComment(e.target.value)}
        placeholder={t("feedback.comment")}
        className="mt-3 w-full max-w-md rounded-md border border-border bg-surface px-3 py-1.5 text-sm text-fg placeholder:text-faint focus:border-border-strong focus:outline-none"
      />
    </section>
  );
}
