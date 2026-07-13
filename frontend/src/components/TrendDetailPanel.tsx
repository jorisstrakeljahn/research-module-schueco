"use client";

import { ArrowUpRight, X } from "lucide-react";
import Link from "next/link";

import Score from "@/components/Score";
import TrendBadges from "@/components/TrendBadges";
import { PESTEL_SECTORS, type PortfolioTrend, type Trend } from "@/lib/api";
import { useI18n } from "@/lib/i18n";

export default function TrendDetailPanel({
  trend,
  onClose,
}: {
  trend: Trend & Partial<PortfolioTrend>;
  onClose: () => void;
}) {
  const { t } = useI18n();
  const sectors = (trend.pestel ?? []).map(
    (k) => PESTEL_SECTORS.find((s) => s.key === k)?.label ?? k,
  );
  const pendingNew =
    Boolean(trend.pending_review) && String(trend.id).startsWith("pending-");
  const detailHref = pendingNew
    ? `/runs/${trend.pending_run_id ?? trend.run_id ?? ""}`
    : `/portfolio/${trend.id}`;

  return (
    <aside className="flex min-h-0 w-72 shrink-0 flex-col overflow-hidden border-l border-border bg-surface max-lg:fixed max-lg:inset-y-0 max-lg:right-0 max-lg:z-20 max-lg:w-full max-lg:max-w-sm max-lg:shadow-xl xl:w-80 2xl:w-96">
      <div className="flex h-14 shrink-0 items-center justify-between border-b border-border bg-bg px-6">
        <h3 className="truncate text-sm font-semibold tracking-tight text-fg">
          {t("detail.panelTitle")}
        </h3>
        <button
          onClick={onClose}
          aria-label={t("common.close")}
          className="flex h-7 w-7 shrink-0 items-center justify-center rounded-lg text-faint transition-colors hover:bg-hover hover:text-fg"
        >
          <X className="h-4 w-4" />
        </button>
      </div>

      <div className="flex-1 overflow-auto">
        <div className="space-y-6 px-6 py-6">
          <TrendBadges trend={trend} />
          {trend.pending_review && (
            <span className="inline-block rounded-full bg-pending/15 px-3 py-1 text-xs font-medium text-pending">
              {t(pendingNew ? "pending.badgeNew" : "pending.badgeChanged")}
            </span>
          )}
          <h2 className="hyphens-auto text-xl wrap-break-word text-fg">{trend.title}</h2>
          <p className="text-sm text-muted">{trend.summary}</p>

          <div className="space-y-4 border-t border-border pt-6">
          <Field label={t("detail.pestelSectors")}>
            <div className="flex flex-wrap gap-1.5">
              {sectors.length > 0 ? (
                sectors.map((s) => (
                  <span
                    key={s}
                    className="rounded-full bg-surface-2 px-3 py-1 text-xs text-fg"
                  >
                    {s}
                  </span>
                ))
              ) : (
                <span className="text-sm text-faint">–</span>
              )}
            </div>
          </Field>

          <div className="grid grid-cols-3 gap-3">
            <Score field="impact" value={trend.impact} />
            <Score field="urgency" value={trend.urgency} />
            <Score field="uncertainty" value={trend.uncertainty} />
          </div>

          {trend.emergence != null && (
            <Field label={t("detail.emergenceLabel")}>
              <span className="text-sm text-fg">{trend.emergence.toFixed(2)}</span>
            </Field>
          )}

          <Field label={t("detail.keywords")}>
            <span className="text-sm text-muted">{trend.keywords.join(", ")}</span>
          </Field>

          <Link
            href={detailHref}
            className="flex w-full items-center justify-center gap-2 rounded-lg bg-primary py-3 text-white transition-colors hover:bg-primary-bright"
          >
            {t(pendingNew ? "pending.reviewCta" : "detail.fullDetails")}{" "}
            <ArrowUpRight className="h-4 w-4" />
          </Link>
          </div>
        </div>
      </div>
    </aside>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <div className="mb-2 text-sm text-muted">{label}</div>
      {children}
    </div>
  );
}
