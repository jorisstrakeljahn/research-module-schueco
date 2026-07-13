"""Trend assessment: PESTEL + category classification and impact/urgency scoring.

This is Teilziel 2 (automated PESTEL analysis) and the scoring half of Teilziel 3
(impact / urgency). Following the Schüco Trendradar, every trend gets:

* a **PESTEL** dimension set (the angular sectors of the radar),
* a thematic **category** (Climate / Technology / Digital / Markets - the colour),
* an **impact** and an **urgency** score on a 1-10 scale, from which the **radar
  stage** (Act / Prepare / Watch) is derived, and
* an **uncertainty** score for the separate impact/uncertainty grid.

Two pluggable implementations keep the offline-first principle: :class:`HeuristicClassifier`
is deterministic and free (lexicon overlap + signal heuristics); :class:`OpenAIClassifier`
uses an LLM with a fixed JSON schema, grounded in the retrieved evidence (ADR-12/13).
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Protocol

from app.llm import get_openai_client
from app.models import PESTEL_DIMENSIONS, TREND_CATEGORIES
from app.pipeline.timeseries import growth_ratio

# Lexicons for the offline, deterministic classifier. Deliberately small and
# domain-tuned; the LLM classifier is the scientific default for nuance.
_PESTEL_LEXICON: dict[str, set[str]] = {
    "political": {
        "policy", "policies", "government", "governmental", "subsidy", "subsidies",
        "tariff", "tariffs", "geopolitical", "geopolitics", "public", "funding",
        "incentive", "incentives", "sovereignty", "trade", "ministry", "municipal",
        "election", "sanction", "sanctions", "diplomacy", "federal", "parliament",
        "programme", "program", "initiative", "governance",
    },
    "economic": {
        "market", "markets", "cost", "costs", "investment", "investments", "price",
        "prices", "pricing", "demand", "supply", "economic", "economy", "business",
        "growth", "servitization", "productivity", "competition", "competitor",
        "financing", "finance", "capital", "revenue", "profitability", "inflation",
        "procurement", "export", "import", "industry", "manufacturer", "startup",
        "venture", "adoption", "commercialization", "commercialisation", "leasing",
    },
    "social": {
        "social", "society", "societal", "demographic", "demographics", "skills",
        "workforce", "user", "users", "health", "wellbeing", "well-being",
        "community", "labour", "labor", "talent", "people", "silver", "aging",
        "ageing", "occupant", "occupants", "tenant", "tenants", "resident",
        "residents", "comfort", "affordable", "affordability", "housing",
        "urbanization", "urbanisation", "migration", "lifestyle", "acceptance",
        "education", "craftsman", "shortage", "safety", "accessibility",
    },
    "technological": {
        "technology", "technologies", "digital", "sensor", "sensors", "automation",
        "software", "innovation", "smart", "platform", "robotic", "robotics",
        "data", "twin", "modular", "prefabrication", "ai", "algorithm",
        "machine", "learning", "iot", "bim", "printing", "additive", "coating",
        "nanotechnology", "photovoltaic", "photovoltaics", "electrochromic",
        "aerogel", "prototype", "patent", "material", "materials", "glazing",
        "actuator", "interoperability", "cyber",
    },
    "environmental": {
        "climate", "carbon", "sustainability", "sustainable", "energy", "emission",
        "emissions", "circular", "circularity", "green", "environmental",
        "decarbonization", "decarbonisation", "resilience", "renewable",
        "renewables", "recycling", "recycled", "embodied", "biodiversity",
        "pollution", "waste", "warming", "adaptation", "mitigation", "heatwave",
        "cradle", "lifecycle", "life-cycle", "ecological", "solar", "geothermal",
    },
    "legal": {
        "legal", "law", "laws", "compliance", "standard", "standards", "directive",
        "directives", "epbd", "certification", "certified", "regulation",
        "regulations", "regulatory", "norm", "norms", "mandate", "mandatory",
        "liability", "warranty", "code", "codes", "taxonomy", "disclosure",
        "audit", "gdpr", "din", "iso", "ce", "permit", "permits", "zoning",
    },
}

_CATEGORY_LEXICON: dict[str, set[str]] = {
    "climate": {
        "climate", "carbon", "decarbonization", "decarbonisation", "sustainability",
        "energy", "emission", "green", "resilience", "circular", "circularity",
        "renewable", "regenerative",
    },
    "technology": {
        "material", "materials", "sensor", "facade", "envelope", "building",
        "photovoltaic", "bipv", "glass", "construction", "insulation", "skin",
    },
    "digital": {
        "ai", "digital", "software", "automation", "autonomous", "data", "platform",
        "iot", "twin", "computing", "algorithm",
    },
    "markets": {
        "market", "markets", "servitization", "business", "renovation", "retrofit",
        "investment", "skills", "industrialization", "industrialisation", "service",
    },
}

_MATURITY_IMPACT = {
    "weak_signal": 3.0,
    "emerging": 5.5,
    "established": 7.0,
    "megatrend": 9.0,
}


@dataclass
class TrendSignal:
    """Everything the classifier needs about one trend (source-agnostic)."""

    keywords: list[str]
    title: str
    summary: str = ""
    maturity: str | None = None
    emergence: float | None = None
    size: int = 0
    n_sources: int = 1
    timepoints: dict[str, int] = field(default_factory=dict)
    evidence: list[dict] = field(default_factory=list)
    language: str = "en"  # language for the human-readable rationale


@dataclass
class Classification:
    pestel: list[str]
    category: str
    impact: float
    urgency: float
    uncertainty: float
    rationale: str = ""


def _clamp(value: float, low: float = 1.0, high: float = 10.0) -> float:
    return float(max(low, min(high, value)))


def radar_stage(impact: float, urgency: float) -> str:
    """Map impact x urgency (1-10) onto the Schüco radar rings (Folie 23).

    Act = high impact *and* pressing; Prepare = clearly relevant on one axis;
    Watch = everything else (monitor for now).
    """
    if impact >= 7.0 and urgency >= 6.0:
        return "act"
    if impact >= 5.5 or urgency >= 6.5:
        return "prepare"
    return "watch"


def _growth(timepoints: dict[str, int]) -> float:
    """Recent-vs-older growth ratio of a topic's quarterly counts, clamped at 0.

    Wraps the shared :func:`app.pipeline.timeseries.growth_ratio`, preserving this
    call site's two extra guarantees: 0.0 for fewer than two periods, and no
    negative values (urgency must not be penalised by a shrinking topic here).
    """
    if len(timepoints) < 2:
        return 0.0
    return max(0.0, growth_ratio(timepoints))


class TrendClassifier(Protocol):
    def classify(self, signal: TrendSignal) -> Classification:
        ...


class HeuristicClassifier:
    """Deterministic, offline classifier: lexicon overlap + signal heuristics."""

    def _tokens(self, signal: TrendSignal) -> list[str]:
        evidence = " ".join(
            str(item.get("title") or "") for item in signal.evidence[:12]
        )
        text = " ".join(signal.keywords) + " " + signal.title + " " + signal.summary
        return re.findall(r"[a-z0-9äöüß-]+", f"{text} {evidence}".lower())

    def _pestel(self, tokens: set[str], category: str) -> list[str]:
        scored = {
            dim: len(tokens & terms) for dim, terms in _PESTEL_LEXICON.items()
        }
        highest = max(scored.values(), default=0)
        if highest > 0:
            threshold = max(1, round(highest * 0.45))
            return [
                dimension
                for dimension, score in sorted(
                    scored.items(), key=lambda item: (-item[1], item[0])
                )
                if score >= threshold
            ][:3]
        return {
            "climate": ["environmental"],
            "markets": ["economic"],
            "digital": ["technological"],
            "technology": ["technological"],
        }[category]

    def _category(self, tokens: set[str]) -> str:
        scored = {
            cat: len(tokens & terms) for cat, terms in _CATEGORY_LEXICON.items()
        }
        best = max(scored.items(), key=lambda x: x[1])
        return best[0] if best[1] > 0 else "technology"

    def classify(self, signal: TrendSignal) -> Classification:
        tokens = set(self._tokens(signal))
        category = self._category(tokens)
        pestel = self._pestel(tokens, category)

        # Impact: anchored on maturity, lifted a little by corpus weight (size).
        impact = _MATURITY_IMPACT.get(signal.maturity or "", 5.0)
        impact += min(2.0, signal.size / 10.0)

        # Urgency: driven by recent growth and novelty (emergence).
        growth = _growth(signal.timepoints)
        urgency = 4.0 + min(4.0, growth * 4.0)
        if signal.emergence is not None:
            urgency += signal.emergence * 2.0

        # Uncertainty: high when few/undiverse sources or the topic is novel.
        uncertainty = 6.0 - min(3.0, signal.n_sources)
        if signal.emergence is not None:
            uncertainty += signal.emergence * 3.0

        impact, urgency, uncertainty = (
            _clamp(impact), _clamp(urgency), _clamp(uncertainty)
        )
        rationale = (
            f"Heuristic: maturity={signal.maturity}, size={signal.size}, "
            f"sources={signal.n_sources}, growth={growth:.2f}."
        )
        return Classification(
            pestel=pestel,
            category=category,
            impact=impact,
            urgency=urgency,
            uncertainty=uncertainty,
            rationale=rationale,
        )


class OpenAIClassifier:
    """LLM classifier with a fixed JSON schema, grounded in retrieved evidence.

    Requires the ``llm`` extra and an API key (ADR-13). The label sets are constrained
    to the canonical PESTEL dimensions and Schüco categories so the output stays usable.
    """

    def __init__(self, model_name: str = "gpt-4o-mini") -> None:
        self._client = get_openai_client()
        self._model_name = model_name
        self._fallback = HeuristicClassifier()

    def classify(self, signal: TrendSignal) -> Classification:
        context = "\n".join(
            f"- {e.get('title', '')}" for e in signal.evidence[:8] if e.get("title")
        )
        rationale_lang = {"de": "German", "en": "English"}.get(
            signal.language, "English"
        )
        prompt = (
            "You are a senior corporate-foresight analyst at Schüco, a manufacturer "
            "of window, door and facade systems. Classify the trend below for the "
            "company trend radar, using ONLY the evidence given.\n\n"
            f"Title: {signal.title}\n"
            f"Keywords: {', '.join(signal.keywords)}\n"
            f"Summary: {signal.summary}\n"
            f"Evidence (document titles):\n{context}\n\n"
            "Step 1 - PESTEL: decide which perspective DRIVES this trend, i.e. what "
            "kind of force is causing the change:\n"
            "- political: government programs, subsidies, geopolitics, public funding\n"
            "- economic: markets, costs, investment, demand, business models, supply chains\n"
            "- social: demographics, workforce and skills, health, user behaviour, housing needs\n"
            "- technological: new technical capabilities, materials, digitalization, automation\n"
            "- environmental: climate change, emissions, energy transition, circularity\n"
            "- legal: laws, directives (e.g. EPBD), standards, certification, compliance\n"
            "Ordering rules - almost every building-sector trend LOOKS technological "
            "because the artifact is technical, so rank by the force that would make "
            "the trend stall if it disappeared:\n"
            "- If the evidence cites a directive, standard or certification scheme "
            "as the reason for adoption, rank legal (or political for funding "
            "programs) BEFORE technological.\n"
            "- If the evidence is about costs, market growth, business models or "
            "supply chains, rank economic first.\n"
            "- If it addresses occupant comfort, health, housing shortage or skilled "
            "labour, rank social first.\n"
            "- Rank technological first ONLY when a genuinely new technical "
            "capability itself is the news (new material, new process, new device).\n"
            "- Energy efficiency alone is not 'environmental'; use environmental "
            "first when climate change, emissions targets or circularity drive it.\n"
            "Pick 1-3 dimensions, strongest driver FIRST, only dimensions with "
            "direct evidence support.\n\n"
            f"Step 2 - Category (radar colour), exactly one of: "
            f"{', '.join(TREND_CATEGORIES)}.\n\n"
            "Step 3 - Scores, each an integer 1-10, and use the full scale:\n"
            "- impact: strategic effect on a facade/window manufacturer (1 = fringe "
            "curiosity, 5 = affects single product lines, 10 = redefines the core "
            "business)\n"
            "- urgency: how soon action is needed (1 = >10 years out, 5 = within "
            "3-5 years, 10 = already binding or being adopted by competitors)\n"
            "- uncertainty: how unpredictable direction and timing are (1 = locked "
            "in, e.g. adopted regulation, 10 = speculative early research)\n\n"
            f"Step 4 - rationale: 1-2 sentences in {rationale_lang}, naming the "
            "driving force and the concrete evidence behind your PESTEL and score "
            "choices, so a reviewer can verify the classification.\n\n"
            'Respond as JSON: {"pestel": ["..."], "category": "...", "impact": 0, '
            '"urgency": 0, "uncertainty": 0, "rationale": "..."}'
        )
        try:
            resp = self._client.chat.completions.create(
                model=self._model_name,
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"},
            )
            data = json.loads(resp.choices[0].message.content)
        except Exception:
            return self._fallback.classify(signal)

        base = self._fallback.classify(signal)
        # The LLM output is untrusted: a non-list ``pestel`` or non-numeric score
        # must degrade to the heuristic rather than crash the whole run.
        try:
            raw_pestel = data.get("pestel", [])
            if not isinstance(raw_pestel, list):
                raw_pestel = []
            pestel = [p for p in raw_pestel if p in PESTEL_DIMENSIONS][:3]
            category = data.get("category")
            if category not in TREND_CATEGORIES:
                category = base.category
            llm_impact = _clamp(float(data.get("impact", 5)))
            llm_urgency = _clamp(float(data.get("urgency", 5)))
            llm_uncertainty = _clamp(float(data.get("uncertainty", 5)))
        except (TypeError, ValueError):
            return base

        # Blend the LLM judgement with corpus-derived signals (maturity, growth,
        # novelty, source count). The LLM alone tends to cluster every building trend
        # around the same impact/urgency; mixing in the heuristic - which varies by
        # maturity and emergence - restores the spread the radar needs and matches the
        # "LLM + Heuristiken" design (ADR-26, project plan §8.7).
        impact = _clamp(0.6 * llm_impact + 0.4 * base.impact)
        urgency = _clamp(0.5 * llm_urgency + 0.5 * base.urgency)
        uncertainty = _clamp(0.5 * llm_uncertainty + 0.5 * base.uncertainty)
        return Classification(
            pestel=pestel or base.pestel,
            category=category,
            impact=impact,
            urgency=urgency,
            uncertainty=uncertainty,
            rationale=str(data.get("rationale", "")).strip(),
        )


def get_classifier(name: str) -> TrendClassifier:
    """Factory: resolve a trend classifier by name."""
    name = name.lower()
    if name in ("heuristic", "offline"):
        return HeuristicClassifier()
    if name == "auto":
        from app.config import get_settings

        return (
            OpenAIClassifier()
            if get_settings().openai_api_key
            else HeuristicClassifier()
        )
    if name == "openai":
        return OpenAIClassifier()
    raise ValueError(f"Unknown classifier: {name!r}")
