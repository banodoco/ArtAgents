# comfy_wrap.run

Generate an image by injecting a text prompt into a ComfyUI workflow JSON and
running it via vibecomfy.

## Intent

This executor is a narrow wrapper: it takes a user prompt, loads a ComfyUI
workflow JSON from `/tmp/example_comfy.json` at run-time, injects the prompt
into the positive CLIPTextEncode node (node id `6`, field `text`), executes
the workflow through vibecomfy, and copies the first output image to the
`out` directory.

## Inputs

| Input | Type | Required | Description |
|---|---|---|---|
| `prompt` | string | yes | Text prompt injected into the positive CLIPTextEncode node |

## Outputs

| Output | Type | Description |
|---|---|---|
| `generated_image` | file | The generated image, written to the `out` directory |

## Dependencies

- `vibecomfy` package (must be installed)
- A ComfyUI workflow JSON at `/tmp/example_comfy.json` with node `6` as a
  `CLIPTextEncode` carrying a `text` input field

## Run via SDK

```python
import astrid.sdk as sdk
result = sdk.invoke("comfy_wrap.run", inputs={"prompt": "your prompt"}, out="path/to/output.png")
```

## Error recovery

- Missing workflow file → ensure `/tmp/example_comfy.json` exists
- Missing prompt node → check that node `6` is a CLIPTextEncode in the workflow
- No outputs → verify the workflow has a SaveImage node and ComfyUI output dir is configured
