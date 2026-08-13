# Debugging Renderers

This guide covers debugging a pluggable timeline renderer you are authoring:
static validation, the deterministic smoke test, facade smoke renders, the
failure replay bundle, and SDK-level debugging. The normative wire contract,
manifest rules, artifact/audio rules, and the golden path live in
[render-backend-v1.md](../contracts/render-backend-v1.md); this guide is the
troubleshooting companion.

## 1. Static validation

`renderers validate <path>` checks a pack directory statically: manifests
parse and conform to their schemas, content roots and runtime entrypoint files
exist, and every `extensions.rendering` manifest validates without importing
or executing backend code. `packs validate`/`packs status` cover the same
checks for any pack directory:

```bash
python3 -m astrid renderers validate .            # inside the pack directory
python3 -m astrid renderers validate ./acme_wave  # or by path
python3 -m astrid packs status                    # validate every discovered pack
```

Common static failures for renderer packs:

- **`id` first segment mismatch** — a renderer id must begin with the owning
  pack id (`acme_wave.wave`, not `rendering.wave`), and the pack folder must
  be named exactly like the pack id for `packs install`.
- **`required_permissions` not a subset** — the renderer manifest's
  `required_permissions` must be a subset of the permissions disclosed by
  `pack.yaml`.
- **Missing `render` operation** — a renderer manifest must declare `render`
  (a planner `plan`, a finalizer `finalize`); `support` is optional.
- **Manifest path escapes** — `extensions.rendering` paths must stay inside
  the pack root after symlink resolution.

## 2. The generated smoke test

The scaffold ships `test_renderer.py`, which drives `render.py` through a real
subprocess and checks the result shape and artifact hash:

```bash
python3 -m pytest -q test_renderer.py
```

The scaffold renderer is deterministic (no timestamps or random ids), so the
test doubles as a byte-stability smoke check: two renders of the same request
must produce identical media and identical result JSON. When you replace
`render.py` with a real implementation, keep `test_renderer.py` green — it is
the fastest regression net for the wire shape.

## 3. The `smoke` verb

After a trusted install, smoke the discovered renderer through the public
service:

```bash
python3 -m astrid renderers smoke acme_wave.wave --out ./out/smoke.mp4
```

The smoke verb runs a deterministic direct-service render in a fresh temporary
workspace (no ledger, no project mutation) and prints the output video path
plus its provenance sidecar path. It requires the candidate to be
execution-eligible — an environment-discovered or untrusted candidate is
reported as ineligible with the reason. `renderers list` prints every
discovered renderer/planner/finalizer qualified id and `renderers inspect
<id>` shows one candidate's manifest fields, source pack, and trust
eligibility; both accept `--pack-root PATH` (repeatable) for extra pack roots.

To render a real timeline through the stable facade (the pipeline path), read
the provenance sidecar the facade writes:

```bash
python3 -m astrid executors run rendering.render \
  --out ./out \
  --input timeline=./out/hype.timeline.json \
  --input backend=acme_wave.wave
```

On success you get `./out/hype.mp4` plus `./out/hype.mp4.provenance.json`.
Read the sidecar to verify the resolution evidence: source pack, manifest
digest, alias chain, override, trust eligibility, support decision, input
hashes, artifact hash/profile, audio ownership, normalization, attachments,
and your `backend_fragments` namespace. On failure there is **no sidecar** —
a sidecar is the publication commit marker and is only written after the
artifact validates.

## 4. The replay bundle

A failed invocation retains (or emits) a self-contained replay bundle instead
of publishing: the resolved request or finalize request, localized timeline/
asset registry and input hashes, only your implementation's configuration
namespace, qualified id/source pack/version/manifest digest/trust evidence,
the support report and render plan when present, redacted captured logs, any
authoritative or partial result, and the exact replay command using absolute
request/result paths. Reproduce the failure with that command directly — no
editorial pipeline rerun needed. The bundle pins your qualified implementation
and request/input/manifest digests; implementation drift is reported and must
be explicitly acknowledged, and replay never silently resolves another
backend. Credentials, authorization headers, private environment values, and
signed URL query strings are removed.

