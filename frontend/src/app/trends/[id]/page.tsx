"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";

import {
  fetchTrend,
  MATURITY_META,
  sendFeedback,
  type Maturity,
  type Timepoint,
  type TrendDetail,
} from "@/lib/api";

export default function TrendDetailPage() {
  const params = useParams<{ id: string }>();
  const trendId = Number(params.id);
  const [trend, setTrend] = useState<TrendDetail | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchTrend(trendId)
      .then(setTrend)
      .catch((e) => setError(String(e)));
  }, [trendId]);

  if (error) return <p className="text-sm text-red-600">{error}</p>;
  if (!trend) return <p className="text-sm text-slate-400">Loading…</p>;

  const meta = trend.maturity ? MATURITY_META[trend.maturity] : null;

  return (
    <article className="mx-auto max-w-3xl">
      <Link
        href="/"
        className="text-[13px] text-slate-400 transition-colors hover:text-slate-700"
      >
        ← Trendradar
      </Link>

      <h1 className="mt-3 text-2xl font-semibold leading-tight tracking-tight text-slate-900">
        {trend.title}
      </h1>

      <div className="mt-2 flex flex-wrap items-center gap-x-2 text-[13px] text-slate-500">
        {meta && (
          <span className={`inline-flex items-center gap-1.5 font-medium ${meta.text}`}>
            <span className={`h-1.5 w-1.5 rounded-full ${meta.dot}`} />
            {meta.label}
          </span>
        )}
        <span className="text-slate-300">·</span>
        <span>{trend.size} documents</span>
        {trend.keywords.length > 0 && (
          <>
            <span className="text-slate-300">·</span>
            <span className="text-slate-400">{trend.keywords.join(", ")}</span>
          </>
        )}
      </div>

      <Section title="Summary">
        <p className="text-[15px] leading-relaxed text-slate-700">
          {trend.summary}
        </p>
      </Section>

      <Section title="Activity over time" hint="documents per quarter">
        <TimeSeriesChart data={trend.timeseries} />
      </Section>

      <Section title={`Evidence · ${trend.evidence.length}`}>
        <ol className="space-y-2 text-[14px]">
          {trend.evidence.map((e, i) => (
            <li key={i} className="flex gap-2.5 leading-snug">
              <span className="w-5 shrink-0 text-right font-mono text-xs text-slate-400">
                {i + 1}
              </span>
              {e.url ? (
                <a
                  href={e.url}
                  target="_blank"
                  rel="noreferrer"
                  className="text-blue-700 hover:underline"
                >
                  {e.title}
                </a>
              ) : (
                <span className="text-slate-700">{e.title}</span>
              )}
            </li>
          ))}
        </ol>
      </Section>

      <FeedbackPanel trendId={trend.id} currentMaturity={trend.maturity} />
    </article>
  );
}

function Section({
  title,
  hint,
  children,
}: {
  title: string;
  hint?: string;
  children: React.ReactNode;
}) {
  return (
    <section className="mt-8 border-t border-slate-200 pt-5">
      <h2 className="mb-3 text-xs font-semibold uppercase tracking-wider text-slate-500">
        {title}
        {hint && (
          <span className="ml-2 font-normal normal-case tracking-normal text-slate-400">
            {hint}
          </span>
        )}
      </h2>
      {children}
    </section>
  );
}

function TimeSeriesChart({ data }: { data: Timepoint[] }) {
  if (data.length === 0)
    return <p className="text-sm text-slate-400">No dated documents.</p>;
  const max = Math.max(...data.map((d) => d.doc_count));
  return (
    <div className="flex items-end gap-1.5 overflow-x-auto border-b border-slate-200 pb-0">
      {data.map((d) => (
        <div key={d.period} className="flex flex-col items-center gap-1">
          <span className="text-[10px] tabular-nums text-slate-400">
            {d.doc_count}
          </span>
          <div
            className="w-7 rounded-t-sm bg-blue-500/85"
            style={{ height: `${(d.doc_count / max) * 110 + 3}px` }}
            title={`${d.period}: ${d.doc_count} documents`}
          />
          <span className="mt-0.5 whitespace-nowrap text-[10px] tabular-nums text-slate-400">
            {d.period}
          </span>
        </div>
      ))}
    </div>
  );
}

function FeedbackPanel({
  trendId,
  currentMaturity,
}: {
  trendId: number;
  currentMaturity: Maturity | null;
}) {
  const [status, setStatus] = useState<string | null>(null);
  const [newMaturity, setNewMaturity] = useState<string>("");
  const [comment, setComment] = useState("");

  async function confirm() {
    try {
      await sendFeedback(trendId, { action: "confirm", comment });
      setStatus("Confirmed. Thank you!");
    } catch (e) {
      setStatus(String(e));
    }
  }

  async function correct() {
    try {
      await sendFeedback(trendId, {
        action: "correct",
        field: "maturity",
        new_value: newMaturity || undefined,
        comment,
      });
      setStatus("Correction saved. Thank you!");
    } catch (e) {
      setStatus(String(e));
    }
  }

  async function reject() {
    try {
      await sendFeedback(trendId, { action: "reject", comment });
      setStatus("Rejected. This topic will be down-weighted next run.");
    } catch (e) {
      setStatus(String(e));
    }
  }

  return (
    <section className="mt-8 border-t border-slate-200 pt-5">
      <h2 className="mb-3 text-xs font-semibold uppercase tracking-wider text-slate-500">
        Expert review
        <span className="ml-2 font-normal normal-case tracking-normal text-slate-400">
          human-in-the-loop
        </span>
      </h2>
      <div className="flex flex-wrap items-center gap-2 text-sm">
        <button
          onClick={confirm}
          className="rounded-md bg-emerald-600 px-3 py-1.5 font-medium text-white transition-colors hover:bg-emerald-700"
        >
          Confirm
        </button>
        <button
          onClick={reject}
          className="rounded-md border border-slate-300 px-3 py-1.5 font-medium text-slate-700 transition-colors hover:border-red-300 hover:bg-red-50 hover:text-red-700"
        >
          Reject
        </button>
        <span className="ml-1 text-slate-400">reclassify</span>
        <select
          value={newMaturity}
          onChange={(e) => setNewMaturity(e.target.value)}
          className="rounded-md border border-slate-300 px-2 py-1.5 text-slate-700"
        >
          <option value="">
            {currentMaturity ? `current: ${currentMaturity}` : "select…"}
          </option>
          <option value="weak_signal">weak_signal</option>
          <option value="emerging">emerging</option>
          <option value="established">established</option>
          <option value="megatrend">megatrend</option>
        </select>
        <button
          onClick={correct}
          className="rounded-md border border-slate-300 px-3 py-1.5 font-medium text-slate-700 transition-colors hover:bg-slate-50"
        >
          Save
        </button>
      </div>
      <input
        value={comment}
        onChange={(e) => setComment(e.target.value)}
        placeholder="Optional comment…"
        className="mt-3 w-full max-w-md rounded-md border border-slate-300 px-3 py-1.5 text-sm placeholder:text-slate-400 focus:border-slate-400 focus:outline-none"
      />
      {status && <p className="mt-2 text-sm text-emerald-700">{status}</p>}
    </section>
  );
}
