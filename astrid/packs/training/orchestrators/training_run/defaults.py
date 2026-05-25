"""Reusable defaults for built-in LTX training runs."""

from __future__ import annotations

RUNPOD_LTX_DEFAULTS = {
    "image": "ostris/aitoolkit:latest",
    "ports": "8675/http,22/tcp",
    "gpu_type": "NVIDIA RTX 6000 Ada Generation",
    "container_disk_gb": 200,
    "max_runtime_seconds": 43200,
}

AI_TOOLKIT_LTX_DEFAULTS = {
    "resolution": 512,
    "resolution_buckets": [512, 768],
    "num_frames": 121,
    "fps": 24,
    "learning_rate": 2.0e-5,
    "steps_default": 2000,
    "steps_smoke": 100,
    "rank": 32,
    "save_every": 250,
    "sample_every": 250,
    "batch_size": 1,
    "gradient_accumulation_steps": 4,
    "seed_default": 42,
    "base_model_default": "Lightricks/LTX-2.3/ltx-2.3-22b-dev.safetensors",
}

__all__ = [
    "AI_TOOLKIT_LTX_DEFAULTS",
    "RUNPOD_LTX_DEFAULTS",
]
