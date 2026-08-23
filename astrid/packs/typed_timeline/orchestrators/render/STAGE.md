# typed_timeline.render — Stage

Single-task orchestrator (no child_executors): admits kernel run+task, maps rows via TypedDataTimelineMapper → timeline.json/assets.json, ensures tone.wav (total_duration_sec), validates via match_and_validate, then ffmpeg renders video.mp4. No second ledger; every run observable. Former child_executors declaration removed to avoid silent divergence.
