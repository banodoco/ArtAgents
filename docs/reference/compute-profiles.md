# User compute profiles

Astrid keeps optional per-user compute profiles at:

```
~/.astrid/compute-profiles/<id>.json
```

The files use the `astrid.compute_profile.v1` schema and describe execution
settings such as a preferred GPU, RunPod network volume, image, and remote
paths. They must never contain API keys, tokens, or other secret values.
Credential entries are environment-variable names only:

```json
{
  "schema": "astrid.compute_profile.v1",
  "schema_version": 1,
  "id": "peter-runpod-eu-ro-1-5090",
  "provider": "runpod",
  "gpu_type": "NVIDIA GeForce RTX 5090",
  "storage_name": "Peter",
  "require_storage": true,
  "datacenter_id": "EU-RO-1",
  "image": "runpod/comfyui:cuda12.8",
  "credentials": {
    "runpod_api_key": "RUNPOD_API_KEY",
    "hf_token": "HF_TOKEN"
  }
}
```

Resolution order is explicit executor field input, the named profile passed by
`--compute-profile`, `ASTRID_COMPUTE_PROFILE`, `default.json`, then executor
defaults. (The named option is itself an explicit profile-selection override.)
Legacy `RUNPOD_*` settings remain supported as executor defaults. The resolved
safe mapping is recorded as `produces/compute_resolved.json`; credential
environment values are never written to that snapshot.

The repository includes [a copyable Peter/5090 example](../examples/peter-runpod-eu-ro-1-5090.json);
copy it into `~/.astrid/compute-profiles/peter-runpod-eu-ro-1-5090.json` if
that is the intended user setup. RunPod's `--compute-profile` option selects a named profile for `provision` and
`session`. Set `ASTRID_COMPUTE_PROFILE` to select one for a process without
adding it to every invocation. The RunPod lifecycle version currently targeted
by Astrid accepts no datacenter constraint, so `datacenter_id` is recorded for
audit and storage placement but does not constrain pod launch; verify the
observed pod location in the provider receipt. A profile does not create or resize storage:
`storage_name` must name an existing RunPod network volume, and callers that
need persistence should also set `require_storage` (or use
`--require-storage`).
