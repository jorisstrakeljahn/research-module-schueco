"use client";

import { ArrowLeft, Loader2, Trash2 } from "lucide-react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useCallback, useEffect, useMemo, useState } from "react";
import { toast } from "sonner";

import PageHeader from "@/components/PageHeader";
import ReviewCard from "@/components/ReviewCard";
import {
  CATEGORY_META,
  deleteRun,
  fetchReviewQueue,
  fetchRunDiff,
  RADAR_STAGE_META,
  type ReviewQueueItem,
  type RunDiff,
  type RunDiffEntry,
} from "@/lib/api";
import { useI18n } from "@/lib/i18n";

export default function RunDetailPage() {
  const { t, lang } = useI18n();
  const router = useRouter();
  const params = useParams<{ id: string }>();
  const runId = Number(params.id);
  const [diff, setDiff] = useState<RunDiff | null>(null);
  const [reviews, setReviews] = useState<ReviewQueueItem[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [deleting, setDeleting] = useState(false);

  async function handleDelete() {
    if (!confirmDelete) {
      setConfirmDelete(true);
      return;
    }
    setDeleting(true);
    try {
      await deleteRun(runId);
      toast.success(t("runDetail.deleteDone"));
      router.push("/runs");
    } catch (deleteError) {
      setDeleting(false);
      setConfirmDelete(false);
      toast.error(t("runDetail.deleteError"), {
        description: String(deleteError),
      });
    }
  }

  const load = useCallback(async () => {
    try {
      const [nextDiff, nextReviews] = await Promise.all([
        fetchRunDiff(runId, lang),
        fetchReviewQueue(runId, lang),
      ]);
      setDiff(nextDiff);
      setReviews(nextReviews);
      setError(null);
    } catch (loadError) {
      setError(String(loadError));
    }
  }, [runId, lang]);

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
    };
  }, [diff]);
  const hasContent =
    reviews.length > 0 ||
    grouped.new.length > 0 ||
    grouped.reclassified.length > 0 ||
    grouped.evidence.length > 0;
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
              <TrendGroup title={t("runGroup.new")} entries={grouped.new} />
              <TrendGroup
                title={t("runGroup.reclassified")}
                entries={grouped.reclassified}
              />
              <TrendGroup title={t("runGroup.evidence")} entries={grouped.evidence} />
              {!hasContent && (
                <p className="rounded-xl border border-border bg-surface p-5 text-sm text-muted">
                  {t("runDetail.noMaterialChanges")}
                </p>
              )}

              <section className="rounded-xl border border-digital/30 bg-digital/5 p-5">
                <h2 className="text-sm font-semibold text-fg">
                  {t("runDetail.deleteTitle")}
                </h2>
                <p className="mt-1 text-sm text-muted">
                  {t("runDetail.deleteHint")}
                </p>
                <div className="mt-4 flex flex-wrap items-center gap-3">
                  <button
                    type="button"
                    onClick={handleDelete}
                    disabled={deleting}
                    className={`inline-flex items-center gap-2 rounded-lg px-4 py-2 text-sm font-medium transition-colors disabled:opacity-60 ${
                      confirmDelete
                        ? "bg-digital text-white hover:opacity-90"
                        : "border border-digital/50 text-digital hover:bg-digital/10"
                    }`}
                  >
                    {deleting ? (
                      <Loader2 className="h-4 w-4 animate-spin" />
                    ) : (
                      <Trash2 className="h-4 w-4" />
                    )}
                    {confirmDelete
                      ? t("runDetail.deleteConfirm")
                      : t("runDetail.delete")}
                  </button>
                  {confirmDelete && !deleting && (
                    <button
                      type="button"
                      onClick={() => setConfirmDelete(false)}
                      className="rounded-lg border border-border px-4 py-2 text-sm text-muted hover:bg-hover"
                    >
                      {t("common.cancel")}
                    </button>
                  )}
                </div>
              </section>
            </div>
          )}
        </div>
      </div>
    </div>
  );

  function TrendGroup({
    title,
    entries,
  }: {
    title: string;
    entries: RunDiffEntry[];
  }) {
    if (entries.length === 0) return null;
    return (
      <section className="space-y-3">
        <h2 className="text-sm font-semibold text-fg">{title}</h2>
        <div className="grid gap-3 md:grid-cols-2">
          {entries.map((entry) => (
            <TrendCard key={entry.occurrence_id} entry={entry} />
          ))}
        </div>
      </section>
    );
  }

  function TrendCard({ entry }: { entry: RunDiffEntry }) {
    const summary =
      typeof entry.after?.summary === "string" ? entry.after.summary : null;
    const changes = entry.changed_fields.filter(
      (field) => field !== "summary" && field !== "title",
    );
    const body = (
      <>
        <h3 className="hyphens-auto font-semibold leading-snug wrap-break-word text-fg group-hover:text-primary">
          {entry.title}
        </h3>
        {summary && (
          <p className="mt-1.5 line-clamp-3 text-sm leading-relaxed text-muted">
            {summary}
          </p>
        )}
        {entry.change_type !== "new" && changes.length > 0 && (
          <div className="mt-3 flex flex-wrap gap-1.5">
            {changes.map((field) => (
              <span
                key={field}
                className="rounded-full bg-surface-2 px-2.5 py-1 text-xs text-muted"
              >
                {t(`field.${field}`)}: {displayValue(entry.before?.[field], field, t)}
                {" → "}
                {displayValue(entry.after?.[field], field, t)}
              </span>
            ))}
          </div>
        )}
        {entry.change_type === "evidence_only" && entry.evidence_added_count > 0 && (
          <p className="mt-3 text-xs text-faint">
            {t("runDetail.newDocs", { n: entry.evidence_added_count })}
          </p>
        )}
      </>
    );
    if (entry.canonical_trend_id != null) {
      return (
        <Link
          href={`/portfolio/${entry.canonical_trend_id}`}
          className="group block rounded-xl border border-border bg-surface p-4 shadow-sm transition hover:border-border-strong hover:bg-surface-2 sm:p-5"
        >
          {body}
        </Link>
      );
    }
    return (
      <div className="rounded-xl border border-border bg-surface p-4 shadow-sm sm:p-5">
        {body}
      </div>
    );
  }
}

function displayValue(
  value: unknown,
  field: string,
  t: (key: string) => string,
): string {
  if (value == null) return "–";
  const localizeOne = (raw: string): string => {
    if (field === "maturity") return t(`maturity.${raw}`);
    if (field === "pestel") return t(`pestel.${raw}`);
    if (field === "category") return CATEGORY_META[raw]?.label ?? raw;
    if (field === "radar_stage") return RADAR_STAGE_META[raw]?.label ?? raw;
    return raw;
  };
  if (Array.isArray(value)) return value.map((v) => localizeOne(String(v))).join(", ");
  if (typeof value === "number") return String(Math.round(value * 10) / 10);
  return localizeOne(String(value));
}
