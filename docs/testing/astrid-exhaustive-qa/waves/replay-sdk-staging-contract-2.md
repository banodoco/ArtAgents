# SDK staging/run-root contract replay 2

Date: 2026-08-24  
Method: independent live SDK agent-UX replay  
Verdict: **PASS**

## Scope

This replay used only the documented public SDK (`AstridClient` project,
timeline, and `invoke` methods) and read-only artifact inspection. It did not
inspect source or tests and did not modify product code.

Fresh disposable boundary:

```text
ASTRID_PROJECTS_ROOT=/tmp/astrid-sdk-staging-contract.ZRYxy0/projects
project=sdk-staging
timeline=main
timeline UUID=3286c93c-d237-5857-a308-c516d8238df0
```

The canonical timeline was a one-second structured-text render with an
authoritative 320x180@30 theme canvas. It was invoked as documented:

```python
with AstridClient.open(projects_root=projects_root) as client:
    result = client.invoke(
        "rendering.render",
        kind="executor",
        project="sdk-staging",
        inputs={"timeline_ref": "main", "expected_version": 1},
    )
```

## First successful invocation

The invocation succeeded with durable kernel identity:

```text
run:     e6af04db434f0e853d50779018
task:    120766a9b72b9214b74fa91d8d
attempt: 01m0sqq9rtyn5djwr382fptfrt
```

The corrected staging contract held:

```text
InvocationResult.run_root = None
"run_root" in InvocationResult.raw_result = false
raw_result keys = kernel_attempt_id, kernel_run_id, kernel_task_id,
                  ok, outputs, run_id
```

Immediately after the returned success:

```text
.astrid/media/.staging exists = true
.astrid/media/.staging recursive entries = []
```

Thus the attempt-owned staging directory was neither exposed in the result nor
left behind on disk.

## Durable output evidence

The returned artifact set contained exactly the expected render and provenance
sidecar. Both locators existed after completion, were under resolved managed
CAS, used correct two-level digest sharding, used the content digest as the
basename, and hashed to the advertised `content_hash`.

### Primary MP4

```text
label: hype.mp4
sha256: b2634deb2f59a0696f93564916f17f9c5c36613b0c6e3e34de6be2d9fd604dc2
path: /private/tmp/astrid-sdk-staging-contract.ZRYxy0/projects/.astrid/media/
      sha256/b2/63/b2634deb2f59a0696f93564916f17f9c5c36613b0c6e3e34de6be2d9fd604dc2
exists: true
hash matches: true
```

`ffprobe` independently confirmed a valid MP4-family container with:

```text
duration: 1.045333s
video: H.264, 320x180
audio: AAC
```

### Provenance sidecar

```text
label: hype.mp4.provenance.json
sha256: 9662c535cd89c7fe95b555832e1df14c047a56af4a9917ba5385a4f387d1ba0a
path: /private/tmp/astrid-sdk-staging-contract.ZRYxy0/projects/.astrid/media/
      sha256/96/62/9662c535cd89c7fe95b555832e1df14c047a56af4a9917ba5385a4f387d1ba0a
exists: true
hash matches: true
valid JSON object: true
```

## Exact replay

The identical documented SDK invocation was submitted again with the same
canonical timeline version pin.

It returned the same immutable identity:

```text
same run: true
same task: true
same attempt: true
same complete artifact mapping: true
```

The replay contract also held:

```text
InvocationResult.run_root = None
raw_result has run_root = false
both durable artifact files still exist and hash correctly
.astrid/media/.staging recursive entries = []
```

A third read-only replay used to probe the media retained the same identity and
did not create staging content.

## Agent friction

No Astrid UX friction remained in the tested contract. The SDK documentation
now states the crucial distinction clearly: `run_id` is durable kernel
identity, `run_root` is `None` for kernel-managed invocations, and output
locators are durable managed media.

One host-filesystem inspection wrinkle is worth recording: on macOS, a root
created as `/tmp/...` is returned canonically as `/private/tmp/...`. A naive
lexical `Path.is_relative_to()` check therefore reports false containment.
Resolving both the configured CAS root and returned locator first proves true
containment. This is an OS path-alias issue, not an Astrid staging or artifact
defect.

## Final verdict

**PASS.** Normal success and exact replay both expose only durable kernel and
CAS identities. No transient staging path appears in either public result, all
returned artifacts remain readable and content-addressed after completion,
and the staging boundary is empty after both execution and replay.

