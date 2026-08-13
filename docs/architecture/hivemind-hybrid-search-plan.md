# Hivemind Hybrid Search

**Status:** Proposed implementation plan
**Date:** 2026-07-28
**Scope:** Replace Hivemind's unranked `ILIKE` retrieval with indexed lexical
search plus optional semantic retrieval, while preserving the public Astrid
pack interface and Hivemind's citation-oriented knowledge workflow.

## Summary

Hivemind should adopt a hybrid retrieval system modeled on Pumpernickel's
production search:

1. Indexed PostgreSQL full-text search produces lexical candidates.
2. One embedding is generated for each normalized query.
3. A shared pgvector index produces semantic candidates across messages,
   resources, and distillations.
4. Reciprocal Rank Fusion combines both candidate lists.
5. Modest source and status weights prefer trustworthy distillations without
   unconditionally placing every distillation before stronger raw matches.
6. Search falls back to lexical results whenever semantic retrieval is
   unavailable.
7. Workflow resources expose separate prose, Python-source, and structured
   representations so agents can search the workflow corpus alone, search
   inside one selected workflow, and inspect the exact code that matched.

The existing `hivemind.search` arguments remain compatible. The pack changes
from making two direct `unified_feed` `ILIKE` requests to making one request to
a Hivemind search Edge Function. The OpenAI credential remains server-side;
installed Astrid clients continue to use only the public Hivemind credential.

Pumpernickel is a strong implementation precedent, but Hivemind should port its
small retrieval algorithms and operational patterns rather than depend on the
Pumpernickel application at runtime.

This is a new search layer built on working infrastructure, not a new platform
or database project:

- The existing Hivemind Supabase project remains the only database and
  deployment target.
- Hivemind's existing schema/DDL, Edge Function, service-role, backfill,
  validation, and test conventions remain the operational foundation.
- Pumpernickel supplies proven retrieval algorithms and evaluation patterns
  that are ported into Hivemind-owned code.
- The existing Hivemind Astrid pack remains the client surface.
- Astrid core does not need a new search subsystem or a code change.
- No Pumpernickel database configuration, runtime service, or deployment is
  copied into Hivemind.

The vector schema, embedding jobs, durable backfill checkpoints, hybrid RPC,
search Edge Function, and HNSW operations are new Hivemind components. Reuse
reduces design and infrastructure work; it does not make those components
already implemented.

## Why this work is needed

The current executor:

- Searches for one contiguous substring with `ILIKE`.
- Makes one request for distillations and another for all other rows.
- Concatenates the two lists instead of ranking them together.
- Applies the requested limit independently to each request.
- Has no lexical relevance score, semantic matching, or deterministic global
  rank.
- Cannot naturally retrieve paraphrases such as "reduce motion strength" for a
  corpus item that says "lower the motion amplitude."
- Performs broad searches against `unified_feed`, an ordinary view that cannot
  itself carry indexes.
- Can discard a useful distillation result when the second request fails.
- Has no author or channel filter in the normal unified search contract.

The database already has useful substrate:

- Approximately 1.25 million Discord messages.
- Thousands of external resources.
- Curated distillations and explicit `distillation_cites`.
- `pg_trgm`.
- A GIN full-text index on the underlying Discord message content.

The public search currently bypasses the useful Discord index by searching the
unified view with `ILIKE`. pgvector is not currently enabled.

## Goals

- Improve retrieval for exact terms, multi-term questions, paraphrases, and
  cross-source questions.
- Search the actual VibeComfy Python representation of workflow resources,
  including exact identifiers and semantic code chunks, without indexing the
  same source twice when it is present in both `body` and `payload`.
- Support workflow-only search and search constrained to one or more selected
  workflow item IDs through additive filters on the existing search endpoint.
- Return one globally ranked list across messages, resources, and
  distillations.
- Preserve the current `hivemind.search` inputs and existing result fields.
- Make new ranking metadata additive and inspectable.
- Keep the public pack free of private database and embedding credentials.
- Degrade to lexical search instead of failing when the embedding provider is
  unavailable or slow.
- Embed source content once, then embed only new or changed content.
- Use one shared semantic index rather than adding unrelated embedding columns
  to every source table.
- Preserve Discord snowflakes exactly as strings at API and shared-index
  boundaries.
- Measure relevance and latency against a Hivemind-specific golden set before
  changing the default.
- Keep Hivemind as a pack-level capability; no new Astrid core search
  subsystem is required.

## Non-goals

- Replacing `unified_feed` as Hivemind's public presentation and hydration
  surface.
- Making embeddings part of the public Hugging Face dataset.
- Training a custom embedding model in the first release.
- Using an LLM to rewrite every query or rerank every result.
- Automatically publishing experiment conclusions to Hivemind.
- Treating message reactions as a reliable popularity score.
- Coupling Hivemind's runtime to the Pumpernickel repository.
- Rebuilding Discord ingestion as part of the search project.
- Embedding volatile URLs, IDs, status fields, or other non-semantic metadata.
- Executing, importing, validating, or otherwise trusting stored workflow
  Python during search. Python is indexed and returned as inert corpus text.

## Existing systems

### Hivemind

The implementation belongs in the Hivemind source repository. The installed
Astrid revision is a distributable snapshot of that pack, not the place to
develop or deploy the backend.

The Hivemind pack currently exposes:

- `hivemind.search`
- `hivemind.get_item`
- `hivemind.contribute`
- ingestion helpers for articles, workflows, and YouTube transcripts
- Discord media URL refresh

`unified_feed` presents messages, external resources, and distillations in a
common shape:

```text
kind, source, item_id, title, body, author, context, url, metadata, created_at
```

This remains the canonical public row shape.

Existing Hivemind code already provides the operational pattern for this work:

- `schema/001_unified_corpus.sql` establishes the repository's DDL
  conventions.
- `supabase/functions/contribute/` demonstrates server-side service-role use,
  request validation, and secret handling.
- `scripts/backfill_workflow_semantics.py` demonstrates paged dry-run/apply
  operations, service-role updates, sampling, and reporting.
- `tests/` covers the Python executors and backend behavior.
- `skill/SKILL.md`, `pack.yaml`, and `executors/` define the public Astrid pack
  contract.

Hivemind's existing workflow-semantics enrichment is structured metadata, not
an embedding system. It should not be mistaken for semantic vector search, but
its paging, validation, reporting, and deployment patterns should be reused.
It does not persist a durable crash-resume checkpoint; that capability remains
new work in this plan.

The workflow corpus currently has more than one representation cohort. A live
read-only audit on 2026-07-28 found newer promoted rows whose
`payload.python_source` is also copied verbatim into `body`, including
individual Python representations hundreds of thousands of characters long.
Many older rows contain only a description, workflow semantics, and a
`corpus_path`; they do not yet have materialized Python or workflow JSON in the
database. Search and backfill therefore need an explicit representation
contract rather than assuming every `kind=workflow` row has the same shape.

### Pumpernickel

The reusable precedent lives primarily in:

- `app/services/retrieval.py`
- `app/services/embeddings.py`
- `app/services/embed_worker.py`
- `app/services/embed_jobs.py`
- `scripts/backfill_embeddings.py`
- `migrations/0056_retrieval_index.sql`
- `migrations/0058_content_embeddings_unified_index.sql`
- `eval/retrieval/`

Pumpernickel already demonstrates:

- `websearch_to_tsquery` and `ts_rank`
- cosine pgvector retrieval through HNSW
- Reciprocal Rank Fusion with `K=60`
- query-embedding normalization, timeout, and caching
- lexical fallback with a `semantic_degraded` signal
- canonical text and SHA-256 content hashes
- asynchronous embed/reembed/drop jobs
- idempotent backfill and model/dimension tracking
- source-aware ranking weights
- a comparative retrieval evaluation harness

Pumpernickel's fair synthetic evaluation used 273 messages and 70 queries. Its
Recall@10 moved from `0.510` for `ILIKE` to `0.853` for semantic and `0.855`
for hybrid RRF; MRR moved from `0.660` to `0.849` and `0.847`. The improvement
was concentrated in paraphrase, topic, and cross-thread queries, while keyword
search remained competitive on verbatim queries. The report explicitly warns
that the corpus and scope model are synthetic. Hivemind must reproduce the
evaluation on its own corpus rather than assuming identical gains.

## Target architecture

```text
Astrid / standalone Hivemind client
                 │
                 │ query + filters + limit
                 ▼
       Hivemind search Edge Function
                 │
       normalize/cache query
       generate embedding or null
                 ▼
       one hybrid-search database RPC
                 │
       ┌─────────┴──────────┐
       │                    │
       ▼                    ▼
 indexed lexical      indexed semantic
 candidates           candidates
       │                    │
       └─────────┬──────────┘
                 ▼
          RRF + source weights
          one global limit
                 ▼
       hydrate from unified_feed
       and attach rank metadata
                 │
                 ▼
          one global result list
```

The Edge Function owns query validation and the external embedding-provider
call because PostgreSQL should not make that network request, and the embedding
key must not be exposed to public clients. It then makes one database RPC,
passing either the validated query vector or `null`. PostgreSQL owns lexical
and semantic candidate generation, fusion, global limiting, and hydration so
all paths share filters, ranking semantics, and a single database snapshot.

## Architectural decisions

### AD-1: Preserve the client contract

The existing inputs remain:

```text
query, kinds, sources, since, limit
```

Add optional filters without breaking existing callers:

```text
channels, authors, item_ids, mode
```

`kinds=["workflow"]` searches the workflow collection independently of
messages, articles, transcripts, and distillations. Combining it with a
bounded `item_ids` list searches inside one selected workflow or a small
explicit comparison set. `item_ids` always contains JSON strings. When
`item_ids` is present, require exactly one `kinds` value so IDs are interpreted
inside one unambiguous entity/concrete-resource namespace.

`mode` is one of:

- `hybrid` — default after rollout.
- `lexical` — never calls the embedding provider.
- `semantic` — primarily diagnostic and evaluation-oriented.
- `legacy` — temporary rollback path during migration.

The existing result fields remain. New rank metadata is additive.

### AD-2: One shared embedding index

Do not add an embedding column to every source table. Create one shared table
whose identity includes source kind and source ID.

Hivemind differs from Pumpernickel because articles and transcripts may be much
longer than messages. The shared table should support chunks from the
beginning:

