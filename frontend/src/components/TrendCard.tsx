"use client";

import Link from "next/link";

import { CATEGORY_META, RADAR_STAGE_META, type Trend } from "@/lib/api";

export default function TrendCard({ trend }: { trend: Trend }) {
  const cat = trend.category ? CATEGORY_META[trend.category] : null;
  const stage = trend.radar_stage ? RADAR_STAGE_META[trend.radar_stage] : null;

  return (
    <div
      draggable
      onDragStart={(e) => {
        e.dataTransfer.setData("text/plain", String(trend.id));
        e.dataTransfer.effectAllowed = "move";
      }}
      className="cursor-grab rounded-lg border border-border bg-surface p-4 shadow-sm transition-colors hover:border-border-strong active:cursor-grabbing"
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
      </div>
      <Link
        href={`/portfolio/${trend.id}`}
        className="block hyphens-auto font-medium leading-snug wrap-break-word text-fg hover:text-primary"
      >
        {trend.title}
      </Link>
      <p className="mt-1.5 line-clamp-3 hyphens-auto text-sm leading-relaxed wrap-break-word text-muted">
        {trend.summary}
      </p>
    </div>
  );
}
