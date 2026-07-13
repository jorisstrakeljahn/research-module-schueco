"use client";

import { Search } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { toast } from "sonner";

import FilterPanel from "@/components/FilterPanel";
import PageHeader from "@/components/PageHeader";
import TrendCard from "@/components/TrendCard";
import {
  decidePortfolioTrend,
  fetchPortfolioTrends,
  MATURITY_META,
  MATURITY_ORDER,
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
  const [query, setQuery] = useState("");

  useEffect(() => {
    fetchPortfolioTrends("active")
      .then(setTrends)
      .catch((e) => setError(String(e)))
      .finally(() => setLoading(false));
  }, []);

  const filtered = useMemo(() => {
    const needle = query.trim().toLocaleLowerCase();
    return trends.filter((trend) => {
      const matchesPestel =
        pestel.length === 0 || (trend.pestel ?? []).some((sector) => pestel.includes(sector));
      const matchesQuery =
        !needle ||
        trend.title.toLocaleLowerCase().includes(needle) ||
        trend.summary.toLocaleLowerCase().includes(needle) ||
        trend.keywords.some((keyword) => keyword.toLocaleLowerCase().includes(needle));
      return matchesPestel && matchesQuery;
    });
  }, [trends, pestel, query]);

  async function reclassify(trendId: string, newMaturity: Maturity) {
    const trend = trends.find((t) => String(t.id) === trendId);
    if (!trend || trend.maturity === newMaturity) return;
    const old = trend.maturity;
    setTrends((prev) =>
      prev.map((t) => (String(t.id) === trendId ? { ...t, maturity: newMaturity } : t)),
    );
    try {
      await decidePortfolioTrend(trendId, {
        action: "correct",
        reviewer: "newsfeed-ui",
        reason: `Maturity changed from ${old ?? "unset"} to ${newMaturity} via newsfeed`,
        changes: { maturity: newMaturity },
      });
      toast.success(t("newsfeed.toastReclass"), {
        description: t("newsfeed.toastReclassDesc", {
          title: trend.title,
          label: t(`maturity.${newMaturity}`),
        }),
      });
    } catch (e) {
      setTrends((prev) =>
        prev.map((tr) => (String(tr.id) === trendId ? { ...tr, maturity: old } : tr)),
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
        <PageHeader
          title={t("newsfeed.title")}
          subtitle={t("newsfeed.subtitle")}
          actions={
            <div className="flex items-center gap-3">
              <label className="flex w-52 items-center gap-2 rounded-lg border border-border bg-surface px-3 py-1.5 shadow-sm lg:w-60 xl:w-72">
                <Search className="h-4 w-4 shrink-0 text-faint" />
                <input
                  type="search"
                  value={query}
                  onChange={(event) => setQuery(event.target.value)}
                  placeholder={t("newsfeed.search")}
                  aria-label={t("newsfeed.search")}
                  className="min-w-0 flex-1 bg-transparent text-sm text-fg outline-none placeholder:text-faint"
                />
              </label>
              <span className="hidden whitespace-nowrap text-xs text-muted 2xl:block">
                {t("newsfeed.count", { n: filtered.length })}
              </span>
            </div>
          }
        />

        {loading ? (
          <p className="p-6 text-sm text-muted">{t("newsfeed.loading")}</p>
        ) : error ? (
          <p className="p-6 text-sm text-digital">{error}</p>
        ) : (
          <div className="flex-1 overflow-auto p-6">
            {filtered.length === 0 ? (
              <p className="rounded-xl border border-dashed border-border p-8 text-center text-sm text-muted">
                {t("newsfeed.empty")}
              </p>
            ) : (
              <div className="grid grid-cols-1 gap-6 md:grid-cols-2 xl:grid-cols-4">
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
                        const id = e.dataTransfer.getData("text/plain");
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
                        {items.map((trend) => (
                          <TrendCard key={trend.id} trend={trend} />
                        ))}
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
