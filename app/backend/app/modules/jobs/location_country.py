from __future__ import annotations

import re
import unicodedata

JOB_COUNTRIES = (
    "Germany",
    "Switzerland",
    "Austria",
    "United States",
    "Spain",
    "United Kingdom",
    "Ireland",
    "Romania",
    "Italy",
    "Portugal",
    "Netherlands",
    "France",
    "Thailand",
    "Japan",
    "Hungary",
    "Greece",
)

_COUNTRY_PATTERNS: tuple[tuple[str, tuple[str, ...]], ...] = (
    (
        "Germany",
        (
            r"\b(germany|deutschland|remote germany|nationwide germany)\b",
            r"\b(multiple de cities|multiple germany cities)\b",
            r"\b(berlin|hamburg|munich|munchen|muenchen|frankfurt|stuttgart|leipzig|hannover|karlsruhe|bremen|dusseldorf|duesseldorf|cologne|koln|koeln|dortmund|mainz|nuremberg|nurnberg|nuernberg|ulm|aachen|darmstadt|dresden|duisburg|erlangen|eschborn|freiburg im breisgau|garching|gottingen|goettingen|heilbronn|ingolstadt|kaiserslautern|kiel|mannheim|offenbach|regensburg|wiesbaden)\b",
            r"\b(bavaria|hesse|saxony|lower saxony|north rhine westphalia|baden wurttemberg|rhineland palatinate|schleswig holstein)\b",
        ),
    ),
    (
        "Switzerland",
        (
            r"\b(switzerland|schweiz|swiss|ch)\b",
            r"\b(zurich|zuerich|basel|bern|berne|baar|geneva|genf|emmen|lausanne|fribourg|gerlafingen|ittigen|lucerne|luzern|meilen|mendrisio|sierre|solothurn|st gallen|zug)\b",
        ),
    ),
    ("Austria", (r"\b(austria|osterreich|oesterreich|vienna|wien)\b",)),
    (
        "United States",
        (
            r"\b(united states|usa|u\.s\.a\.|remote us)\b",
            r"\b(san francisco|new york|austin|santa clara|seattle|cambridge|boulder|charlotte|mountain view|oakland|redmond|san jose|san mateo|sunnyvale)\b",
            r",\s*(ca|ny|tx|wa|ma|co|nc)\b",
        ),
    ),
    ("Spain", (r"\b(spain|espana|barcelona|madrid|granada)\b",)),
    ("United Kingdom", (r"\b(united kingdom|uk|london)\b",)),
    ("Ireland", (r"\b(ireland|dublin)\b",)),
    ("Romania", (r"\b(romania|iasi)\b",)),
    ("Italy", (r"\b(italy)\b",)),
    ("Portugal", (r"\b(portugal)\b",)),
    ("Netherlands", (r"\b(netherlands|amsterdam)\b",)),
    ("France", (r"\b(france|paris)\b",)),
    ("Thailand", (r"\b(thailand|bangkok)\b",)),
    ("Japan", (r"\b(japan|tokyo|yokohama)\b",)),
    ("Hungary", (r"\b(hungary|budapest)\b",)),
    ("Greece", (r"\b(greece|athens)\b",)),
)


def infer_countries_from_location(location: str | None) -> list[str]:
    normalized = _normalize_location_text(location)
    if not normalized:
        return []
    return [
        country
        for country, patterns in _COUNTRY_PATTERNS
        if any(re.search(pattern, normalized) for pattern in patterns)
    ]


def serialize_countries(countries: list[str] | tuple[str, ...]) -> str:
    unique = []
    for country in countries:
        if country in JOB_COUNTRIES and country not in unique:
            unique.append(country)
    return "".join(f"|{country}|" for country in unique)


def parse_serialized_countries(value: str | None) -> list[str]:
    if not value:
        return []
    return [country for country in JOB_COUNTRIES if f"|{country}|" in value]


def _normalize_location_text(value: str | None) -> str:
    normalized = unicodedata.normalize("NFKD", value or "")
    asciiish = "".join(char for char in normalized if not unicodedata.combining(char))
    return re.sub(r"\s+", " ", asciiish).strip().casefold()
