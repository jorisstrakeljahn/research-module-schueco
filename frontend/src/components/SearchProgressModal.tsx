"use client";

import { Check, Loader2, X } from "lucide-react";
import Link from "next/link";
import { useEffect, useMemo, useRef } from "react";

import type { RunDiff, RunMode, RunProgress, RunProgressEvent } from "@/lib/api";
import { useI18n } from "@/lib/i18n";

export default function SearchProgressModal({
  open,
  query,
  mode,
  progress,
  diff,
  onClose,
}: {
  open: boolean;
  query: string;
  mode: RunMode;
  progress: RunProgress;
  diff: RunDiff | null;
  onClose: () => void;
}) {
  const { t, lang } = useI18n();
  const failed = progress.status === "failed";
  const completed = progress.status === "completed";
  const running = !failed && !completed;
  const feedRef = useRef<HTMLDivElement>(null);

  const lines = useMemo(
    () => buildFeed(progress.events, t),
    [progress.events, t],
  );

  useEffect(() => {
    const el = feedRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [lines.length]);

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/45 p-4 backdrop-blur-sm"
      role="dialog"
      aria-modal="true"
      aria-labelledby="search-progress-title"
    >
      {/* Fixed height: the dialog opens at its final size instead of growing
          line by line while progress events stream in. */}
      <div className="flex h-[min(44rem,90vh)] w-full max-w-2xl flex-col overflow-hidden rounded-2xl border border-border-strong bg-surface shadow-2xl">
        <header className="border-b border-border px-6 py-4">
          <div className="flex items-start justify-between gap-4">
            <div className="min-w-0">
              <h2 id="search-progress-title" className="text-base font-semibold text-fg">
                {t(
                  failed
                    ? "search.progress.failedTitle"
                    : completed
                      ? "search.progress.doneTitle"
                      : "search.progress.title",
                )}
              </h2>
              <p className="mt-0.5 truncate text-sm text-muted">
                “{query}” ·{" "}
                {t(mode === "deep_research" ? "search.modeDeep" : "search.modeSimple")}
              </p>
            </div>
            <button
              type="button"
              onClick={onClose}
              aria-label={t("search.progress.close")}
              className="rounded-lg p-2 text-muted transition-colors hover:bg-hover hover:text-fg"
            >
              <X className="h-5 w-5" />
            </button>
          </div>
          <div className="mt-3 flex items-center gap-3">
            <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-surface-2">
              <div
                className={`h-full rounded-full transition-[width] duration-700 ${
                  failed ? "bg-digital" : "bg-primary"
                }`}
                style={{ width: `${progress.progress}%` }}
              />
            </div>
            <span className="w-10 text-right text-xs font-medium tabular-nums text-muted">
              {progress.progress}%
            </span>
          </div>
        </header>

        <div ref={feedRef} className="flex-1 overflow-y-auto px-6 py-4">
          <ol className="space-y-1">
            {lines.map((line, index) => {
              const isLast = index === lines.length - 1;
              const pending = isLast && running;
              return (
                <li key={line.key} className="flex gap-3 py-1.5">
                  <span className="mt-1 flex h-3.5 w-3.5 shrink-0 items-center justify-center">
                    {pending ? (
                      <Loader2 className="h-3.5 w-3.5 animate-spin text-primary" />
                    ) : (
                      <span className="h-1.5 w-1.5 rounded-full bg-primary/50" />
                    )}
                  </span>
                  <div className="min-w-0 flex-1">
                    <p className={`text-sm ${pending ? "text-fg" : "text-muted"}`}>
                      {line.text}
                    </p>
                    {line.secondary && (
                      <p className="truncate text-xs text-faint">{line.secondary}</p>
                    )}
                  </div>
                  <span className="shrink-0 text-[11px] tabular-nums text-faint">
                    {new Intl.DateTimeFormat(lang, {
                      hour: "2-digit",
                      minute: "2-digit",
                      second: "2-digit",
                    }).format(new Date(line.at))}
                  </span>
                </li>
              );
            })}
            {failed && (
              <li className="flex gap-3 py-1.5">
                <span className="mt-0.5 flex h-4 w-4 shrink-0 items-center justify-center">
                  <X className="h-3.5 w-3.5 text-digital" />
                </span>
                <p className="text-sm text-digital">
                  {progress.error || t("search.progress.failed")}
                </p>
              </li>
            )}
          </ol>

          {completed && (
            <div className="mt-4 rounded-xl border border-border bg-surface-2/60 p-4">
              <p className="text-sm font-medium text-fg">
                {t("search.progress.summary", {
                  docs: progress.n_documents,
                  topics: progress.n_topics,
                })}
              </p>
              {diff && (
                <p className="mt-1 text-sm text-muted">
                  {t("search.progress.summaryDiff", {
                    fresh: diff.counts.new ?? 0,
                    changed:
                      (diff.counts.classification_changed ?? 0) +
                      (diff.counts.content_changed ?? 0),
                    evidence: diff.counts.evidence_only ?? 0,
                  })}
                </p>
              )}
            </div>
          )}
        </div>

        <footer className="flex flex-wrap items-center justify-between gap-3 border-t border-border px-6 py-4">
          <p className="text-xs text-muted">
            {completed
              ? t("search.progress.saved")
              : t("search.progress.backgroundHint")}
          </p>
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={onClose}
              className="rounded-lg border border-border bg-surface px-4 py-2 text-sm font-medium text-fg hover:bg-hover"
            >
              {completed
                ? t("search.progress.close")
                : t("search.progress.background")}
            </button>
            {/* No onClick close here: unmounting the link mid-transition can
                cancel the navigation. GlobalSearchProgress closes the dialog
                once the route change lands. */}
            {completed && (
              <Link
                href={`/runs/${progress.run_id}`}
                className="rounded-lg bg-primary px-4 py-2 text-sm font-medium text-white hover:bg-primary-bright"
              >
                {t("search.progress.openResult")}
              </Link>
            )}
          </div>
        </footer>
      </div>
    </div>
  );
}

