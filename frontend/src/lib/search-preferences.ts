export type SearchRegion =
  | "global"
  | "europe"
  | "dach"
  | "north_america"
  | "asia_pacific"
  | "china";

export type ResearchDepth = "quick" | "standard" | "deep";

export interface SearchPreferences {
  region: SearchRegion;
  depth: ResearchDepth;
  sources: string[];
  /** Source ids that were available when the preferences were saved. Lets the UI
   * auto-enable sources that became available later (e.g. new API key). */
  knownSources?: string[];
}

const STORAGE_KEY = "trendscout-search-preferences-v2";
export const ALL_SEARCH_SOURCES = [
  "openalex",
  "arxiv",
  "firecrawl",
  "firecrawl_web",
] as const;

export const DEFAULT_SEARCH_PREFERENCES: SearchPreferences = {
  region: "global",
  depth: "deep",
  sources: [...ALL_SEARCH_SOURCES],
};

export function readSearchPreferences(): SearchPreferences {
  if (typeof window === "undefined") return DEFAULT_SEARCH_PREFERENCES;
  try {
    const value = JSON.parse(localStorage.getItem(STORAGE_KEY) ?? "{}");
    return {
      region: value.region ?? DEFAULT_SEARCH_PREFERENCES.region,
      depth: value.depth ?? DEFAULT_SEARCH_PREFERENCES.depth,
      sources: Array.isArray(value.sources)
        ? value.sources
        : DEFAULT_SEARCH_PREFERENCES.sources,
      knownSources: Array.isArray(value.knownSources)
        ? value.knownSources
        : undefined,
    };
  } catch {
    return DEFAULT_SEARCH_PREFERENCES;
  }
}

export function writeSearchPreferences(preferences: SearchPreferences) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(preferences));
}
