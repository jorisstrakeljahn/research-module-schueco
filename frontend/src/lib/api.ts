// Typed client for the trendscout backend API.

export const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE ?? "http://127.0.0.1:8000";

const BFF_BASE = "/api/backend";

export type Maturity =
  | "weak_signal"
  | "emerging"
  | "established"
  | "megatrend";

export interface Trend {
  id: string | number;
  run_id: number | null;
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

export type PortfolioStatus =
  | "active"
  | "review"
  | "rejected"
  | "dormant"
  | "merged";

export interface PortfolioTrend extends Trend {
  status: PortfolioStatus;
  first_run_id: number | null;
  last_run_id: number | null;
  merged_into_id: string | number | null;
  occurrence_count?: number;
  updated_at?: string | null;
  /** Manual drag & drop sort position within the newsfeed column. */
  position?: number | null;
}

export interface TrendEvidence {
  title: string;
  url: string | null;
  source?: string | null;
  published_at?: string | null;
  run_id?: number | null;
}

export interface TrendDecision {
  id: string | number;
  action: "confirm" | "correct" | "reject" | "restore" | "link" | "create" | "merge";
  reviewer: string | null;
  reason: string | null;
  created_at: string;
  before?: Record<string, unknown> | null;
  after?: Record<string, unknown> | null;
}

export interface TrendHistoryPoint {
  run_id: number;
  occurred_at?: string | null;
  maturity: Maturity | null;
  impact: number | null;
  urgency: number | null;
  uncertainty: number | null;
  emergence: number | null;
  size?: number;
  change_type?: RunDiffKind;
}

export interface TrendHistory {
  trend_id: string | number;
  points: TrendHistoryPoint[];
  evidence: TrendEvidence[];
  decisions: TrendDecision[];
}

export interface PortfolioTrendDetail extends PortfolioTrend {
  rationale: string | null;
  evidence: TrendEvidence[];
  timeseries: Timepoint[];
}

export interface PestelDimensionAnalysis {
  dimension: string;
  relevance: number;
  matched_documents: number;
  total_documents: number;
  signal_terms: string[];
  evidence: TrendEvidence[];
}

export interface PestelAnalysis {
  trend_id: string;
  run_id: number;
  dimensions: PestelDimensionAnalysis[];
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
  params: Record<string, unknown> | null;
  error: string | null;
  change_counts: Partial<Record<RunDiffKind, number>>;
  review_counts: Partial<Record<ReviewStatus, number>>;
}

export interface RunProgressEvent {
  id: number;
  phase: string;
  progress: number;
  message: string;
  details: Record<string, unknown> | null;
  created_at: string;
}

export interface RunProgress {
  run_id: number;
  status: string;
  phase: string;
  progress: number;
  message: string;
  n_documents: number;
  n_topics: number;
  error: string | null;
  events: RunProgressEvent[];
}

export interface SearchSourceCapability {
  id: string;
  enabled: boolean;
  requires_configuration: boolean;
}

export interface SearchCapabilities {
  sources: SearchSourceCapability[];
  default_sources: string[];
  openai_enrichment: boolean;
  topic_model: string;
  max_documents: number;
}

export type RunDiffKind =
  | "new"
  | "classification_changed"
  | "content_changed"
  | "evidence_only"
  | "unchanged";

export type ReviewStatus = "pending" | "approved" | "rejected" | "not_required";

export interface ReviewReason {
  code: string;
  kind: "identity" | "classification" | string;
  field?: string;
  before?: unknown;
  after?: unknown;
}

export interface RunDiffEntry {
  occurrence_id: string | number;
  canonical_trend_id: string | number | null;
  trend_id?: string | number | null;
  title: string;
  change_type: RunDiffKind;
  match_score: number | null;
  margin: number | null;
  changed_fields: string[];
  review_status: ReviewStatus;
  review_reasons: ReviewReason[];
  evidence_added_count: number;
  evidence_removed_count: number;
  prevalence: number | null;
  before?: Record<string, unknown> | null;
  after?: Record<string, unknown> | null;
}

export interface RunDiff {
  run_id: number;
  started_at: string;
  query: string | null;
  counts: Record<RunDiffKind, number>;
  entries: RunDiffEntry[];
}

export interface ReviewQueueItem {
  occurrence_id: string | number;
  run_id: number;
  canonical_trend_id: string | number | null;
  title: string;
  summary: string;
  maturity: Maturity | null;
  match_score: number | null;
  margin: number | null;
  change_type: RunDiffKind;
  review_status: ReviewStatus;
  review_reasons: ReviewReason[];
  changed_fields: string[];
  evidence_added_count: number;
  evidence_removed_count: number;
  prevalence: number | null;
  reason: string | null;
  suggested_trend?: Pick<PortfolioTrend, "id" | "title" | "status"> | null;
  candidates?: Array<{
    id: string | number;
    title: string;
    score: number | null;
  }>;
}

export interface PortfolioDecisionInput {
  action: "confirm" | "correct" | "reject" | "restore" | "merge";
  reviewer: string;
  reason: string;
  changes?: Record<string, unknown>;
  target_trend_id?: string | number;
  idempotency_key?: string;
  /** UI language of manual edits, keeps the bilingual record in sync. */
  language?: ContentLang;
}

export interface ReviewDecisionInput {
  action: "confirm" | "correct" | "reject" | "link" | "create" | "merge";
  reviewer: string;
  reason: string;
  changes?: Record<string, unknown>;
  canonical_trend_id?: string | number;
  target_trend_id?: string | number;
  idempotency_key?: string;
  language?: ContentLang;
}

async function getJSON<T>(path: string): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, { cache: "no-store" });
  if (!res.ok) throw new Error(`API ${path} failed: ${res.status}`);
  return res.json() as Promise<T>;
}

