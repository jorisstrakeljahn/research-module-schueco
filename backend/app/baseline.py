"""Constants for the immutable report baseline and legacy run-7 import."""

BASELINE_KEY = "schueco-table-3-2026"

# Exact accepted table order and expert values. The IDs are historical references,
# not mutable portfolio IDs.
BASELINE_ROWS = (
    (34, "Adaptive Reuse", 4.0, "bekannt, nicht aktiv", 5.0),
    (49, "Decarbonization", 5.0, "bekannt, aktiv", 5.0),
    (33, "Green Standards (China)", 5.0, "bekannt, nicht aktiv", 5.0),
    (40, "BIPV", 5.0, "bekannt, nicht aktiv", 5.0),
    (38, "Industrialized Construction", 5.0, "bekannt, aktiv", 5.0),
    (48, "Innovative Building Envelopes", 5.0, "bekannt, aktiv", 5.0),
    (36, "Circular Economy Materials", 5.0, "bekannt, aktiv", 5.0),
    (45, "Generative AI Facade Design", 5.0, "bekannt, nicht aktiv", 5.0),
    (41, "Drones: Cleaning/Inspection", 5.0, "bekannt, aktiv", 5.0),
    (46, "Construction Servitization", 5.0, "bekannt, nicht aktiv", 4.0),
    (47, "Curtain Wall Market", 5.0, "bekannt, nicht aktiv", 5.0),
)
BASELINE_TREND_IDS = tuple(row[0] for row in BASELINE_ROWS)
