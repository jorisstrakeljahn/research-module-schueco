"use client";

import { BrainCircuit, Check, Database, ShieldCheck } from "lucide-react";
import { useEffect, useState } from "react";
import { toast } from "sonner";

import PageHeader from "@/components/PageHeader";
import {
  fetchSearchCapabilities,
  type SearchCapabilities,
} from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import {
  DEFAULT_SEARCH_PREFERENCES,
  readSearchPreferences,
  writeSearchPreferences,
  type ResearchDepth,
  type SearchPreferences,
  type SearchRegion,
  type TopicGranularity,
} from "@/lib/search-preferences";

const REGIONS: SearchRegion[] = [
  "global",
  "europe",
  "dach",
  "north_america",
  "asia_pacific",
  "china",
];
const DEPTHS: ResearchDepth[] = ["quick", "standard", "deep"];
const GRANULARITIES: TopicGranularity[] = ["compact", "balanced", "detailed"];

export default function SettingsPage() {
  const { t } = useI18n();
  const [preferences, setPreferences] = useState<SearchPreferences>(
    DEFAULT_SEARCH_PREFERENCES,
  );
  const [capabilities, setCapabilities] = useState<SearchCapabilities | null>(null);

  useEffect(() => {
    async function loadSettings() {
      const stored = readSearchPreferences();
      try {
        const data = await fetchSearchCapabilities();
        setCapabilities(data);
        const enabled = new Set(data.sources.filter((source) => source.enabled).map((source) => source.id));
        const sources = stored.sources.filter((source) => enabled.has(source));
        const normalized = {
          ...stored,
          sources: sources.length > 0 ? sources : data.default_sources,
        };
        setPreferences(normalized);
        writeSearchPreferences(normalized);
      } catch {
        setPreferences(stored);
      }
    }
    loadSettings();
  }, []);

  function save() {
    writeSearchPreferences(preferences);
    toast.success(t("settings.saved"));
  }

  return (
    <div className="flex h-full min-w-0 flex-col overflow-hidden">
      <PageHeader title={t("settings.title")} subtitle={t("settings.subtitle")} />
      <div className="flex-1 overflow-auto p-6">
        <div className="mx-auto max-w-4xl space-y-6">
          <section className="rounded-xl border border-border bg-surface p-6 shadow-sm">
            <div className="flex items-start gap-3">
              <Database className="mt-0.5 h-5 w-5 text-primary" />
              <div>
                <h2 className="font-semibold text-fg">{t("settings.searchDefaults")}</h2>
                <p className="mt-1 text-sm text-muted">{t("settings.searchDefaultsHint")}</p>
              </div>
            </div>

            <div className="mt-6 grid gap-5 md:grid-cols-2">
              <label className="grid gap-2">
                <span className="text-sm font-medium text-fg">{t("search.region")}</span>
                <select
                  value={preferences.region}
                  onChange={(event) =>
                    setPreferences((current) => ({
                      ...current,
                      region: event.target.value as SearchRegion,
                    }))
                  }
                  className="h-11 rounded-lg border border-border bg-bg px-3 text-sm text-fg outline-none focus:border-primary"
                >
                  {REGIONS.map((region) => (
                    <option key={region} value={region}>
                      {t(`search.region.${region}`)}
                    </option>
                  ))}
                </select>
              </label>

              <div className="grid gap-2">
                <span className="text-sm font-medium text-fg">{t("search.depth")}</span>
                <div className="grid grid-cols-3 rounded-lg border border-border bg-bg p-1">
                  {DEPTHS.map((depth) => (
                    <button
                      key={depth}
                      type="button"
                      onClick={() =>
                        setPreferences((current) => ({ ...current, depth }))
                      }
                      className={`rounded-md px-3 py-2 text-xs font-medium ${
                        preferences.depth === depth
                          ? "bg-surface text-fg shadow-sm"
                          : "text-muted hover:text-fg"
                      }`}
                    >
                      {t(`search.depth.${depth}`)}
                    </button>
                  ))}
                </div>
                <p className="text-[11px] text-faint">
                  {t(`search.depthHint.${preferences.depth}`)}
                </p>
              </div>
            </div>

            <div className="mt-6">
              <h3 className="text-sm font-medium text-fg">{t("search.sources")}</h3>
              <p className="mt-1 text-xs text-muted">{t("settings.sourcesHint")}</p>
              <div className="mt-3 grid gap-3 sm:grid-cols-2">
                {capabilities?.sources.map((source) => (
                  <label
                    key={source.id}
                    className={`flex items-center justify-between rounded-lg border p-3 ${
                      source.enabled ? "border-border" : "border-border/60 bg-surface-2"
                    }`}
                  >
                    <span className="flex items-center gap-3">
                      <input
                        type="checkbox"
                        checked={preferences.sources.includes(source.id)}
                        disabled={
                          !source.enabled ||
                          (preferences.sources.includes(source.id) &&
                            preferences.sources.length === 1)
                        }
                        onChange={(event) =>
                          setPreferences((current) => ({
                            ...current,
                            sources: event.target.checked
                              ? [...current.sources, source.id]
                              : current.sources.filter((item) => item !== source.id),
                          }))
                        }
                        className="accent-primary"
                      />
                      <span className="text-sm text-fg">{t(`search.source.${source.id}`)}</span>
                    </span>
                    <span className={`text-[11px] ${source.enabled ? "text-primary" : "text-faint"}`}>
                      {source.enabled ? t("settings.available") : t("settings.notConfigured")}
                    </span>
                  </label>
                ))}
              </div>
            </div>

          </section>

          <section className="rounded-xl border border-border bg-surface p-6 shadow-sm">
            <div className="flex items-start gap-3">
              <BrainCircuit className="mt-0.5 h-5 w-5 text-primary" />
              <div className="min-w-0 flex-1">
                <div className="flex flex-wrap items-center gap-2">
                  <h2 className="font-semibold text-fg">{t("settings.model")}</h2>
                  <span className="rounded-full bg-primary/10 px-2 py-0.5 text-[11px] font-medium uppercase text-primary">
                    {capabilities?.topic_model ?? "BERTopic"}
                  </span>
                </div>
                <p className="mt-1 text-sm text-muted">{t("settings.modelHint")}</p>
              </div>
            </div>

            <div className="mt-6">
              <span className="text-sm font-medium text-fg">
                {t("settings.granularity")}
              </span>
              <div className="mt-2 grid grid-cols-3 rounded-lg border border-border bg-bg p-1">
                {GRANULARITIES.map((granularity) => (
                  <button
                    key={granularity}
                    type="button"
                    onClick={() =>
                      setPreferences((current) => ({
                        ...current,
                        topicGranularity: granularity,
                      }))
                    }
                    className={`rounded-md px-3 py-2 text-xs font-medium ${
                      preferences.topicGranularity === granularity
                        ? "bg-surface text-fg shadow-sm"
                        : "text-muted hover:text-fg"
                    }`}
                  >
                    {t(`settings.granularity.${granularity}`)}
                  </button>
                ))}
              </div>
              <p className="mt-2 text-xs leading-relaxed text-muted">
                {t(`settings.granularityHint.${preferences.topicGranularity}`)}
              </p>
            </div>
            <button
              type="button"
              onClick={save}
              className="mt-6 inline-flex items-center gap-2 rounded-lg bg-primary px-4 py-2.5 text-sm font-medium text-white hover:bg-primary-bright"
            >
              <Check className="h-4 w-4" />
              {t("settings.save")}
            </button>
          </section>

          <section className="rounded-xl border border-border bg-surface p-6 shadow-sm">
            <div className="flex items-start gap-3">
              <ShieldCheck className="mt-0.5 h-5 w-5 text-primary" />
              <div>
                <h2 className="font-semibold text-fg">{t("settings.security")}</h2>
                <p className="mt-1 text-sm leading-relaxed text-muted">
                  {t("settings.securityHint")}
                </p>
              </div>
            </div>
            {capabilities && (
              <dl className="mt-5 grid gap-3 sm:grid-cols-2">
                <StatusRow
                  label={t("settings.firecrawl")}
                  ready={capabilities.sources.some(
                    (source) => source.id === "firecrawl" && source.enabled,
                  )}
                />
                <StatusRow
                  label={t("settings.openai")}
                  ready={capabilities.openai_enrichment}
                />
              </dl>
            )}
          </section>
        </div>
      </div>
    </div>
  );
}

function StatusRow({ label, ready }: { label: string; ready: boolean }) {
  const { t } = useI18n();
  return (
    <div className="flex items-center justify-between rounded-lg bg-surface-2 px-4 py-3">
      <dt className="text-sm text-fg">{label}</dt>
      <dd className={`text-xs font-medium ${ready ? "text-primary" : "text-faint"}`}>
        {ready ? t("settings.ready") : t("settings.notConfigured")}
      </dd>
    </div>
  );
}
