"""Coarse country -> region mapping for the regional trend filter (project plan §7.3).

Connectors set an ISO-3166 alpha-2 ``country`` where the source exposes it (e.g.
OpenAlex institution country codes). :func:`region_for_country` collapses that into a
small set of macro-regions used by the Trendradar's region filter. Unknown codes map
to ``None`` (treated as "global / unspecified"), so the feature degrades gracefully.
"""

from __future__ import annotations

REGIONS = ("Europe", "Asia", "North America", "South America", "Africa", "Oceania")

# Deliberately limited to the countries that matter for the building-envelope domain
# and the China/Asia focus; extend as needed. Keys are upper-case ISO-2 codes.
_COUNTRY_TO_REGION: dict[str, str] = {
    # Europe
    "DE": "Europe", "AT": "Europe", "CH": "Europe", "FR": "Europe", "GB": "Europe",
    "IT": "Europe", "ES": "Europe", "NL": "Europe", "BE": "Europe", "DK": "Europe",
    "SE": "Europe", "NO": "Europe", "FI": "Europe", "PL": "Europe", "PT": "Europe",
    "IE": "Europe", "CZ": "Europe", "GR": "Europe", "RO": "Europe", "HU": "Europe",
    # Asia
    "CN": "Asia", "JP": "Asia", "KR": "Asia", "IN": "Asia", "SG": "Asia",
    "HK": "Asia", "TW": "Asia", "ID": "Asia", "MY": "Asia", "TH": "Asia",
    "AE": "Asia", "SA": "Asia", "IL": "Asia", "TR": "Asia", "VN": "Asia",
    # North America
    "US": "North America", "CA": "North America", "MX": "North America",
    # South America
    "BR": "South America", "AR": "South America", "CL": "South America",
    "CO": "South America",
    # Africa
    "ZA": "Africa", "EG": "Africa", "NG": "Africa", "MA": "Africa", "KE": "Africa",
    # Oceania
    "AU": "Oceania", "NZ": "Oceania",
}


def region_for_country(country_code: str | None) -> str | None:
    """Map an ISO-2 country code to a macro-region, or ``None`` if unknown."""
    if not country_code:
        return None
    return _COUNTRY_TO_REGION.get(country_code.strip().upper())
