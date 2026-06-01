# Quote Scout

**Executor**: `editorial.quote_scout`  
**Status**: implemented  
**Pipeline step**: 6 (quote extraction before pool building)

Scans the transcript for quotable lines suitable for hype clips. The
executor reads `transcript.json` from editorial.transcribe and uses an
LLM to identify high-impact, emotionally resonant, or contextually
interesting quotes. Each candidate includes the original text, timestamps,
speaker (when available), and a relevance score.

Output is `quote_candidates.json` — a structured list of quote snippets
with metadata. Downstream arrangement and refinement steps use these
candidates to select and sequence spoken-word clips in the final cut.

## CLI quick-start

```bash
python -m astrid executors run editorial.quote_scout -- \
  --transcript ./out/transcript.json --out ./out
```

With an explicit env file for API credentials:

```bash
python -m astrid executors run editorial.quote_scout -- \
  --transcript ./out/transcript.json --env-file .env.local --out ./out
```

## Inputs

| Name       | Type | Required | Description                              |
|------------|------|----------|------------------------------------------|
| transcript | file | no       | Transcript JSON from editorial.transcribe |
| env_file   | file | no       | Optional environment file for API credentials |

## Outputs

| Name             | Type | Path                            | Description                     |
|------------------|------|---------------------------------|---------------------------------|
| quote_candidates | file | `{out}/quote_candidates.json`   | Quotable line candidates with metadata |

## Pipeline position

Step 6 of the editorial pipeline. Depends on the full early editorial
stack plus scene descriptions from understanding.scene_describe.
Quote candidates feed into pool_build, arrange, and refine.

## Depends on

- `editorial.transcribe`
- `editorial.scenes`
- `editorial.quality_zones`
- `editorial.shots`
- `editorial.triage`
- `understanding.scene_describe`
