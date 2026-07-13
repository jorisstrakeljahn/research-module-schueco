"use client";

import {
  ArrowLeft,
  Archive,
  ClipboardCheck,
  Files,
  Sparkles,
  Tags,
} from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useMemo, useState } from "react";

import ChangeBadge from "@/components/ChangeBadge";
import PageHeader from "@/components/PageHeader";
import ReviewCard from "@/components/ReviewCard";
import {
  fetchReviewQueue,
  fetchRunDiff,
  type ReviewQueueItem,
  type RunDiff,
  type RunDiffEntry,
} from "@/lib/api";
import { useI18n } from "@/lib/i18n";

type GroupKey = "review" | "new" | "reclassified" | "evidence" | "unchanged";

const GROUPS = [
  { key: "review", icon: ClipboardCheck },
  { key: "new", icon: Sparkles },
  { key: "reclassified", icon: Tags },
  { key: "evidence", icon: Files },
  { key: "unchanged", icon: Archive },
] as const;

export default function RunDetailPage() {
  const { t, lang } = useI18n();
  const params = useParams<{ id: string }>();
  const runId = Number(params.id);
  const [diff, setDiff] = useState<RunDiff | null>(null);
  const [reviews, setReviews] = useState<ReviewQueueItem[]>([]);
  const [selected, setSelected] = useState<GroupKey | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const [nextDiff, nextReviews] = await Promise.all([
        fetchRunDiff(runId),
        fetchReviewQueue(runId),
      ]);
      setDiff(nextDiff);
      setReviews(nextReviews);
      setSelected((current) =>
        current === null || (current === "review" && nextReviews.length === 0)
          ? nextReviews.length > 0
            ? "review"
            : "new"
          : current,
      );
      setError(null);
    } catch (loadError) {
      setError(String(loadError));
    }
  }, [runId]);

  useEffect(() => {
    void load();
  }, [load]);

  const grouped = useMemo(() => {
    const available = (diff?.entries ?? []).filter(
      (entry) => entry.review_status !== "pending",
    );
    return {
      review: [],
      new: available.filter((entry) => entry.change_type === "new"),
      reclassified: available.filter(
        (entry) =>
          entry.change_type === "classification_changed" ||
          entry.change_type === "content_changed",
      ),
      evidence: available.filter((entry) => entry.change_type === "evidence_only"),
      unchanged: available.filter((entry) => entry.change_type === "unchanged"),
    } satisfies Record<GroupKey, RunDiffEntry[]>;
  }, [diff]);

  const counts: Record<GroupKey, number> = {
    review: reviews.length,
    new: grouped.new.length,
    reclassified: grouped.reclassified.length,
    evidence: grouped.evidence.length,
    unchanged: grouped.unchanged.length,
  };
  const title = diff
    ? t("runDetail.title", {
        date: new Intl.DateTimeFormat(lang, {
          dateStyle: "long",
          timeStyle: "short",
        }).format(new Date(diff.started_at)),
      })
    : t("runDetail.pendingTitle");

  return (
    <div className="flex h-full min-w-0 flex-col overflow-hidden">
      <PageHeader title={title} subtitle={diff?.query || t("runDetail.subtitle")} />
      <div className="flex-1 overflow-auto p-4 sm:p-6">
        <div className="mx-auto max-w-6xl space-y-6">
          <Link href="/runs" className="inline-flex items-center gap-2 text-sm text-muted hover:text-fg">
            <ArrowLeft className="h-4 w-4" /> {t("runDetail.back")}
          </Link>

          {error ? (
            <p className="text-sm text-digital">{error}</p>
          ) : !diff ? (
            <p className="text-sm text-muted">{t("runDetail.loading")}</p>
          ) : (
            <>
              <section>
                <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-5">
                  {GROUPS.map(({ key, icon: Icon }) => (
                    <button
                      type="button"
                      key={key}
                      onClick={() => setSelected(key)}
                      className={`rounded-xl border p-3 text-left shadow-sm transition-colors ${
                        selected === key
                          ? "border-primary bg-primary/5"
                          : "border-border bg-surface hover:bg-hover"
                      } ${key === "review" && counts.review > 0 ? "border-markets/40" : ""}`}
                    >
                      <div className="flex items-center justify-between gap-2">
                        <Icon
                          className={`h-4 w-4 ${
                            key === "review" && counts.review > 0
                              ? "text-markets"
                              : "text-muted"
                          }`}
                        />
                        <span className="text-xl font-semibold tabular-nums text-fg">
                          {counts[key]}
                        </span>
                      </div>
                      <p className="mt-2 text-xs font-medium text-muted">
                        {t(`runGroup.${key}`)}
                      </p>
                    </button>
                  ))}
                </div>
              </section>

              {selected === "review" ? (
                <section className="space-y-4">
                  {reviews.length === 0 ? (
                    <EmptyGroup />
                  ) : (
                    reviews.map((item) => (
                      <ReviewCard
                        key={item.occurrence_id}
                        item={item}
                        onResolved={load}
                      />
                    ))
                  )}
                </section>
              ) : selected ? (
                <TrendGroup entries={grouped[selected]} minimal={selected === "unchanged"} />
              ) : null}
            </>
          )}
        </div>
      </div>
    </div>
  );
  function EmptyGroup() {
    return (
      <div className="rounded-xl border border-dashed border-border bg-surface p-8 text-center text-sm text-muted">
        {t("runDetail.noChanges")}
      </div>
    );
  }

  function TrendGroup({
    entries,
    minimal,
  }: {
    entries: RunDiffEntry[];
    minimal: boolean;
  }) {
    if (entries.length === 0) return <EmptyGroup />;
    return (
      <section className="overflow-hidden rounded-xl border border-border bg-surface shadow-sm">
        <div className="divide-y divide-border">
          {entries.map((entry) =>
            minimal ? (
              <div
                key={entry.occurrence_id}
                className="flex items-center justify-between gap-3 px-4 py-3 sm:px-5"
              >
                <TrendTitle entry={entry} />
                <span className="text-xs text-faint">
                  {t("runDetail.prevalence", {
                    n: entry.prevalence == null ? "–" : `${(entry.prevalence * 100).toFixed(1)}%`,
                  })}
                </span>
              </div>
            ) : (
              <TrendDetails key={entry.occurrence_id} entry={entry} />
            ),
          )}
        </div>
      </section>
    );
  }

  function TrendDetails({ entry }: { entry: RunDiffEntry }) {
    const summary =
      typeof entry.after?.summary === "string" ? entry.after.summary : null;
    return (
      <details className="group p-4 sm:p-5">
        <summary className="flex cursor-pointer list-none flex-wrap items-start justify-between gap-3">
          <div className="min-w-0">
            <TrendTitle entry={entry} />
            {summary && <p className="mt-1 line-clamp-2 text-sm text-muted">{summary}</p>}
          </div>
          <ChangeBadge
            kind={entry.change_type}
            label={t(`diff.${entry.change_type}`)}
          />
        </summary>
        <div className="mt-4 grid gap-4 border-t border-border pt-4 lg:grid-cols-[1fr_auto]">
          <div>
            {entry.changed_fields.length > 0 && (
              <dl className="grid gap-2 sm:grid-cols-2">
                {entry.changed_fields.map((field) => (
                  <div key={field} className="rounded-lg bg-surface-2 p-3">
                    <dt className="text-xs font-medium text-muted">{t(`field.${field}`)}</dt>
                    <dd className="mt-1 text-sm text-fg">
                      {displayValue(entry.before?.[field])}
                      <span className="mx-2 text-faint">→</span>
                      {displayValue(entry.after?.[field])}
                    </dd>
                  </div>
                ))}
              </dl>
            )}
          </div>
          <dl className="grid min-w-48 grid-cols-2 gap-x-5 gap-y-2 text-xs">
            <Metric label={t("runDetail.evidenceAdded")} value={`+${entry.evidence_added_count}`} />
            <Metric label={t("runDetail.evidenceRemoved")} value={`−${entry.evidence_removed_count}`} />
            <Metric
              label={t("runDetail.prevalenceLabel")}
              value={entry.prevalence == null ? "–" : `${(entry.prevalence * 100).toFixed(1)}%`}
            />
            <Metric
              label={t("runDetail.match")}
              value={entry.match_score == null ? "–" : `${(entry.match_score * 100).toFixed(0)}%`}
            />
          </dl>
        </div>
      </details>
    );
  }

  function TrendTitle({ entry }: { entry: RunDiffEntry }) {
    return entry.canonical_trend_id != null ? (
      <Link
        href={`/portfolio/${entry.canonical_trend_id}`}
        className="font-medium text-fg hover:text-primary"
      >
        {entry.title}
      </Link>
    ) : (
      <h3 className="font-medium text-fg">{entry.title}</h3>
    );
  }

  function Metric({ label, value }: { label: string; value: string }) {
    return (
      <div>
        <dt className="text-faint">{label}</dt>
        <dd className="font-medium tabular-nums text-fg">{value}</dd>
      </div>
    );
  }
}

function displayValue(value: unknown): string {
  if (value == null) return "–";
  if (Array.isArray(value)) return value.join(", ");
  if (typeof value === "object") return Object.values(value).join(", ");
  return String(value);
}