```sql
content_embeddings (
    contract_id     bigint      not null,
    entity_type     text        not null,
    item_id         text        not null,
    representation_type text    not null default 'prose',
    chunk_index     integer     not null default 0,
    chunk_text      text,
    embedding       vector(D)   not null,
    representation_hash text   not null,
    chunk_hash      text        not null,
    embedded_at     timestamptz not null default now(),
    primary key (
        contract_id,
        entity_type,
        item_id,
        representation_type,
        chunk_index
    )
)
```

Messages and distillations normally have one row with `chunk_index = 0`.
Long resources may have multiple chunks. Semantic ranking must collapse chunks
and representation types to the best matching chunk per item before fusing
results, so long resources or workflows with both prose and code do not gain
an unfair advantage merely by having more chunks.

`representation_type` is normally `prose`. Workflow resources may additionally
use `workflow_python`. The field is part of the embedding identity so prose
and code can be independently hashed, refreshed, inspected, and evaluated
without creating a second vector table.

The internal `entity_type` vocabulary is deliberately small and stable:
`message`, `resource`, or `distillation`. A resource's concrete public kind
(`article`, `workflow`, `transcript`, and so on) is a separate `result_kind`
on the searchable/hydration surface and continues to appear as `kind` in
`unified_feed`. This matches the citation vocabulary and avoids changing an
embedding identity when resource classification changes. Embedding identity,
chunk collapse, deletion, and hydration use `(entity_type, item_id)`;
result filtering and presentation may additionally use `result_kind`.

`item_id` is text. This avoids JavaScript precision loss for Discord
snowflakes and gives all source types one stable identity.

`representation_hash` covers the complete canonical representation identified by
`representation_type`;
`chunk_hash` covers the individual embedded chunk. The distinction makes
representation-level freshness checks and chunk-level reuse unambiguous.

Define embedding contracts separately:

```sql
embedding_contracts (
    id                       bigint primary key,
    provider                 text not null,
    model                    text not null,
    dimension                integer not null,
    canonicalization_version integer not null,
    chunking_version         integer not null,
    status                   text not null
)
```

The production vector column has one fixed dimension; PostgreSQL cannot put
384- and 1536-dimensional vectors into the same constrained column and HNSW
index. Select the production dimension during the pilot. Parallel contracts of
the same dimension may coexist through `contract_id`. A dimension migration
uses a separate fixed-dimension table and HNSW index, followed by an atomic
active-contract switch in the search function. Do not mix dimensions in one
table or overwrite the active contract before replacement coverage passes.

### AD-3: Search underlying indexed tables; hydrate afterward

Keep `unified_feed` for the public common shape, but do not scan it to discover
candidates.

Lexical candidate generation should:

- Search the underlying Discord messages table through its existing matching
  GIN expression.
- Add generated `tsvector` columns and GIN indexes to resources and
  distillations.
- Return only ranked identities and lightweight ranking fields.
- Hydrate author, context, URLs, reactions, and full bodies only after the
  global candidate set is small.

This avoids paying for the joins and correlated reaction lookup across a broad
message scan.

### AD-4: Canonical representations are explicit, deduplicated, and versioned

Only stable semantic content participates in embeddings and hashes. Ordinary
resources use human-readable prose. Workflow resources have separately
labeled prose and Python representations so the code is searchable without
being accidentally included twice.

| Item/representation | Canonical semantic text |
|---|---|
| Message / `prose` | `content` |
| Non-workflow resource / `prose` | `title`, then `body`, then stable textual tags |
| Workflow / `prose` | `title`, description/summary, stable tags, and stable `workflow_semantics` fields such as task, media, model families, aliases, node types, custom nodes, and models |
| Workflow / `workflow_python` | Exact Python from `payload.python_source`; otherwise an exactly delimited legacy Python block extracted from `body` |
| Distillation / `prose` | `question`, then `conditions`, then `answer` |

Workflow Python precedence is strict:

1. Use non-empty `payload.python_source`.
2. Otherwise extract a Python representation only from a recognized,
   versioned body delimiter such as `Python ready-template source:` or
   `Python scratchpad source:`.
3. Otherwise mark the Python representation unavailable.

When `payload.python_source` exists and the same bytes also occur in `body`,
remove that delimited code block from the workflow's canonical prose before
hashing or embedding. Never embed both copies. Raw `workflow_json`,
`compiled_api`, and arbitrary `payload` JSON are not embedded wholesale;
their stable, searchable facts are projected through `workflow_semantics`.
The exact stored Python remains searchable as inert text and is never executed.

Before workflow Python enters a public body, lexical document, embedding,
snippet, or `get_item` response, run a deterministic secret scanner covering
private-key blocks, known provider/token prefixes, credential assignments,
credential-bearing URLs, and high-confidence high-entropy tokens. A hit
quarantines that Python representation from public search/retrieval and records
only non-secret reason codes for operator review. Do not log or include the
matched value in metadata. New ingestion fails closed; historical public hits
enter the documented security-remediation path rather than being silently
copied into a new index.

Do not embed:

- Database IDs.
- URLs.
- Creation timestamps.
- Reactions.
- Approval status or confidence labels.
- Discord channel IDs.
- Other volatile operational metadata.

Store a `canonicalization_version` either on the embedding row or in the model
identifier used by the job system. Version the workflow delimiter,
representation precedence, semantics projection, and code chunker as part of
that contract. A canonical-representation change must be able to trigger a
controlled re-embed even when the source row did not otherwise change.

### AD-5: Prose and workflow Python use representation-aware chunking

Use deterministic paragraph-aware chunks for prose and deterministic
code-aware chunks for workflow Python. The code chunker should align to
imports, top-level statements, assignments/call blocks, and stable line or
token windows where possible, with a bounded fallback for generated archives
whose large literals cannot be divided cleanly by the Python AST. Use modest
overlap and never require importing or executing the stored code. Record:

- `representation_type`
- `chunk_index`
- content hash
- optionally the chunk text or stable source offsets

The exact chunk size is an evaluation parameter, not an undocumented constant.
Start with ranges appropriate to the chosen embedding model and compare at
least two settings on resource-heavy and workflow-code queries.

Do not chunk ordinary Discord messages. A pathological overlong message may use
the same resource chunker, but that should be exceptional and observable.

### AD-6: Hybrid rank uses RRF, not incomparable raw scores

Full-text rank and cosine distance are not directly comparable. Retrieve
separate ranked lists and combine them with Reciprocal Rank Fusion:

```text
score(item) =
  source_weight(item) *
  [1 / (K + lexical_rank) + 1 / (K + semantic_rank)]
```

Use Pumpernickel's initial `K=60`, then validate it rather than tuning against a
few anecdotes.

Initial candidate policy:

- Up to `candidate_multiplier × limit` lexical candidates.
- Up to `candidate_multiplier × limit` semantic candidates.
- A reasonable initial multiplier is 5, capped to prevent abusive requests.
- Collapse semantic chunks to one best chunk per item before assigning the
  semantic item rank.

Initial source/status weighting should be conservative:

- Approved distillation: modest boost.
- Pending distillation: smaller or neutral boost.
- External resource: neutral.
- Raw message: neutral.

Weights must not overpower both retrieval signals. A weak distillation should
not outrank a direct, strong match merely because of its type.

### AD-7: Semantic search is optional on every request

Use a short query-embedding timeout, initially matching Pumpernickel's
approximately 400 ms policy. If embedding fails, times out, returns the wrong
dimension, or the vector RPC fails:

- Run lexical retrieval.
- Return normal results.
- Set `semantic_degraded: true`.
- Include a machine-readable degradation reason in response metadata and
  server logs, without leaking secrets.

Exact/lexical mode never attempts query embedding and is not considered
degraded.

### AD-8: Port code, do not create a runtime dependency

Reuse the following Pumpernickel logic with attribution and fresh Hivemind
tests:

- Query normalization.
- Vector validation and L2 normalization.
- Content hashing.
- RRF fusion.
- Query timeout and best-effort cache behavior.
- Job retry/backoff and stale-content supersession.
- Idempotent backfill, hash skipping, and coverage checks.
- Evaluation metrics and report structure.

Rewrite:

- Pumpernickel's `mediator.*` SQL.
- UUID-specific source identity code.
- User, bot, dyad, topic, and private visibility rules.
- Python app-server wiring.
- Pumpernickel-specific canonicalizers and hydrators.

The Hivemind repo owns the resulting SQL, Edge Function, worker/backfill tools,
tests, and pack executor.

### Reuse and ownership boundaries

| Concern | Owner / source | Treatment |
|---|---|---|
| Production data and database | Existing Hivemind Supabase project | Extend additively; do not create or copy another database. |
| Schema, RPCs, Edge Function, backfill, and tests | Hivemind source repository | Implement and deploy here using existing conventions. |
| Search client and agent guidance | Existing Hivemind Astrid pack | Preserve the executor contract and update the pack in place. |
| Retrieval algorithms and evaluation structure | Pumpernickel repository | Port and adapt with attribution; no runtime dependency. |
| Organization embedding-provider credential | Existing approved credential | Register in Hivemind's server-side secret store; never copy into source or the public pack. |
| Astrid core | Existing Astrid repository | No core feature or framework change required. |

“Hivemind-owned secret” in this plan means that the secret is registered and
used at Hivemind's deployment boundary. It does not mean creating another
provider account, billing relationship, or API key when an approved
organizational credential already exists.

## Lexical search design

### Messages

Query the base Discord message table first. Pumpernickel uses the `simple`
PostgreSQL text-search configuration, while Hivemind's existing Discord index
uses `english`; a query only benefits from an expression index when its
configuration and expression match. Phase 1 must therefore choose and build
one canonical Hivemind expression—prefer `simple` for punctuation-heavy model,
version, filename, and node vocabulary—rather than accidentally querying an
`english` index with a `simple` query. Apply:

- Corpus eligibility and opt-out/deletion rules.
- `since`.
- Optional channel and author filters.
- Message kind/source constraints.

After limiting ranked IDs, hydrate display names, channels, links, and
reactions.

### Resources

Add a stored or maintained weighted `tsvector`:

```text
title: high weight
tags: medium weight
body: normal weight
```

Support concrete resource kinds such as article, workflow, and transcript
through the existing `kind` value. For ordinary resources, `body` remains one
searchable prose document.

For `kind=workflow`, build the lexical document from the canonical
representations rather than assuming `body` is prose:

```text
title and prose summary: high weight
workflow semantics, aliases, nodes, models, and custom nodes: medium weight
full Python representation: normal weight
```

