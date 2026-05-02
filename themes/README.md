# Themes

Workspace-level render themes live here. Each theme gets one directory with a `theme.json` file:

```text
themes/
  <theme-id>/
    theme.json
```

The render pipeline loads a theme JSON and passes it to Remotion as a top-level prop. Effects should read visual values from the theme tokens instead of hardcoding colors, typography, or motion constants.
