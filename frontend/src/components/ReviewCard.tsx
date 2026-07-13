"use client";

import { useEffect, useMemo, useState } from "react";
import { toast } from "sonner";

import {
  CATEGORY_META,
  decideReviewItem,
  fetchPortfolioTrends,
  RADAR_STAGE_META,
  type PortfolioTrend,
  type ReviewDecisionInput,
  type ReviewQueueItem,
} from "@/lib/api";
import { useI18n } from "@/lib/i18n";

type Action = ReviewDecisionInput["action"];

const DEFAULT_EDITABLE_FIELDS = ["title", "summary"] as const;

const portfolioCache = new Map<string, Promise<PortfolioTrend[]>>();

function loadPortfolio(lang: "de" | "en"): Promise<PortfolioTrend[]> {
  const cached = portfolioCache.get(lang);
  if (cached) return cached;
  const promise = fetchPortfolioTrends("active", lang).catch(() => {
    portfolioCache.delete(lang);
    return [];
  });
  portfolioCache.set(lang, promise);
  return promise;
}

export default function ReviewCard({
  item,
  onResolved,
}: {
  item: ReviewQueueItem;
  onResolved: () => void | Promise<void>;
}) {
  const { t, lang } = useI18n();
  const identityReview = item.review_reasons.some((reason) => reason.kind === "identity");
  const actions = useMemo<Action[]>(() => {
    const all: Action[] = ["confirm", "correct", "link", "create", "merge", "reject"];
    // Without an assigned trend there is nothing to merge; linking covers that case.
    return item.canonical_trend_id == null
      ? all.filter((action) => action !== "merge")
      : all;
  }, [item.canonical_trend_id]);
  const [action, setAction] = useState<Action>("confirm");
  const [target, setTarget] = useState(String(item.suggested_trend?.id ?? ""));
  const [portfolio, setPortfolio] = useState<PortfolioTrend[]>([]);
  const [reviewer, setReviewer] = useState("");
  const [reason, setReason] = useState("");
  const [saving, setSaving] = useState(false);
  const editableFields = useMemo(() => {
    const fromReasons = item.review_reasons
      .filter((entry) => entry.field)
      .map((entry) => ({ field: entry.field!, value: formatValue(entry.after), exemplar: entry.after }));
    if (fromReasons.length > 0) return fromReasons;
    return DEFAULT_EDITABLE_FIELDS.map((field) => ({
      field,
      value: String(item[field] ?? ""),
      exemplar: item[field] as unknown,
    }));
  }, [item]);
  const [changes, setChanges] = useState<Record<string, string>>(() =>
    Object.fromEntries(editableFields.map((entry) => [entry.field, entry.value])),
  );

  const needsTarget = action === "link" || action === "merge";
  useEffect(() => {
    if (!needsTarget) return;
    let active = true;
    void loadPortfolio(lang).then((trends) => {
      if (active) setPortfolio(trends);
    });
    return () => {
      active = false;
    };
  }, [needsTarget, lang]);

  const targetOptions = useMemo(
    () =>
      portfolio.filter(
        (trend) =>
          !(action === "merge" && String(trend.id) === String(item.canonical_trend_id)),
      ),
    [portfolio, action, item.canonical_trend_id],
  );

  async function submit() {
    if (!reviewer.trim() || !reason.trim()) {
      toast.error(t("review.required"));
      return;
    }
    if (needsTarget && !target.trim()) {
      toast.error(t("review.targetRequired"));
      return;
    }
    setSaving(true);
    try {
      await decideReviewItem(item.occurrence_id, {
        action,
        reviewer: reviewer.trim(),
        reason: reason.trim(),
        language: lang,
        canonical_trend_id: action === "link" ? target.trim() : undefined,
        target_trend_id: action === "merge" ? target.trim() : undefined,
        changes:
          action === "correct"
            ? Object.fromEntries(
                editableFields.map((entry) => [
                  entry.field,
                  parseValue(changes[entry.field] ?? "", entry.exemplar),
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
          <h3 className="mt-1.5 hyphens-auto text-base font-semibold wrap-break-word text-fg">
            {item.title}
          </h3>
          <p className="mt-1.5 text-sm leading-relaxed text-muted">{item.summary}</p>
          {item.suggested_trend && (
            <p className="mt-2 text-xs text-muted">
              {t("review.suggested", { title: item.suggested_trend.title })}
            </p>
          )}
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
                {formatFieldValue(entry.field, entry.before, t)} →{" "}
                {formatFieldValue(entry.field, entry.after, t)}
              </p>
            )}
          </div>
        ))}
      </div>

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
        <p className="mt-2 text-xs text-faint">{t(`review.hint.${action}`)}</p>

        {action === "correct" && (
          <div className="mt-3 grid gap-3 sm:grid-cols-2">
            {editableFields.map((entry) => (
              <label key={entry.field} className="text-xs font-medium text-muted">
                {t(`field.${entry.field}`)}
                <input
                  value={changes[entry.field] ?? ""}
                  onChange={(event) =>
                    setChanges((current) => ({
                      ...current,
                      [entry.field]: event.target.value,
                    }))
                  }
                  className="mt-1 block h-9 w-full rounded-md border border-border bg-bg px-3 text-sm font-normal text-fg outline-none focus:border-primary"
                />
              </label>
            ))}
          </div>
        )}

        {needsTarget && (
          <select
            value={target}
            onChange={(event) => setTarget(event.target.value)}
            className="mt-3 h-9 w-full rounded-md border border-border bg-bg px-3 text-sm text-fg outline-none focus:border-primary sm:max-w-md"
          >
            <option value="">{t("review.targetPlaceholder")}</option>
            {targetOptions.map((trend) => (
              <option key={trend.id} value={String(trend.id)}>
                {trend.title}
              </option>
            ))}
          </select>
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
  if (typeof value === "number") return String(Math.round(value * 10) / 10);
  return String(value);
}

/** Enum-like fields get their display label instead of the raw backend value. */
function formatFieldValue(
  field: string,
  value: unknown,
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
  if (typeof value === "string") return localizeOne(value);
  return formatValue(value);
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