The full Python representation participates in exact lexical retrieval.
Imports, function/class names, VibeComfy variable names, ComfyUI node classes,
model filenames, keyword arguments, and comments must be discoverable. Use the
underlying `external_resources` indexes, including a bounded trigram/code
fragment arm where punctuation-aware FTS is insufficient; do not scan
`unified_feed`.

Because some workflow bodies are hundreds of thousands of characters, Phase 0
must measure `tsvector`, trigram, update, and query costs. If a single
maintained resource vector approaches PostgreSQL's document-size limit or
becomes too large or noisy, store bounded indexed lexical documents per
`(resource_id, representation_type, chunk_index)` and collapse those matches
to the resource identity before global ranking. Reject or split over-limit
documents deterministically; never silently truncate the searchable Python.
This is an implementation choice behind the same public contract, not a
reason to omit the Python source.

### Distillations

Add a weighted `tsvector`:

```text
question: high weight
conditions: medium weight
answer: normal weight
```

Status and confidence influence policy/weighting but do not enter the search
text.

### Exact identifiers and punctuation

Full-text search alone is not sufficient for names such as `Wan 2.2`,
`FLUX.1`, LoRA filenames, repository paths, and ComfyUI node names.

Lexical candidate generation must include an exact-identifier arm alongside
normal FTS:

- Normalize case and Unicode while preserving a raw exact phrase.
- Produce punctuation-preserving and punctuation-separated identifier forms.
- Use `phraseto_tsquery('simple', ...)` where the name tokenizes safely.
- Use a bounded trigram-backed exact/subsequence path for names that do not.
- Add trigram indexes first to high-value short fields such as resource titles
  and distillation questions.
- Measure the storage cost of a message-content trigram index before creating
  it across the full archive; if it exceeds the Phase 0 cap, use a separately
  maintained normalized identifier side index instead.
- Merge exact-identifier and FTS candidates deterministically before hybrid
  RRF.

The golden set must include versioned model names, dotted names, hyphenated
node names, filenames, Python imports, function/class names, keyword
arguments, code fragments, and common aliases. Exact-name and workflow-code
retrieval are blocking gates, not optional polish.

### Query parsing

Use `websearch_to_tsquery` so normal user questions support multiple terms,
quoted phrases, and exclusions without requiring callers to construct
PostgreSQL query syntax. Pass the same explicit text-search configuration used
by the corresponding indexed expression; never rely on the database default.

Return deterministic tie-breaks:

1. Rank score descending.
2. Creation time descending.
3. `(entity_type, item_id)` ascending or another stable identity order.

## Semantic search design

Enable pgvector and choose one active embedding contract:

```text
contract_id =
  provider + model + dimension + canonicalization version + chunking version
```

The dimension decision should be made by evaluation:

- A 384-dimensional index is the preferred starting candidate because it
  materially reduces storage and HNSW memory.
- A 1536-dimensional index remains the quality fallback.
- Do not build both full-corpus indexes before evidence shows that both are
  useful.

Create an HNSW cosine index after the initial bulk backfill reaches its rollout
coverage threshold. Bulk-loading most vectors before building the index is
preferable to maintaining a large HNSW index through the entire historical
backfill.

Semantic candidate SQL should:

1. Restrict to the atomically selected active contract.
2. Apply requested source, kind, and date filters before final ranking where
   practical.
3. Rank prose and workflow-Python chunks by cosine distance.
4. Keep the best chunk across representation types per item.
5. Assign semantic item rank.
6. Return the matched representation type plus bounded chunk text or offsets
   for an explanatory snippet.

Workflow-code embeddings are built from the exact canonical Python
representation, not a second copy recovered from prose. Evaluate their
incremental recall, vector count, storage, and ranking effect separately from
workflow prose. They remain in the shared embedding table and are collapsed to
one workflow result before RRF.

## Search API

### Edge Function request

```json
{
  "query": "Where is block swap configured?",
  "kinds": ["workflow"],
  "item_ids": ["2580"],
  "sources": ["vibecomfy-external"],
  "limit": 20,
  "mode": "hybrid"
}
```

All fields except `query` are optional. With `kinds=["workflow"]`, omitting
`item_ids` searches every workflow; passing one workflow ID searches only that
workflow's prose, semantics, and Python chunks. Enforce:

- A maximum query length.
- A bounded result limit.
- Allow-listed modes.
- Valid timestamps.
- Arrays with bounded lengths.
- Exact string handling for all item IDs.
- Exactly one compatible `kinds` value whenever `item_ids` is present; reject
  ambiguous or cross-kind bare IDs.
- `item_ids` only as a bounded allow-listed identity filter, never interpolated
  SQL.

### Response

```json
{
  "results": [
    {
      "kind": "workflow",
      "source": "vibecomfy-external",
      "item_id": "2580",
      "title": "WanVideo Image-to-Video with Florence2 and LoRA",
      "body": "…",
      "author": null,
      "context": null,
      "url": "…",
      "metadata": {},
      "created_at": "…",
      "truncated": true,
      "match_type": "both",
      "keyword_rank": 2,
      "semantic_rank": 5,
      "rrf_score": 0.0309,
      "matched_representation": "workflow_python",
      "matched_snippet": "sampler = WanVideoSampler(…)"
    }
  ],
  "count": 1,
  "meta": {
    "mode_requested": "hybrid",
    "mode_used": "hybrid",
    "semantic_degraded": false,
    "degradation_reason": null,
    "embedding_model": "…",
    "embedding_dimension": 384,
    "latency_ms": 182
  }
}
```

Continue truncating large bodies in `hivemind.search`; callers use
`hivemind.get_item` for the full body and citation context.

For workflow results, a Python hit must include a bounded,
secret-safe `matched_snippet` and `matched_representation=workflow_python`.
Extend `hivemind.get_item` additively with an opt-in
`representation=python` request that returns the whitelisted full
`python_source` plus representation version/hash. Do not expose the whole
arbitrary `payload`, local `corpus_path`, or other operational provenance
merely to make code matches inspectable.

The current executor uses the citation vocabulary
`kind=message|resource|distillation`. Preserve that contract and add
`kind=workflow` as a backwards-compatible convenience alias for
`kind=resource` plus concrete resource-kind validation. Both
`kind=resource id=2580 representation=python` and
`kind=workflow id=2580 representation=python` may resolve the same workflow;
the Python option must fail closed if the hydrated resource is not actually
`kind=workflow`.

Retain the existing no-distillation nudge, but base it on the final ranked
results rather than a separate distillation request.

### Workflow-only and single-workflow examples

The existing search capability handles workflow scope; a separate workflow
search service is unnecessary:

```text
# Search only workflow resources
hivemind.search query="WanVideoSampler with multiple LoRAs" kinds=workflow

# Search inside one known workflow
hivemind.search query="where is block swap configured" \
  kinds=workflow item_ids=2580

# Retrieve the complete whitelisted Python representation after a hit
hivemind.get_item kind=workflow id=2580 representation=python
```

The pack's CLI/Astrid serialization may use its normal `--input` syntax; these
examples describe the request contract rather than prescribing a second
executor.

## Workflow representation lifecycle

### Historical workflow representation remediation

Workflow representation remediation is a source-enrichment step that happens
before lexical/embedding backfill. It is not the same operation as embedding
the text that is already present.

Create an idempotent, resumable
`scripts/backfill_workflow_representations.py` command using the existing
`backfill_workflow_semantics.py` paging, dry-run/apply, service-role, sample,
and reporting conventions. Inventory every eligible `kind=workflow` row into
exactly one source cohort:

1. `payload_python` — non-empty `payload.python_source` is authoritative.
2. `body_python` — an exact Python block can be extracted through a recognized
   body delimiter.
3. `recoverable` — Python can be deterministically regenerated from approved
   VibeComfy workflow JSON, ready-template source, `corpus_path`, or provenance
   using the existing VibeComfy exporter/converter.
4. `unavailable` — no trustworthy Python representation can be recovered.

For rows with recovered Python, record a separate public-search state:
`safe` or `quarantined`. Quarantine is not a competing source cohort; it says
whether the authoritative bytes may enter public search and retrieval.

The remediation command must:

- Default to audit/dry-run and write a cohort/count/error report.
- Persist a durable run, cursor, high-water boundary, counters, and retryable
  row failures.
- Never overwrite a non-empty `payload.python_source`.
- Never infer Python from prose with an LLM.
- Run the deterministic secret scanner before writing/searching Python; reject
  or quarantine suspect source without echoing the match into logs, reports,
  snippets, hashes exposed to clients, or metadata.
- Use the existing VibeComfy rendering/export logic rather than maintain a
  second incompatible code generator in Hivemind.
- Resolve local `corpus_path` values only in an authorized operator job with an
  explicit VibeComfy root; Edge/search requests never read local paths.
- Materialize `payload.python_source`, recognized representations, derivation
  provenance, representation version, and SHA-256 hashes where authorized.
- Render `body` according to the existing Hivemind/VibeComfy searchable-body
  contract, with the Python block present exactly once.
- Preserve existing titles, descriptions, URLs, IDs, citations, and native
  workflow artifacts.
- Mark unrecoverable rows explicitly while leaving their prose and workflow
  semantics searchable.
- Recompute `workflow_semantics` from the best available structured evidence.
- Refresh maintained lexical state only after the source-row patch commits.
  Record the remediation high-water boundary; Phase 2's representation-aware
  embedding backfill consumes the reconciled rows after its job/index schema
  exists, rather than Phase 1 enqueueing jobs into a not-yet-deployed table.
- Support interruption, resume, hash skipping, bounded batches, safe logs, and
  a final reconciliation report.

New workflow ingestion must write the same versioned representation shape so
the historical script converges toward the normal steady-state contract rather
than creating a permanent second path.

Quarantined Python does not participate in lexical or semantic search and is
not returned by `get_item`; its non-sensitive prose/semantics may remain
searchable if independently safe. Any credential-like material already present
in a public row is a security incident to remove/rotate through the approved
operational process, not merely a backfill warning.

Completion requires counts for total eligible workflows, each source cohort,
safe/quarantined state, materialized Python coverage, unavailable rows,
stale/mismatched hashes, and rows whose body contains duplicate Python. Every
unavailable or quarantined row must have a non-secret recorded reason; `100%`
Python availability is a target only where the source artifact is actually
recoverable and safe.

## Embedding lifecycle

### Incremental changes

Source-table triggers should enqueue lightweight work, never call the
embedding provider inside a database transaction.

Use a generalized job shape:

