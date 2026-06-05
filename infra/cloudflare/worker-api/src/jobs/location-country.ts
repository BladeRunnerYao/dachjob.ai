export const JOB_COUNTRIES = [
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
] as const;

export type JobCountry = (typeof JOB_COUNTRIES)[number];

type CountryPattern = {
  country: JobCountry;
  patterns: RegExp[];
};

const COUNTRY_PATTERNS: CountryPattern[] = [
  {
    country: "Germany",
    patterns: [
      /\b(germany|deutschland|remote germany|nationwide germany)\b/,
      /\b(multiple de cities|multiple germany cities)\b/,
      /\b(berlin|hamburg|munich|munchen|muenchen|metropolregion munchen|frankfurt|stuttgart|leipzig|hannover|karlsruhe|bremen|dusseldorf|duesseldorf|cologne|koln|koeln|dortmund|mainz|nuremberg|nurnberg|nuernberg|ulm|aachen|darmstadt|dresden|duisburg|erlangen|eschborn|freiburg im breisgau|garching|gottingen|goettingen|heilbronn|ingolstadt|kaiserslautern|kiel|mannheim|offenbach|regensburg|wiesbaden|wurzburg|wuerzburg)\b/,
      /\b(bavaria|hesse|saxony|lower saxony|north rhine westphalia|baden wurttemberg|rhineland palatinate|schleswig holstein)\b/,
    ],
  },
  {
    country: "Switzerland",
    patterns: [
      /\b(switzerland|schweiz|swiss|ch)\b/,
      /\b(zurich|zuerich|basel|bern|berne|baar|geneva|genf|emmen|lausanne|fribourg|gerlafingen|ittigen|lucerne|luzern|meilen|mendrisio|sierre|solothurn|st gallen|zug)\b/,
      /\b(vaud|waadt|ticino)\b/,
    ],
  },
  {
    country: "Austria",
    patterns: [/\b(austria|osterreich|oesterreich|vienna|wien)\b/],
  },
  {
    country: "United States",
    patterns: [
      /\b(united states|usa|u\.s\.a\.|remote us)\b/,
      /\b(san francisco|new york|austin|santa clara|seattle|cambridge|boulder|charlotte|mountain view|oakland|redmond|san jose|san mateo|sunnyvale)\b/,
      /,\s*(ca|ny|tx|wa|ma|co|nc)\b/,
    ],
  },
  {
    country: "Spain",
    patterns: [/\b(spain|espana|barcelona|madrid|granada)\b/],
  },
  {
    country: "United Kingdom",
    patterns: [/\b(united kingdom|uk|london)\b/],
  },
  {
    country: "Ireland",
    patterns: [/\b(ireland|dublin)\b/],
  },
  {
    country: "Romania",
    patterns: [/\b(romania|iasi)\b/],
  },
  {
    country: "Italy",
    patterns: [/\b(italy)\b/],
  },
  {
    country: "Portugal",
    patterns: [/\b(portugal)\b/],
  },
  {
    country: "Netherlands",
    patterns: [/\b(netherlands|amsterdam)\b/],
  },
  {
    country: "France",
    patterns: [/\b(france|paris)\b/],
  },
  {
    country: "Thailand",
    patterns: [/\b(thailand|bangkok)\b/],
  },
  {
    country: "Japan",
    patterns: [/\b(japan|tokyo|yokohama)\b/],
  },
  {
    country: "Hungary",
    patterns: [/\b(hungary|budapest)\b/],
  },
  {
    country: "Greece",
    patterns: [/\b(greece|athens)\b/],
  },
];

export function inferCountriesFromLocation(location?: string | null): JobCountry[] {
  const normalized = normalizeLocationText(location);
  if (!normalized) return [];

  const countries: JobCountry[] = [];
  for (const { country, patterns } of COUNTRY_PATTERNS) {
    if (patterns.some((pattern) => pattern.test(normalized))) {
      countries.push(country);
    }
  }
  return countries;
}

export function serializeCountries(countries: readonly string[]): string {
  const normalized = countries
    .map((country) => country.trim())
    .filter((country): country is JobCountry => isJobCountry(country));
  return [...new Set(normalized)].map((country) => `|${country}|`).join("");
}

export function parseSerializedCountries(value?: string | null): JobCountry[] {
  if (!value) return [];
  return JOB_COUNTRIES.filter((country) => value.includes(`|${country}|`));
}

export function countriesForLocation(location?: string | null): {
  countries: JobCountry[];
  serialized: string;
} {
  const countries = inferCountriesFromLocation(location);
  return { countries, serialized: serializeCountries(countries) };
}

function isJobCountry(value: string): value is JobCountry {
  return (JOB_COUNTRIES as readonly string[]).includes(value);
}

function normalizeLocationText(value?: string | null): string {
  return (value || "")
    .normalize("NFKD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/&/g, " and ")
    .replace(/[()]/g, " ")
    .replace(/\s+/g, " ")
    .trim()
    .toLowerCase();
}
