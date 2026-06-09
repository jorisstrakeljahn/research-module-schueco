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
  emergence: number | null;
  keywords: string[];
  size: number;
  region: string | null;
  country: string | null;
  pestel: string[] | null;
  category: string | null;
  impact: number | null;
  urgency: number | null;
  uncertainty: number | null;
  radar_stage: string | null;
}

export interface Timepoint {
  period: string;
  doc_count: number;
}

export interface TrendDetail extends Trend {
  rationale: string | null;
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

export type RunMode = "deep_research" | "simple";

export async function startRun(
  keywords: string[],
  language: "de" | "en" = "en",
  mode: RunMode = "deep_research",
): Promise<{ query: string; language: string; mode: RunMode }> {
  const res = await fetch(`${API_BASE}/runs`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ keywords, language, mode }),
  });
  if (!res.ok) throw new Error(`Start run failed: ${res.status}`);
  return res.json();
}

export async function translateTrend(
  trendId: number,
  language: "de" | "en",
): Promise<{
  language: string;
  title: string;
  summary: string;
  rationale: string | null;
}> {
  const res = await fetch(`${API_BASE}/trends/${trendId}/translate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ language }),
  });
  if (!res.ok) throw new Error(`Translate failed: ${res.status}`);
  return res.json();
}

export async function sendFeedback(
  trendId: number,
  body: {
    action: "confirm" | "correct" | "reject";
    field?: string;
    old_value?: string;
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

// Maturity colours (Schüco green ramp, darkest = most mature). `color` is a hex
// for inline styles (bars, dots, radar). Human-readable labels are localised via
// i18n (`maturity.<key>`), so they are intentionally not stored here.
export const MATURITY_META: Record<Maturity, { color: string; order: number }> =
  {
    weak_signal: { color: "#8bb89d", order: 0 },
    emerging: { color: "#6b9a7a", order: 1 },
    established: { color: "#4d7c5e", order: 2 },
    megatrend: { color: "#00a651", order: 3 },
  };

// Newsfeed/dashboard order: most mature first (Megatrends → Weak Signals).
export const MATURITY_ORDER: Maturity[] = [
  "megatrend",
  "established",
  "emerging",
  "weak_signal",
];

// PESTEL dimensions mapped to Schüco's Trendradar sector labels (ADR-25).
// Order = clockwise sector order on the radar.
export const PESTEL_SECTORS: { key: string; label: string }[] = [
  { key: "environmental", label: "Environmental" },
  { key: "technological", label: "Technological" },
  { key: "social", label: "Societal" },
  { key: "legal", label: "Regulatory" },
  { key: "political", label: "Political" },
  { key: "economic", label: "Building Industry" },
];

// Schüco's thematic colour taxonomy (ADR-27).
export const CATEGORY_META: Record<string, { label: string; color: string }> = {
  climate: { label: "Climate", color: "#2BA8E0" },
  technology: { label: "Technology", color: "#7FC241" },
  digital: { label: "Digital", color: "#D0021B" },
  markets: { label: "Markets", color: "#F5A623" },
};

// Radar rings: Act (inner, most urgent) -> Prepare -> Watch (outer).
export const RADAR_STAGE_META: Record<
  string,
  { label: string; ring: number }
> = {
  act: { label: "Act", ring: 0 },
  prepare: { label: "Prepare", ring: 1 },
  watch: { label: "Watch", ring: 2 },
};
