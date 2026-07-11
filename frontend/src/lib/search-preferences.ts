export type SearchRegion =
  | "global"
  | "europe"
  | "dach"
  | "north_america"
  | "asia_pacific"
  | "china";

export type ResearchDepth = "quick" | "standard" | "deep";
export type TopicGranularity = "compact" | "balanced" | "detailed";

export interface SearchPreferences {
  region: SearchRegion;
  depth: ResearchDepth;
  sources: string[];
  topicGranularity: TopicGranularity;
}

const STORAGE_KEY = "trendscout-search-preferences";

export const DEFAULT_SEARCH_PREFERENCES: SearchPreferences = {
  region: "global",
  depth: "standard",
  sources: [],
  topicGranularity: "balanced",
};

export function readSearchPreferences(): SearchPreferences {
  if (typeof window === "undefined") return DEFAULT_SEARCH_PREFERENCES;
  try {
    const value = JSON.parse(localStorage.getItem(STORAGE_KEY) ?? "{}");
    return {
      region: value.region ?? DEFAULT_SEARCH_PREFERENCES.region,
      depth: value.depth ?? DEFAULT_SEARCH_PREFERENCES.depth,
      sources: Array.isArray(value.sources) ? value.sources : [],
      topicGranularity:
        value.topicGranularity ?? DEFAULT_SEARCH_PREFERENCES.topicGranularity,
    };
  } catch {
    return DEFAULT_SEARCH_PREFERENCES;
  }
}

export function writeSearchPreferences(preferences: SearchPreferences) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(preferences));
}
