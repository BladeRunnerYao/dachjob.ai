import { describe, expect, it } from "vitest";
import { resumeGeneratorTestables } from "./resume-generator";

const { buildResumePrompt, collectJobSkills, extractHtmlDocument, normalizeResumeStyle, parseJsonObject } =
  resumeGeneratorTestables;

describe("resume generator prompt parity", () => {
  it("defaults to US resume style for ATS-heavy output", () => {
    expect(normalizeResumeStyle()).toBe("us");
    expect(normalizeResumeStyle("")).toBe("us");
    expect(normalizeResumeStyle("dach")).toBe("german");
  });

  it("builds a career-ops style US prompt with supported JD keywords", () => {
    const parsedJob = {
      must_have_skills: ["Python", "distributed systems and cloud infrastructure"],
      nice_to_have_skills: ["Insurance technology", "SQL"],
      required_qualifications: ["production ownership"],
    };
    const jdSkills = collectJobSkills(parsedJob);
    const prompt = buildResumePrompt({
      style: "us",
      job: {
        id: "job-1",
        title: "Senior Software Engineer",
        company: "Kalepa",
        raw_description: "Build data-intensive backend services.",
      },
      parsedJob,
      profile: {
        id: "profile-1",
        name: "Tiyao Li",
        raw_cv_md: "# Tiyao Li\n\n## Experience\nPython, Kafka, Kubernetes, Terraform.",
        profile_json: null,
      },
      parsedProfile: null,
      confirmedSkills: ["Insurance technology"],
      jdSkills,
      matchResult: null,
    });

    expect(prompt).toContain("Generate a US / ATS-heavy software engineering resume.");
    expect(prompt).toContain("One page, one column, letterpaper, no photo");
    expect(prompt).toContain("Career-ops Resume Tailor Mode parity rules");
    expect(prompt).toContain("Use exact JD wording for ATS keywords");
    expect(prompt).toContain("If a JD skill is not present in the CV/profile/match evidence");
    expect(prompt).toContain("Python, distributed systems and cloud infrastructure");
    expect(prompt).toContain("API confirmed_skills:\nInsurance technology");
    expect(prompt).toContain("Kalepa");
  });

  it("extracts an HTML document from fenced model output", () => {
    expect(extractHtmlDocument("```html\n<!DOCTYPE html><html><body>ok</body></html>\n```")).toBe(
      "<!DOCTYPE html><html><body>ok</body></html>"
    );
    expect(
      extractHtmlDocument("I tailored it below.\n\n```html\n<!DOCTYPE html><html><body>ok</body></html>\n```")
    ).toBe("<!DOCTYPE html><html><body>ok</body></html>");
    expect(extractHtmlDocument("No HTML here")).toBeNull();
  });

  it("parses only JSON objects for profile and job metadata", () => {
    expect(parseJsonObject('{"skills":["Python"]}')).toEqual({ skills: ["Python"] });
    expect(parseJsonObject("[1,2,3]")).toBeNull();
    expect(parseJsonObject("not json")).toBeNull();
  });
});
