"use client";

import { ArrowUpRight, X } from "lucide-react";
import Link from "next/link";

import {
  CATEGORY_META,
  MATURITY_META,
  PESTEL_SECTORS,
  RADAR_STAGE_META,
  type Maturity,
  type Trend,
} from "@/lib/api";
import { useI18n } from "@/lib/i18n";

export default function TrendDetailPanel({
  trend,
  onClose,
}: {
  trend: Trend;
  onClose: () => void;
}) {
  const { t } = useI18n();
  const cat = trend.category ? CATEGORY_META[trend.category] : null;
  const stage = trend.radar_stage ? RADAR_STAGE_META[trend.radar_stage] : null;
  const maturity = trend.maturity ? (trend.maturity as Maturity) : null;
  const sectors = (trend.pestel ?? []).map(
    (k) => PESTEL_SECTORS.find((s) => s.key === k)?.label ?? k,
  );

  return (
    <aside className="w-96 shrink-0 overflow-auto border-l border-border bg-surface">
      <div className="sticky top-0 z-10 flex items-center justify-between border-b border-border bg-surface px-6 py-5">
        <h3 className="text-sm font-medium text-fg">{t("detail.panelTitle")}</h3>
        <button
          onClick={onClose}
          aria-label="close"
          className="flex h-7 w-7 items-center justify-center rounded-lg text-faint transition-colors hover:bg-hover hover:text-fg"
        >
          <X className="h-4 w-4" />
        </button>
      </div>

      <div className="space-y-6 px-6 pb-6">
        <div>
          <div className="mb-4 flex flex-wrap items-center gap-2 text-xs">
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
          <h2 className="mb-3 text-xl text-fg">{trend.title}</h2>
          <p className="text-sm text-muted">{trend.summary}</p>
        </div>

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
                <span className="text-sm text-faint">n/a</span>
              )}
            </div>
          </Field>

          <div className="grid grid-cols-3 gap-3">
            <Score label="Impact" value={trend.impact} />
            <Score label="Urgency" value={trend.urgency} />
            <Score label="Uncertainty" value={trend.uncertainty} />
          </div>

          {trend.emergence != null && (
            <Field label={t("detail.emergenceLabel")}>
              <span className="text-sm text-fg">{trend.emergence.toFixed(2)}</span>
            </Field>
          )}

          <Field label={t("detail.keywords")}>
            <span className="text-sm text-muted">{trend.keywords.join(", ")}</span>
          </Field>
        </div>

        <Link
          href={`/trends/${trend.id}`}
          className="flex w-full items-center justify-center gap-2 rounded-lg bg-primary py-3 text-white transition-colors hover:bg-primary-bright"
        >
          {t("detail.fullDetails")} <ArrowUpRight className="h-4 w-4" />
        </Link>
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

function Score({ label, value }: { label: string; value: number | null }) {
  const v = value ?? 0;
  return (
    <div>
      <div className="flex items-baseline justify-between text-[12px] text-muted">
        <span>{label}</span>
        <span className="font-mono text-fg">{value != null ? value.toFixed(1) : "n/a"}</span>
      </div>
      <div className="mt-1 h-1.5 w-full rounded-full bg-surface-2">
        <div
          className="h-1.5 rounded-full bg-primary"
          style={{ width: `${(v / 10) * 100}%` }}
        />
      </div>
    </div>
  );
}
