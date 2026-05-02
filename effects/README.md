# Effects

Workspace-level Remotion effects live here. Each effect gets one directory named by its stable effect id:

```text
effects/
  <effect-id>/
    component.tsx
    schema.json
    defaults.json
    meta.json
    preview.mp4      # optional
```

The render-time catalog is discovered by scanning direct child directories under `effects/`. A directory is considered an effect only when it has both `component.tsx` and `meta.json`; schema, defaults, and preview assets are consumed by the pipeline and authoring tools when present.

Effect ids are folder names. Keep ids lowercase and URL-safe because they become `clipType` values in generated timelines.
