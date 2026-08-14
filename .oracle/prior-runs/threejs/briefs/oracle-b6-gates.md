# Oracle Batch 6 — gates / baseline / hygiene / schema / wheel (research + commands)

Repo: /Users/peteromalley/Documents/reigh-workspace/Astrid-threejs-oracle (HEAD fc0c3cee, branch oracle-run-threejs)
Main checkout for comparison: /Users/peteromalley/Documents/reigh-workspace/Astrid (HEAD b1c5f53c, branch main)
Do not edit any files. Do not run `make ci` or the full rendering suites. Bounded commands only.

## 1. Zero core edits (T6.7)

```bash
git -C /Users/peteromalley/Documents/reigh-workspace/Astrid-threejs-oracle diff --name-only b1c5f53c..HEAD -- astrid/core/
git -C /Users/peteromalley/Documents/reigh-workspace/Astrid-threejs-oracle diff --name-only 8723ca05..HEAD -- astrid/core/
git -C /Users/peteromalley/Documents/reigh-workspace/Astrid-threejs-oracle diff --name-only b1c5f53c..HEAD --name-only | rg -n "model\.py|node_modules|out/|build/|\.mp4|\.png|browser|dist/" || true
git -C /Users/peteromalley/Documents/reigh-workspace/Astrid-threejs-oracle ls-files astrid/core | wc -l
```

Both core diffs MUST be empty. List any generated artifacts in the epic tracked diff.

## 2. Ruff baseline regen

Host claim: our BLE001 fixes cleaned our files; regenerated baseline 1458→1469; the +11 is PRE-EXISTING on main (main also scans 1469).

Verify:

```bash
# What changed in the baseline file
git -C /Users/peteromalley/Documents/reigh-workspace/Astrid-threejs-oracle show fc0c3cee --stat -- scripts/reshape/baselines/ruff_astrid.json
git -C /Users/peteromalley/Documents/reigh-workspace/Astrid-threejs-oracle diff 8723ca05..fc0c3cee -- scripts/reshape/baselines/ruff_astrid.json | head -80

# Compare baseline files
python3 - <<'PY'
import json
from pathlib import Path
oracle = json.loads(Path("/Users/peteromalley/Documents/reigh-workspace/Astrid-threejs-oracle/scripts/reshape/baselines/ruff_astrid.json").read_text())
main = json.loads(Path("/Users/peteromalley/Documents/reigh-workspace/Astrid/scripts/reshape/baselines/ruff_astrid.json").read_text())
print("oracle type", type(oracle).__name__, "main type", type(main).__name__)
def count(x):
    if isinstance(x, list): return len(x)
    if isinstance(x, dict):
        if "violations" in x: return len(x["violations"])
        if "diagnostics" in x: return len(x["diagnostics"])
        return {k: (len(v) if hasattr(v,"__len__") and not isinstance(v,str) else v) for k,v in list(x.items())[:20]}
    return x
print("oracle count", count(oracle))
print("main count", count(main))
# If list of {filename,code}: show codes unique to each
def codes(obj):
    items = obj if isinstance(obj, list) else obj.get("violations") or obj.get("diagnostics") or []
    out=[]
    for it in items:
        if isinstance(it, dict):
            out.append((it.get("filename") or it.get("path") or "?", it.get("code") or it.get("rule") or "?"))
    return out
oc, mc = codes(oracle), codes(main)
print("oracle n", len(oc), "main n", len(mc))
so, sm = set(map(tuple,oc)), set(map(tuple,mc))
print("only oracle", sorted(so-sm)[:30], "n", len(so-sm))
print("only main", sorted(sm-so)[:30], "n", len(sm-so))
PY
```

If the JSON is a hash/count, print enough structure to judge whether regen HID our regressions or just refreshed pre-existing drift.

Do NOT run full ruff unless the JSON parse is inconclusive; if you must, run ruff only on the two threejs files vs the rest.

Is regen justified? FAIL only if the new baseline hides NEW findings in our threejs files.

## 3. Hygiene untrack (.codex / .vscode / mp3)

```bash
git -C /Users/peteromalley/Documents/reigh-workspace/Astrid-threejs-oracle ls-files -- '.codex' '.vscode' 'Up Beat (Married Life).mp3'
git -C /Users/peteromalley/Documents/reigh-workspace/Astrid ls-files -- '.codex' '.vscode' 'Up Beat (Married Life).mp3'
git -C /Users/peteromalley/Documents/reigh-workspace/Astrid-threejs-oracle log --oneline --diff-filter=A -- 'Up Beat (Married Life).mp3' '.vscode' '.codex' | head
git -C /Users/peteromalley/Documents/reigh-workspace/Astrid log -1 --format='%H %s' -- 'Up Beat (Married Life).mp3'
```

Confirm: files were on main (b768588e or similar), `git rm --cached` only (working copies still untracked locally is OK), no history rewrite. Right fix for a hygiene gate that failed identically on main? Any risk to main's history? (untracking in this branch is a normal commit; merging will untrack on main too — note that.)

## 4. test_schema_contract.py — identical on main?

Do NOT run the full suite. Run ONLY this file on BOTH checkouts:

```bash
PYENV_VERSION=3.11.11 python -m pytest -q tests/test_schema_contract.py --tb=no 2>&1 | tail -20
```

in the oracle worktree AND in `/Users/peteromalley/Documents/reigh-workspace/Astrid`.

Then:

```bash
git -C /Users/peteromalley/Documents/reigh-workspace/Astrid-threejs-oracle diff --name-only b1c5f53c..HEAD -- tests/test_schema_contract.py astrid/core/
```

If any of the 10 failures is caused by this epic → FAIL. If identical on main and no epic file touches timeline schema → pre-existing.

Also confirm `.oracle/legacy-epic/baseline.md` documents those failures (quote the relevant sentence).

## 5. Wheel evidence

Read `.oracle/findings/wheel-manifest.txt`. Confirm it lists:
`backends/threejs/{__init__.py,run.py,renderer.yaml}` and `planners/threejs_hybrid/{__init__.py,run.py,planner.yaml}`.

If you can, `unzip -l` the newest `dist/astrid-0.1.0-py3-none-any.whl` if it still exists; otherwise trust the saved manifest and say so.

## Output (<300 words)

```
CORE_DIFF_EPIC: empty | <paths>
CORE_DIFF_BATCH: empty | <paths>
GENERATED_TRACKED: none | <paths>
RUFF_BASELINE: justified | hides_regression <what>
  oracle_n: N  main_n: N  only_oracle: ...  only_main: ...
HYGIENE: correct | wrong <why>
  history_rewrite: no | yes
  merge_effect: untracks on main when merged (state this)
SCHEMA: pre-existing-identical | epic-caused <which>
  oracle: X failed / Y passed
  main: X failed / Y passed
WHEEL: present | missing <what>
ISSUES: none | numbered checkpoint-failing problems only
NOTES: non-blocking
```

Take a position. Cite commands + numbers. Do not hedge.