export function SearchProgressPill({
  progress,
  onClick,
}: {
  progress: RunProgress;
  onClick: () => void;
}) {
  const { t } = useI18n();
  const finished = progress.status === "completed" || progress.status === "failed";
  return (
    <button
      type="button"
      onClick={onClick}
      className="fixed bottom-5 right-5 z-40 flex items-center gap-3 rounded-full border border-border-strong bg-surface px-4 py-3 shadow-xl transition-transform hover:-translate-y-0.5"
    >
      {finished ? (
        progress.status === "completed" ? (
          <Check className="h-4 w-4 text-primary" />
        ) : (
          <X className="h-4 w-4 text-digital" />
        )
      ) : (
        <Loader2 className="h-4 w-4 animate-spin text-primary" />
      )}
      <span className="text-left">
        <span className="block text-xs font-semibold text-fg">
          {t(`search.progress.phase.${progress.phase}`)}
        </span>
        <span className="block text-[11px] text-muted">{progress.progress}%</span>
      </span>
    </button>
  );
}

interface FeedLine {
  key: string;
  text: string;
  secondary?: string;
  at: string;
}

function sourceLabel(details: Record<string, unknown>): string {
  const source = String(details.source ?? "");
  if (source.toLowerCase() === "firecrawl") {
    return details.source_type === "web" ? "Firecrawl Web" : "Firecrawl News";
  }
  return source;
}

/** Translate raw pipeline events into user-facing, localized feed lines. */
function buildFeed(
  events: RunProgressEvent[],
  t: (key: string, params?: Record<string, string | number>) => string,
): FeedLine[] {
  const lines: FeedLine[] = [];
  const seenPhases = new Set<string>();
  for (const event of events) {
    const details = (event.details ?? {}) as Record<string, unknown>;
    const code = typeof details.code === "string" ? details.code : null;
    const key = `event-${event.id}`;
    if (code === "search_started") {
      lines.push({ key, at: event.created_at, text: t("search.progress.event.started") });
    } else if (code === "round_started") {
      const queries = Array.isArray(details.queries) ? details.queries : [];
      lines.push({
        key,
        at: event.created_at,
        text: t("search.progress.event.round", {
          n: Number(details.round ?? 1),
          k: queries.length,
        }),
      });
    } else if (code === "source_searched") {
      lines.push({
        key,
        at: event.created_at,
        text: t("search.progress.event.source", {
          source: sourceLabel(details),
          n: Number(details.findings ?? 0),
        }),
        secondary: typeof details.query === "string" ? `„${details.query}“` : undefined,
      });
    } else if (code === "source_failed") {
      lines.push({
        key,
        at: event.created_at,
        text: t("search.progress.event.sourceFailed", { source: sourceLabel(details) }),
        secondary: typeof details.query === "string" ? `„${details.query}“` : undefined,
      });
    } else if (code === "queries_expanded") {
      const queries = Array.isArray(details.queries) ? details.queries : [];
      lines.push({
        key,
        at: event.created_at,
        text: t("search.progress.event.expanded", { n: queries.length }),
        secondary: queries.join(" · "),
      });
    } else if (code === "round_completed") {
      lines.push({
        key,
        at: event.created_at,
        text: t("search.progress.event.roundDone", {
          n: Number(details.round ?? 1),
          total: Number(details.total ?? 0),
        }),
      });
    } else if (code === "search_completed") {
      lines.push({
        key,
        at: event.created_at,
        text: t("search.progress.event.searchDone", {
          n: Number(details.findings ?? 0),
        }),
      });
    } else if (event.phase === "corpus") {
      lines.push({
        key,
        at: event.created_at,
        text: t("search.progress.event.corpus", {
          total: Number(details.documents ?? 0),
          fresh: Number(details.new_documents ?? 0),
        }),
      });
    } else if (!seenPhases.has(event.phase)) {
      // One line per pipeline phase (embedding, clustering, ...), no duplicates.
      seenPhases.add(event.phase);
      lines.push({
        key,
        at: event.created_at,
        text: t(`search.progress.phase.${event.phase}`),
      });
    }
  }
  if (lines.length === 0) {
    lines.push({
      key: "queued",
      at: new Date().toISOString(),
      text: t("search.progress.phase.queued"),
    });
  }
  return lines;
}
