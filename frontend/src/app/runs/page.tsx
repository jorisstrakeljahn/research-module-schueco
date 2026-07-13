"use client";

import { ClipboardCheck, Clock3, Database, Files, Sparkles } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";

import PageHeader from "@/components/PageHeader";
import RunStatus from "@/components/RunStatus";
import { fetchRuns, type Run } from "@/lib/api";
import { useI18n } from "@/lib/i18n";

export default function RunsPage() {
  const { t } = useI18n();
  const [runs, setRuns] = useState<Run[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchRuns(100).then(setRuns).catch((e) => setError(String(e)));
  }, []);

  return (
    <div className="flex h-full min-w-0 flex-col overflow-hidden">
      <PageHeader title={t("runs.title")} subtitle={t("runs.subtitle")} />
      <div className="flex-1 overflow-auto p-4 sm:p-6">
        <div className="mx-auto max-w-5xl">
          {error ? (
            <p className="text-sm text-digital">{error}</p>
          ) : runs.length === 0 ? (
            <p className="text-sm text-muted">{t("runs.empty")}</p>
          ) : (
            <div className="space-y-3">
              {runs.map((run) => (
                <RunRow key={run.id} run={run} />
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function RunRow({ run }: { run: Run }) {
  const { t, lang } = useI18n();
  const query = typeof run.params?.query === "string" ? run.params.query : null;
  const mode = typeof run.params?.mode === "string" ? run.params.mode : null;
  const sources = Array.isArray(run.params?.sources)
    ? run.params.sources.filter((source): source is string => typeof source === "string")
    : [];
  const date = new Intl.DateTimeFormat(lang, {
    dateStyle: "long",
    timeStyle: "short",
  }).format(new Date(run.started_at));
  const meta = [
    sources.length > 0 ? t("runs.source", { sources: sources.join(", ") }) : null,
    run.topic_model ? t("runs.model", { model: run.topic_model }) : null,
  ].filter(Boolean);
  return (
    <Link
      href={`/runs/${run.id}`}
      className="grid gap-4 rounded-xl border border-border bg-surface p-4 shadow-sm transition-colors hover:border-border-strong hover:bg-hover sm:grid-cols-[minmax(0,1fr)_auto] sm:items-center"
    >
      <div className="min-w-0">
        <div className="flex items-center gap-2">
          <h2 className="truncate font-semibold text-fg">{t("runs.run", { date })}</h2>
          <RunStatus status={run.status} />
          {mode && (
            <span className="rounded-full bg-hover px-2 py-0.5 text-[11px] font-medium text-muted">
              {t(`runs.mode.${mode}`)}
            </span>
          )}
        </div>
        {query && <p className="mt-1 line-clamp-1 text-sm text-fg">{query}</p>}
        <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-xs text-faint">
          <span className="flex items-center gap-1.5">
            <Database className="h-3.5 w-3.5" />
            {t("runs.metrics", { docs: run.n_documents, topics: run.n_topics })}
          </span>
          {run.finished_at && (
            <span className="flex items-center gap-1.5">
              <Clock3 className="h-3.5 w-3.5" />
              {t("runs.duration", {
                duration: formatDuration(run.started_at, run.finished_at),
              })}
            </span>
          )}
          {meta.length > 0 && <span>{meta.join(" · ")}</span>}
        </div>
      </div>
      <div className="grid grid-cols-3 gap-2 sm:w-80">
        <RunMetric
          icon={Sparkles}
          value={run.change_counts.new ?? 0}
          label={t("runs.newTrends")}
          accent="text-primary"
        />
        <RunMetric
          icon={Files}
          value={run.change_counts.evidence_only ?? 0}
          label={t("runs.newEvidence")}
          accent="text-markets"
        />
        <RunMetric
          icon={ClipboardCheck}
          value={run.review_counts.pending ?? 0}
          label={t("runs.openReviews")}
          accent="text-climate"
        />
      </div>
    </Link>
  );
}

function RunMetric({
  icon: Icon,
  value,
  label,
  accent,
}: {
  icon: typeof Sparkles;
  value: number;
  label: string;
  accent: string;
}) {
  return (
    <div className="rounded-lg bg-surface-2 px-2.5 py-2">
      <div className={`flex items-center gap-1.5 ${accent}`}>
        <Icon className="h-3.5 w-3.5" />
        <span className="font-semibold tabular-nums">{value}</span>
      </div>
      <p className="mt-0.5 truncate text-[10px] text-muted">{label}</p>
    </div>
  );
}

function formatDuration(startedAt: string, finishedAt: string) {
  const seconds = Math.max(
    0,
    Math.round((new Date(finishedAt).getTime() - new Date(startedAt).getTime()) / 1000),
  );
  if (seconds < 60) return `${seconds} s`;
  const minutes = Math.floor(seconds / 60);
  return `${minutes} min ${seconds % 60} s`;
}
