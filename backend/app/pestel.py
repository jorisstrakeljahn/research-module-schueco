"""Evidence-grounded six-dimensional PESTEL analysis for portfolio trends."""

from __future__ import annotations

import math
import re
from collections import Counter

from sqlmodel import Session, select

from app.models import (
    PESTEL_DIMENSIONS,
    Document,
    RunDocument,
    Source,
    Topic,
    Trend,
    TrendOccurrence,
)
from app.pipeline.classify import _PESTEL_LEXICON
from app.schemas import (
    PestelAnalysisOut,
    PestelDimensionAnalysisOut,
    TrendEvidenceOut,
)

TOKEN_RE = re.compile(r"[a-zA-Z][a-zA-Z-]{2,}")

# German display labels for the (English) lexicon terms. The matching itself
# always runs against the English corpus tokens; only the labels shown in the
# UI are localized. Singular/plural variants collapse onto one label.
_TERM_LABELS_DE: dict[str, str] = {
    # political
    "policy": "Politik", "policies": "Politik", "government": "Regierung",
    "governmental": "Regierung", "subsidy": "Subventionen", "subsidies": "Subventionen",
    "tariff": "Zölle", "tariffs": "Zölle", "geopolitical": "Geopolitik",
    "geopolitics": "Geopolitik", "public": "Öffentliche Hand", "funding": "Förderung",
    "incentive": "Anreize", "incentives": "Anreize", "sovereignty": "Souveränität",
    "trade": "Handel", "ministry": "Ministerium", "municipal": "Kommunen",
    "election": "Wahlen", "sanction": "Sanktionen", "sanctions": "Sanktionen",
    "diplomacy": "Diplomatie", "federal": "Bund", "parliament": "Parlament",
    "programme": "Programme", "program": "Programme", "initiative": "Initiativen",
    "governance": "Governance",
    # economic
    "market": "Markt", "markets": "Märkte", "cost": "Kosten", "costs": "Kosten",
    "investment": "Investitionen", "investments": "Investitionen", "price": "Preise",
    "prices": "Preise", "pricing": "Preisgestaltung", "demand": "Nachfrage",
    "supply": "Angebot", "economic": "Wirtschaft", "economy": "Wirtschaft",
    "business": "Geschäftsmodell", "growth": "Wachstum",
    "servitization": "Servitization", "productivity": "Produktivität",
    "competition": "Wettbewerb", "competitor": "Wettbewerber",
    "financing": "Finanzierung", "finance": "Finanzierung", "capital": "Kapital",
    "revenue": "Umsatz", "profitability": "Rentabilität", "inflation": "Inflation",
    "procurement": "Beschaffung", "export": "Export", "import": "Import",
    "industry": "Industrie", "manufacturer": "Hersteller", "startup": "Start-ups",
    "venture": "Wagniskapital", "adoption": "Marktdurchdringung",
    "commercialization": "Kommerzialisierung",
    "commercialisation": "Kommerzialisierung", "leasing": "Leasing",
    # social
    "social": "Soziales", "society": "Gesellschaft", "societal": "Gesellschaft",
    "demographic": "Demografie", "demographics": "Demografie",
    "skills": "Qualifikationen", "workforce": "Arbeitskräfte", "user": "Nutzer",
    "users": "Nutzer", "health": "Gesundheit", "wellbeing": "Wohlbefinden",
    "well-being": "Wohlbefinden", "community": "Gemeinschaft",
    "labour": "Arbeitsmarkt", "labor": "Arbeitsmarkt", "talent": "Fachkräfte",
    "people": "Menschen", "silver": "Alternde Gesellschaft", "aging": "Alterung",
    "ageing": "Alterung", "occupant": "Gebäudenutzer", "occupants": "Gebäudenutzer",
    "tenant": "Mieter", "tenants": "Mieter", "resident": "Bewohner",
    "residents": "Bewohner", "comfort": "Komfort", "affordable": "Bezahlbarkeit",
    "affordability": "Bezahlbarkeit", "housing": "Wohnen",
    "urbanization": "Urbanisierung", "urbanisation": "Urbanisierung",
    "migration": "Migration", "lifestyle": "Lebensstil", "acceptance": "Akzeptanz",
    "education": "Bildung", "craftsman": "Handwerk", "shortage": "Fachkräftemangel",
    "safety": "Sicherheit", "accessibility": "Barrierefreiheit",
    # technological
    "technology": "Technologie", "technologies": "Technologien",
    "digital": "Digitalisierung", "sensor": "Sensorik", "sensors": "Sensorik",
    "automation": "Automatisierung", "software": "Software",
    "innovation": "Innovation", "smart": "Smart-Technologien",
    "platform": "Plattformen", "robotic": "Robotik", "robotics": "Robotik",
    "data": "Daten", "twin": "Digitale Zwillinge", "modular": "Modulbauweise",
    "prefabrication": "Vorfertigung", "ai": "KI", "algorithm": "Algorithmen",
    "machine": "Maschinelles Lernen", "learning": "Maschinelles Lernen",
    "iot": "IoT", "bim": "BIM", "printing": "3D-Druck", "additive": "Additive Fertigung",
    "coating": "Beschichtungen", "nanotechnology": "Nanotechnologie",
    "photovoltaic": "Photovoltaik", "photovoltaics": "Photovoltaik",
    "electrochromic": "Elektrochrome Systeme", "aerogel": "Aerogel",
    "prototype": "Prototypen", "patent": "Patente", "material": "Materialien",
    "materials": "Materialien", "glazing": "Verglasung", "actuator": "Aktorik",
    "interoperability": "Interoperabilität", "cyber": "Cybersicherheit",
    # environmental
    "climate": "Klima", "carbon": "CO2", "sustainability": "Nachhaltigkeit",
    "sustainable": "Nachhaltigkeit", "energy": "Energie", "emission": "Emissionen",
    "emissions": "Emissionen", "circular": "Kreislaufwirtschaft",
    "circularity": "Kreislaufwirtschaft", "green": "Green Building",
    "environmental": "Umwelt", "decarbonization": "Dekarbonisierung",
    "decarbonisation": "Dekarbonisierung", "resilience": "Resilienz",
    "renewable": "Erneuerbare Energien", "renewables": "Erneuerbare Energien",
    "recycling": "Recycling", "recycled": "Recycling", "embodied": "Graue Energie",
    "biodiversity": "Biodiversität", "pollution": "Verschmutzung", "waste": "Abfall",
    "warming": "Erderwärmung", "adaptation": "Klimaanpassung",
    "mitigation": "Klimaschutz", "heatwave": "Hitzewellen",
    "cradle": "Cradle-to-Cradle", "lifecycle": "Lebenszyklus",
    "life-cycle": "Lebenszyklus", "ecological": "Ökologie", "solar": "Solarenergie",
    "geothermal": "Geothermie",
    # legal
    "legal": "Recht", "law": "Gesetze", "laws": "Gesetze",
    "compliance": "Compliance", "standard": "Standards", "standards": "Standards",
    "directive": "Richtlinien", "directives": "Richtlinien", "epbd": "EPBD",
    "certification": "Zertifizierung", "certified": "Zertifizierung",
    "regulation": "Regulierung", "regulations": "Regulierung",
    "regulatory": "Regulierung", "norm": "Normen", "norms": "Normen",
    "mandate": "Vorgaben", "mandatory": "Verpflichtungen", "liability": "Haftung",
    "warranty": "Gewährleistung", "code": "Bauvorschriften",
    "codes": "Bauvorschriften", "taxonomy": "EU-Taxonomie",
    "disclosure": "Offenlegungspflichten", "audit": "Audits", "gdpr": "DSGVO",
    "din": "DIN-Normen", "iso": "ISO-Normen", "ce": "CE-Kennzeichnung",
    "permit": "Genehmigungen", "permits": "Genehmigungen", "zoning": "Bauleitplanung",
}