```text
entity_type
item_id
representation_type: prose | workflow_python
job_kind: embed | reembed | drop
representation_hash
contract_id
status
attempts
next_attempt_at
locked_at
locked_by
last_error
```

The worker:

1. Claims jobs with `FOR UPDATE SKIP LOCKED`.
2. Fetches the current source through a canonical searchable-content surface,
   including versioned workflow prose/Python representations.
3. Recomputes every applicable representation and its hash.
4. Supersedes a stale job if the source changed after it was queued.
5. Generates one or more deterministic, representation-aware chunks.
6. Embeds chunks in provider-supported batches.
7. Atomically replaces that item's rows for the claimed representation.
8. Retries transient failures with bounded backoff.
9. Deletes vectors for removed or no-longer-public items.

Run incremental jobs as a bounded `embedding-worker` Edge Function invoked by
Supabase Cron. Each invocation claims and processes at most one configured
batch, records outcomes, and exits within the platform limit. Do not port
Pumpernickel's indefinitely running Python worker into an Edge Function.
Provide an authenticated manual invocation for recovery and testing; prevent
overlapping invocations through the database claim protocol.

### Historical backfill

Do not enqueue 1.25 million individual historical jobs.

Provide a human-run, resumable backfill command that:

- Requires a direct/session-mode Hivemind database URL.
- Refuses known transaction-pooler endpoints.
- Iterates each source by stable cursor.
- Batches provider requests within input/token limits.
- Persists a durable `embedding_backfill_runs` record and per-source cursor,
  success count, skip count, failure count, contract, and timestamps.
- Uses content hashes and idempotent upserts.
- Supports source selection and date windows.
- Supports `--dry-run`.
- Can resume without regenerating unchanged vectors.
- Builds or enables HNSW only at the approved rollout gate.
- Never prints credentials or source bodies in normal logs.

Pumpernickel's current script provides idempotent hash skipping but keeps its
iteration cursor in process memory. Hivemind's persisted backfill-run state is
new work required for a genuine crash-resume guarantee.

Recommended backfill order:

1. Complete and reconcile workflow representation remediation.
2. Approved distillations.
3. Pending distillations.
4. External resources, including separate workflow prose and Python chunks.
5. A small, representative Discord sample for evaluation.
6. Recent/high-signal Discord messages.
7. Remaining eligible messages only after the quality and capacity gate.

This order makes semantic search useful early without committing immediately to
the full message index.

## Credentials and deployment configuration

The required infrastructure and most access already exist. The audit on
2026-07-28 confirmed the following on the current development machine:

| Capability on current audited machine | Current state |
|---|---|
| Existing Hivemind Supabase project and linked source repository | Ready |
| Supabase CLI authentication and linked database connectivity | Ready |
| Database session/direct-style access for migrations and index work | Ready |
| Hivemind Edge Function deployment and secret-store access | Ready |
| Supabase service-role secret in the Hivemind deployment | Ready |
| Public publishable credential used by installed clients | Ready |
| Local Hivemind contributor credential | Ready |
| GitHub access to the Hivemind source repository | Ready |
| Existing approved organizational OpenAI credential | Available locally |
| `OPENAI_API_KEY` registered in Hivemind's Edge secret store | **Remaining setup action** |

No new database, Supabase project, deployment system, provider account, or API
key is required. Before a live embedding smoke test, register the approved
existing OpenAI credential as `OPENAI_API_KEY` in the existing Hivemind
Supabase Edge secret store. This is deployment configuration, not a new
credential source.

There are two authorized embedding-provider consumers:

1. The search Edge Function reads `OPENAI_API_KEY` from Hivemind's Edge secret
   store for query embeddings.
2. The operator-run backfill reads the approved provider credential from its
   authorized local or managed job environment for corpus embeddings.

They may use the same approved organizational key; no new provider key is
required. Register each consumer through its normal secret mechanism rather
than transferring a value through source code, command history, or the plan.

Do not:

- Put the OpenAI secret in the Astrid pack, repository, or client environment
  contract.
- Pass the service-role key to `hivemind.search` clients.
- Commit a direct database URL.
- Print, paste into documentation, or commit any secret value.
- Copy Pumpernickel's database URL, Supabase project configuration, or runtime
  environment into Hivemind.

Use a deterministic fake embedder for unit tests and local contract tests.
Only the authorized smoke test and later controlled runs should call the
hosted provider.

The audited readiness applies to the current development machine and its
authenticated CLI/keychain state. A developer working on another machine still
needs their own authorized GitHub and Supabase access; local authentication
files and keychain state should never be handed over or committed.

In this document, “staging” means an authorized, isolated,
production-representative rehearsal target. It does not imply that a new
long-lived Supabase project must be created. Phase 0 must record the approved
target—such as an existing staging target, a temporary database branch/clone,
or a local restore—before risky migrations or index builds are rehearsed.

## Pack changes

The Hivemind upstream pack should own the client update.

Change `hivemind.search` so that it:

1. Preserves its CLI and Astrid input names.
2. Calls the new search Edge Function once.
3. Serializes optional `kinds`, `sources`, `channels`, `authors`, and
   `item_ids` lists safely.
4. Preserves body truncation and the distillation nudge.
5. Passes through additive rank/degradation metadata.
6. Supports an environment-controlled legacy fallback during rollout.
7. Distinguishes validation, authorization, rate-limit, timeout, and server
   failures in its error output.

Change `hivemind.get_item` so that an optional
`representation=python` request for a workflow returns only the whitelisted
Python representation and its version/hash alongside the existing item. The
default invocation and response remain compatible.

Update:

- `executors/search/run.py`
- `executors/search/executor.yaml`
- `executors/get_item/run.py`
- `executors/get_item/executor.yaml`
- search executor tests
- get-item executor tests
- Hivemind pack skill search guidance
- standalone usage documentation

Astrid core needs no new executor or orchestrator. The installed Hivemind pack
remains the canonical shared-knowledge capability.

## Evaluation plan

### Golden set

Create a Hivemind-specific set of at least 100 judged queries, balanced across:

- Exact model and node names.
- Multiple required terms.
- Paraphrases and conceptual questions.
- Settings and troubleshooting questions.
- Named-author questions.
- Channel-scoped questions.
- Time-scoped questions.
- Cross-source questions.
- Questions whose best result is a distillation.
- Questions whose best result is a raw message or resource.
- Expected no-result queries.
- Common spelling and naming variants.
- Long-resource queries whose answer is in a later chunk.
- Workflow-only queries whose best result must come from `kind=workflow`.
- Single-workflow queries constrained to one stable workflow item ID.
- Exact Python imports, functions/classes, variable names, node classes,
  keyword arguments, model filenames, and code fragments.
- Natural-language questions whose relevant evidence exists only in a
  workflow Python chunk.
- Equivalent workflow rows with Python in `payload`, legacy Python only in
  `body`, and both locations, proving source precedence and no double
  indexing.

Keep evaluation queries and relevance judgments free of private content. Store
stable item identities and relevance grades, not fragile row positions.

### Compared systems

Run the same set against:

1. Current two-pass `ILIKE`.
2. Indexed lexical search.
3. Semantic-only retrieval.
4. Hybrid RRF.
5. Hybrid RRF with proposed source weights.
6. Any 384-vs-1536 dimension comparison selected at the semantic gate.

### Metrics

Measure:

- Recall@5 and Recall@10.
- MRR.
- nDCG@10 when graded judgments are available.
- Zero-result rate.
- Exact-name regression rate.
- Distillation retrieval rate.
- Duplicate-item rate after chunk collapsing.
- p50 and p95 latency.
- Semantic degradation rate.
- Embedding coverage by source and model.
- Workflow Python materialization and embedding coverage.
- Workflow code exact-match and semantic Recall@10.
- Duplicate workflow-representation rate.
- Search errors and timeouts.

### Initial quality gates

Fix thresholds before looking at the full evaluation results. Use these
defaults unless Phase 0 records a different value and rationale:

- Hybrid Recall@10 is at least `0.15` absolute above current `ILIKE`.
- Hybrid MRR is at least `0.10` absolute above current `ILIKE`.
- Exact-identifier Recall@10 is at least `0.95` and no more than `0.02`
  absolute below the best lexical configuration.
- Overall hybrid Recall@10 is no more than `0.01` below the better of lexical
  and semantic alone.
- Duplicate-item rate after chunk collapse is exactly `0`.
- Every response contains at most the requested global limit.
- Forced embedding failure returns lexical results in `100%` of valid test
  cases and marks every response degraded.
- On a production-like staging sample, warm end-to-end p95 is at most `1.0 s`
  and p50 at most `500 ms`.
- End-to-end p95 including measured Edge cold starts is at most `2.0 s`.
- Lexical-only/degraded p95 is at most `750 ms`.
- Non-validation search error rate is below `0.5%` in the load test.
- With the provider healthy, unplanned semantic degradation is below `2%`.
- Workflow-code exact-match Recall@10 is at least `0.95`.
- Every judged single-workflow query returns only its requested `item_id`.
- Duplicate indexing of identical workflow Python from `body` and `payload` is
  exactly `0`.

## Test strategy

### Unit tests

- Canonical text for every source type.
- Workflow representation precedence, delimiter extraction, deduplication,
  versioning, and hashing.
- Workflow secret-pattern scanning, quarantine, safe reason codes, snippet
  redaction, and false-positive fixtures.
- Unicode/query normalization.
- Content hashing.
- Deterministic resource chunking.
- Deterministic workflow-Python chunking, including large generated literals
  and parser-fallback cases.
- Vector dimension and finite-value validation.
- RRF fusion and stable tie-breaking.
- Source/status weighting.
- Semantic chunk collapse.
- Filter parsing and validation.
- Body truncation and existing output compatibility.
- Workflow-only and `item_ids` filter serialization.
- Bounded code snippets and opt-in full Python `get_item` responses.
- Snowflake string preservation.
- Retry, supersession, and drop-job behavior.

### SQL tests

- Full-text indexes are used for representative source queries.
- Lexical filters are applied before the final limit.
- Semantic queries use the HNSW index when enabled.
- Active model and dimension are enforced.
- Deleted, opted-out, or otherwise ineligible rows cannot rank.
- Best semantic chunk is selected once per item.
- Hydration returns the correct common row.
- Workflow code matches collapse across lexical/semantic representations to
  one resource and retain the matched representation/snippet.
- `item_ids` securely limits candidates before the final rank/limit.
- The result order is deterministic.

