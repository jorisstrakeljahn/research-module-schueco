"use client";

import {
  CATEGORY_META,
  MATURITY_META,
  RADAR_STAGE_META,
  type Maturity,
  type Trend,
} from "@/lib/api";
import { useI18n } from "@/lib/i18n";

export default function TrendBadges({
  trend,
  className = "",
}: {
  trend: Trend;
  className?: string;
}) {
  const { t } = useI18n();
  const cat = trend.category ? CATEGORY_META[trend.category] : null;
  const stage = trend.radar_stage ? RADAR_STAGE_META[trend.radar_stage] : null;
  const maturity = trend.maturity ? (trend.maturity as Maturity) : null;

  return (
    <div className={`flex flex-wrap items-center gap-2 text-xs ${className}`.trim()}>
      {stage && (
        <span className="rounded-full bg-fg px-2.5 py-0.5 font-medium text-bg">
          {stage.label}
        </span>
      )}
      {cat && (
        <span
          className="rounded-full px-2.5 py-0.5 font-medium text-white"
          style={{ backgroundColor: cat.color }}
        >
          {cat.label}
        </span>
      )}
      {maturity && (
        <span
          className="rounded-full px-2.5 py-0.5 font-medium text-white"
          style={{ backgroundColor: MATURITY_META[maturity].color }}
        >
          {t(`maturity.${maturity}`)}
        </span>
      )}
    </div>
  );
}
