"use client";

import { useMemo, useState } from "react";
import { toast } from "sonner";

import {
  decideReviewItem,
  type ReviewDecisionInput,
  type ReviewQueueItem,
} from "@/lib/api";
import { useI18n } from "@/lib/i18n";

const IDENTITY_ACTIONS = [
  "link",
  "create",
  "merge",
  "reject",
] as const;

const CLASSIFICATION_ACTIONS = [
  "confirm",
  "correct",
  "reject",
] as const;

export default function ReviewCard({
  item,
  onResolved,
}: {
  item: ReviewQueueItem;
  onResolved: () => void | Promise<void>;
}) {
  const { t } = useI18n();
  const identityReview = item.review_reasons.some((reason) => reason.kind === "identity");
  const actions = identityReview ? IDENTITY_ACTIONS : CLASSIFICATION_ACTIONS;
  const [action, setAction] = useState<ReviewDecisionInput["action"]>(actions[0]);
  const [target, setTarget] = useState(String(item.suggested_trend?.id ?? ""));
  const [reviewer, setReviewer] = useState("");
  const [reason, setReason] = useState("");
  const [saving, setSaving] = useState(false);
  const editableReasons = useMemo(
    () => item.review_reasons.filter((entry) => entry.field),
    [item.review_reasons],
  );
  const [changes, setChanges] = useState<Record<string, string>>(() =>
    Object.fromEntries(
      editableReasons.map((entry) => [entry.field!, formatValue(entry.after)]),
    ),
  );

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
        changes:
          action === "correct"
            ? Object.fromEntries(
                editableReasons.map((entry) => [
                  entry.field!,
                  parseValue(changes[entry.field!] ?? "", entry.after),
                ]),
              )
            : undefined,
      });
      toast.success(t("review.saved"));
      await onResolved();
    } catch (error) {
      toast.error(t("review.saveError"), { description: String(error) });
    } finally {
      setSaving(false);
    }
  }

  return (
    <article className="rounded-xl border border-markets/30 bg-surface p-4 shadow-sm sm:p-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0 max-w-3xl">
          <div className="flex flex-wrap items-center gap-2 text-xs text-faint">
            <span>{t(`review.kind.${identityReview ? "identity" : "classification"}`)}</span>
            {item.match_score != null && (
              <span>{t("review.score", { n: (item.match_score * 100).toFixed(0) })}</span>
            )}
          </div>
          <h3 className="mt-1.5 text-base font-semibold text-fg">{item.title}</h3>
          <p className="mt-1.5 text-sm leading-relaxed text-muted">{item.summary}</p>
        </div>
        <span className="rounded-full bg-markets/15 px-2.5 py-1 text-xs font-medium text-markets">
          {t("runGroup.review")}
        </span>
      </div>

      <div className="mt-4 grid gap-2 sm:grid-cols-2">
        {item.review_reasons.map((entry, index) => (
          <div key={`${entry.code}-${entry.field ?? index}`} className="rounded-lg bg-surface-2 p-3">
            <p className="text-xs font-medium text-fg">
              {t(`review.code.${entry.code}`)}
              {entry.field ? ` · ${t(`field.${entry.field}`)}` : ""}
            </p>
            {entry.field && (
              <p className="mt-1 text-xs text-muted">
                {formatValue(entry.before)} → {formatValue(entry.after)}
              </p>
            )}
          </div>
        ))}
      </div>

      {item.candidates && item.candidates.length > 0 && (
        <div className="mt-4 flex flex-wrap gap-2">
          {item.candidates.map((candidate) => (
            <button
              type="button"
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

      <div className="mt-5 border-t border-border pt-4">
        <div className="flex flex-wrap gap-1.5">
          {actions.map((value) => (
            <button
              type="button"
              key={value}
              onClick={() => setAction(value)}
              className={`inline-flex h-9 items-center gap-1.5 rounded-md px-3 text-xs font-medium ${
                action === value
                  ? "bg-primary text-white"
                  : "border border-border text-muted hover:bg-hover"
              }`}
            >
              {t(`review.action.${value}`)}
            </button>
          ))}
        </div>

        {action === "correct" && editableReasons.length > 0 && (
          <div className="mt-3 grid gap-3 sm:grid-cols-2">
            {editableReasons.map((entry) => (
              <label key={entry.field} className="text-xs font-medium text-muted">
                {t(`field.${entry.field}`)}
                <input
                  value={changes[entry.field!] ?? ""}
                  onChange={(event) =>
                    setChanges((current) => ({
                      ...current,
                      [entry.field!]: event.target.value,
                    }))
                  }
                  className="mt-1 block h-9 w-full rounded-md border border-border bg-bg px-3 text-sm font-normal text-fg outline-none focus:border-primary"
                />
              </label>
            ))}
          </div>
        )}

        {(action === "link" || action === "merge") && (
          <input
            value={target}
            onChange={(event) => setTarget(event.target.value)}
            placeholder={t("review.target")}
            className="mt-3 h-9 w-full rounded-md border border-border bg-bg px-3 text-sm text-fg outline-none focus:border-primary sm:max-w-sm"
          />
        )}

        <div className="mt-3 grid gap-3 sm:grid-cols-2 lg:grid-cols-[0.7fr_1.3fr_auto]">
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
            type="button"
            onClick={submit}
            disabled={saving}
            className="h-9 rounded-md bg-primary px-4 text-sm font-medium text-white hover:bg-primary-bright disabled:opacity-50"
          >
            {saving ? t("review.saving") : t("review.decide")}
          </button>
        </div>
      </div>
    </article>
  );
}

function formatValue(value: unknown): string {
  if (value == null) return "–";
  if (Array.isArray(value)) return value.join(", ");
  return String(value);
}

function parseValue(value: string, exemplar: unknown): unknown {
  if (Array.isArray(exemplar)) {
    return value
      .split(",")
      .map((entry) => entry.trim())
      .filter(Boolean);
  }
  if (typeof exemplar === "number") {
    const parsed = Number(value);
    return Number.isNaN(parsed) ? exemplar : parsed;
  }
  return value;
}
