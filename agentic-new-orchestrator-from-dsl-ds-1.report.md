# Report: New Orchestrator from DSL (DS-1)

## 1. What did you build?

**Qualified id:** `file_summarizer.e2e_text_pipeline`
**Pack:** `file_summarizer` (under `astrid/packs/file_summarizer/`)
**File path:** `astrid/packs/file_summarizer/e2e_text_pipeline.py`
**Step shape:** Three sequential steps — one `code`, two `attested`:

| Step | Kind | Produces | Check |
|------|------|----------|-------|
| `read_input` | code | `input.txt` | `file_nonempty` |
| `write_summary` | attested | `summary.json` | `json_file` |
| `write_verdict` | attested | `verdict.json` | `json_file` |

The code step copies a text file from a fixture (or an `ASTRID_TASK_INPUT_TEXT` env-var override) into the step's produces directory. It uses a Python one-liner with `shutil.copyfile`, falling back to `fixtures/e2e_text_pipeline/input.txt` when the env var is unset. The `file_nonempty` check ensures the copy succeeded before the gate advances.

The first attested step instructs the agent to read the staged text and emit a summary JSON with line/word/char counts plus a one-sentence note describing the content. It requires the agent to actually count the file's lines, words, and characters rather than fabricating numbers. The `json_file` check validates that valid JSON was written to the produces path, though it does not enforce a specific schema — I chose `json_file` over `json_schema` deliberately to keep the contract looser and let the agent's natural output shape pass validation without schema-failure rewinds.

The second attested step instructs the agent to review the summary and emit a single-key verdict JSON (`{"verdict": "<one-line assessment>"}`). Like the summary step, it uses `json_file` for a permissive check. Both attested steps use `ack="agent"` so the gate waits for agent attestation before advancing the cursor. I chose two attested steps over a nested sub-plan because the three-step flat structure is simpler to reason about and the verdict step genuinely benefits from human/agent review of the summary before committing.

I also created a fixture file at `fixtures/e2e_text_pipeline/input.txt` containing one sentence ("The quick brown fox jumps over the lazy dog...") so the orchestrator can run end-to-end without external wiring. The fixture lives inside the pack, respecting the constraint not to edit outside pack boundaries.

## 2. Authoring surface

I used `astrid author new file_summarizer.e2e_text_pipeline` to scaffold the skeleton, which created the `.py` file, a `fixtures/` subdirectory with a `.keep` file, and a `golden/` events stub. The scaffold produced a minimal stub with one TODO code step and the correct imports (`code`, `file_nonempty`, `orchestrator`). I then hand-edited the file to replace the stub with three real steps, adding `attested` and `json_file` to the import block. I did not write raw YAML at any point — the DSL is pure Python using decorators (`@orchestrator`) and builder functions (`code()`, `attested()`) from `astrid.orchestrate`.

I validated with `astrid author check` (static DSL validation — checks that the Python defines a valid plan without executing it) and compiled with `astrid author compile` (emits a version-2 plan JSON into `build/e2e_text_pipeline.json`). I also ran `astrid author describe` to inspect the plan shape and `astrid author explain` to see how the gate would present instructions to an agent at runtime. All four verbs worked without error.

The scaffold gave me the correct decorator, function signature, and module docstring template. I only had to fill in the step list and add the necessary imports. I also created the fixture text file manually since `author new` only creates a `.keep` placeholder. The entire authoring flow was: scaffold → edit one file → check → compile — no other files touched.

## 3. Compile loop

`astrid author check file_summarizer.e2e_text_pipeline` passed on the very first try after editing (4.7 ms). There were zero failures and zero rework cycles. The DSL's construction-time guards — `OrchestrateDefinitionError` raised at definition time for typos in produces names, invalid ack kinds, missing required fields, or duplicate sibling step ids — meant that authoring mistakes would have surfaced immediately, but I didn't trigger any because I modeled the shape closely on the existing `document_pipeline.py` in the same pack.

`astrid author compile` also passed cleanly on first attempt, writing the compiled plan to `build/e2e_text_pipeline.json`. The round-trip through `load_plan` validation (embedded in `_PlanBuilder.to_dict()`) confirmed the emitted JSON is byte-shape-equivalent to what the task-mode gate expects. The compiled JSON includes the shlex-joined command string, the full instructions text, the ack configuration, and the produces checks — all exactly as the v2 plan schema requires.

I ran `astrid author check` again after compilation to confirm idempotency, and it still passed. The entire compile loop — scaffold, edit, check, compile, re-check — took under 60 seconds and involved only three shell invocations of the author CLI.

## 4. Discovery friction

I found the DSL primitives by reading `astrid/orchestrate/__init__.py` and `astrid/orchestrate/dsl.py` directly — these are the canonical API surfaces for the builders and verifiers. The `astrid author --help` output listed the six verbs (`new`, `check`, `compile`, `describe`, `explain`, `test`) but didn't describe the DSL API itself; I had to source-dive to discover the full set of builders (`code`, `attested`, `nested`, `plan`, `repeat_for_each`, `repeat_until`) and verifiers (`file_nonempty`, `json_file`, `json_schema`, `image_dimensions`, `audio_duration_min`, `all_of`).

The existing authored orchestrators were invaluable reference implementations. I studied `classify_grid.py` (in `builtin/`) for the `repeat_for_each` and `json_schema` patterns, and `text_digest/summarize.py` plus `file_summarizer/document_pipeline.py` for the basic code→attested→nested shape. These artifacts collectively demonstrated every DSL feature I needed.

One surprise: `orchestrators list` only shows the legacy built-in JSON-manifest orchestrators (`builtin.hype`, `seinfeld.lora_train`, etc.), not the DSL-authored ones. The two authoring paths coexist in the same `astrid/packs/` tree but have completely separate discovery surfaces — JSON manifests appear in `orchestrators list` while DSL plans appear only through `astrid author describe`. A second surprise: the `author` CLI requires a bound session (`astrid attach`), which wasn't obvious from the help text; attempting `author new` without a session produces a clear error, but the requirement isn't documented in `--help`.

I also had to guess at the exact semantics of `ack="agent"` vs `ack="actor"` — the DSL module's `_VALID_ACK_KINDS` constant confirms both are valid, but the behavioral difference (whether a human or an AI agent attests) required reading the existing orchestrators to see which used which. The `explain` verb helped clarify runtime behavior after compilation.

## 5. One-line verdict on the authoring UX

The DSL is clean, the compile-loop is instant, and the construction-time guards catch errors eagerly — but you currently need source-diving and existing-artifact reading to know what builders and verifiers exist, because there's no `astrid author primitives` or in-CLI API reference, and the dual authoring paths (JSON manifests vs DSL Python) create a discoverability split that new authors will trip over.
