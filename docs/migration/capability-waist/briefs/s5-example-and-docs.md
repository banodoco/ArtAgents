# S5 — Worked example + docs

**Context:** RFC + MIGRATION-PLAN §6 (inline example draft). **Profile:** solo / light / low. Depends on S4.

## Outcome
A newcomer reads one page, sees that a fal model and a Remotion element are the same contract shape, and writes their own capability from the template. (This is the third success metric: a third-party pack author ships a typed capability without touching core.)

## Scope (IN)
1. **Worked example** under `docs/examples/capability-contract/`: a fal **model** and a Remotion **element** side by side in contract form (MIGRATION-PLAN §6), each with `consumes`/`produces` artifact types + `runtime` adapter, plus a one-paragraph "how composition type-checks" walkthrough via the real timeline → render path.
2. **Guide** in `docs/contracts/`: the capability/artifact/scoped-config contract — the three primitives, composition = type-match + id-reference, the open-string fallback (and the Reigh-boundary leniency rule).
3. **Update `docs/templates/element/`** to the post-S4 form: `consumes`/`produces`/`runtime`, no required `component.tsx` framing.

## Anti-scope (OUT)
No code changes beyond making the example validate. One canonical example + one guide, not a tutorial series.

## Done / GATE
The example manifests validate against the real `ArtifactTypeRegistry`; docs build; the template produces a loadable capability.
