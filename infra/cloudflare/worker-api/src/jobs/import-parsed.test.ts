import { describe, expect, it } from "vitest";
import { jobsRoutesTestables } from "./routes";

const { canonicalJobKey, normalizeParsedImportItems } = jobsRoutesTestables;

describe("parsed job import helpers", () => {
  it("uses LinkedIn job ids as stable canonical keys", () => {
    expect(canonicalJobKey("https://www.linkedin.com/jobs/view/senior-engineer-4424680395")).toBe(
      "linkedin:4424680395"
    );
    expect(canonicalJobKey("https://www.linkedin.com/jobs/view/4424680395?trk=public_jobs")).toBe(
      "linkedin:4424680395"
    );
  });

  it("keeps only valid already-parsed import items", () => {
    const items = normalizeParsedImportItems({
      jobs: [
        {
          url: " https://www.linkedin.com/jobs/view/4424680395 ",
          title: " Senior Platform Engineer ",
          company: "Example",
          location: "Berlin, Germany",
          countries: ["Germany"],
          raw_description: "Build Python data platform services.",
          parsed_json: { must_have_skills: ["Python"] },
        },
        {
          url: "https://www.linkedin.com/jobs/view/invalid",
          title: "",
          raw_description: "Missing title",
          parsed_json: {},
        },
      ],
    });

    expect(items).toHaveLength(1);
    expect(items[0].title).toBe("Senior Platform Engineer");
    expect(items[0].url).toBe("https://www.linkedin.com/jobs/view/4424680395");
  });
});