The CLI reproduces the failure for you without rerunning the editorial
pipeline:

```bash
python3 -m astrid renderers replay <bundle-dir>                # or the alias:
python3 -m astrid replay <bundle-dir>                          # top-level alias
python3 -m astrid renderers replay <bundle-dir> --acknowledge-drift  # accept drift
```

`replay <bundle-dir>` re-runs the bundle's pinned command with the localized
`request.json`/inputs in a fresh temporary workspace and persists the
reproduced output plus its provenance sidecar next to the bundle
(`<bundle-dir>.replay-output/`). It refuses a tampered `request.json`
(request-digest mismatch), a drifted manifest (silent backend substitution),
or a drifted localized input unless `--acknowledge-drift` is passed — and it
prints the pinned ids/digests and the drift verdict. See the worked example in
[render-backend-v1.md](../contracts/render-backend-v1.md#the-replay-verb).

**V1 scope.** V1 is synchronous local execution only; asynchronous job
scheduling, remote render infrastructure, and layer compositing are explicitly
deferred beyond V1 and are NOT part of the V1 renderer contract. A replay is
therefore a local, synchronous re-run of the exact captured command — there is
no queue, no remote farm, and no compositing service in V1.

## 5. Structured error kinds

Every failure is a structured `RendererError`. Map the `kind` to the fix:

| kind | Meaning | Typical fix |
|---|---|---|
| `protocol` | Missing/malformed result, wrong shape, unknown version | Re-read the request; write exactly one authoritative result file; keep `schema_version: 1`. |
| `unsupported` | Request-sensitive support probe said no | Return actionable `reasons`; use a planner/fallback policy or a supported request. |
| `binary_missing` | A manifest-declared required binary is absent | Install the binary or drop it from `required_binaries`. |
| `timeout` | Deadline exceeded | Respect `timeout_seconds`; stream progress; shorten the work. |
| `interrupted` | Host cancellation | Check `RenderContext.raise_if_interrupted()` between long steps. |
| `invalid_artifact` | Missing/escaping/empty/hash-mismatched/incompatible output | Fix the relative `path`, write non-empty media, match the declared profile, correct the digest. |
| `internal` | Unexpected backend bug | Capture redacted logs/details and fix the implementation. |

## 6. SDK-level debugging

A `render.py` written against the public rendering SDK
(`astrid.renderer_main`, `astrid.RenderContext`) keeps the same failure
shapes. Useful SDK debugging moves:

- `astrid.support(backend, timeline_path=...)` — resolve a qualified backend
  and print its request-sensitive `SupportReport` without rendering.
- `astrid.render(...)` with `out_path=` — drive the shared `RenderService`
  directly from a Python session and inspect the returned published path.
- `RenderContext.run(...)` with `check=False` — run your vendor tool and
  inspect the bounded, redacted `SubprocessResult` instead of letting the
  frozen error raise.
- `RenderContext.log`/`progress` — all entries are scrubbed of secret values
  and carried into the result `logs`; use them instead of bare `print`.

`docs/reference/sdk.md` (Rendering SDK) has the full worked example.

## 7. Golden path recap

```bash
python3 -m astrid renderers create wave acme_wave
cd acme_wave
python3 -m pytest -q test_renderer.py
python3 -m astrid renderers validate .
python3 -m astrid packs install . --trust --yes
python3 -m astrid renderers list
python3 -m astrid renderers smoke acme_wave.wave --out ./out/smoke.mp4
python3 -m astrid renderers replay <bundle-dir>   # debug a captured failure bundle
```

The authoritative golden-path walkthrough is
[render-backend-v1.md](../contracts/render-backend-v1.md#renderer-author-golden-path).
