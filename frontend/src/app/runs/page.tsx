"use client";

import { ArrowRight, Clock3, Database, GitCompareArrows } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";

import PageHeader from "@/components/PageHeader";
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
      <div className="flex-1 overflow-auto p-6">
        <div className="mx-auto max-w-5xl">
          {error ? (
            <p className="text-sm text-digital">{error}</p>
          ) : runs.length === 0 ? (
            <p className="text-sm text-muted">{t("runs.empty")}</p>
          ) : (
            <div className="overflow-hidden rounded-xl border border-border bg-surface shadow-sm">
              {runs.map((run, index) => (
                <RunRow key={run.id} run={run} divided={index > 0} />
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function RunRow({ run, divided }: { run: Run; divided: boolean }) {
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
      className={`flex flex-wrap items-center gap-4 p-5 transition-colors hover:bg-hover ${
        divided ? "border-t border-border" : ""
      }`}
    >
      <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary/10 text-primary">
        <GitCompareArrows className="h-5 w-5" />
      </div>
      <div className="min-w-56 flex-1">
        <div className="flex items-center gap-2">
          <h2 className="font-semibold text-fg">{t("runs.run", { date })}</h2>
          <RunStatus status={run.status} />
          {mode && (
            <span className="rounded-full bg-hover px-2 py-0.5 text-[11px] font-medium text-muted">
              {t(`runs.mode.${mode}`)}
            </span>
          )}
        </div>
        {query && <p className="mt-1 line-clamp-1 text-sm text-fg">{query}</p>}
        {meta.length > 0 && <p className="mt-1 text-xs text-faint">{meta.join(" · ")}</p>}
      </div>
      <div className="grid gap-1.5 text-sm text-muted">
        <span className="flex items-center gap-2">
          <Database className="h-4 w-4" />
          {t("runs.metrics", { docs: run.n_documents, topics: run.n_topics })}
        </span>
        {run.finished_at && (
          <span className="flex items-center gap-2">
            <Clock3 className="h-4 w-4" />
            {t("runs.duration", {
              duration: formatDuration(run.started_at, run.finished_at),
            })}
          </span>
        )}
      </div>
      <ArrowRight className="h-4 w-4 text-faint" />
    </Link>
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

function RunStatus({ status }: { status: string }) {
  const { t } = useI18n();
  const success = status === "completed";
  const failed = status === "failed";
  return (
    <span
      className={`rounded-full px-2 py-0.5 text-[11px] font-medium ${
        success
          ? "bg-primary/12 text-primary"
          : failed
            ? "bg-digital/10 text-digital"
            : "bg-markets/15 text-markets"
      }`}
    >
      {t(`runs.status.${status}`)}
    </span>
  );
}
