"""Frozen public DTO surface for the rendering wire contract."""

from .contracts import (
    Attachment,
    AudioOwnership,
    BackendConfig,
    FrameWindow,
    RenderPlan,
    RenderProfile,
    RenderRequest,
    RenderResult,
    RendererError,
    SupportReport,
    VideoArtifact,
)

__all__ = [
    "RenderRequest",
    "SupportReport",
    "RenderPlan",
    "FrameWindow",
    "RenderProfile",
    "AudioOwnership",
    "VideoArtifact",
    "RenderResult",
    "RendererError",
    "BackendConfig",
    "Attachment",
]
