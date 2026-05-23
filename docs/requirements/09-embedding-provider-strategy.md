# Requirement 09: Embedding Provider Strategy

## Owner Agent

RAG and Resume Agent

## Goal

Add a documented provider strategy for generating embeddings used by evidence retrieval. The MVP should continue to support a local-first path, while leaving a clean option to use managed cloud embedding APIs later.

This document supplements `06-rag-resume-generation.md`. It does not require immediate implementation.

## Background

The RAG evidence workflow needs embeddings to compare job requirements against CV evidence chunks:

1. Split the candidate CV into `evidence_chunks`.
2. Generate an embedding vector for each chunk.
3. Store vectors in Postgres/pgvector.
4. Generate an embedding for the parsed job description or individual requirements.
5. Retrieve the closest evidence chunks by vector similarity.
6. Use only retrieved evidence when generating tailored CV content.

The current requirement document proposes local embeddings with:

- `sentence-transformers/all-MiniLM-L6-v2`

That path pulls in PyTorch through `sentence-transformers`. The model is small enough for a Mac mini M2, but PyTorch increases install time, Docker image size, and local dependency complexity.

## Current Code State

As of this document, the backend dependency list includes `sentence-transformers`, but the application code does not directly import PyTorch or `SentenceTransformer`.

Current evidence retrieval uses keyword scoring, not vector similarity. The `EvidenceChunk.embedding` field exists, but embeddings are not generated or queried yet.

## Provider Options

The implementation should eventually support three modes:

| Mode | Description | Primary Use |
|---|---|---|
| `keyword` | Existing keyword-based fallback with no embedding model. | Fastest local demo and lowest complexity. |
| `local` | Local embedding model, such as `sentence-transformers/all-MiniLM-L6-v2`. | Private local development without API cost. |
| `cloud` | Managed embedding API provider. | Lighter Docker image, simpler setup, and stronger managed models. |

## Recommended Configuration

Future implementation should expose provider selection through environment variables:

```env
EMBEDDING_PROVIDER=keyword
EMBEDDING_MODEL=
EMBEDDING_DIMENSIONS=
```

Example local configuration:

```env
EMBEDDING_PROVIDER=local
EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2
```

Example OpenAI configuration:

```env
EMBEDDING_PROVIDER=openai
EMBEDDING_MODEL=text-embedding-3-small
OPENAI_API_KEY=sk-...
```

Example Voyage configuration:

```env
EMBEDDING_PROVIDER=voyage
EMBEDDING_MODEL=voyage-4-lite
VOYAGE_API_KEY=...
```

## Cloud Provider Comparison

Prices and free tiers change. Values below were checked on 2026-05-22 and must be re-verified before production use.

| Provider | Model | Approx. price | Free usage | Notes |
|---|---|---:|---|---|
| OpenAI | `text-embedding-3-small` | `$0.02 / 1M tokens` | No stable free tier; account trial credits may apply. | Recommended default cloud option for simplicity and ecosystem support. |
| OpenAI | `text-embedding-3-large` | `$0.13 / 1M tokens` | No stable free tier; account trial credits may apply. | Higher quality/capacity, likely unnecessary for this MVP. |
| Voyage AI | `voyage-4-lite` | `$0.02 / 1M tokens` | First `200M` tokens free for eligible accounts. | Strong free option for prototyping. |
| Voyage AI | `voyage-4` | `$0.06 / 1M tokens` | First `200M` tokens free for eligible accounts. | Higher quality than lite. |
| Voyage AI | `voyage-4-large` | `$0.12 / 1M tokens` | First `200M` tokens free for eligible accounts. | Higher-end retrieval model. |
| Google Gemini / Vertex AI | `gemini-embedding-001` | `$0.15 / 1M tokens`; batch lower | Gemini API has a free tier. | Free tier content may be used to improve Google products; paid tier has different data-use terms. |
| Google Vertex AI | legacy text embeddings | Priced per 1K characters for some non-Gemini models. | Depends on Google Cloud billing/free tier. | Useful if the project already runs on GCP. |
| Mistral AI | `mistral-embed` | `$0.10 / 1M tokens` | No stable API free tier assumed. | European provider; simple text embedding API. |
| AWS Bedrock | Amazon Titan Text Embeddings V2 | Around `$0.02 / 1M tokens`, region dependent. | No simple free tier assumed. | Useful if AWS credentials and Bedrock access are already configured. |
| Cohere | `embed-v4.0` | Public pricing is more enterprise-oriented; commonly listed around `$0.12 / 1M text tokens`. | Trial terms vary. | Strong multilingual and enterprise retrieval option. |
| Jina AI | `jina-embeddings-v4` and related models | Token top-up model; public pages emphasize usage tiers more than a single fixed price. | New API keys commonly include free tokens; verify current dashboard terms. | Good multilingual option; verify commercial terms for selected model/API. |

