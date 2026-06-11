"use client";

import { ArrowUpRight, X } from "lucide-react";
import Link from "next/link";

import Score from "@/components/Score";
import TrendBadges from "@/components/TrendBadges";
import { PESTEL_SECTORS, type Trend } from "@/lib/api";
import { useI18n } from "@/lib/i18n";

export default function TrendDetailPanel({
  trend,
  onClose,
}: {
  trend: Trend;
  onClose: () => void;
}) {
  const { t } = useI18n();
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
          <TrendBadges trend={trend} className="mb-4" />
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
