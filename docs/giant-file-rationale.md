# Giant-file rationale

This is the canonical M4 follow-up inventory for Python files under
`astrid/`. The structure contract treats a file as oversized when it exceeds
1,200 physical lines. Line counts use `wc -l` and are a snapshot; the contract
allows a drift of up to 50 lines while requiring every current oversized file
to remain documented.

The entries below are explicit, time-bounded exemptions for the current
Stage1 product boundary. They identify cohesive surfaces that still need
decomposition without disguising the files as separate authorities or adding
compatibility paths. A future decomposition should update this inventory in
the same change that moves the code, and remove an entry once the file is at
or below the threshold.

| # | File | Lines | Current exemption and next decomposition seam |
|---:|---|---:|---|
| 1 | `astrid/core/execution/generic_host.py` | 2304 | Generic executor host owns discovery, admission, worker execution, and settlement orchestration. Split protocol boundary, admission, and worker lifecycle into cohesive modules. |
| 2 | `astrid/core/rendering/contracts.py` | 2279 | Rendering contract DTOs and validation remain one versioned wire surface. Split independent profile, timeline, backend, and provenance contract groups while preserving one public contract module. |
| 3 | `astrid/core/rendering/service.py` | 2196 | Managed rendering admission and lifecycle are kept together for transaction and preflight ordering. Split backend selection, staging, and lifecycle orchestration behind the service boundary. |
| 4 | `astrid/packs/rendering/executors/timeline_visualize/emit.py` | 2130 | Visualization evidence emission is a capability-local implementation with tightly coupled output formats. Split manifest, page, and companion emitters without changing the executor entrypoint. |
| 5 | `astrid/packs/rendering/executors/timeline_visualize/layout.py` | 2123 | Visualization layout calculations share frozen metric and ordering rules. Split metric computation, pagination, and SVG/HTML layout helpers with fixture parity tests. |
| 6 | `astrid/packs/rendering/executors/timeline_visualize/frozen.py` | 2048 | Frozen visualization schemas and deterministic constants are kept together as one capability contract. Split immutable schema definitions from rendering constants only when the frozen hashes remain unchanged. |
| 7 | `astrid/packs/rendering/executors/timeline_visualize/run.py` | 1740 | The visualization executor coordinates input validation, snapshots, layout, and output publication. Split orchestration from pure preparation helpers while retaining the canonical `run.py` entrypoint. |
| 8 | `astrid/sdk/invocation.py` | 1625 | SDK invocation owns the single admission/execution/finalization path. Split transport preparation, ledger transitions, and output projection behind the same facade. |
| 9 | `astrid/packs/rendering/finalizers/ffmpeg/run.py` | 1444 | FFmpeg finalization keeps media probing, command construction, and output verification aligned. Split pure command/profile logic from subprocess and provenance handling. |
| 10 | `astrid/sdk/rendering.py` | 1277 | Public rendering facade validates and delegates the stable render contract. Split input/profile validation from the facade without creating a second render authority. |
| 11 | `astrid/core/execution/executor/runner.py` | 1273 | Executor lifecycle and subprocess fencing remain together at the kernel boundary. Split lifecycle phases only behind the existing runner protocol. |
| 12 | `astrid/core/experiments/normalize.py` | 1268 | Experiment normalization applies one canonical provider-independent model. Split source adapters from canonical normalization and preserve deterministic diagnostics. |
| 13 | `astrid/packs/video_editing/orchestrators/iteration_video/run.py` | 1211 | Iteration-video orchestration coordinates preparation, render, and finalization. Split stage adapters from orchestration while keeping one declared capability entrypoint. |
