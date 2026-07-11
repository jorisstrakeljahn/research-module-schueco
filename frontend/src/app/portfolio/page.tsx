"use client";

import { Search } from "lucide-react";
import Link from "next/link";
import { useEffect, useMemo, useState } from "react";

import PageHeader from "@/components/PageHeader";
import TrendBadges from "@/components/TrendBadges";
import { fetchPortfolioTrends, type PortfolioTrend } from "@/lib/api";
import { useI18n } from "@/lib/i18n";

export default function PortfolioPage() {
  const { t, lang } = useI18n();
  const [trends, setTrends] = useState<PortfolioTrend[]>([]);
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchPortfolioTrends("active")
      .then(setTrends)
      .catch((e) => setError(String(e)))
      .finally(() => setLoading(false));
  }, []);

  const visible = useMemo(() => {
    const needle = query.trim().toLocaleLowerCase();
    if (!needle) return trends;
    return trends.filter(
      (trend) =>
        trend.title.toLocaleLowerCase().includes(needle) ||
        trend.summary.toLocaleLowerCase().includes(needle) ||
        trend.keywords.some((keyword) => keyword.toLocaleLowerCase().includes(needle)),
    );
  }, [query, trends]);

  return (
    <div className="flex h-full min-w-0 flex-col overflow-hidden">
      <PageHeader title={t("portfolio.title")} subtitle={t("portfolio.subtitle")} />
      <div className="flex-1 overflow-auto p-6">
        <div className="mx-auto max-w-6xl space-y-5">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <label className="flex w-full max-w-md items-center gap-2 rounded-lg border border-border bg-surface px-3 py-2 shadow-sm">
              <Search className="h-4 w-4 text-faint" />
              <input
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                placeholder={t("portfolio.search")}
                className="min-w-0 flex-1 bg-transparent text-sm text-fg outline-none placeholder:text-faint"
              />
            </label>
            <span className="text-sm text-muted">{t("portfolio.count", { n: visible.length })}</span>
          </div>

          {loading ? (
            <p className="text-sm text-muted">{t("portfolio.loading")}</p>
          ) : error ? (
            <p className="text-sm text-digital">{error}</p>
          ) : visible.length === 0 ? (
            <p className="rounded-xl border border-dashed border-border p-8 text-center text-sm text-muted">
              {t("portfolio.empty")}
            </p>
          ) : (
            <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
              {visible.map((trend) => (
                <Link
                  key={trend.id}
                  href={`/portfolio/${trend.id}`}
                  className="group flex min-h-56 flex-col rounded-xl border border-border bg-surface p-5 shadow-sm transition hover:border-border-strong hover:bg-surface-2"
                >
                  <TrendBadges trend={trend} />
                  <h2 className="mt-4 text-lg font-semibold leading-snug text-fg group-hover:text-primary">
                    {trend.title}
                  </h2>
                  <p className="mt-2 line-clamp-3 text-sm leading-relaxed text-muted">
                    {trend.summary}
                  </p>
                  <div className="mt-auto flex items-center justify-between pt-5 text-xs text-faint">
                    <span>{t("card.docs", { n: trend.size })}</span>
                    {trend.updated_at && (
                      <span>
                        {t("portfolio.lastRun", {
                          date: new Intl.DateTimeFormat(lang, { dateStyle: "medium" }).format(
                            new Date(trend.updated_at),
                          ),
                        })}
                      </span>
                    )}
                  </div>
                </Link>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
