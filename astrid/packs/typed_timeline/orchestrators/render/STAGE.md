# typed_timeline.render — Stage

Single-task orchestrator (no child executors): admits exactly one kernel task,
maps host-admitted rows, validates the complete audio-reactive timeline, and
performs a real FFmpeg render. It succeeds only when `ffprobe` proves the
encoded frame count equals the mapped frame count; there is no fake MP4,
one-second fallback, second database, or filesystem ledger. Outputs and the
portable result manifest stay inside the assigned staging directory.
