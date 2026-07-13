"use client";

import Link from "next/link";

import { CATEGORY_META, RADAR_STAGE_META, type PortfolioTrend, type Trend } from "@/lib/api";
import { useI18n } from "@/lib/i18n";

function isPendingNew(trend: Trend & Partial<PortfolioTrend>): boolean {
  return Boolean(trend.pending_review) && String(trend.id).startsWith("pending-");
}

export default function TrendCard({ trend }: { trend: Trend & Partial<PortfolioTrend> }) {
  const { t } = useI18n();
  const cat = trend.category ? CATEGORY_META[trend.category] : null;
  const stage = trend.radar_stage ? RADAR_STAGE_META[trend.radar_stage] : null;
  const pending = Boolean(trend.pending_review);
  const pendingNew = isPendingNew(trend);
  // Provisional trends have no portfolio page yet; their detail lives in the
  // run review. Pending changes on known trends keep their portfolio link.
  const href = pendingNew
    ? `/runs/${trend.pending_run_id ?? trend.run_id ?? ""}`
    : `/portfolio/${trend.id}`;

  return (
    <div
      draggable={!pendingNew}
      onDragStart={(e) => {
        e.dataTransfer.setData("text/plain", String(trend.id));
        e.dataTransfer.effectAllowed = "move";
      }}
      className={`rounded-lg border bg-surface p-4 shadow-sm transition-colors ${
        pending
          ? "border-dashed border-pending/60 bg-pending/5 hover:border-pending"
          : "border-border hover:border-border-strong"
      } ${pendingNew ? "" : "cursor-grab active:cursor-grabbing"}`}
    >
      <div className="mb-2 flex items-center gap-2">
        {cat && (
          <span
            className="h-2 w-2 shrink-0 rounded-full"
            style={{ backgroundColor: cat.color }}
            title={cat.label}
          />
        )}
        {stage && (
          <span className="text-[11px] font-medium uppercase tracking-wide text-faint">
            {stage.label}
          </span>
        )}
        {pending && (
          <span className="ml-auto shrink-0 rounded-full bg-pending/15 px-2 py-0.5 text-[11px] font-medium text-pending">
            {t(pendingNew ? "pending.badgeNew" : "pending.badgeChanged")}
          </span>
        )}
      </div>
      <Link
        href={href}
        className="block hyphens-auto font-medium leading-snug wrap-break-word text-fg hover:text-primary"
      >
        {trend.title}
      </Link>
      <p className="mt-1.5 line-clamp-3 hyphens-auto text-sm leading-relaxed wrap-break-word text-muted">
        {trend.summary}
      </p>
      {pending && (
        <Link
          href={`/runs/${trend.pending_run_id ?? trend.run_id ?? ""}`}
          className="mt-3 inline-flex items-center gap-1 text-xs font-medium text-pending hover:underline"
        >
          {t("pending.reviewCta")} →
        </Link>
      )}
    </div>
  );
}