Use `EXPLAIN (ANALYZE, BUFFERS)` during staging validation and preserve compact
plans for representative message, resource, and distillation searches.

### Integration tests

- Public client to Edge Function to RPC to hydrated response.
- Hybrid success.
- Forced embedding timeout with lexical degradation.
- Invalid provider response.
- Empty and overlong queries.
- Kind/source/channel/author/date filters.
- Workflow-only and one-workflow `item_ids` searches.
- Exact and semantic hits that exist only in Python source.
- Workflow `get_item representation=python` without arbitrary payload leakage.
- Quarantined workflow Python cannot rank, produce a snippet, enter an
  embedding request, or be returned by `get_item`.
- Exact global limit.
- `hivemind.get_item` compatibility for returned identities.
- Existing standalone executor invocation.

### Operational tests

- Ten-item dry-run and live embedding smoke test.
- Workflow-representation audit, ten-item remediation dry-run/apply, restart,
  and reconciliation.
- Interrupted backfill and resume.
- Re-embedding only changed canonical content.
- Python-source changes triggering lexical refresh and re-embedding while
  prose-only changes do not duplicate code chunks.
- Worker concurrency with `SKIP LOCKED`.
- Model/dimension mismatch rejection.
- HNSW creation on a representative staging volume.
- Load test with realistic concurrent search traffic.

## Cost and capacity

Embedding API cost is expected to be much smaller than vector storage and
database compute.

At 1.25 million messages:

- 384 float32 dimensions require approximately 1.9 GB of raw vector values.
- 1536 float32 dimensions require approximately 7.7 GB of raw vector values.
- HNSW, table, chunk text, PostgreSQL tuple, and index overhead are additional.
- Resource chunking adds more vectors, though there are far fewer resources
  than messages.
- Workflow Python can be much larger than workflow prose; model its token,
  chunk, vector, and lexical-index cost as a separate cohort rather than
  hiding it inside an average resource length.

Embedding cost can be estimated as:

```text
total canonical input tokens / 1,000,000 × provider price per million tokens
```

Using the discussed `text-embedding-3-small` price assumption of $0.02 per
million input tokens:

- 50 average tokens across 1.25 million messages is approximately $1.25.
- 100 average tokens is approximately $2.50.
- One million 20-token query embeddings is approximately $0.40.

These are dated planning estimates, not a budget guarantee. Recalculate against
the provider's current pricing before backfill.

The capacity gate should therefore focus on:

- Final vector dimension.
- Number of indexed message rows.
- Resource chunk count.
- Workflow prose/Python coverage, code chunk count, and largest indexed Python
  representations.
- HNSW build size and memory.
- Supabase database storage and compute tier.
- Measured query latency under concurrency.

Use these default stop conditions until the owner approves a different budget:

- Pilot embedding API spend is capped at `$25`.
- Full-corpus backfill does not begin if projected vector-table plus HNSW
  storage exceeds `12 GB`.
- Progressive backfill pauses if observed search-related infrastructure cost is
  projected to add more than `$50/month`.
- Active-contract coverage must be `100%` for eligible distillations and
  resources and at least `95%` for the message cohort being enabled.
- Stale or mismatched representation hashes must remain below `0.1%`; any ineligible
  indexed item is a release blocker.

These are rollout guardrails, not claims that the final system will cost those
amounts. Crossing one requires an explicit capacity/budget decision rather
than an automatic continuation.

## Security and abuse controls

The search Edge Function is public-facing and must:

- Keep the embedding and service-role credentials server-side.
- Enforce query and filter size limits.
- Cap candidate and result counts.
- Rate-limit by the strongest available caller/IP signal.
- Use statement and provider timeouts.
- Avoid logging full sensitive query bodies unless explicitly required.
- Return generic provider failure reasons to clients.
- Preserve all current public-corpus eligibility and opt-out rules.
- Treat item IDs as strings throughout JSON handling.
- Treat workflow Python as inert public corpus text: never import, execute, or
  resolve code-controlled paths during search or embedding.
- Whitelist the workflow representation fields returned by `get_item`; never
  return arbitrary payload merely because the caller requested Python.
- Scan workflow Python before public indexing/retrieval, quarantine
  high-confidence credential matches, expose only non-secret reason codes, and
  ensure snippets are redacted as defense in depth.

The client calls only the Edge Function with the public Hivemind credential.
The Edge Function calls the database with its server-side service role. The
hybrid RPC is therefore a hardened trust boundary:

- Implement it as a narrowly scoped `SECURITY DEFINER` function.
- Fully qualify every relation and function reference.
- Set a fixed trusted `search_path` that cannot resolve caller-created objects.
- Revoke execution from `PUBLIC`, `anon`, and ordinary authenticated roles.
- Grant execution only to the service-role path used by the Edge Function.
- Encode corpus eligibility, deletion, opt-out, and distillation-status
  predicates inside the function; service-role RLS bypass must never imply
  "return every row."
- Bound statement time, candidates, filters, and result count inside SQL even
  if Edge validation is bypassed.
- Add a security regression test that inserts an ineligible fixture and proves
  it cannot rank or hydrate.

The search function is read-only. It does not use contributor credentials and
does not change distillation publication status.

## Observability

Record structured, non-secret metrics:

- Request count by mode.
- p50/p95 total, embedding, lexical, semantic, fusion, and hydration latency.
- Candidate counts by retriever.
- Result counts by source type.
- Semantic degradation count and reason.
- Provider errors/timeouts.
- Database statement timeouts.
- Embedding coverage and stale-representation-hash counts.
- Workflow representation coverage by `payload_python`, `body_python`,
  `recoverable`, and `unavailable` cohort.
- Workflow prose/code chunk counts, deduplication failures, and remediation
  cursor/errors.
- Job queue depth, age, retry count, and permanent failures.
- Backfill cursor and throughput.

Do not treat clickthrough as the first relevance signal because the normal
consumer is often an agent. Evaluation judgments and downstream citations are
more meaningful initial signals.

## Implementation task backlog and difficulty

This is the execution checklist for the whole plan. Difficulty describes
technical uncertainty, operational risk, and coordination—not simply typing
time.

| Rating | Meaning |
|---|---|
| **Easy** | Isolated, well-understood work with a narrow blast radius; usually less than half a focused day. |
| **Medium** | Several moving parts but a known implementation pattern; usually half to one-and-a-half focused days. |
| **Difficult** | Cross-component design, retrieval judgment, production database work, or substantial tests; usually two to four focused days if done alone. |
| **Extremely Hard** | Large-scale or security-critical work with material operational risk and unavoidable iteration; usually four or more focused days or a long monitored operation. |

Tasks within a phase may run in parallel when their dependencies allow. The
ratings are deliberately conservative for production-quality work. They are not
meant to be summed mechanically into a calendar estimate.

### Backlog summary

| Difficulty | Tasks | Share |
|---|---:|---:|
| Easy | 5 | 7% |
| Medium | 33 | 47% |
| Difficult | 29 | 41% |
| Extremely Hard | 3 | 4% |
| **Total** | **70** | **100%** |

The three Extremely Hard tasks are the true risk centers:

1. Running the progressive full Discord embedding backfill while live
   ingestion continues.
2. Building and validating the production HNSW index without destabilizing the
   database.
3. Proving that edits, deletes, opt-outs, hashes, and active contracts remain
   consistent throughout the live backfill/index transition.

### Phase 0 tasks — Baseline, access, and fixed gates

| ID | Task | Difficulty | Depends on | Completion signal |
|---|---|---|---|---|
| 0.1 | Confirm the existing Hivemind Supabase project/deployment ownership and verify current CLI, database, Edge deployment, secret-store, and session-mode access. | **Medium** | — | The audited access paths work against the intended Hivemind project; no new database or project is created and nothing is copied from Pumpernickel. |
| 0.2 | Inventory source tables, views, eligibility rules, opt-outs, deletion behavior, RLS, grants, and ingestion paths. | **Difficult** | 0.1 | A reviewed schema/eligibility map covers messages, resources, distillations, and citations. |
| 0.3 | Measure row counts, text/token length distributions, long-resource distribution, workflow prose/Python sizes and representation coverage, and current index sizes. | **Easy** | 0.1 | Reproducible inventory report with dated counts, percentiles, and workflow representation cohorts. |
| 0.4 | Capture current `ILIKE` relevance, latency, timeout, zero-result, and doubled-limit behavior. | **Medium** | 0.2 | Machine-readable baseline results and latency report are checked in. |
| 0.5 | Build the golden-set schema, adapters, metrics, and comparison report generator by porting the reusable Pumpernickel evaluation structure. | **Difficult** | 0.2 | One command compares systems and emits Recall, MRR, nDCG, latency, and failure metrics. |
| 0.6 | Curate and judge at least 100 representative Hivemind queries, including exact identifiers, paraphrases, filters, long resources, workflow-only/single-workflow/code-only evidence, and no-hit cases. | **Difficult** | 0.5 | Golden set has stable item IDs, relevance grades, query categories, and reviewer notes. |
| 0.7 | Model storage, HNSW memory, provider spend, Edge invocations, and database compute for 384- and 1536-dimensional candidates. | **Medium** | 0.3 | Capacity report evaluates the `$25`, `12 GB`, and `$50/month` gates. |
| 0.8 | Inventory workflow representation cohorts and freeze the authoritative Python precedence, delimiters, recovery/quarantine/no-duplication rules, pilot embedding contracts, prose/code chunk candidates, numeric quality gates, and rollback criteria. | **Medium** | 0.2–0.7 | A dated decision record classifies the workflow cohorts and fixes the representation, security, embedding, chunking, evaluation, and rollback contracts. |

### Phase 1 tasks — Indexed lexical search