def _localize_terms(terms: list[str], language: str | None) -> list[str]:
    """Map lexicon terms to display labels; collapse variants, keep order."""
    if language != "de":
        return terms
    labels: list[str] = []
    for term in terms:
        label = _TERM_LABELS_DE.get(term, term)
        if label not in labels:
            labels.append(label)
    return labels


def build_pestel_analysis(
    session: Session,
    *,
    canonical_id: str,
    occurrence: TrendOccurrence,
    language: str | None = None,
) -> PestelAnalysisOut:
    """Analyze all six PESTEL dimensions against the latest cluster documents."""
    trend = session.get(Trend, occurrence.trend_id)
    topic = session.get(Topic, trend.topic_id) if trend else None
    if trend is None or topic is None:
        raise ValueError("Occurrence snapshot is unavailable")

    rows = session.exec(
        select(Document, Source)
        .join(RunDocument, RunDocument.document_id == Document.id)
        .join(Source, Source.id == Document.source_id, isouter=True)
        .where(
            RunDocument.run_id == occurrence.run_id,
            RunDocument.topic_index == topic.topic_index,
            RunDocument.is_outlier.is_(False),
        )
        .order_by(Document.published_at.desc(), Document.id)
    ).all()
    corpus = [
        {
            "title": document.title,
            "text": document.text,
            "url": document.url,
            "published_at": document.published_at,
            "source": source.name if source else None,
        }
        for document, source in rows
    ]
    if not corpus:
        corpus = [
            {
                "title": item.get("title", ""),
                "text": item.get("title", ""),
                "url": item.get("url"),
                "published_at": None,
                "source": item.get("source"),
            }
            for item in (trend.evidence or [])
            if item.get("title")
        ]
    total = len(corpus)
    dimensions: list[PestelDimensionAnalysisOut] = []
    for dimension in PESTEL_DIMENSIONS:
        lexicon = _PESTEL_LEXICON[dimension]
        matches: list[tuple[int, dict, set[str]]] = []
        term_counts: Counter[str] = Counter()
        for item in corpus:
            tokens = {
                token.casefold()
                for token in TOKEN_RE.findall(f"{item['title']} {item['text']}")
            }
            terms = tokens & lexicon
            if not terms:
                continue
            term_counts.update(terms)
            matches.append((len(terms), item, terms))
        matches.sort(
            key=lambda item: (
                item[0],
                item[1]["published_at"] is not None,
                item[1]["published_at"],
            ),
            reverse=True,
        )
        coverage = len(matches) / total if total else 0.0
        relevance = round(min(10.0, 10.0 * math.sqrt(coverage)), 1)
        evidence = [
            TrendEvidenceOut(
                title=item["title"],
                url=item["url"],
                source=item["source"],
                published_at=(
                    item["published_at"].date().isoformat()
                    if item["published_at"]
                    else None
                ),
                run_id=occurrence.run_id,
            )
            for _, item, _ in matches[:3]
        ]
        dimensions.append(
            PestelDimensionAnalysisOut(
                dimension=dimension,
                relevance=relevance,
                matched_documents=len(matches),
                total_documents=total,
                signal_terms=_localize_terms(
                    [term for term, _ in term_counts.most_common(5)], language
                ),
                evidence=evidence,
            )
        )
    return PestelAnalysisOut(
        trend_id=canonical_id,
        run_id=occurrence.run_id,
        dimensions=dimensions,
    )
