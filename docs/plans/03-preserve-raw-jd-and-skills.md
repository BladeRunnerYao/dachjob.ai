# Preserve Raw JD And Skill Extraction Plan

## Goal

Fix the job import pipeline so `raw_jd` stores the full original job posting content, while the UI can still present it cleanly. Improve parsed skill extraction so hard requirements and nice-to-have items are separated, broad enough, and visible in two columns.

## Current Findings

1. `raw_jd` is currently overwritten by an LLM formatting step during URL import.
   - `import_job_urls()` calls `format_raw_jd()`.
   - If the LLM returns anything longer than 80 characters, the result replaces `scraped.raw_jd`.
   - This makes `raw_jd` no longer raw. Any LLM omission becomes permanent data loss.

2. The GetYourGuide example is mainly a scraper problem before it is a model problem.
   - The static Webflow HTML has an empty `#wrapper-el`.
   - The real description is loaded client-side from Greenhouse:
     `https://boards-api.greenhouse.io/v1/boards/getyourguide/jobs/7581804`.
   - Current scraper does not discover or call that API, so it falls back to page text and benefits/similar-jobs chrome.

3. The model choice makes the damage worse.
   - Production `llm_runs` for the GetYourGuide import show `jd_format` used `gemini-3.1-flash-lite`.
   - It produced a short formatted output and then `jd_extract` saw that already-truncated text.
   - Result: `must_have_skills=[]`, `nice_to_have_skills=[]`, `responsibilities=[]`.

4. This is not isolated to one row, but the exact failure mode differs.
   - Production has 6 jobs in the default tenant.
   - GetYourGuide Search Platform kept only about 24% of the stored original page text and has zero parsed skills.
   - Lever jobs usually preserve raw text when formatting is skipped, but when the LLM provider fails, the deterministic parser is too narrow and misses many skills.
   - Some manually seeded LinkedIn jobs have good skills because they were curated or parsed by a different provider.

5. Skill extraction is underpowered.
   - The prompt asks for atomic skills, but no schema validation or post-processing enforces coverage.
   - Deterministic extraction only knows a small fixed skill list.
   - Section detection misses common headings such as `What you must have`, `Get some bonus points`, and curly-apostrophe variants.
   - Frontend displays hard requirements and nice-to-haves as separate vertical cards, not the two-column comparison view requested.

## Implementation Plan

1. Make `raw_jd` raw again.
   - Stop using LLM formatting during URL import.
   - Keep any source text and scraper diagnostics in `scraped_json`.
   - Preserve the full ATS/job-post content in `raw_jd`.
   - Keep presentation formatting in frontend parsing/rendering, not in the stored source field.

2. Add ATS-aware scraping.
   - Add Greenhouse support:
     - `job-boards.greenhouse.io/{board}/jobs/{id}`
     - `boards.greenhouse.io/{board}/jobs/{id}`
     - custom pages with `gh_jid` or path job id plus an embedded `boards-api.greenhouse.io/v1/boards/{board}/jobs/{id}` script.
   - Call the Greenhouse Job Board API first when detected.
   - Decode escaped HTML content and strip it into readable text with headings and list boundaries preserved.
   - Store source metadata: ATS provider, board token, API URL, API content length, and original page fallback length.

3. Improve text extraction.
   - Preserve line breaks around headings, paragraphs, and list items.
   - Avoid concatenating all HTML text into one long line.
   - Filter obvious page chrome only for generic fallback, not for trusted ATS content.

4. Improve parser prompt/model use.
   - Do not use the model for raw JD formatting.
   - Keep LLM extraction for structured JSON, but strengthen the prompt:
     - hard requirements go to `must_have_skills`;
     - optional/preferred/bonus items go to `nice_to_have_skills`;
     - extract all explicit technical skills, tools, protocols, platforms, practices, and domain capabilities;
     - return atomic items and avoid broad summaries.
   - Use the reasoning model for `jd_extract` if the fast model returns low coverage, invalid JSON, or empty skills for a long JD.

