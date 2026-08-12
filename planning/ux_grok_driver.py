"""Grok 4.6 UX validation driver for the timeline visualization surface.

Runs six UX challenges against the generated evidence pack with Grok 4.6
(vision-capable, fresh model — an unfamiliar reader). Each challenge gives
Grok the reading guide + the relevant PNG pages, asks a navigation/understanding
task, then asks for structured feedback on the UX (what was clear, what
confused it, what it would change).

Usage: GEMINI-style env not needed — grok CLI uses its own auth.
    python3 ux_grok_driver.py <pack_root>
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

GROK = "/Users/peteromalley/.grok/bin/grok"
MODEL = "grok-4.6"


def grok_once(prompt: str, timeout: int = 240) -> str:
    """One fresh single-turn grok session (headless via pty wrapper)."""
    cmd = [
        "script", "-q", "/dev/null",
        GROK, "--single", prompt, "-m", MODEL,
    ]
    completed = subprocess.run(
        cmd, stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=timeout
    )
    out = completed.stdout
    # strip the pty's ^D and any leading noise; keep the tail (the answer)
    if out.startswith("^D"):
        out = out[2:]
    return out.strip()


def build_challenge(
    pack_root: Path,
    challenge_id: str,
    title: str,
    task: str,
    pages: list[str],
    feedback_prompt: str,
) -> str:
    guide = (pack_root / "reading-guide.md").read_text(encoding="utf-8")
    page_lines = "\n".join(
        f"- {name} (image: {pack_root / name})" for name in pages
    )
    return f"""You are an unfamiliar agent reader validating the UX of a timeline
visualization evidence pack. You see ONLY the images listed and the reading
guide below — nothing else (no JSON, no ground truth).

IMAGES:
{page_lines}

=== READING GUIDE (the only documentation) ===
{guide}

CHALLENGE: {challenge_id} — {title}
TASK: {task}

After completing the task, respond with ONE JSON object:
{{"task_answer": <your answer to the task>, "task_confident": <true/false>,
 "ux_rating": <1-5 how easy the surface was to use for this task>,
 "ux_clear": [<what was clear, strings>],
 "ux_confusing": [<what confused you, strings>],
 "ux_improve": [<concrete UX improvements, strings>],
 "timeline_understanding": "<one sentence: what you believe the timeline is doing>"}}

Be honest about confusion — the goal is to find UX gaps.
Under 400 words total."""


CHALLENGES = [
    {
        "id": "CH1-orient",
        "title": "Orient — what is this timeline?",
        "task": (
            "In one paragraph: what timeline is this, how long is it, what tracks "
            "exist, what is the snapshot state, and which clip is the focus of page 1?"
        ),
        "pages": ["PG001.png", "PG002.png"],
        "feedback": "Orient the reader from the overview pages alone.",
    },
    {
        "id": "CH2-zoom",
        "title": "Zoom — find a specific clip and its window",
        "task": (
            "Page 1 shows several storyboard clips. Pick the SECOND visual clip "
            "(TL01.CL02 if labeled). State: its exact frame window, its start/end "
            "times in seconds, and what the FOCUS cue says you should do next."
        ),
        "pages": ["PG001.png"],
        "feedback": "Zoom into one clip's timing + next action from the cue.",
    },
    {
        "id": "CH3-jump",
        "title": "Jump — locate the audio track",
        "task": (
            "There is a long music/audio clip (TL01.CL05). State: its frame window, "
            "its role in the timeline, whether the timeline's total duration is "
            "driven by it, and the FOCUS/PARENT/SOURCE cue line verbatim."
        ),
        "pages": ["PG001.png"],
        "feedback": "Jump to a different track and read its full cue line.",
    },
    {
        "id": "CH4-verify",
        "title": "Verify — original vs derived media",
        "task": (
            "The SOURCE cue reports an asset id + role + integrity state. State "
            "exactly: the asset id, its role, its integrity state, and whether it "
            "is an exact original or a derived/missing/thumbnail representation."
        ),
        "pages": ["PG001.png"],
        "feedback": "Verify the provenance claims from the SOURCE cue alone.",
    },
    {
        "id": "CH5-follow",
        "title": "Follow — can you act on the cue?",
        "task": (
            "The reading guide says: read the FOCUS id, then use action-index.json. "
            "From the cue on page 1, state: the exact FOCUS id, the PARENT id, and "
            "what command you would run next (the action kind, e.g. focus_context / "
            "inspect_original). Do NOT invent a command — derive it from the cue + guide."
        ),
        "pages": ["PG001.png"],
        "feedback": "Act on the cue: derive the next executable action.",
    },
    {
        "id": "CH6-explain",
        "title": "Explain — the structural story",
        "task": (
            "Explain the full temporal structure: the visual storyboard progression "
            "(how many frames, what order), the audio overlay, where the 1-frame "
            "overlap/gap markers are, and how the SPEECH/CAPTION/OTHER TEXT lanes "
            "relate to the clips. Use the lane bands and ruler ticks as evidence."
        ),
        "pages": ["PG001.png", "PG002.png"],
        "feedback": "Synthesize the structural narrative from the visual grammar.",
    },
]


def main() -> int:
    pack_root = Path(sys.argv[1]).resolve()
    results: dict[str, dict] = {}
    for challenge in CHALLENGES:
        print(f"--- {challenge['id']} {challenge['title']} ---", flush=True)
        prompt = build_challenge(
            pack_root,
            challenge["id"],
            challenge["title"],
            challenge["task"],
            challenge["pages"],
            challenge["feedback"],
        )
        try:
            raw = grok_once(prompt)
        except subprocess.TimeoutExpired:
            results[challenge["id"]] = {"error": "timeout"}
            print("  TIMEOUT", flush=True)
            continue
        results[challenge["id"]] = {"raw": raw}
        # try to extract the JSON verdict
        try:
            start = raw.find("{")
            verdict = json.loads(raw[start: raw.rfind("}") + 1])
            results[challenge["id"]]["verdict"] = verdict
            print(f"  rating={verdict.get('ux_rating')} confident={verdict.get('task_confident')}", flush=True)
        except Exception:
            print(f"  no JSON verdict; raw tail: {raw[-300:]}", flush=True)
    out = pack_root / "ux-grok-results.json"
    out.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(f"results -> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
