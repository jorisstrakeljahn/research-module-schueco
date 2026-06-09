"use client";

import { ChevronLeft, ChevronRight } from "lucide-react";
import { useState } from "react";

import { MATURITY_META, MATURITY_ORDER, PESTEL_SECTORS, type Maturity } from "@/lib/api";
import { useI18n } from "@/lib/i18n";

export default function FilterPanel({
  selectedMaturities,
  selectedPestel,
  onMaturityChange,
  onPestelChange,
  regions = [],
  selectedRegion = null,
  onRegionChange,
}: {
  selectedMaturities: Maturity[];
  selectedPestel: string[];
  onMaturityChange: (v: Maturity[]) => void;
  onPestelChange: (v: string[]) => void;
  regions?: string[];
  selectedRegion?: string | null;
  onRegionChange?: (v: string | null) => void;
}) {
  const { t } = useI18n();
  const [open, setOpen] = useState(true);

  const toggleMaturity = (m: Maturity) =>
    onMaturityChange(
      selectedMaturities.includes(m)
        ? selectedMaturities.filter((x) => x !== m)
        : [...selectedMaturities, m],
    );

  const togglePestel = (p: string) =>
    onPestelChange(
      selectedPestel.includes(p)
        ? selectedPestel.filter((x) => x !== p)
        : [...selectedPestel, p],
    );

  if (!open) {
    return (
      <div className="flex w-12 shrink-0 flex-col items-center border-r border-border py-3">
        <button
          type="button"
          onClick={() => setOpen(true)}
          title={t("filter.show")}
          aria-label={t("filter.show")}
          className="flex h-8 w-8 items-center justify-center rounded-md text-faint transition-colors hover:bg-hover hover:text-fg"
        >
          <ChevronRight className="h-4 w-4" />
        </button>
      </div>
    );
  }

  return (
    <aside className="flex w-60 shrink-0 flex-col overflow-auto border-r border-border">
      <div className="flex h-14 shrink-0 items-center justify-between border-b border-border px-5">
        <h3 className="text-sm font-semibold text-fg">{t("filter.title")}</h3>
        <button
          type="button"
          onClick={() => setOpen(false)}
          title={t("filter.hide")}
          aria-label={t("filter.hide")}
          className="flex h-8 w-8 items-center justify-center rounded-md text-faint transition-colors hover:bg-hover hover:text-fg"
        >
          <ChevronLeft className="h-4 w-4" />
        </button>
      </div>

      <div className="overflow-auto p-5">

      <div className="space-y-6">
        <div>
          <h4 className="mb-2 text-xs font-medium uppercase tracking-wider text-faint">
            {t("filter.maturity")}
          </h4>
          <div className="space-y-0.5">
            {MATURITY_ORDER.map((m) => {
              const sel = selectedMaturities.includes(m);
              return (
                <button
                  key={m}
                  onClick={() => toggleMaturity(m)}
                  className={`flex w-full items-center gap-2.5 rounded-lg px-2.5 py-2 text-sm transition-colors ${
                    sel ? "text-fg" : "text-muted hover:bg-hover hover:text-fg"
                  }`}
                >
                  <span
                    className="h-2.5 w-2.5 shrink-0 rounded-full"
                    style={{
                      backgroundColor: sel ? MATURITY_META[m].color : "transparent",
                      boxShadow: sel ? "none" : "inset 0 0 0 1.5px var(--faint)",
                    }}
                  />
                  <span className="truncate">{t(`maturity.${m}`)}</span>
                </button>
              );
            })}
          </div>
        </div>

        <div>
          <div className="mb-2 flex items-center justify-between">
            <h4 className="text-xs font-medium uppercase tracking-wider text-faint">
              {t("filter.pestel")}
            </h4>
            {selectedPestel.length > 0 && (
              <button
                onClick={() => onPestelChange([])}
                className="text-xs text-primary transition-colors hover:text-primary-bright"
              >
                {t("filter.resetPestel")}
              </button>
            )}
          </div>
          <div className="flex flex-wrap gap-1.5">
            {PESTEL_SECTORS.map((s) => {
              const sel = selectedPestel.includes(s.key);
              return (
                <button
                  key={s.key}
                  onClick={() => togglePestel(s.key)}
                  className={`rounded-full border px-3 py-1 text-xs transition-colors ${
                    sel
                      ? "border-primary/30 bg-primary/12 text-primary"
                      : "border-border text-muted hover:bg-hover hover:text-fg"
                  }`}
                >
                  {s.label}
                </button>
              );
            })}
          </div>
        </div>

        {regions.length > 0 && onRegionChange && (
          <div>
            <h4 className="mb-2 text-xs font-medium uppercase tracking-wider text-faint">
              {t("filter.region")}
            </h4>
            <div className="flex flex-wrap gap-1.5">
              {[null, ...regions].map((r) => {
                const sel = selectedRegion === r;
                return (
                  <button
                    key={r ?? "all"}
                    onClick={() => onRegionChange(r)}
                    className={`rounded-full border px-3 py-1 text-xs transition-colors ${
                      sel
                        ? "border-primary/30 bg-primary/12 text-primary"
                        : "border-border text-muted hover:bg-hover hover:text-fg"
                    }`}
                  >
                    {r ?? t("filter.regionAll")}
                  </button>
                );
              })}
            </div>
          </div>
        )}
      </div>
      </div>
    </aside>
  );
}