| ID | Task | Difficulty | Depends on | Completion signal |
|---|---|---|---|---|
| 1.1 | Choose the canonical PostgreSQL text-search configuration and exact indexed expressions for all entity/representation types. | **Medium** | 0.2, 0.6, 0.8 | Decision explicitly resolves `simple` versus existing `english` behavior and bounded workflow-code documents. |
| 1.2 | Add weighted lexical documents/GIN indexes for resource prose/code and distillations, including workflow-Python precedence, secret scanning/quarantine, deduplication, and bounded code documents. | **Medium** | 1.1 | Migrations and fixtures prove safe workflow Python is searchable, quarantined Python is excluded, duplicate body/payload code is indexed once, and representative queries use the indexes. |
| 1.3 | Build the canonical Discord message FTS index safely on staging and production-sized data. | **Difficult** | 0.3, 1.1 | Online index build completes within storage/lock limits and query plans use it. |
| 1.4 | Implement and test Unicode, case, punctuation-preserving, punctuation-separated, and alias normalization for model/node/code identifiers. | **Difficult** | 0.6, 1.1 | Golden fixtures cover dotted, versioned, hyphenated, filename, Python symbol, keyword-argument, and alias forms. |
| 1.5 | Add bounded trigram indexes for high-value short fields such as resource titles and distillation questions. | **Medium** | 1.4 | Trigram candidate queries are indexed and remain inside the capacity gate. |
| 1.6 | Select and implement the full-message exact-identifier path: message trigram index or normalized identifier side index. | **Difficult** | 0.3, 0.7, 1.3–1.5 | Production-sized test proves exact-name quality, acceptable index size, and acceptable write/query cost. |
| 1.7 | Implement the lexical candidate SQL combining FTS, phrase, exact-identifier, and bounded workflow-code fragment arms with deterministic ranks. | **Difficult** | 1.2–1.6 | One ranked identity stream covers all entity/representation types without duplicate items. |
| 1.8 | Add kind, item-ID, source, date, author, and channel filters plus post-limit hydration into the public `unified_feed` shape. | **Difficult** | 0.2, 1.7 | Filters apply before final ranking where required and every identity hydrates correctly. |
| 1.9 | Wrap lexical retrieval in a hardened `SECURITY DEFINER` RPC with fixed `search_path`, qualified relations, eligibility predicates, grants, and limits. | **Difficult** | 0.2, 1.8 | Anon roles cannot execute it directly and ineligible fixtures never rank. |
| 1.10 | Add SQL plan, unit, integration, timeout, workflow-only/single-workflow/code-snippet/security, Snowflake round-trip, and deterministic-order tests. | **Medium** | 1.7–1.9 | Tests pass, ambiguous `item_ids` are rejected, quarantined code never ranks, and saved `EXPLAIN (ANALYZE, BUFFERS)` plans show index use. |
| 1.11 | Run the lexical evaluation and decide whether Phase 1 passes its exact-name, workflow-code, single-workflow, security, relevance, latency, and capacity gates. | **Medium** | 0.4–0.8, 1.10 | Signed gate verdict is `proceed` or lists concrete revisions. |

### Phase 2 tasks — Embedding foundation and semantic pilot

| ID | Task | Difficulty | Depends on | Completion signal |
|---|---|---|---|---|
| 2.1 | Port provider interface, deterministic fake embedder, OpenAI embedder, vector validation, query normalization, and content hashing with attribution. | **Medium** | 0.8 | Provider-independent tests pass without network; one authorized smoke call uses the existing approved credential through Hivemind's server-side secret boundary. |
| 2.2 | Enable pgvector in staging and prepare the production extension migration. | **Medium** | 0.1, 0.7 | Extension and rollback procedure are validated without touching source content. |
| 2.3 | Implement `embedding_contracts` plus one fixed-dimension, contract-keyed, representation- and chunk-aware embedding table and indexes. | **Difficult** | 0.8, 2.2 | Schema forbids dimension mixing, identifies prose versus workflow Python, and supports atomic same-dimension contract transitions. |
| 2.4 | Implement the `entity_type`/`result_kind` identity mapping and exact string handling for Discord snowflakes. | **Medium** | 0.2, 2.3 | Messages, concrete resource kinds, distillations, citations, hydration, and `get_item` agree. |
| 2.5 | Implement canonical representations and hashes for each entity/representation type, including strict workflow Python precedence, secret-state exclusion, deduplication, and contract versioning. | **Medium** | 0.8, 2.1, 2.4 | Python/TypeScript and SQL fixtures produce identical safe prose/code representations and hashes without duplicate or quarantined Python. |
| 2.6 | Implement deterministic paragraph-aware prose and code-aware workflow-Python chunking, overlap, offsets, parser fallback, and best-chunk fixtures. | **Difficult** | 0.3, 0.8, 2.5 | Repeated runs yield identical chunks; long prose and generated-Python golden cases can hit later chunks. |
| 2.7 | Add generalized embed/reembed/drop jobs and source-table triggers that only enqueue work, including changes to workflow Python, prose, and semantics. | **Difficult** | 2.3–2.5 | New, changed, deleted, and ineligible source representations produce the correct idempotent jobs. |
| 2.8 | Implement hardened RPCs for claiming jobs with `SKIP LOCKED`, completing, retrying, superseding, and failing jobs. | **Difficult** | 2.7 | Concurrent worker tests prove no double processing and bounded retries. |
| 2.9 | Implement the bounded `embedding-worker` Edge Function and schedule it with Supabase Cron. | **Difficult** | 0.1, 2.1, 2.6–2.8 | Each invocation processes one bounded batch, records outcomes, and exits inside platform limits. |
| 2.10 | Implement stale-source, deletion, opt-out, failed-contract, and replacement-contract cleanup behavior. | **Difficult** | 2.7–2.9 | Semantic index contains no deleted/ineligible fixture and contract switches preserve the active index. |
| 2.11 | Add durable `embedding_backfill_runs` and per-source cursor/coverage/error state. | **Medium** | 2.3–2.5 | A killed test run resumes from a persisted cursor with intact counters. |
| 2.12 | Build the direct-session, resumable historical backfill CLI with a first workflow-representation remediation/reconciliation stage followed by rate-limited embedding, dry-run/apply, VibeComfy recovery, quarantine, batching, hash skipping, durable checkpoints, and safe logs. | **Difficult** | 0.1, 1.2, 2.1, 2.3–2.6, 2.11 | Interrupt/resume, source preservation, recovery/unavailable/quarantine reporting, retry, partial failure, idempotence, no-duplication, and prose/code coverage tests pass on a production-shaped fixture. |
| 2.13 | After workflow remediation, backfill approved/pending distillations, resources including workflow prose/Python, and a representative Discord sample. | **Medium** | 2.9, 2.12 | Pilot coverage meets its per-representation gate and all failures are classified. |
| 2.14 | Compare 384/1536 dimensions and at least two chunk configurations against the fixed golden set. | **Difficult** | 0.8, 2.13 | Report chooses one production dimension and chunking contract without post-hoc threshold changes. |
| 2.15 | Implement semantic candidate SQL with active-contract filtering, vector distance, requested kind/item-ID filters, and one best chunk across representations per entity. | **Difficult** | 2.3, 2.4, 2.13 | No entity duplicates; matched representation, snippet/chunk, and ranks are deterministic. |
| 2.16 | Build and tune the pilot HNSW index, including `ef_search`, latency, recall, and storage measurements. | **Difficult** | 2.14, 2.15 | Pilot meets semantic relevance and latency gates within the capacity budget. |
| 2.17 | Add lifecycle, worker, representation-remediation/backfill, vector, workflow code canonicalization/chunking/change/deduplication/quarantine, semantic SQL, dimension-mismatch, and failure-mode tests. | **Difficult** | 2.1–2.16 | Payload-only, legacy-body-only, duplicated, changed, huge generated, parser-fallback, unavailable, and quarantined workflow fixtures pass the semantic, concurrency, and recovery suites. |

### Phase 3 tasks — Hybrid search service

| ID | Task | Difficulty | Depends on | Completion signal |
|---|---|---|---|---|
| 3.1 | Implement Edge request parsing, validation, bounded arrays including string `item_ids`, modes, timestamps, query length, and result caps. | **Medium** | 1.9 | Invalid requests fail predictably before provider/database work. |
| 3.2 | Implement one normalized query embedding per request with timeout, vector validation, and best-effort per-instance cache. | **Medium** | 2.1, 2.14 | Cache, timeout, wrong-dimension, and provider-failure tests pass. |
| 3.3 | Implement the single hybrid `SECURITY DEFINER` RPC combining lexical candidates, filtered semantic candidates, selective-filter over-fetch/iteration, representation/chunk collapse, RRF, source/status weights, global limit, and hydration. | **Difficult** | 1.7–1.11, 2.14–2.17 | One database snapshot produces secure, duplicate-free, deterministic mixed results for all filters and modes, including workflow-only, item-ID, author, channel, and date filters. |
| 3.4 | Implement conservative approved/pending distillation and source weighting as configuration, not scattered constants. | **Medium** | 0.8, 3.3 | Weight sweeps are reproducible and cannot overpower both retrieval arms. |
| 3.5 | Implement lexical degradation, `semantic_degraded`, reason codes, match metadata, and no-distillation nudge semantics. | **Medium** | 3.2, 3.3 | Forced outages return useful lexical results in every valid test case. |
| 3.6 | Add public request rate limiting and abuse caps appropriate to the available caller/IP signals. | **Difficult** | 0.1, 3.1 | Load/abuse tests prove caps without breaking normal installed clients. |
| 3.7 | Harden the Edge/RPC trust boundary, service-role use, fixed search path, grants, eligibility checks, and secret-safe errors/logs. | **Difficult** | 0.2, 1.9, 3.1–3.6 | Security tests prove anon cannot bypass the Edge Function and service-role bypass cannot leak ineligible rows. |
| 3.8 | Add structured latency, candidate, source, degradation, provider, statement-timeout, and error metrics. | **Medium** | 3.3–3.7 | Staging dashboards/log queries expose every metric named in Observability. |
| 3.9 | Run concurrency, cold-start, provider-timeout, database-timeout, malformed-vector, and partial-outage tests. | **Difficult** | 3.5–3.8 | Load report meets error and latency gates or yields a revision list. |
| 3.10 | Run lexical/semantic/hybrid/weighted evaluation and issue the Phase 3 gate verdict. | **Medium** | 0.8, 3.9 | Numeric relevance, exact-name, latency, and degradation gates pass. |

### Phase 4 tasks — Hivemind pack integration

