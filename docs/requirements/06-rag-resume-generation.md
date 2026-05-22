# Requirement 06: RAG Evidence and Tailored Resume Generation

## Owner Agent

RAG and Resume Agent

## Goal

Generate tailored CV drafts for each job using only real user evidence. Every generated bullet must be traceable to source evidence chunks.

## Profile and Evidence Flow

1. User uploads or pastes CV Markdown.
2. Backend stores raw CV in `candidate_profiles.raw_cv_md`.
3. Backend chunks the CV into `evidence_chunks`.
4. Each chunk receives metadata:
   - section
   - company/project
   - date range
   - skills
   - source label
5. Embeddings are generated locally and stored in pgvector.

## Embedding Requirement

For MVP, use local embedding model to avoid extra API cost:

- `sentence-transformers/all-MiniLM-L6-v2`

If this is too heavy for Docker on the first pass, use a simple keyword retriever first and keep the vector interface ready.

## Evidence Retrieval

Input:

- Parsed JD
- Match report
- Candidate profile

Output:

- Top evidence chunks per job requirement
- Similarity score or keyword score
- Human-readable source labels

## Resume Generation Rules

The generated CV must:

- Use only retrieved evidence.
- Preserve truthful metrics.
- Not invent new projects, companies, dates, tools, or achievements.
- Prefer DACH-style one-page structure for MVP.
- Output HTML first.
- Export PDF with Playwright.
- Store artifacts in MinIO.

## Provenance Requirement

Every generated bullet must include metadata:

```json
{
  "bullet": "Built event-driven AI/data processing pipelines with Kafka and KEDA...",
  "source_chunk_ids": ["uuid-1", "uuid-2"],
  "confidence": 0.94,
  "used_for_requirements": [
    "Kubernetes orchestration",
    "Kafka-based distributed processing"
  ]
}
```

## CV HTML Template

MVP sections:

- Name and headline
- Contact/location/languages
- Profile summary tailored to JD
- Selected experience
- Selected technical skills
- Education

## API Endpoints

### Upload CV

`POST /api/profile/cv`

Input:

```json
{
  "raw_cv_md": "# Tiyao Li\n..."
}
```

### Get Evidence

`GET /api/jobs/{job_id}/evidence`

### Generate Resume

`POST /api/jobs/{job_id}/resume`

Output:

```json
{
  "resume_artifact_id": "uuid",
  "html_url": "signed-url-or-local-url",
  "pdf_url": "signed-url-or-local-url",
  "provenance": []
}
```

## Acceptance Criteria

- CV upload creates evidence chunks.
- Evidence retrieval returns relevant chunks for a job.
- Resume generation creates HTML.
- PDF export works locally.
- Artifact is stored under tenant-prefixed MinIO key.
- Provenance metadata is saved.
- Generated CV does not contain bullets without evidence.

## Implementation Plan

1. Implement CV upload endpoint.
2. Implement chunking.
3. Implement embedding or keyword retrieval interface.
4. Implement evidence retrieval endpoint.
5. Implement resume generation prompt and schema.
6. Implement HTML CV renderer.
7. Implement Playwright PDF export.
8. Implement storage upload.
9. Add tests for provenance enforcement.
