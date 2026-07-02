"use client";

import { useEffect, useMemo, useState } from "react";
import { toast } from "sonner";

import FilterPanel from "@/components/FilterPanel";
import PageHeader from "@/components/PageHeader";
import TrendCard from "@/components/TrendCard";
import {
  fetchTrends,
  MATURITY_META,
  MATURITY_ORDER,
  sendFeedback,
  type Maturity,
  type Trend,
} from "@/lib/api";
import { useI18n } from "@/lib/i18n";

export default function NewsfeedPage() {
  const { t } = useI18n();
  const [trends, setTrends] = useState<Trend[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [dragOver, setDragOver] = useState<Maturity | null>(null);
  const [maturities, setMaturities] = useState<Maturity[]>([...MATURITY_ORDER]);
  const [pestel, setPestel] = useState<string[]>([]);

  useEffect(() => {
    fetchTrends()
      .then(setTrends)
      .catch((e) => setError(String(e)))
      .finally(() => setLoading(false));
  }, []);

  const filtered = useMemo(
    () =>
      trends.filter(
        (t) =>
          pestel.length === 0 || (t.pestel ?? []).some((p) => pestel.includes(p)),
      ),
    [trends, pestel],
  );

  async function reclassify(trendId: number, newMaturity: Maturity) {
    const trend = trends.find((t) => t.id === trendId);
    if (!trend || trend.maturity === newMaturity) return;
    const old = trend.maturity;
    setTrends((prev) =>
      prev.map((t) => (t.id === trendId ? { ...t, maturity: newMaturity } : t)),
    );
    try {
      await sendFeedback(trendId, {
        action: "correct",
        field: "maturity",
        old_value: old ?? undefined,
        new_value: newMaturity,
      });
      toast.success(t("newsfeed.toastReclass"), {
        description: t("newsfeed.toastReclassDesc", {
          title: trend.title,
          label: t(`maturity.${newMaturity}`),
        }),
      });
    } catch (e) {
      setTrends((prev) =>
        prev.map((tr) => (tr.id === trendId ? { ...tr, maturity: old } : tr)),
      );
      toast.error(t("newsfeed.toastSaveError"), { description: String(e) });
    }
  }

  return (
    <div className="flex h-full min-w-0 overflow-hidden">
      <FilterPanel
        selectedMaturities={maturities}
        selectedPestel={pestel}
        onMaturityChange={setMaturities}
        onPestelChange={setPestel}
      />

      <div className="flex min-w-0 flex-1 flex-col overflow-hidden">
        <PageHeader title={t("newsfeed.title")} subtitle={t("newsfeed.subtitle")} />

        {loading ? (
          <p className="p-6 text-sm text-muted">{t("newsfeed.loading")}</p>
        ) : error ? (
          <p className="p-6 text-sm text-digital">{error}</p>
        ) : (
          <div className="grid flex-1 grid-cols-1 gap-6 overflow-auto p-6 md:grid-cols-2 xl:grid-cols-4">
            {MATURITY_ORDER.filter((m) => maturities.includes(m)).map((m) => {
              const items = filtered.filter((t) => t.maturity === m);
              const over = dragOver === m;
              return (
                <div
                  key={m}
                  onDragOver={(e) => {
                    e.preventDefault();
                    setDragOver(m);
                  }}
                  onDragLeave={() => setDragOver((d) => (d === m ? null : d))}
                  onDrop={(e) => {
                    e.preventDefault();
                    setDragOver(null);
                    const id = Number(e.dataTransfer.getData("text/plain"));
                    if (id) reclassify(id, m);
                  }}
                  className="flex flex-col"
                >
                  <div className="mb-3 flex items-center gap-2">
                    <span
                      className="h-2 w-2 shrink-0 rounded-full"
                      style={{ backgroundColor: MATURITY_META[m].color }}
                    />
                    <h3 className="text-sm font-medium text-fg">{t(`maturity.${m}`)}</h3>
                    <span className="text-xs text-faint">{items.length}</span>
                  </div>
                  <div
                    className={`min-h-24 flex-1 space-y-2.5 rounded-xl p-1 transition-colors ${
                      over ? "bg-primary/5 ring-1 ring-primary/30" : ""
                    }`}
                  >
                    {items.map((t) => (
                      <TrendCard key={t.id} trend={t} />
                    ))}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
