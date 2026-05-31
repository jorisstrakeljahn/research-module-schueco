// Typed client for the trendscout backend API.

export const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE ?? "http://127.0.0.1:8000";

export type Maturity =
  | "weak_signal"
  | "emerging"
  | "established"
  | "megatrend";

export interface Trend {
  id: number;
  run_id: number;
  title: string;
  summary: string;
  maturity: Maturity | null;
  keywords: string[];
  size: number;
  pestel: string[] | null;
  impact: number | null;
  uncertainty: number | null;
  radar_stage: string | null;
}

export interface Timepoint {
  period: string;
  doc_count: number;
}

export interface TrendDetail extends Trend {
  evidence: { title: string; url: string | null }[];
  timeseries: Timepoint[];
}

export interface Run {
  id: number;
  status: string;
  started_at: string;
  finished_at: string | null;
  n_documents: number;
  n_topics: number;
  embedder: string | null;
  topic_model: string | null;
  describer: string | null;
}

async function getJSON<T>(path: string): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, { cache: "no-store" });
  if (!res.ok) throw new Error(`API ${path} failed: ${res.status}`);
  return res.json() as Promise<T>;
}

export function fetchTrends(maturity?: string): Promise<Trend[]> {
  const q = maturity ? `?maturity=${encodeURIComponent(maturity)}` : "";
  return getJSON<Trend[]>(`/trends${q}`);
}

export function fetchTrend(id: number): Promise<TrendDetail> {
  return getJSON<TrendDetail>(`/trends/${id}`);
}

export function fetchRuns(): Promise<Run[]> {
  return getJSON<Run[]>(`/runs`);
}

export async function sendFeedback(
  trendId: number,
  body: {
    action: "confirm" | "correct" | "reject";
    field?: string;
    new_value?: string;
    comment?: string;
  },
): Promise<void> {
  const res = await fetch(`${API_BASE}/trends/${trendId}/feedback`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`Feedback failed: ${res.status}`);
}

export const MATURITY_META: Record<
  Maturity,
  { label: string; dot: string; text: string; order: number }
> = {
  weak_signal: { label: "Weak signal", dot: "bg-slate-400", text: "text-slate-600", order: 0 },
  emerging: { label: "Emerging", dot: "bg-amber-500", text: "text-amber-700", order: 1 },
  established: { label: "Established", dot: "bg-emerald-600", text: "text-emerald-700", order: 2 },
  megatrend: { label: "Megatrend", dot: "bg-violet-600", text: "text-violet-700", order: 3 },
};

export const MATURITY_ORDER: Maturity[] = [
  "weak_signal",
  "emerging",
  "established",
  "megatrend",
];
