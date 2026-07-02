"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useSyncExternalStore,
} from "react";

export type Lang = "de" | "en";

const STORAGE_KEY = "trendscout-lang";

// Language is kept in localStorage and exposed through a tiny external store so
// it can be read with useSyncExternalStore. This is SSR-safe (server snapshot is
// always "de") and avoids calling setState inside an effect.
const langListeners = new Set<() => void>();

function readLang(): Lang {
  if (typeof localStorage === "undefined") return "de";
  return localStorage.getItem(STORAGE_KEY) === "en" ? "en" : "de";
}

function subscribeLang(callback: () => void): () => void {
  langListeners.add(callback);
  return () => langListeners.delete(callback);
}

function writeLang(next: Lang): void {
  try {
    localStorage.setItem(STORAGE_KEY, next);
  } catch {
    /* storage unavailable — ignore */
  }
  langListeners.forEach((l) => l());
}

type Dict = Record<string, string>;

// UI copy. Taxonomy proper nouns (PESTEL sector labels, thematic categories,
// radar stages Act/Prepare/Watch) stay constant across languages because Schüco
// uses them as fixed English labels on their own radar.
const messages: Record<Lang, Dict> = {
  de: {
    "nav.dashboard": "Dashboard",
    "nav.newsfeed": "Newsfeed",
    "nav.radar": "Radar",
    "brand.tagline": "AI Trend Scouting",
    "sidebar.collapse": "Einklappen",
    "sidebar.expand": "Ausklappen",

    "theme.label": "Darstellung",
    "theme.light": "Hell",
    "theme.dark": "Dunkel",
    "theme.system": "System",
    "lang.label": "Sprache",

    "maturity.megatrend": "Megatrends",
    "maturity.established": "Etablierte Trends",
    "maturity.emerging": "Aufkommende Trends",
    "maturity.weak_signal": "Schwache Signale",

    "dashboard.title": "Dashboard",
    "dashboard.subtitle": "Strategische Trendübersicht für Schüco",
    "dashboard.loading": "Lade Dashboard",
    "dashboard.apiError": "API nicht erreichbar.",
    "dashboard.kpi.total": "Identifizierte Trends",
    "dashboard.kpi.act": "Trends mit Handlungsbedarf",
    "dashboard.panel.maturity": "Trends nach Reifegrad",
    "dashboard.panel.pestel": "PESTEL-Verteilung",
    "dashboard.quick.newsfeedDesc":
      "Trends per Drag and Drop über die vier Reifegrade kuratieren",
    "dashboard.quick.radarDesc":
      "Trends nach Sektor und Dringlichkeit visualisieren",
    "dashboard.open": "Öffnen",
    "dashboard.runMeta": "Letzter Lauf {id}",
    "dashboard.runStats": "{docs} Dokumente, {topics} Themen",

    "search.title": "KI-gestützte Trendidentifikation",
    "search.subtitle": "Keywords eingeben und einen Analyse-Lauf starten",
    "search.placeholder": "Keyword eingeben und Enter drücken",
    "search.button": "Trends identifizieren",
    "search.running": "Lauf wird gestartet",
    "search.modeDeep": "Tiefenrecherche",
    "search.modeSimple": "Schnell",
    "search.modeDeepHint": "Mehrere Quellen, iterative Recherche (langsamer)",
    "search.modeSimpleHint": "Einmalige Suche über alle Quellen (schnell)",
    "search.toastStartTitle": "Analyse-Lauf gestartet",
    "search.toastStartDesc": "Quelle: {query}",
    "search.toastErrorTitle": "Lauf konnte nicht gestartet werden",
    "search.toastDoneTitle": "Neue Trends verfügbar",
    "search.toastDoneDesc": "{topics} Themen aus {docs} Dokumenten",
    "search.toastFailedTitle": "Analyse-Lauf fehlgeschlagen",
    "search.toastTimeout":
      "Der Lauf dauert länger als erwartet – er läuft im Hintergrund weiter.",

    "newsfeed.title": "Newsfeed",
    "newsfeed.subtitle":
      "Reifegrad per Drag and Drop korrigieren, fließt als Experten-Feedback zurück",
    "newsfeed.loading": "Lade Trends",
    "newsfeed.count": "{n} Trends",
    "newsfeed.toastReclass": "Reifegrad korrigiert",
    "newsfeed.toastReclassDesc": "{title}: {label}",
    "newsfeed.toastSaveError": "Konnte nicht speichern",

    "radar.title": "Radar",
    "radar.subtitle": "Trends nach Sektor, Dringlichkeit und Kategorie",
    "radar.loading": "Lade Radar",
    "radar.empty": "Noch keine Trends. Starte einen Lauf über das Dashboard.",
    "radar.legend.category": "Kategorie",
    "radar.legend.ring": "Ring",
    "radar.ring.act": "Act",
    "radar.ring.actDesc": "hoher Impact, dringend",
    "radar.ring.prepare": "Prepare",
    "radar.ring.prepareDesc": "relevant, vorbereiten",
    "radar.ring.watch": "Watch",
    "radar.ring.watchDesc": "vorerst beobachten",
    "radar.legend.size": "Punktgröße zeigt den Korpusanteil",

    "filter.title": "Filter",
    "filter.maturity": "Reifegrad",
    "filter.pestel": "PESTEL",
    "filter.resetPestel": "Zurücksetzen",
    "filter.region": "Region",
    "filter.regionAll": "Alle",
    "filter.show": "Filter einblenden",
    "filter.hide": "Filter ausblenden",

    "card.docs": "{n} Dokumente",

    "detail.back": "Zurück zum Radar",
    "detail.backNewsfeed": "Zurück zum Newsfeed",
    "detail.backRadar": "Zurück zum Radar",
    "detail.backDashboard": "Zurück zum Dashboard",
    "detail.translate": "Übersetzen",
    "detail.translating": "Übersetze…",
    "detail.showOriginal": "Original anzeigen",
    "detail.translated": "KI-übersetzt",
    "detail.loading": "Lade",
    "detail.docs": "{n} Dokumente",
    "detail.emergenceLabelShort": "Emergence",
    "detail.emergenceTip":
      "Semantische Neuheit gegenüber dem Vorlauf, 0 bedeutet Fortsetzung, 1 bedeutet neu",
    "detail.section.summary": "Zusammenfassung",
    "detail.section.assessment": "Strategische Bewertung",
    "detail.section.activity": "Aktivität über Zeit",
    "detail.section.evidence": "Evidenz",
    "detail.noDated": "Keine datierten Dokumente.",
    "detail.fullDetails": "Vollständige Details",
    "detail.pestelSectors": "PESTEL-Sektoren",
    "detail.emergenceLabel": "Emergence",
    "detail.keywords": "Keywords",
    "detail.panelTitle": "Trend-Details",

    "feedback.title": "Experten-Review",
    "feedback.confirm": "Bestätigen",
    "feedback.reject": "Ablehnen",
    "feedback.save": "Speichern",
    "feedback.reclassify": "Umklassifizieren",
    "feedback.select": "wählen",
    "feedback.current": "aktuell: {v}",
    "feedback.comment": "Optionaler Kommentar",
    "feedback.toastConfirm": "Bestätigt, danke!",
    "feedback.toastReject": "Abgelehnt, wird im nächsten Lauf abgewertet",
    "feedback.toastCorrect": "Korrektur gespeichert, danke!",
    "feedback.toastError": "Feedback fehlgeschlagen",
  },
  en: {
    "nav.dashboard": "Dashboard",
    "nav.newsfeed": "Newsfeed",
    "nav.radar": "Radar",
    "brand.tagline": "AI Trend Scouting",
    "sidebar.collapse": "Collapse",
    "sidebar.expand": "Expand",

    "theme.label": "Appearance",
    "theme.light": "Light",
    "theme.dark": "Dark",
    "theme.system": "System",
    "lang.label": "Language",

    "maturity.megatrend": "Megatrends",
    "maturity.established": "Established Trends",
    "maturity.emerging": "Emerging Trends",
    "maturity.weak_signal": "Weak Signals",

    "dashboard.title": "Dashboard",
    "dashboard.subtitle": "Strategic trend overview for Schüco",
    "dashboard.loading": "Loading dashboard",
    "dashboard.apiError": "API not reachable.",
    "dashboard.kpi.total": "Identified trends",
    "dashboard.kpi.act": "Trends needing action",
    "dashboard.panel.maturity": "Trends by maturity",
    "dashboard.panel.pestel": "PESTEL distribution",
    "dashboard.quick.newsfeedDesc":
      "Curate trends across the four maturity stages via drag and drop",
    "dashboard.quick.radarDesc": "Visualise trends by sector and urgency",
    "dashboard.open": "Open",
    "dashboard.runMeta": "Latest run {id}",
    "dashboard.runStats": "{docs} documents, {topics} topics",

    "search.title": "AI-assisted trend identification",
    "search.subtitle": "Enter keywords and start an analysis run",
    "search.placeholder": "Enter keyword and press Enter",
    "search.button": "Identify trends",
    "search.running": "Starting run",
    "search.modeDeep": "Deep research",
    "search.modeSimple": "Quick",
    "search.modeDeepHint": "Multiple sources, iterative crawl (slower)",
    "search.modeSimpleHint": "Single search across all sources (fast)",
    "search.toastStartTitle": "Analysis run started",
    "search.toastStartDesc": "Source: {query}",
    "search.toastErrorTitle": "Could not start run",
    "search.toastDoneTitle": "New trends available",
    "search.toastDoneDesc": "{topics} topics from {docs} documents",
    "search.toastFailedTitle": "Analysis run failed",
    "search.toastTimeout":
      "The run is taking longer than expected — it continues in the background.",

    "newsfeed.title": "Newsfeed",
    "newsfeed.subtitle":
      "Correct maturity via drag and drop, flows back as expert feedback",
    "newsfeed.loading": "Loading trends",
    "newsfeed.count": "{n} trends",
    "newsfeed.toastReclass": "Maturity corrected",
    "newsfeed.toastReclassDesc": "{title}: {label}",
    "newsfeed.toastSaveError": "Could not save",

    "radar.title": "Radar",
    "radar.subtitle": "Trends by sector, urgency and category",
    "radar.loading": "Loading radar",
    "radar.empty": "No trends yet. Start a run from the dashboard.",
    "radar.legend.category": "Category",
    "radar.legend.ring": "Ring",
    "radar.ring.act": "Act",
    "radar.ring.actDesc": "high impact, urgent",
    "radar.ring.prepare": "Prepare",
    "radar.ring.prepareDesc": "relevant, get ready",
    "radar.ring.watch": "Watch",
    "radar.ring.watchDesc": "observe for now",
    "radar.legend.size": "Dot size shows the corpus share",

    "filter.title": "Filter",
    "filter.maturity": "Maturity",
    "filter.pestel": "PESTEL",
    "filter.resetPestel": "Reset",
    "filter.region": "Region",
    "filter.regionAll": "All",
    "filter.show": "Show filters",
    "filter.hide": "Hide filters",

    "card.docs": "{n} documents",

    "detail.back": "Back to radar",
    "detail.backNewsfeed": "Back to newsfeed",
    "detail.backRadar": "Back to radar",
    "detail.backDashboard": "Back to dashboard",
    "detail.translate": "Translate",
    "detail.translating": "Translating…",
    "detail.showOriginal": "Show original",
    "detail.translated": "AI-translated",
    "detail.loading": "Loading",
    "detail.docs": "{n} documents",
    "detail.emergenceLabelShort": "Emergence",
    "detail.emergenceTip":
      "Semantic novelty vs. prior runs, 0 means continuation, 1 means new",
    "detail.section.summary": "Summary",
    "detail.section.assessment": "Strategic assessment",
    "detail.section.activity": "Activity over time",
    "detail.section.evidence": "Evidence",
    "detail.noDated": "No dated documents.",
    "detail.fullDetails": "Full details",
    "detail.pestelSectors": "PESTEL sectors",
    "detail.emergenceLabel": "Emergence",
    "detail.keywords": "Keywords",
    "detail.panelTitle": "Trend details",

    "feedback.title": "Expert review",
    "feedback.confirm": "Confirm",
    "feedback.reject": "Reject",
    "feedback.save": "Save",
    "feedback.reclassify": "Reclassify",
    "feedback.select": "select",
    "feedback.current": "current: {v}",
    "feedback.comment": "Optional comment",
    "feedback.toastConfirm": "Confirmed, thanks!",
    "feedback.toastReject": "Rejected, will be down-weighted next run",
    "feedback.toastCorrect": "Correction saved, thanks!",
    "feedback.toastError": "Feedback failed",
  },
};

interface I18nContextValue {
  lang: Lang;
  setLang: (lang: Lang) => void;
  t: (key: string, vars?: Record<string, string | number>) => string;
}

const I18nContext = createContext<I18nContextValue | null>(null);

export function I18nProvider({ children }: { children: React.ReactNode }) {
  const lang = useSyncExternalStore(subscribeLang, readLang, () => "de" as Lang);

  useEffect(() => {
    document.documentElement.lang = lang;
  }, [lang]);

  const setLang = useCallback((next: Lang) => writeLang(next), []);

  const t = useCallback(
    (key: string, vars?: Record<string, string | number>) => {
      let out = messages[lang][key] ?? messages.en[key] ?? key;
      if (vars) {
        for (const [k, v] of Object.entries(vars)) {
          out = out.replace(new RegExp(`\\{${k}\\}`, "g"), String(v));
        }
      }
      return out;
    },
    [lang],
  );

  const value = useMemo(() => ({ lang, setLang, t }), [lang, setLang, t]);

  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>;
}

export function useI18n(): I18nContextValue {
  const ctx = useContext(I18nContext);
  if (!ctx) throw new Error("useI18n must be used within an I18nProvider");
  return ctx;
}