5. Add deterministic coverage fallback.
   - Expand heading detection for must-have, nice-to-have, responsibilities, and bonus sections.
   - Extract likely skills from section text using:
     - existing curated patterns;
     - proper nouns/acronyms/tools from bullet lines;
     - phrase extraction around `experience with`, `knowledge of`, `proficiency with`, `familiarity with`, `using`, `such as`, and parenthesized lists.
   - Merge deterministic results with LLM output, preserving must/nice categories and avoiding duplicates.

6. Update frontend skill presentation.
   - Render hard requirements and nice-to-haves in a responsive two-column layout.
   - Keep profile-match/manual-confirm interactions.
   - Show counts per column and handle empty columns cleanly.

7. Tests and verification.
   - Add backend tests for GetYourGuide Greenhouse custom-page discovery.
   - Add backend tests proving `import_job_urls()` no longer calls formatting or overwrites `raw_jd`.
   - Add backend tests for hard/nice skill section extraction using the Amazon RIVR sample.
   - Add frontend/lint checks if available.
   - Run local add-job tests against currently live URLs from `career-ops/data/pipeline.md`, including:
     - GetYourGuide Greenhouse custom page;
     - direct Greenhouse board URL;
     - Lever URL.

## Acceptance Criteria

1. Importing `https://getyourguide.careers/jobs/7581804?gh_jid=7581804` stores the Greenhouse job description, including team mission, role responsibilities, requirements, and benefits when present in the source API.
2. `raw_jd` is not an LLM summary.
3. Parsed skills for real jobs are non-empty when the JD contains explicit skill/requirement language.
4. Skills are split into hard requirements and nice-to-haves.
5. The job detail page shows the two skill groups in two columns.
6. Existing manual paste/create job flow still works.

## Verification Notes - 2026-05-24

1. Pipeline-wide dry-run coverage.
   - Source file: `/Users/yao/02_Repos/career-ops/data/pipeline.md`.
   - Unique URLs tested: 315.
   - Method: fetch with the application scraper, preserve `raw_jd`, run deterministic parse/enrichment, and classify the result without writing all rows to the database or triggering LLM calls for every URL.
   - Final result after fixes: 255 usable job descriptions, 56 empty/dead/blocked links, 4 BMW source timeouts, 0 poor-quality fallbacks.
   - Result artifact: `/tmp/dachjob_pipeline_results_after.json`.

2. Confirmed working source classes.
   - Greenhouse direct board URLs.
   - Greenhouse custom career pages: GetYourGuide, Helsing, SumUp, Trade Republic, Wayve.
   - Greenhouse confirmation URLs with `for` and `token` query parameters.
   - Lever job pages.
   - Ashby pages that still expose a live posting.
   - Personio pages.
   - Workday pages with JSON-LD.
   - Amazon job pages that are still live.
   - LinkedIn job pages that expose the public job description block.
   - Google Careers pages that expose an actual job result instead of only the search shell.

3. Confirmed rejected source classes.
   - 404/410 expired jobs.
   - 403 blocked sites such as Indeed/myGwork in the current environment.
   - LinkedIn `/jobs/view` URLs that resolve to search-result pages instead of a job detail page.
   - Google Careers links that return the `Jobs search - Google Careers` shell for an unavailable job.
   - Known Greenhouse custom pages whose `gh_jid` no longer exists in the Greenhouse API.

4. Targeted live examples verified.
   - GetYourGuide `7581804`: Greenhouse raw JD, non-empty must/nice skills.
   - Helsing `4871604101`: hidden Greenhouse board fallback to `helsing`.
   - Trade Republic `7685049003`: hidden Greenhouse board fallback to `traderepublicbank`.
   - SumUp `8508079002`: hidden Greenhouse board fallback to `sumup`.
   - Wayve `8551387002`: original URL `gh_jid` preserved across redirect and resolved to `wayve`.
   - LinkedIn `4414805630`: public description block extracted without sign-in chrome.
   - Greenhouse confirmation `yoodliinc/4246665009`: resolved back to the real job post.
