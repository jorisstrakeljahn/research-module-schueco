"use client";

import { Search } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import { toast } from "sonner";

import FilterPanel from "@/components/FilterPanel";
import PageHeader from "@/components/PageHeader";
import TrendCard from "@/components/TrendCard";
import {
  decidePortfolioTrend,
  fetchPortfolioTrends,
  MATURITY_META,
  MATURITY_ORDER,
  updatePortfolioOrder,
  type Maturity,
  type PortfolioTrend,
} from "@/lib/api";
import { useI18n } from "@/lib/i18n";

interface DropTarget {
  maturity: Maturity;
  index: number; // insertion index within the column's visible card list
}

export default function NewsfeedPage() {
  const { t, lang } = useI18n();
  const [trends, setTrends] = useState<PortfolioTrend[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [maturities, setMaturities] = useState<Maturity[]>([...MATURITY_ORDER]);
  const [pestel, setPestel] = useState<string[]>([]);
  const [query, setQuery] = useState("");
  const [dragId, setDragId] = useState<string | null>(null);
  const [dropTarget, setDropTarget] = useState<DropTarget | null>(null);
  const saveTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    fetchPortfolioTrends("active", lang)
      .then(setTrends)
      .catch((e) => setError(String(e)))
      .finally(() => setLoading(false));
  }, [lang]);

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

  function persistOrder(next: PortfolioTrend[]) {
    // The whole array order is authoritative; debounce so rapid consecutive
    // drags collapse into one request.
    if (saveTimer.current) clearTimeout(saveTimer.current);
    saveTimer.current = setTimeout(() => {
      updatePortfolioOrder(
        next.map((trend, index) => ({ id: trend.id, position: index })),
      ).catch((e) => toast.error(t("newsfeed.toastSaveError"), { description: String(e) }));
    }, 400);
  }

  async function persistMaturity(trend: PortfolioTrend, previous: Maturity | null) {
    try {
      await decidePortfolioTrend(trend.id, {
        action: "correct",
        reviewer: "newsfeed-ui",
        reason: `Maturity changed from ${previous ?? "unset"} to ${trend.maturity} via newsfeed`,
        changes: { maturity: trend.maturity },
        language: lang,
      });
      toast.success(t("newsfeed.toastReclass"), {
        description: t("newsfeed.toastReclassDesc", {
          title: trend.title,
          label: t(`maturity.${trend.maturity}`),
        }),
      });
    } catch (e) {
      setTrends((prev) =>
        prev.map((item) =>
          String(item.id) === String(trend.id) ? { ...item, maturity: previous } : item,
        ),
      );
      toast.error(t("newsfeed.toastSaveError"), { description: String(e) });
    }
  }

  function handleDrop(target: DropTarget) {
    if (!dragId) return;
    const dragged = trends.find((trend) => String(trend.id) === dragId);
    if (!dragged) return;

    const withoutDragged = trends.filter((trend) => String(trend.id) !== dragId);
    // Same list the column renders (still contains the dragged card), so the
    // insertion index from the drag-over handlers maps 1:1.
    const columnItems = filtered.filter((trend) => trend.maturity === target.maturity);

    // Find the card the drop lands in front of, skipping the dragged card itself.
    let reference: PortfolioTrend | undefined;
    for (let i = target.index; i < columnItems.length; i += 1) {
      if (String(columnItems[i].id) !== dragId) {
        reference = columnItems[i];
        break;
      }
    }

    let insertAt: number;
    if (reference) {
      insertAt = withoutDragged.findIndex((trend) => trend.id === reference.id);
    } else {
      const remaining = columnItems.filter((trend) => String(trend.id) !== dragId);
      insertAt =
        remaining.length > 0
          ? withoutDragged.findIndex(
              (trend) => trend.id === remaining[remaining.length - 1].id,
            ) + 1
          : withoutDragged.length;
    }

    const previousMaturity = dragged.maturity;
    const moved = { ...dragged, maturity: target.maturity };
    const next = [
      ...withoutDragged.slice(0, insertAt),
      moved,
      ...withoutDragged.slice(insertAt),
    ];
    setTrends(next);
    persistOrder(next);
    if (previousMaturity !== target.maturity) {
      persistMaturity(moved, previousMaturity);
    }
  }

  function clearDrag() {
    setDragId(null);
    setDropTarget(null);
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
          <div className="@container flex-1 overflow-auto p-6">
            {filtered.length === 0 ? (
              <p className="rounded-xl border border-dashed border-border p-8 text-center text-sm text-muted">
                {t("newsfeed.empty")}
              </p>
            ) : (
              <div className="grid grid-cols-1 gap-6 @lg:grid-cols-2 @3xl:grid-cols-4">
                {MATURITY_ORDER.filter((m) => maturities.includes(m)).map((m) => {
                  const items = filtered.filter((trend) => trend.maturity === m);
                  const isTargetColumn = dropTarget?.maturity === m && dragId != null;
                  return (
                    <div
                      key={m}
                      onDragOver={(event) => {
                        event.preventDefault();
                        event.dataTransfer.dropEffect = "move";
                        // Only reached when hovering the empty space below the
                        // cards (card wrappers stop propagation).
                        setDropTarget({ maturity: m, index: items.length });
                      }}
                      onDrop={(event) => {
                        event.preventDefault();
                        handleDrop(dropTarget ?? { maturity: m, index: items.length });
                        clearDrag();
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
                        className={`min-h-24 flex-1 rounded-xl p-1 transition-colors ${
                          isTargetColumn ? "bg-primary/5 ring-1 ring-primary/30" : ""
                        }`}
                      >
                        {items.map((trend, index) => (
                          <div
                            key={trend.id}
                            onDragOver={(event) => {
                              event.preventDefault();
                              event.stopPropagation();
                              event.dataTransfer.dropEffect = "move";
                              const rect = event.currentTarget.getBoundingClientRect();
                              const before =
                                event.clientY < rect.top + rect.height / 2;
                              setDropTarget({ maturity: m, index: before ? index : index + 1 });
                            }}
                            className={
                              String(trend.id) === dragId ? "opacity-40" : undefined
                            }
                          >
                            <DropIndicator
                              visible={isTargetColumn && dropTarget?.index === index}
                            />
                            {/* TrendCard is draggable itself; dragstart bubbles up here. */}
                            <div
                              onDragStart={() => setDragId(String(trend.id))}
                              onDragEnd={clearDrag}
                              className="pt-0.5 pb-2"
                            >
                              <TrendCard trend={trend} />
                            </div>
                          </div>
                        ))}
                        <DropIndicator
                          visible={isTargetColumn && dropTarget?.index === items.length}
                        />
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

/** Insertion marker shown while dragging: a line where the card would land. */
function DropIndicator({ visible }: { visible: boolean }) {
  return (
    <div
      aria-hidden
      className={`pointer-events-none h-1 rounded-full transition-all ${
        visible ? "my-0.5 bg-primary opacity-100" : "opacity-0"
      }`}
    />
  );
}
