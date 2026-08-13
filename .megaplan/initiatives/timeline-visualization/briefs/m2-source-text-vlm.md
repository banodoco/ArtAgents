# Milestone 2 — Source Text and VLM Proof

## Outcome

Extend the implemented milestone-one navigation spine with
provenance-correct transcript/text inspection, then iteratively render and
test the complete agent journey until unfamiliar VLMs reliably understand it.

Read first:

- `.megaplan/initiatives/timeline-visualization/NORTHSTAR.md`
- `.megaplan/initiatives/timeline-visualization/briefs/timeline-visualization.md`
- `.megaplan/initiatives/timeline-visualization/decisions/timeline-visualization-plan.md`
- `docs/architecture/timeline-visualization-agent-navigation.md`

The last file is milestone one's binding implemented contract. Extend it; do
not create a second navigation system.

## Required scope

1. Normalize explicitly linked transcript sources and preserve segment
   timestamps, text, speakers, and word timing only when it actually survives
   in source data.
2. Map source transcript time through clip trim and speed:

   ```text
   timeline_time = clip.at + (source_time - clip.from) / clip.speed
   ```

   Clip intervals to the source window and timeline bounds.
3. Represent one source transcript segment as `TS` and each timeline use as a
   distinct `SP`; repeated source use must never collapse occurrences.
4. Keep authored timeline captions/text, mapped speech, and pixel-baked text
   distinct. Baked text is `not_inspected` without recorded OCR evidence.
5. Add `SPEECH`, `CAPTION`, and `OTHER TEXT` lanes, compact excerpts, and a
   paginated text-map image. Full evidence lives in
   `transcript-index.json` and `structure.md`.
6. Add actions among `CL`, `AS`, `TS`, and `SP` while retaining the frozen
   root id map and parent lineage.
7. Harden missing transcript, changed/missing media, remote source, snapshot
   drift, and unsupported extraction behavior. Never infer a nearby transcript
   file or silently substitute media.
8. Run the complete image-only and stdout-discovery VLM gates, revise visual
   grammar where evidence shows ambiguity, and convert every failure into an
   automated fixture, invariant, or diagnostic.

## Critical fixtures

- source transcript clipped at both clip edges;
- speed changes and non-zero source trims;
- one transcript segment reused by multiple clips;
- speakers and authored captions active at the same time;
- missing explicit transcript provenance;
- visual text with no OCR evidence;
- exact original still versus thumbnail, source approximation, generation
  reference/output, and rendered sample;
- snapshot version 7 versus current version 8;
- project timeline id collisions;
- the full desert-plant overview → range/shot → clip → original journey.

## VLM gate

- Every fixture declares an exact ordered image bundle and schema-constrained
  questions.
- Give the evaluator only those images and generic `reading-guide.md`; withhold
  source JSON, `structure.md`, and ground truth.
- Ask exact questions about next focus id, parent id, source asset, active
  layers, evidence type, transcript mapping, original/derived status, and
  snapshot/current state.
- Require exact critical answers, ±0.05-second timing, at least 95% overall,
  and three consecutive fresh-session passes per critical fixture.
- Run a separate fresh-agent discovery test beginning only with CLI stdout.
- Record model/settings, prompts, hashes, answers, and scores as ignored run
  evidence.

## Done

The epic is done only when the public command supports every locked scope; the
agent can traverse overview → segment → clip → exact original and inspect
caption/speech evidence using generated actions; children remain frozen to the
root snapshot; original/derived media and all text evidence types are
unambiguous; focused and relevant broader tests pass; and all VLM gates satisfy
the locked thresholds with every prior failure represented by durable test
evidence.
