"use client";

import { ArrowLeft } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useMemo, useState } from "react";

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

export default function RunDetailPage() {
  const { t, lang } = useI18n();
  const params = useParams<{ id: string }>();
  const runId = Number(params.id);
  const [diff, setDiff] = useState<RunDiff | null>(null);
  const [reviews, setReviews] = useState<ReviewQueueItem[]>([]);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const [nextDiff, nextReviews] = await Promise.all([
        fetchRunDiff(runId),
        fetchReviewQueue(runId),
      ]);
      setDiff(nextDiff);
      setReviews(nextReviews);
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
      new: available.filter((entry) => entry.change_type === "new"),
      reclassified: available.filter(
        (entry) =>
          entry.change_type === "classification_changed" ||
          entry.change_type === "content_changed",
      ),
      evidence: available.filter((entry) => entry.change_type === "evidence_only"),
      unchanged: available.filter((entry) => entry.change_type === "unchanged"),
    };
  }, [diff]);
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
      <PageHeader title={title} />
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
            <div className="space-y-8">
              {reviews.length > 0 && (
                <section className="space-y-4">
                  <h2 className="text-sm font-semibold text-fg">{t("runGroup.review")}</h2>
                  {reviews.map((item) => (
                    <ReviewCard key={item.occurrence_id} item={item} onResolved={load} />
                  ))}
                </section>
              )}
              <TrendGroup
                title={t("runGroup.new")}
                entries={grouped.new}
                minimal={false}
              />
              <TrendGroup
                title={t("runGroup.reclassified")}
                entries={grouped.reclassified}
                minimal={false}
              />
              <TrendGroup
                title={t("runGroup.evidence")}
                entries={grouped.evidence}
                minimal={false}
              />
              {reviews.length === 0 &&
                grouped.new.length === 0 &&
                grouped.reclassified.length === 0 &&
                grouped.evidence.length === 0 && (
                  <p className="rounded-xl border border-border bg-surface p-5 text-sm text-muted">
                    {t("runDetail.noMaterialChanges")}
                  </p>
                )}
              {grouped.unchanged.length > 0 && (
                <details>
                  <summary className="cursor-pointer list-none text-sm font-medium text-muted hover:text-fg">
                    {t("runGroup.unchanged")}
                  </summary>
                  <div className="mt-3">
                    <TrendGroup entries={grouped.unchanged} minimal />
                  </div>
                </details>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
  function TrendGroup({
    title,
    entries,
    minimal,
  }: {
    title?: string;
    entries: RunDiffEntry[];
    minimal: boolean;
  }) {
    if (entries.length === 0) return null;
    return (
      <section className="space-y-3">
        {title && <h2 className="text-sm font-semibold text-fg">{title}</h2>}
        <div className="overflow-hidden rounded-xl border border-border bg-surface shadow-sm">
          <div className="divide-y divide-border">
            {entries.map((entry) =>
              minimal ? (
                <div key={entry.occurrence_id} className="px-4 py-3 sm:px-5">
                  <TrendTitle entry={entry} />
                </div>
              ) : (
                <TrendDetails key={entry.occurrence_id} entry={entry} />
              ),
            )}
          </div>
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
