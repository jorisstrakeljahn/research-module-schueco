"use client";

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
      <PageHeader title={t("runs.title")} />
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
  const sources = Array.isArray(run.params?.sources)
    ? run.params.sources.filter((source): source is string => typeof source === "string")
    : [];
  const date = new Intl.DateTimeFormat(lang, {
    dateStyle: "long",
    timeStyle: "short",
  }).format(new Date(run.started_at));
  const pendingReviews = run.review_counts.pending ?? 0;
  return (
    <Link
      href={`/runs/${run.id}`}
      className="flex items-start justify-between gap-4 rounded-xl border border-border bg-surface p-4 shadow-sm transition-colors hover:border-border-strong hover:bg-hover"
    >
      <div className="min-w-0">
        <h2 className="truncate font-semibold text-fg">{t("runs.run", { date })}</h2>
        {query && <p className="mt-1 line-clamp-1 text-sm text-muted">{query}</p>}
        {sources.length > 0 && (
          <p className="mt-1 text-xs text-faint">
            {t("runs.source", { sources: sources.join(", ") })}
          </p>
        )}
      </div>
      {run.status === "completed" ? (
        pendingReviews > 0 && (
          <span className="shrink-0 rounded-full bg-pending/15 px-2.5 py-1 text-xs font-medium text-pending">
            {t("runs.todo")}
          </span>
        )
      ) : (
        <RunStatus status={run.status} />
      )}
    </Link>
  );
}
