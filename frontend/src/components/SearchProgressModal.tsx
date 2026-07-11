"use client";

import {
  Check,
  CheckCircle2,
  ChevronRight,
  Circle,
  Database,
  ExternalLink,
  FileSearch,
  GitCompareArrows,
  Loader2,
  Network,
  Search,
  Sparkles,
  X,
  XCircle,
} from "lucide-react";
import Link from "next/link";
import { useMemo } from "react";

import type { RunDiff, RunMode, RunProgress } from "@/lib/api";
import { useI18n } from "@/lib/i18n";

const PHASES = [
  { key: "queued", icon: Circle },
  { key: "researching", icon: Search },
  { key: "ingesting", icon: FileSearch },
  { key: "corpus", icon: Database },
  { key: "embedding", icon: Network },
  { key: "clustering", icon: Sparkles },
  { key: "analyzing", icon: FileSearch },
  { key: "matching", icon: GitCompareArrows },
  { key: "completed", icon: CheckCircle2 },
] as const;

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
  const currentIndex = Math.max(
    0,
    PHASES.findIndex((phase) => phase.key === progress.phase),
  );
  const metrics = useMemo(
    () =>
      Object.assign(
        {},
        ...progress.events.map((event) => event.details ?? {}),
      ) as Record<string, unknown>,
    [progress.events],
  );

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/45 p-4 backdrop-blur-sm"
      role="dialog"
      aria-modal="true"
      aria-labelledby="search-progress-title"
    >
      <div className="relative flex max-h-[92vh] w-full max-w-4xl flex-col overflow-hidden rounded-2xl border border-border-strong bg-surface shadow-2xl">
        <div className="pointer-events-none absolute inset-x-0 top-0 h-28 bg-gradient-to-r from-primary/12 via-primary-bright/8 to-climate/10" />
        <header className="relative flex items-start gap-4 border-b border-border px-6 py-5">
          <div className="relative mt-0.5 flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-primary text-white shadow-lg shadow-primary/20">
            {failed ? (
              <XCircle className="h-5 w-5" />
            ) : completed ? (
              <CheckCircle2 className="h-5 w-5" />
            ) : (
              <>
                <Sparkles className="h-5 w-5" />
                <span className="absolute inset-0 animate-ping rounded-xl border border-primary-bright/50" />
              </>
            )}
          </div>
          <div className="min-w-0 flex-1">
            <div className="flex flex-wrap items-center gap-2">
              <h2 id="search-progress-title" className="text-lg font-semibold text-fg">
                {t(
                  failed
                    ? "search.progress.failedTitle"
                    : completed
                      ? "search.progress.doneTitle"
                      : "search.progress.title",
                )}
              </h2>
              <span className="rounded-full border border-border bg-surface/80 px-2.5 py-1 text-[11px] font-medium text-muted">
                {t("search.progress.run", { id: progress.run_id })}
              </span>
            </div>
            <p className="mt-1 truncate text-sm text-muted">
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
        </header>

        <div className="flex-1 overflow-y-auto">
          <section className="border-b border-border px-6 py-5">
            <div className="mb-2 flex items-end justify-between gap-4">
              <div>
                <p className="text-xs font-medium uppercase tracking-[0.14em] text-faint">
                  {t("search.progress.current")}
                </p>
                <p className="mt-1 text-sm font-medium text-fg">
                  {failed
                    ? progress.error || t("search.progress.failed")
                    : t(`search.progress.phase.${progress.phase}`)}
                </p>
              </div>
              <span className="text-2xl font-semibold tabular-nums text-primary">
                {progress.progress}%
              </span>
            </div>
            <div className="h-2 overflow-hidden rounded-full bg-surface-2">
              <div
                className={`h-full rounded-full transition-[width] duration-700 ${
                  failed
                    ? "bg-digital"
                    : "bg-gradient-to-r from-primary to-primary-bright"
                }`}
                style={{ width: `${progress.progress}%` }}
              />
            </div>
          </section>

          <section className="grid gap-6 px-6 py-5 lg:grid-cols-[1.25fr_0.75fr]">
            <div>
              <h3 className="text-sm font-semibold text-fg">
                {t("search.progress.pipeline")}
              </h3>
              <div className="mt-4 grid grid-cols-3 gap-2 sm:grid-cols-5">
                {PHASES.map((phase, index) => {
                  const Icon = phase.icon;
                  const active = phase.key === progress.phase && !failed && !completed;
                  const done = completed || index < currentIndex;
                  return (
                    <div
                      key={phase.key}
                      className={`relative rounded-xl border p-3 transition-colors ${
                        active
                          ? "border-primary/50 bg-primary/8"
                          : done
                            ? "border-primary/20 bg-primary/5"
                            : "border-border bg-surface-2/50"
                      }`}
                    >
                      <div
                        className={`flex h-7 w-7 items-center justify-center rounded-lg ${
                          active || done
                            ? "bg-primary text-white"
                            : "bg-surface text-faint"
                        }`}
                      >
                        {active ? (
                          <Loader2 className="h-3.5 w-3.5 animate-spin" />
                        ) : done ? (
                          <Check className="h-3.5 w-3.5" />
                        ) : (
                          <Icon className="h-3.5 w-3.5" />
                        )}
                      </div>
                      <p className="mt-2 text-[11px] font-medium leading-tight text-fg">
                        {t(`search.progress.phase.${phase.key}`)}
                      </p>
                    </div>
                  );
                })}
              </div>

              <h3 className="mt-6 text-sm font-semibold text-fg">
                {t("search.progress.liveLog")}
              </h3>
              <div className="mt-3 overflow-hidden rounded-xl border border-border bg-bg/70">
                {progress.events.slice(-6).map((event, index) => (
                  <div
                    key={event.id}
                    className={`flex gap-3 px-4 py-3 ${
                      index > 0 ? "border-t border-border" : ""
                    }`}
                  >
                    <span className="mt-1 h-2 w-2 shrink-0 rounded-full bg-primary" />
                    <div className="min-w-0 flex-1">
                      <p className="text-xs font-medium text-fg">
                        {t(`search.progress.phase.${event.phase}`)}
                      </p>
                      <p className="mt-0.5 text-[11px] text-faint">
                        {new Intl.DateTimeFormat(lang, {
                          hour: "2-digit",
                          minute: "2-digit",
                          second: "2-digit",
                        }).format(new Date(event.created_at))}
                      </p>
                    </div>
                    <span className="text-xs tabular-nums text-muted">
                      {event.progress}%
                    </span>
                  </div>
                ))}
              </div>
            </div>

            <aside className="space-y-4">
              <div className="rounded-xl border border-border bg-surface-2/60 p-4">
                <h3 className="text-sm font-semibold text-fg">
                  {t("search.progress.metrics")}
                </h3>
                <dl className="mt-3 space-y-3">
                  <Metric
                    label={t("search.progress.findings")}
                    value={numberValue(metrics.findings)}
                  />
                  <Metric
                    label={t("search.progress.corpus")}
                    value={numberValue(metrics.documents) || progress.n_documents}
                  />
                  <Metric
                    label={t("search.progress.newDocs")}
                    value={numberValue(metrics.new_documents)}
                    accent
                  />
                  <Metric
                    label={t("search.progress.carried")}
                    value={numberValue(metrics.carried_forward)}
                  />
                  <Metric
                    label={t("search.progress.topics")}
                    value={numberValue(metrics.topics) || progress.n_topics}
                  />
                </dl>
              </div>

              {diff && (
                <div className="rounded-xl border border-border bg-surface-2/60 p-4">
                  <h3 className="text-sm font-semibold text-fg">
                    {t("search.progress.portfolioResult")}
                  </h3>
                  <div className="mt-3 grid grid-cols-2 gap-2">
                    {(["new", "updated", "unchanged", "review"] as const).map(
                      (kind) => (
                        <div key={kind} className="rounded-lg bg-surface p-3">
                          <div className="text-xl font-semibold tabular-nums text-fg">
                            {diff.counts[kind] ?? 0}
                          </div>
                          <div className="text-[11px] text-muted">{t(`diff.${kind}`)}</div>
                        </div>
                      ),
                    )}
                  </div>
                </div>
              )}
            </aside>
          </section>
        </div>

        <footer className="flex flex-wrap items-center justify-between gap-3 border-t border-border bg-surface-2/50 px-6 py-4">
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
            {completed && (
              <Link
                href={`/runs/${progress.run_id}`}
                className="inline-flex items-center gap-2 rounded-lg bg-primary px-4 py-2 text-sm font-medium text-white hover:bg-primary-bright"
              >
                {t("search.progress.openResult")}
                <ExternalLink className="h-4 w-4" />
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
          <CheckCircle2 className="h-5 w-5 text-primary" />
        ) : (
          <XCircle className="h-5 w-5 text-digital" />
        )
      ) : (
        <Loader2 className="h-5 w-5 animate-spin text-primary" />
      )}
      <span className="text-left">
        <span className="block text-xs font-semibold text-fg">
          {t("search.progress.run", { id: progress.run_id })}
        </span>
        <span className="block text-[11px] text-muted">
          {t(`search.progress.phase.${progress.phase}`)} · {progress.progress}%
        </span>
      </span>
      <ChevronRight className="h-4 w-4 text-faint" />
    </button>
  );
}

function Metric({
  label,
  value,
  accent = false,
}: {
  label: string;
  value: number;
  accent?: boolean;
}) {
  return (
    <div className="flex items-center justify-between gap-3">
      <dt className="text-xs text-muted">{label}</dt>
      <dd
        className={`text-sm font-semibold tabular-nums ${
          accent ? "text-primary" : "text-fg"
        }`}
      >
        {value}
      </dd>
    </div>
  );
}

function numberValue(value: unknown): number {
  return typeof value === "number" ? value : 0;
}
