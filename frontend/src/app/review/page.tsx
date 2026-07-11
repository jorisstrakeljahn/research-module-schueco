"use client";

import { Check, Link2, Merge, Plus, X } from "lucide-react";
import { useEffect, useState } from "react";
import { toast } from "sonner";

import PageHeader from "@/components/PageHeader";
import {
  decideReviewItem,
  fetchReviewQueue,
  type ReviewDecisionInput,
  type ReviewQueueItem,
} from "@/lib/api";
import { useI18n } from "@/lib/i18n";

export default function ReviewPage() {
  const { t } = useI18n();
  const [items, setItems] = useState<ReviewQueueItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchReviewQueue()
      .then(setItems)
      .catch((e) => setError(String(e)))
      .finally(() => setLoading(false));
  }, []);

  function resolved(id: string | number) {
    setItems((current) => current.filter((item) => item.occurrence_id !== id));
  }

  return (
    <div className="flex h-full min-w-0 flex-col overflow-hidden">
      <PageHeader title={t("review.title")} subtitle={t("review.subtitle")} />
      <div className="flex-1 overflow-auto p-6">
        <div className="mx-auto max-w-5xl space-y-4">
          {loading ? (
            <p className="text-sm text-muted">{t("review.loading")}</p>
          ) : error ? (
            <p className="text-sm text-digital">{error}</p>
          ) : items.length === 0 ? (
            <div className="rounded-xl border border-dashed border-border p-10 text-center">
              <Check className="mx-auto h-8 w-8 text-primary" />
              <p className="mt-3 font-medium text-fg">{t("review.empty")}</p>
              <p className="mt-1 text-sm text-muted">{t("review.emptyHint")}</p>
            </div>
          ) : (
            items.map((item) => (
              <ReviewCard key={item.occurrence_id} item={item} onResolved={resolved} />
            ))
          )}
        </div>
      </div>
    </div>
  );
}

function ReviewCard({
  item,
  onResolved,
}: {
  item: ReviewQueueItem;
  onResolved: (id: string | number) => void;
}) {
  const { t } = useI18n();
  const [action, setAction] = useState<ReviewDecisionInput["action"]>("link");
  const [target, setTarget] = useState(String(item.suggested_trend?.id ?? ""));
  const [reviewer, setReviewer] = useState("");
  const [reason, setReason] = useState("");
  const [saving, setSaving] = useState(false);

  async function submit() {
    if (!reviewer.trim() || !reason.trim()) {
      toast.error(t("review.required"));
      return;
    }
    if ((action === "link" || action === "merge") && !target.trim()) {
      toast.error(t("review.targetRequired"));
      return;
    }
    setSaving(true);
    try {
      await decideReviewItem(item.occurrence_id, {
        action,
        reviewer: reviewer.trim(),
        reason: reason.trim(),
        canonical_trend_id: action === "link" ? target.trim() : undefined,
        target_trend_id: action === "merge" ? target.trim() : undefined,
      });
      toast.success(t("review.saved"));
      onResolved(item.occurrence_id);
    } catch (e) {
      toast.error(t("review.saveError"), { description: String(e) });
    } finally {
      setSaving(false);
    }
  }

  const actions = [
    { value: "link" as const, icon: Link2 },
    { value: "create" as const, icon: Plus },
    { value: "merge" as const, icon: Merge },
    { value: "reject" as const, icon: X },
  ];

  return (
    <article className="rounded-xl border border-border bg-surface p-5 shadow-sm">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="max-w-2xl">
          <div className="flex items-center gap-2 text-xs text-faint">
            {item.match_score != null && (
              <span>{t("review.score", { n: (item.match_score * 100).toFixed(0) })}</span>
            )}
          </div>
          <h2 className="mt-2 text-lg font-semibold text-fg">{item.title}</h2>
          <p className="mt-2 text-sm leading-relaxed text-muted">{item.summary}</p>
          {item.reason && <p className="mt-3 text-xs text-markets">{item.reason}</p>}
        </div>
        <span className="rounded-full bg-markets/15 px-2.5 py-1 text-xs font-medium text-markets">
          {t("diff.review")}
        </span>
      </div>

      {item.candidates && item.candidates.length > 0 && (
        <div className="mt-4 flex flex-wrap gap-2">
          {item.candidates.map((candidate) => (
            <button
              key={candidate.id}
              onClick={() => {
                setAction("link");
                setTarget(String(candidate.id));
              }}
              className={`rounded-lg border px-3 py-2 text-left text-xs ${
                target === String(candidate.id)
                  ? "border-primary bg-primary/5 text-primary"
                  : "border-border text-muted hover:bg-hover"
              }`}
            >
              {candidate.title}
              {candidate.score != null && ` · ${(candidate.score * 100).toFixed(0)}%`}
            </button>
          ))}
        </div>
      )}

      <div className="mt-5 grid gap-3 border-t border-border pt-5 lg:grid-cols-[auto_1fr_1fr_auto]">
        <div className="flex flex-wrap gap-1">
          {actions.map(({ value, icon: Icon }) => (
            <button
              key={value}
              onClick={() => setAction(value)}
              title={t(`review.action.${value}`)}
              className={`flex h-9 items-center gap-1.5 rounded-md px-2.5 text-xs font-medium ${
                action === value
                  ? "bg-primary text-white"
                  : "border border-border text-muted hover:bg-hover"
              }`}
            >
              <Icon className="h-3.5 w-3.5" />
              {t(`review.action.${value}`)}
            </button>
          ))}
        </div>
        <input
          value={reviewer}
          onChange={(event) => setReviewer(event.target.value)}
          placeholder={t("review.reviewer")}
          className="h-9 rounded-md border border-border bg-bg px-3 text-sm text-fg outline-none focus:border-primary"
        />
        <input
          value={reason}
          onChange={(event) => setReason(event.target.value)}
          placeholder={t("review.reason")}
          className="h-9 rounded-md border border-border bg-bg px-3 text-sm text-fg outline-none focus:border-primary"
        />
        <button
          onClick={submit}
          disabled={saving}
          className="h-9 rounded-md bg-primary px-4 text-sm font-medium text-white hover:bg-primary-bright disabled:opacity-50"
        >
          {saving ? t("review.saving") : t("review.decide")}
        </button>
      </div>
      {(action === "link" || action === "merge") && (
        <input
          value={target}
          onChange={(event) => setTarget(event.target.value)}
          placeholder={t("review.target")}
          className="mt-3 h-9 w-full rounded-md border border-border bg-bg px-3 text-sm text-fg outline-none focus:border-primary lg:max-w-sm"
        />
      )}
    </article>
  );
}