| ID | Task | Difficulty | Depends on | Completion signal |
|---|---|---|---|---|
| 4.1 | Replace the executor's two PostgREST `ILIKE` calls with one Edge Function request. | **Medium** | 3.10 | Existing basic invocation returns the new globally ranked response. |
| 4.2 | Preserve existing inputs and add optional channels, authors, item IDs, and mode without breaking standalone or Astrid calls. | **Easy** | 4.1 | Old commands parse unchanged and new inputs serialize safely. |
| 4.3 | Preserve body truncation and nudge behavior while passing through additive rank/degradation and matched-representation/snippet metadata. | **Easy** | 4.1 | Output contract tests cover legacy and new fields. |
| 4.4 | Add environment-controlled `legacy`, `lexical`, `semantic`, and `hybrid` rollout modes and safe fallback behavior. | **Medium** | 4.1–4.3 | Operators can switch modes without changing source or exposing secrets. |
| 4.5 | Update `executor.yaml`, pack version/metadata, Hivemind skill guidance, standalone examples, and deployment documentation. | **Easy** | 4.2–4.4 | Discovery and documentation accurately describe the new behavior. |
| 4.6 | Extend `hivemind.get_item` with the concrete `kind=workflow` alias and opt-in whitelisted `representation=python` implementation, then add executor/API-contract/error-shaping/Snowflake/compatibility/workflow-only/item-ID/code-snippet tests. | **Medium** | 4.1–4.5 | Legacy `kind=resource` remains compatible; the workflow alias and Python retrieval pass installed/standalone suites without arbitrary payload or quarantined-source leakage. |
| 4.7 | Publish a staging/canary pack revision and smoke-test it from Astrid, Codex, Claude, Hermes, and standalone Python where available. | **Medium** | 4.6 | Each supported harness either passes or has a documented environment-specific exception. |

### Phase 5 tasks — Progressive production backfill

| ID | Task | Difficulty | Depends on | Completion signal |
|---|---|---|---|---|
| 5.1 | Define message cohorts, snapshot/high-water boundary, live incremental-job overlap, ordering, stop conditions, maintenance windows, and operator ownership. | **Medium** | 0.3, 0.7, 2.14 | Reviewed runbook proves every row belongs to either the historical snapshot or incremental path and orders recent/high-signal, topic, general, and historical cohorts. |
| 5.2 | Validate production secrets, direct connection, provider quotas, database headroom, backups, alerts, and recovery commands. | **Medium** | 0.1, 5.1 | Signed preflight is green without printing secrets. |
| 5.3 | Run/reconcile production workflow representation remediation and quarantine review, then backfill and verify all eligible distillations and resource representations under the selected active contract. | **Medium** | 2.12–2.17, 5.2 | Eligible prose coverage is 100%; every recoverable safe workflow has one canonical Python source; unavailable/quarantined rows are explained; stale representation hashes are below 0.1%; no Python is double indexed. |
| 5.4 | Backfill and verify the recent/high-signal Discord cohort. | **Difficult** | 5.3 | Cohort reaches at least 95% coverage and passes relevance, latency, and spend gates. |
| 5.5 | Run and babysit the remaining 1.25-million-message progressive backfill with pause/resume and cohort gates. | **Extremely Hard** | 5.4 | Every approved cohort completes or stops safely at a documented gate; no source data is modified. |
| 5.6 | Build/rebuild and validate the production HNSW index at the approved coverage point without destabilizing ingestion or search. | **Extremely Hard** | 5.4 or 5.5 | Index completes inside lock/storage/latency limits and rollback is rehearsed. |
| 5.7 | Track storage, compute, provider spend, queue depth, failures, latency, and degradation during every cohort. | **Difficult** | 3.8, 5.3–5.6 | Each cohort has a dated operational report and explicit proceed/stop verdict. |
| 5.8 | Prove live consistency across the snapshot boundary: reconcile representation hashes, active contracts, chunk counts, duplicate identities, concurrent edits, deletes, opt-outs, and citation/get-item compatibility. | **Extremely Hard** | 5.1, 5.3–5.6 | No gap exists between historical and incremental processing, no ineligible item remains indexed, and every mismatch is explained or repaired. |
| 5.9 | Re-run the frozen golden set after each material cohort and compare against the pre-backfill baseline. | **Medium** | 0.8, 5.3–5.6 | No cohort crosses a relevance or exact-name regression gate. |
| 5.10 | Drill worker failure, provider outage, interrupted backfill, HNSW failure, lexical-only operation, and contract rollback. | **Difficult** | 5.6–5.9 | Operators complete the recovery checklist using staging/production-safe procedures. |

### Phase 6 tasks — Default switch and completion

| ID | Task | Difficulty | Depends on | Completion signal |
|---|---|---|---|---|
| 6.1 | Enable hybrid by default for a small canary while retaining explicit lexical and legacy overrides. | **Medium** | 4.7, 5.10 | Canary uses hybrid and rollback remains one configuration change. |
| 6.2 | Ramp the default across clients while watching quality, latency, error, degradation, storage, and cost gates. | **Difficult** | 6.1 | Every ramp stage has a proceed verdict; no unresolved release-blocking metric remains. |
| 6.3 | Rehearse rollback from default hybrid to lexical and legacy modes under simulated provider/database failures. | **Difficult** | 6.1 | Rollback succeeds within the agreed operational window without losing source or index data. |
| 6.4 | Run the bounded production observation window and triage all search, worker, and backfill anomalies. | **Medium** | 6.2, 6.3 | Observation window closes with no unresolved high-severity issue. |
| 6.5 | Publish the final relevance, latency, coverage, storage, provider-spend, infrastructure-cost, and incident report. | **Medium** | 6.4 | Report compares every fixed gate with actual production results. |
| 6.6 | Decide and execute legacy `ILIKE` deprecation, retention, or removal based on the observation report. | **Medium** | 6.5 | Decision is recorded; any removal has a tested migration and fallback story. |
| 6.7 | Finalize the operator runbook, pack skill, standalone docs, workflow-only/single-workflow/code-search examples, architecture status, and ownership handoff. | **Easy** | 6.5, 6.6 | A new operator can search, inspect workflow Python, monitor, remediate/backfill, pause, resume, degrade, and roll back from documented commands. |

### Parallel work lanes

The backlog can be shortened without weakening gates by running these lanes in
parallel:

- **Evaluation lane:** 0.4–0.6, then 1.11, 2.14, 3.10, 5.9.
- **Workflow representation work:** folded into 0.8, 1.1–1.10, 2.5–2.6,
  2.12–2.13, and 2.17 rather than maintained as a separate project.
- **Lexical/database lane:** 0.2–0.3, then Phase 1 schema/RPC work.
- **Embedding lifecycle lane:** 2.1–2.13 and 2.17 after the representation and
  embedding contracts are frozen.
- **Semantic SQL lane:** 2.14–2.16, then 3.3–3.5.
- **Edge/security lane:** 3.1–3.2 and 3.6–3.9.
- **Pack lane:** manifest/docs test preparation can begin during Phase 3, but
  the endpoint switch waits for 3.10.
- **Operations lane:** capacity, dashboards, runbooks, and cohort planning can
  begin before the semantic pilot completes.

### Critical paths

The fastest useful lexical release follows:

```text
0.1 → 0.2/0.3 → 0.8 → 1.1 → 1.2/1.3/1.4
  → 1.7 → 1.8 → 1.9 → 1.10 → 1.11
```

The hybrid beta follows:

```text
0.5–0.8
  → 2.1–2.8
  → 2.11–2.17
  → 3.1–3.10
  → 4.1–4.7
```

Full production completion follows:

```text
hybrid beta → 5.1–5.10 → 6.1–6.7
```

## Rollout plan

### Phase 0 — Baseline and decisions

Deliver:

- Current-search latency and relevance baseline.
- Golden-set schema and first judged queries.
- Corpus token-length and resource-length distributions, including separate
  workflow prose/Python sizes and representation cohorts.
- 384-vs-1536 capacity estimate.
- Frozen workflow representation precedence, delimiter, recovery, hashing,
  unavailable-state, and no-duplication contract.
- Verified access to the existing Hivemind project, Edge deployment,
  secret store, and database path used for migrations/backfill.
- The existing approved OpenAI credential registered as a Hivemind Edge
  secret, without exposing it to the repository or pack.

Exit gate:

- Evaluation set and success thresholds are fixed.
- Embedding model/dimension pilot candidates are approved.
- No secret is required by the public pack.

### Phase 1 — Indexed lexical search

Deliver:

- Resource and distillation `tsvector` indexes.
- Workflow Python indexing and bounded code-fragment retrieval.
- Indexed message candidate query on the underlying table.
- One server-side lexical search RPC with global ranking and limit.
- Author, channel, kind, item-ID, source, and date filters.
- Hydration through the common Hivemind row shape.
- Workflow representation audit/remediation command and staging rehearsal.
- Workflow-only, single-workflow, code-snippet, and opt-in full-Python
  retrieval.
- Pack opt-in mode for the new lexical endpoint.

Exit gate:

- Query plans show index usage.
- Lexical search outperforms or matches current `ILIKE` on exact queries.
- Workflow-code exact-match and one-workflow gates pass.
- Every recoverable staging workflow has one authoritative Python
  representation and duplicate indexing is zero.
- Current output compatibility and no-result behavior pass.

This phase provides immediate value with no embedding API dependency.

### Phase 2 — Shared semantic index and pilot

Deliver:

- pgvector migration.
- Chunk-aware `content_embeddings`.
- Generalized incremental job table and triggers.
- Ported canonicalization, hashing, vector validation, and worker behavior.
- Separate workflow prose/Python canonicalization, code-aware chunking,
  change detection, and result collapse.
- Resumable human-run backfill tool.
- Distillation/resource backfill after workflow representation remediation.
- Representative Discord sample backfill.
- Dimension and chunk-size comparison.

Exit gate:

- Coverage and hash correctness meet the pilot threshold.
- Semantic retrieval improves paraphrase/resource and workflow-code queries.
- Storage and latency remain within the approved envelope.

### Phase 3 — Hybrid search Edge Function

Deliver:

- Server-side query embedding.
- One hybrid database RPC accepting query text plus an optional query vector.
- Chunk collapse.
- Database-side RRF, global limiting, hydration, and conservative source/status
  weights.
- Query timeout and lexical degradation.
- Structured response metadata.
- Workflow matched-representation and bounded code-snippet metadata.
- Rate limits and operational metrics.

Exit gate:

- Hybrid passes relevance, latency, degradation, and security tests.
- No public client receives a private credential.

### Phase 4 — Pack integration

Deliver:

- One-call `hivemind.search` client.
- Backward-compatible inputs and additive output metadata.
- Workflow-only and bounded single-workflow search through `kinds` and
  `item_ids`, plus opt-in full Python retrieval through `get_item`.
- `legacy`, `lexical`, and `hybrid` rollout modes.
- Updated executor manifest, tests, skill, and documentation.
- Standalone smoke-test instructions.

Exit gate:

- Astrid and standalone invocations return equivalent results.
- `hivemind.get_item` resolves every returned identity.
- A forced semantic outage remains usable.

