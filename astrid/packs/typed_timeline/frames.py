from __future__ import annotations


def ms_to_frame(ms: int | float, fps: int | float) -> int:
    return int(round(float(ms) * float(fps) / 1000.0))


def frame_to_ms(frame: int, fps: int | float) -> float:
    return float(frame) * 1000.0 / float(fps)


def total_frames(total_duration_sec: float, fps: int | float) -> int:
    return int(round(float(total_duration_sec) * float(fps)))


def frame_to_sec(frame: int, fps: int | float) -> float:
    return float(frame) / float(fps)
