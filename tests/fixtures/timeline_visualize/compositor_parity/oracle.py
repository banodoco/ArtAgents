"""Independent timing oracle for timeline-composition v0.0.6 rules 1-4."""

from math import floor


def _round_like_javascript(value):
    return floor(value + 0.5)


def clip_facts(clip, fps):
    hold = clip.get("hold")
    source = (
        hold
        if type(hold) in (int, float)
        else (clip.get("to") or 0) - (clip.get("from") or 0)
    )
    speed = clip.get("speed") if clip.get("speed") is not None else 1
    timeline = source / speed
    start = _round_like_javascript(clip["at"] * fps)
    duration = max(1, _round_like_javascript(timeline * fps))
    return {
        "source_seconds": source,
        "timeline_seconds": timeline,
        "start_frame": start,
        "duration_frames": duration,
        "end_frame": start + duration,
    }


def timeline_facts(timeline, fps):
    clips = {clip["id"]: clip_facts(clip, fps) for clip in timeline["clips"]}
    frames = max([1, *(facts["end_frame"] for facts in clips.values())])
    return {"clips": clips, "timeline_frames": frames, "timeline_seconds": frames / fps}
