"use client";

import { ArrowLeft, ArrowRight } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useMemo, useState } from "react";

import ChangeBadge from "@/components/ChangeBadge";
import PageHeader from "@/components/PageHeader";
import { fetchRunDiff, type RunDiff, type RunDiffKind } from "@/lib/api";
import { useI18n } from "@/lib/i18n";

const KINDS: RunDiffKind[] = ["new", "updated", "unchanged", "review"];

export default function RunDetailPage() {
  const { t, lang } = useI18n();
  const params = useParams<{ id: string }>();
  const runId = Number(params.id);
  const [diff, setDiff] = useState<RunDiff | null>(null);
  const [selected, setSelected] = useState<RunDiffKind | "all">("all");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchRunDiff(runId).then(setDiff).catch((e) => setError(String(e)));
  }, [runId]);

  const entries = useMemo(
    () =>
      diff?.entries.filter((entry) => selected === "all" || entry.change_type === selected) ??
      [],
    [diff, selected],
  );
  const title = diff
    ? t("runDetail.title", {
        date: new Intl.DateTimeFormat(lang, {
          dateStyle: "long",
          timeStyle: "short",
        }).format(new Date(diff.started_at)),
      })
    : t("runDetail.pendingTitle");

  return (
    <div className="flex h-full min-w-0 flex-col overflow-hidden">
      <PageHeader title={title} subtitle={diff?.query || t("runDetail.subtitle")} />
      <div className="flex-1 overflow-auto p-6">
        <div className="mx-auto max-w-6xl space-y-6">
          <Link href="/runs" className="inline-flex items-center gap-2 text-sm text-muted hover:text-fg">
            <ArrowLeft className="h-4 w-4" /> {t("runDetail.back")}
          </Link>

          {error ? (
            <p className="text-sm text-digital">{error}</p>
          ) : !diff ? (
            <p className="text-sm text-muted">{t("runDetail.loading")}</p>
          ) : (
            <>
              <section className="rounded-xl border border-border bg-surface p-5 shadow-sm">
                <h2 className="text-sm font-semibold text-fg">{t("runDetail.funnel")}</h2>
                <div className="mt-4 flex flex-col gap-2 md:flex-row md:items-center">
                  {KINDS.map((kind, index) => (
                    <div key={kind} className="contents">
                      <button
                        onClick={() => setSelected(kind)}
                        className={`min-w-0 flex-1 rounded-lg border p-4 text-left transition-colors ${
                          selected === kind
                            ? "border-primary bg-primary/5"
                            : "border-border hover:bg-hover"
                        }`}
                      >
                        <ChangeBadge kind={kind} label={t(`diff.${kind}`)} />
                        <div className="mt-3 text-2xl font-semibold tabular-nums text-fg">
                          {diff.counts[kind] ?? 0}
                        </div>
                      </button>
                      {index < KINDS.length - 1 && (
                        <ArrowRight className="hidden h-4 w-4 shrink-0 text-faint md:block" />
                      )}
                    </div>
                  ))}
                </div>
              </section>

              <section className="overflow-hidden rounded-xl border border-border bg-surface shadow-sm">
                <div className="flex items-center justify-between border-b border-border px-5 py-4">
                  <h2 className="font-semibold text-fg">{t("runDetail.changes")}</h2>
                  {selected !== "all" && (
                    <button onClick={() => setSelected("all")} className="text-xs text-primary">
                      {t("runDetail.showAll")}
                    </button>
                  )}
                </div>
                {entries.length === 0 ? (
                  <p className="p-6 text-sm text-muted">{t("runDetail.noChanges")}</p>
                ) : (
                  <div className="divide-y divide-border">
                    {entries.map((entry) => (
                      <div key={entry.occurrence_id} className="p-5">
                        <div className="flex flex-wrap items-start justify-between gap-3">
                          <div>
                            {entry.canonical_trend_id != null ? (
                              <Link
                                href={`/portfolio/${entry.canonical_trend_id}`}
                                className="font-medium text-fg hover:text-primary"
                              >
                                {entry.title}
                              </Link>
                            ) : (
                              <h3 className="font-medium text-fg">{entry.title}</h3>
                            )}
                            {entry.changed_fields.length > 0 && (
                              <p className="mt-1 text-xs text-muted">
                                {t("runDetail.fields")}: {entry.changed_fields.join(", ")}
                              </p>
                            )}
                          </div>
                          <div className="flex items-center gap-3">
                            {entry.match_score != null && (
                              <span className="text-xs tabular-nums text-faint">
                                {t("runDetail.match")} {(entry.match_score * 100).toFixed(0)}%
                              </span>
                            )}
                            <ChangeBadge
                              kind={entry.change_type}
                              label={t(`diff.${entry.change_type}`)}
                            />
                          </div>
                        </div>
                        {(entry.before || entry.after) && (
                          <div className="mt-4 grid gap-3 md:grid-cols-2">
                            <Snapshot label={t("runDetail.before")} value={entry.before} />
                            <Snapshot label={t("runDetail.after")} value={entry.after} />
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                )}
              </section>
            </>
          )}
        </div>
      </div>
    </div>
  );
}

function Snapshot({
  label,
  value,
}: {
  label: string;
  value: Record<string, unknown> | null | undefined;
}) {
  return (
    <div className="rounded-lg bg-surface-2 p-3">
      <p className="mb-2 text-[11px] font-semibold uppercase tracking-wide text-faint">{label}</p>
      <dl className="space-y-1 text-xs">
        {Object.entries(value ?? {}).map(([key, item]) => (
          <div key={key} className="flex gap-2">
            <dt className="text-muted">{key}</dt>
            <dd className="ml-auto max-w-[65%] truncate text-right text-fg">{String(item)}</dd>
          </div>
        ))}
      </dl>
    </div>
  );
}
