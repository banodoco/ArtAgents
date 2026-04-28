# @banodoco/timeline-schema

Canonical `TimelineConfig` schema. TS+Zod is source of truth at
`typescript/src/`; Python TypedDicts are generated into `python/banodoco_timeline_schema/generated.py` from a JSON Schema artifact.

## Install (Python, editable)

```
pip install -e packages/timeline-schema/python
```

## Build / regenerate

```
cd packages/timeline-schema
npm install
npm run build         # tsc + emit JSON Schema artifact
npm run gen:python    # JSON Schema -> Python TypedDicts
bash scripts/check-codegen.sh   # CI gate
```