DeepSeek should not be assumed as an embedding provider. As of the referenced DeepSeek API docs, the public model list focuses on chat/reasoning models and does not show an official public embedding endpoint.

Anthropic/Claude should also not be assumed as an embedding provider. Anthropic documents recommend using a third-party embedding provider rather than offering a native Claude embedding model.

## Cost Expectation for This Project

For the dachjob.ai MVP, embedding usage should be small:

- A personal CV split into chunks is usually only a few thousand tokens.
- Each pasted job description is usually a few thousand tokens.
- Even hundreds of jobs should stay in the low millions of tokens.

At `$0.02 / 1M tokens`, the embedding cost for local demo usage is likely cents rather than dollars. Cloud embeddings are mainly a privacy and dependency tradeoff, not a major cost driver for this MVP.

## Recommended MVP Decision

Use this order of preference:

1. Keep `keyword` retrieval as the no-dependency fallback.
2. Keep `local` embeddings as the local-first/private option.
3. Add one cloud provider first, preferably OpenAI `text-embedding-3-small` for implementation simplicity or Voyage `voyage-4-lite` for generous free prototyping.
4. Add more providers only behind the same `EmbeddingProvider` interface.

## Implementation Shape

Future implementation should introduce an internal provider interface, for example:

```python
class EmbeddingProvider:
    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        ...

    async def embed_query(self, text: str) -> list[float]:
        ...
```

Suggested providers:

- `KeywordRetriever` or `KeywordEvidenceRetriever`
- `LocalSentenceTransformerEmbeddingProvider`
- `OpenAIEmbeddingProvider`
- `VoyageEmbeddingProvider`
- Optional later: `GoogleEmbeddingProvider`, `JinaEmbeddingProvider`, `MistralEmbeddingProvider`, `BedrockEmbeddingProvider`

The rest of the RAG/resume code should depend on the interface, not on vendor SDKs directly.

## Privacy and Data Policy Requirements

Candidate CVs and job application evidence can contain sensitive personal data. If cloud embeddings are enabled:

- The UI or configuration docs must make it clear that CV/job text is sent to the selected provider.
- Free tiers must be treated carefully because some providers may use free-tier content to improve their products.
- Paid tiers or enterprise deployments should be preferred for sensitive or production use.
- API keys must stay in environment variables and must never be committed.

## Acceptance Criteria

When implemented later:

- `EMBEDDING_PROVIDER=keyword` runs without PyTorch and without any embedding API key.
- `EMBEDDING_PROVIDER=local` runs with a local model and does not call external embedding APIs.
- At least one cloud provider can generate and store embeddings.
- The embedding dimension is tracked or validated so existing vectors are not mixed across incompatible models.
- Switching embedding models requires re-indexing evidence chunks or invalidating stale vectors.
- Retrieval tests cover keyword fallback and at least one embedding provider through a fake provider.
- Provider errors degrade gracefully to keyword retrieval or return a clear typed error.

## Source References

- OpenAI embeddings and pricing: https://platform.openai.com/docs/guides/embeddings and https://platform.openai.com/docs/pricing
- Voyage AI pricing: https://docs.voyageai.com/docs/pricing
- Google Gemini pricing: https://ai.google.dev/gemini-api/docs/pricing
- Google Vertex AI embeddings pricing: https://cloud.google.com/gemini-enterprise-agent-platform/generative-ai/pricing
- Mistral Embed model card: https://docs.mistral.ai/models/model-cards/mistral-embed-23-12
- AWS Bedrock Titan embeddings: https://docs.aws.amazon.com/bedrock/latest/userguide/titan-embedding-models.html
- Cohere Embed docs: https://docs.cohere.com/docs/cohere-embed
- Jina embeddings: https://jina.ai/en-US/embeddings/
- DeepSeek public model list: https://api-docs.deepseek.com/api/list-models
- Anthropic embeddings guidance: https://docs.anthropic.com/en/docs/build-with-claude/embeddings
