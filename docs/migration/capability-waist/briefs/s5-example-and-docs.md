# S5 — Worked example + docs

**Read first:** RFC + MIGRATION-PLAN (§6 inline example draft). **Profile:** solo / light / low.
**Why:** docs + a validated example; lowest stakes; the contract is real by now. Depends on S4.

## Outcome
A newcomer can read one page and see that a fal model and a Remotion element are the same contract shape, then write their own capability from the template.

## Scope (IN)
1. **Worked example** under `docs/examples/capability-contract/`: a fal **model** and a Remotion **element** side by side in contract form (per plan §6), each with `consumes`/`produces` artifact types + `runtime` adapter, plus a one-paragraph "how composition type-checks" walkthrough using the real timeline → render path.
2. **Guide** in `docs/contracts/`: the capability/artifact/scoped-config contract explained — the three primitives, the composition rule (type-match + id-reference), the open-string fallback.
3. **Update `docs/templates/element/`** (`element.yaml`, `component.tsx`, `STAGE.md`) to the post-S4 form: `consumes`/`produces`/`runtime`, no required `component.tsx` framing.

## Anti-scope (OUT)
No code changes beyond what's needed to make the example validate. Not a tutorial series — one canonical example + one guide.

## Done criteria / GATE
The example manifests validate against the real `ArtifactTypeRegistry`; docs build; the template produces a loadable capability.

## Touchpoints
`docs/examples/capability-contract/`, `docs/contracts/`, `docs/templates/element/`.
