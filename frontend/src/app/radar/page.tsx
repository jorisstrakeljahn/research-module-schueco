"use client";

import { useEffect, useMemo, useState } from "react";

import FilterPanel from "@/components/FilterPanel";
import PageHeader from "@/components/PageHeader";
import TrendDetailPanel from "@/components/TrendDetailPanel";
import TrendRadar from "@/components/TrendRadar";
import { fetchTrends, MATURITY_ORDER, type Maturity, type Trend } from "@/lib/api";
import { useI18n } from "@/lib/i18n";

export default function RadarPage() {
  const { t } = useI18n();
  const [trends, setTrends] = useState<Trend[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState<Trend | null>(null);
  const [maturities, setMaturities] = useState<Maturity[]>([...MATURITY_ORDER]);
  const [pestel, setPestel] = useState<string[]>([]);
  const [region, setRegion] = useState<string | null>(null);

  useEffect(() => {
    fetchTrends()
      .then(setTrends)
      .catch((e) => setError(String(e)))
      .finally(() => setLoading(false));
  }, []);

  const regions = useMemo(
    () =>
      Array.from(
        new Set(trends.map((t) => t.region).filter((r): r is string => !!r)),
      ).sort(),
    [trends],
  );

  const filtered = useMemo(
    () =>
      trends.filter((t) => {
        const mMatch = t.maturity
          ? maturities.includes(t.maturity as Maturity)
          : true;
        const pMatch =
          pestel.length === 0 || (t.pestel ?? []).some((p) => pestel.includes(p));
        const rMatch = !region || t.region === region;
        return mMatch && pMatch && rMatch;
      }),
    [trends, maturities, pestel, region],
  );

  return (
    <div className="relative flex h-full min-w-0 overflow-hidden">
      <FilterPanel
        selectedMaturities={maturities}
        selectedPestel={pestel}
        onMaturityChange={setMaturities}
        onPestelChange={setPestel}
        regions={regions}
        selectedRegion={region}
        onRegionChange={setRegion}
      />

      <div className="flex min-w-0 flex-1 flex-col overflow-hidden">
        <PageHeader title={t("radar.title")} subtitle={t("radar.subtitle")} />

        <div className="flex min-h-0 flex-1 flex-col p-4 lg:p-5">
          {loading ? (
            <p className="text-sm text-muted">{t("radar.loading")}</p>
          ) : error ? (
            <p className="text-sm text-digital">{error}</p>
          ) : filtered.length === 0 ? (
            <p className="text-sm text-muted">{t("radar.empty")}</p>
          ) : (
            <div className="flex min-h-0 min-w-0 flex-1 flex-col overflow-hidden rounded-xl border border-border bg-surface p-3 shadow-sm lg:p-4">
              <TrendRadar
                trends={filtered}
                selectedId={selected?.id ?? null}
                onSelect={setSelected}
              />
            </div>
          )}
        </div>
      </div>

      {selected && (
        <>
          <button
            type="button"
            aria-label="close"
            className="fixed inset-0 z-10 bg-fg/20 lg:hidden"
            onClick={() => setSelected(null)}
          />
          <TrendDetailPanel trend={selected} onClose={() => setSelected(null)} />
        </>
      )}
    </div>
  );
}
