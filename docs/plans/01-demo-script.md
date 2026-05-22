# dachjob.ai 2-Minute Demo Script

## Audience

Hiring manager or interviewer for AI Platform, Data Platform, Backend Cloud, or MLOps roles.

## Opening

`dachjob.ai` is a local-first AI job search platform for the DACH market. I built it as a product-shaped demo of multi-tenant AI platform architecture: job ingestion, structured LLM extraction, deterministic matching, RAG-based evidence retrieval, tailored CV generation, artifact storage, and LLM observability.

## Demo Flow

1. Open dashboard.
2. Show tenant `tiyao-local`.
3. Open Profile Vault and show CV evidence chunks.
4. Paste a German/DACH AI Platform Engineer job.
5. Click Parse JD.
6. Show extracted requirements: skills, seniority, location, language, salary.
7. Click Generate Match.
8. Show score breakdown and gaps.
9. Open Evidence tab and show which CV chunks support each requirement.
10. Click Generate CV.
11. Preview tailored one-page CV.
12. Show provenance metadata behind generated bullets.
13. Open LLM Runs page and show DeepSeek model, latency, task, status.
14. Open Tracker and show application status.

## Architecture Talking Points

- Modular monolith for local-first MVP.
- Every table has tenant isolation.
- DeepSeek calls go through a central LLM gateway.
- Structured LLM output is schema-validated.
- CV generation is evidence-grounded to avoid hallucination.
- MinIO locally simulates cloud object storage.
- Storage and LLM providers are abstracted for future Azure/AWS/GCP deployment.

## Closing

The point of this project is not to mass-apply to jobs. It is to make high-quality applications faster while demonstrating how to build reliable AI platform workflows with observability, data grounding, and human approval.