function listFrom<T>(payload: T[] | { items?: T[]; trends?: T[]; runs?: T[] }): T[] {
  if (Array.isArray(payload)) return payload;
  return payload.items ?? payload.trends ?? payload.runs ?? [];
}

export type ContentLang = "de" | "en";

function query(params: Record<string, string | number | undefined>): string {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== "") search.set(key, String(value));
  }
  const s = search.toString();
  return s ? `?${s}` : "";
}

export function fetchTrends(maturity?: string, language?: ContentLang): Promise<Trend[]> {
  return getJSON<Trend[]>(`/trends${query({ maturity, language })}`);
}

export function fetchTrend(id: number, language?: ContentLang): Promise<TrendDetail> {
  return getJSON<TrendDetail>(`/trends/${id}${query({ language })}`);
}

export function fetchRuns(limit = 20): Promise<Run[]> {
  return getJSON<Run[] | { items?: Run[]; runs?: Run[] }>(`/runs?limit=${limit}`).then(
    listFrom,
  );
}

export function fetchSearchCapabilities(): Promise<SearchCapabilities> {
  return getJSON<SearchCapabilities>("/search/capabilities");
}

export function fetchPortfolioTrends(
  status = "active",
  language?: ContentLang,
): Promise<PortfolioTrend[]> {
  return getJSON<
    PortfolioTrend[] | { items?: PortfolioTrend[]; trends?: PortfolioTrend[] }
  >(`/portfolio/trends${query({ status, language })}`).then(listFrom);
}

export function fetchPortfolioTrend(
  id: string | number,
  language?: ContentLang,
): Promise<PortfolioTrendDetail> {
  return getJSON<PortfolioTrendDetail>(
    `/portfolio/trends/${encodeURIComponent(id)}${query({ language })}`,
  );
}

export function fetchPestelAnalysis(
  id: string | number,
  language?: ContentLang,
): Promise<PestelAnalysis> {
  return getJSON<PestelAnalysis>(
    `/portfolio/trends/${encodeURIComponent(id)}/pestel-analysis${query({ language })}`,
  );
}

export function fetchTrendHistory(id: string | number): Promise<TrendHistory> {
  return getJSON<TrendHistory>(
    `/portfolio/trends/${encodeURIComponent(id)}/history`,
  );
}

export function fetchRunDiff(id: number, language?: ContentLang): Promise<RunDiff> {
  return getJSON<RunDiff>(`/runs/${id}/diff${query({ language })}`);
}

export function fetchRunProgress(id: number): Promise<RunProgress> {
  return getJSON<RunProgress>(`/runs/${id}/progress`);
}

export function fetchReviewQueue(
  runId?: number,
  language?: ContentLang,
): Promise<ReviewQueueItem[]> {
  return getJSON<ReviewQueueItem[] | { items?: ReviewQueueItem[] }>(
    `/review-queue${query({ run_id: runId, language })}`,
  ).then(listFrom);
}

async function mutate<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`${BFF_BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const detail = await res.text();
    throw new Error(detail || `Mutation ${path} failed: ${res.status}`);
  }
  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

export type RunMode = "deep_research" | "simple";

export async function startRun(
  input: {
    query: string;
    keywords?: string[];
    language?: "de" | "en";
    mode?: RunMode;
    depth?: "quick" | "standard" | "deep";
    region?: string;
    sources?: string[];
  },
): Promise<{
  run_id: number;
  query: string;
  language: string;
  mode: RunMode;
  started_at: string;
}> {
  return mutate("/runs", {
    ...input,
    holistic_pestel: true,
  });
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
  return mutate(`/trends/${trendId}/translate`, { language });
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
  await mutate(`/trends/${trendId}/feedback`, body);
}

export function decidePortfolioTrend(
  trendId: string | number,
  body: PortfolioDecisionInput,
): Promise<TrendDecision> {
  return mutate(`/portfolio/trends/${encodeURIComponent(trendId)}/decisions`, {
    ...body,
    idempotency_key: body.idempotency_key ?? crypto.randomUUID(),
  });
}

export function updatePortfolioOrder(
  items: { id: string | number; position: number }[],
): Promise<{ updated: number }> {
  return mutate("/portfolio/order", { items });
}

export function decideReviewItem(
  occurrenceId: string | number,
  body: ReviewDecisionInput,
): Promise<TrendDecision> {
  return mutate(`/review-queue/${encodeURIComponent(occurrenceId)}/decision`, {
    ...body,
    idempotency_key: body.idempotency_key ?? crypto.randomUUID(),
  });
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
