import { describe, expect, it } from "vitest";
import {
  inferCountriesFromLocation,
  parseSerializedCountries,
  serializeCountries,
} from "./location-country";

describe("job country inference", () => {
  it("infers Germany from German cities and metropolitan areas", () => {
    expect(inferCountriesFromLocation("Hamburg")).toEqual(["Germany"]);
    expect(inferCountriesFromLocation("Greater Munich Metropolitan Area")).toEqual(["Germany"]);
    expect(inferCountriesFromLocation("Metropolregion München")).toEqual(["Germany"]);
  });

  it("infers Switzerland from Swiss city names and German country names", () => {
    expect(inferCountriesFromLocation("Zürich, Schweiz")).toEqual(["Switzerland"]);
    expect(inferCountriesFromLocation("Geneva, Switzerland")).toEqual(["Switzerland"]);
  });

  it("keeps multi-country jobs in every matching country bucket", () => {
    expect(inferCountriesFromLocation("Germany/Spain/Italy/Portugal (Remote)")).toEqual([
      "Germany",
      "Spain",
      "Italy",
      "Portugal",
    ]);
    expect(
      inferCountriesFromLocation("Berlin, Germany / London, United Kingdom / Iasi, Romania")
    ).toEqual(["Germany", "United Kingdom", "Romania"]);
  });

  it("serializes countries for stable LIKE-based filtering", () => {
    const serialized = serializeCountries(["Germany", "Switzerland", "Germany"]);

    expect(serialized).toBe("|Germany||Switzerland|");
    expect(parseSerializedCountries(serialized)).toEqual(["Germany", "Switzerland"]);
  });
});
