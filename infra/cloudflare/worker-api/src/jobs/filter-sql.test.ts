import { describe, expect, it } from "vitest";
import { jobsRoutesTestables } from "./routes";

const { buildJobFilterSql, escapeSqlLike } = jobsRoutesTestables;

describe("job filter SQL", () => {
  it("supports case-insensitive partial company queries", () => {
    const filter = buildJobFilterSql({ companyQuery: "Google" });

    expect(filter.sql).toContain("LOWER(company) LIKE ? ESCAPE '\\'");
    expect(filter.params).toEqual(["%google%"]);
  });

  it("escapes user-entered LIKE wildcards in company queries", () => {
    expect(escapeSqlLike(String.raw`100%_remote\team`)).toBe(String.raw`100\%\_remote\\team`);

    const filter = buildJobFilterSql({ companyQuery: String.raw`100%_Remote` });
    expect(filter.params).toEqual([String.raw`%100\%\_remote%`]);
  });

  it("keeps exact company filters available for existing callers", () => {
    const filter = buildJobFilterSql({ company: "Google DeepMind" });

    expect(filter.sql).toContain("company = ?");
    expect(filter.params).toEqual(["Google DeepMind"]);
  });
});