### Phase 5 — Progressive message backfill

Backfill in measured cohorts:

1. Recent/high-signal channels.
2. Remaining topic channels.
3. General channels.
4. Historical tail.

At every cohort:

- Measure storage growth.
- Measure HNSW/query latency.
- Re-run the golden set.
- Inspect failure and stale-representation-hash rates.
- Stop automatically at the approved capacity boundary.

Before the resource cohort, run and reconcile the workflow representation
remediation. Do not embed a legacy workflow until it is classified as
`payload_python`, `body_python`, `recoverable`, or `unavailable`; unavailable
Python does not block prose indexing but must remain visible in coverage.

Exit gate:

- The agreed coverage target is reached.
- Search quality remains stable or improves.
- Monthly database cost is understood.

### Phase 6 — Default switch and cleanup

Deliver:

- Hybrid becomes the default.
- Legacy mode remains available for a bounded observation window.
- Remove doubled-limit and two-request behavior.
- Publish final evaluation and operational report.
- Decide whether to retire legacy `ILIKE`.

Do not remove the legacy path until production metrics and a rollback rehearsal
are complete.

## Developer handoff

The plan is intended to be executable without rediscovering its architecture:

| Role | Audited local checkout |
|---|---|
| Implementation repository | `/Users/peteromalley/Documents/banodoco-workspace/hivemind` |
| Retrieval/evaluation reference | `/Users/peteromalley/Documents/Pumpernickel` |
| Workflow representation/export reference | `/Users/peteromalley/Documents/reigh-workspace/vibecomfy` |
| Planning document | `/Users/peteromalley/Documents/reigh-workspace/Astrid/docs/architecture/hivemind-hybrid-search-plan.md` |
| Installed pack snapshot (inspect only) | `/Users/peteromalley/.astrid/packs/hivemind/revisions/hivemind` |

These paths describe the audited machine, not a portable repository layout.

- Make backend and pack changes in the Hivemind source repository, not in an
  installed Astrid revision.
- Use the existing Hivemind Supabase project and repository deployment
  workflow. Do not initialize another database or Supabase project.
- Treat the Pumpernickel files listed above as implementation references. Port
  the narrow algorithms and test patterns; do not import Pumpernickel as a
  package or reuse its database configuration.
- Reuse VibeComfy's existing ready-template/external-workflow Python exporters
  and Hivemind upload representation contract. Do not invent a second
  generator in Hivemind or execute stored workflow Python during remediation.
- Register the already-approved organizational OpenAI key in Hivemind's Edge
  secret store before the one live provider smoke test. Do not put its value in
  a ticket, plan, shell transcript, commit, or pack configuration.
- Configure the operator-run backfill through an authorized local or managed
  secret environment; do not assume an Edge secret is automatically visible to
  a local script.
- Preserve the current dirty Hivemind working tree and coordinate around
  pre-existing modifications and untracked files before editing overlapping
  paths.
- Keep Discord snowflakes as strings at every JSON and shared-index boundary.
- Run the Hivemind repository's existing test command,
  `python3 -m unittest discover tests/`, plus the new Deno/SQL/integration
  checks introduced by this project.
- Commit this plan with the implementation repository, or link it from a
  Hivemind-owned issue/brief, before handing work to a developer on another
  machine. This Astrid copy is currently planning context, not deployed code.

On the current machine, no further product or architectural context is
required before implementation beyond the remaining Edge-secret registration
and explicit backfill-secret wiring.

For another machine, the handoff should name—but never contain values for:

- the Hivemind repository and implementation branch;
- the intended Supabase project reference and CLI login/link procedure;
- the required database, Edge deployment, and secret-management roles;
- the approved process for obtaining direct/session database connectivity;
- the person responsible for registering the provider secret in Hivemind; and
- the approved mechanism for exposing that credential to the backfill job.

No secrets or machine-local authentication artifacts should be copied into the
handoff.

## Suggested change boundaries

Keep reviewable deployment boundaries:

1. Evaluation harness and current baseline.
2. Workflow representation contract, remediation tool, and staging report.
3. Lexical schema/RPC, workflow-code search, and tests.
4. Vector schema, worker, and pilot embedding backfill.
5. Hybrid Edge Function and API tests.
6. Hivemind pack client and documentation.
7. Progressive production backfill and default switch.

Avoid one migration that enables pgvector, backfills the corpus, builds HNSW,
deploys the Edge Function, and switches every client at once.

## Rollback and recovery

- Keep schema changes additive during rollout.
- Keep a server-side flag and client override for `legacy` or `lexical`.
- If the embedding provider fails, degrade per request.
- If semantic quality regresses, disable semantic retrieval without deleting
  vectors.
- If HNSW causes capacity pressure, drop or rebuild the index during an
  approved maintenance operation; retain embedding rows for diagnosis.
- Backfill resumes from its durable cursor and content hashes.
- Workflow remediation resumes from its separate durable cursor and never
  restores an older representation over a newer authoritative source.
- Failed/stale jobs remain inspectable and retryable.
- Never roll back by deleting source content.

## Risks and mitigations

### Ordinary views cannot be indexed

Mitigation: retrieve candidates from indexed source tables and hydrate through
`unified_feed` afterward.

### Large messages table makes vector indexing expensive

Mitigation: evaluate 384 dimensions, backfill in cohorts, build HNSW after bulk
load, and retain lexical search as a complete fallback.

### Long resources are poorly represented by one vector

Mitigation: deterministic chunking and best-chunk-per-item collapse.

### Huge workflow Python overwhelms prose relevance or index capacity

Mitigation: keep workflow prose and Python as separately labeled
representations, use code-aware bounded chunks, measure code-specific token and
vector counts, apply one-best-representation collapse, and keep exact code
retrieval available even if evaluation requires conservative semantic-code
weighting.

### Workflow Python is duplicated between body and payload

Mitigation: enforce strict `payload.python_source` precedence, extract only
recognized legacy body blocks, hash representations independently, and make a
zero-duplicate reconciliation gate block rollout.

### Legacy workflow source cannot be recovered

Mitigation: classify and report the row as `unavailable`, preserve its prose
and workflow-semantics search, never synthesize code from prose, and permit a
later authoritative source repair without changing the workflow identity.

### Workflow Python contains an accidentally committed credential

Mitigation: deterministic pre-publication scanning, fail-closed new ingestion,
historical quarantine, snippet redaction, non-secret reason codes, and a
documented remove/rotate incident path. Never rely on embeddings or model
behavior to hide a secret.

### Source weighting hides better raw evidence

Mitigation: modest weights, golden-set evaluation, and rank metadata that makes
the effect inspectable.

### Query embedding adds latency or an external dependency

Mitigation: short timeout, best-effort cache, lexical degradation, and an
explicit lexical mode.

### Edge Function instances do not share an in-memory cache

Mitigation: begin with per-instance best-effort caching because query embedding
cost is small. Add a bounded database or external cache only if measurements
justify the complexity.

### Shared organizational credentials blur system ownership

Mitigation: Pumpernickel supplies patterns and code only. The approved provider
credential is registered separately at Hivemind's deployment boundary and is
never inherited through Pumpernickel configuration, exposed to clients, or
committed to either repository.

### Backfill races with new edits

Mitigation: content hashes, idempotent upserts, stale-job supersession, and
incremental jobs active before or during historical backfill.

### Semantic chunks produce duplicate resource results

Mitigation: collapse to one best chunk per `(entity_type, item_id)` before
assigning semantic rank.

## Acceptance criteria

The project is complete when:

- `hivemind.search` accepts its existing arguments unchanged.
- One request returns one globally limited and deterministically ranked list.
- Indexed lexical retrieval covers messages, resources, and distillations.
- Semantic retrieval uses one shared, chunk-aware embedding table.
- `kinds=["workflow"]` searches only workflows, and bounded string `item_ids`
  can constrain search to one selected workflow.
- Workflow lexical retrieval searches the exact canonical Python
  representation, including imports, symbols, node classes, model filenames,
  keyword arguments, and code fragments.
- Workflow semantic retrieval uses separately labeled prose and
  `workflow_python` chunks and collapses them to one workflow result.
- When identical Python is present in `payload.python_source` and `body`, it is
  indexed and embedded exactly once.
- Python-source changes refresh lexical state and enqueue re-embedding without
  changing the workflow item identity.
- Every recoverable historical workflow has a materialized, versioned, hashed
  Python representation; every unavailable row has an explicit reason and
  remains prose-searchable.
- Python-source hits return a bounded matched snippet, and
  `hivemind.get_item representation=python` returns the full whitelisted code
  without exposing arbitrary payload.
- Workflow Python that matches the secret scanner is quarantined before
  lexical indexing, embedding, snippets, or full-code retrieval; logs and
  metadata never contain the matched secret.
- A query is embedded at most once per request.
- Messages and distillations are not redundantly chunked.
- Long resources can match through a non-leading chunk.
- Hybrid ranking exposes match type and component ranks.
- Approved distillations receive a measured, non-dominating preference.
- All returned Discord snowflakes survive JSON round-trips exactly.
- Semantic failure automatically returns lexical results with
  `semantic_degraded: true`.
- No OpenAI, service-role, or database credential is exposed to the pack.
- Backfill is resumable, idempotent, hash-aware, and bounded.
- Workflow representation remediation is separately resumable, idempotent,
  source-preserving, auditable, and completed before resource embedding
  backfill.
- New and changed source rows are incrementally embedded.
- Deleted or ineligible content is removed from the semantic index.
- The Hivemind golden-set report demonstrates the agreed relevance improvement.
- Staging load tests meet the agreed p95 latency and error thresholds.
- Rollback to lexical or legacy mode is rehearsed.
- The Hivemind skill and executor documentation describe the new behavior.

## Recommended first implementation slice

Begin with Phase 0 and Phase 1:

1. Create the golden-set harness.
2. Capture the current `ILIKE` baseline.
3. Freeze and audit the workflow representation contract.
4. Rehearse workflow representation remediation on a bounded staging sample.
5. Add the lexical RPC over indexed source tables, including workflow Python.
6. Switch a local `hivemind.search` build to the lexical RPC behind a flag.
7. Evaluate exact/code search, workflow-only and single-workflow filters,
   latency, and global limiting.

Only then enable pgvector and run a small semantic pilot over distillations,
workflow prose/Python, other resources, and a representative Discord sample.
This gives Hivemind a useful search improvement quickly and establishes
evidence for the storage-sensitive dimension and backfill decisions.
