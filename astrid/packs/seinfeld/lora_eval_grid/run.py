#!/usr/bin/env python3
"""seinfeld.lora_eval_grid — baseline + per-checkpoint inference + index.html viewer."""


from __future__ import annotations


from astrid.packs._canonical_entrypoint import guard_canonical_entrypoint
guard_canonical_entrypoint('seinfeld.lora_eval_grid')
import argparse
import html
import json
import subprocess
import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    yaml = None  # type: ignore[assignment]

def _build_prompts(vocab: dict, smoke: bool) -> list[str]:
    configured = vocab.get("eval_prompts") or vocab.get("sample_prompts")
    n = 3 if smoke else 6
    if isinstance(configured, list) and configured:
        return [str(prompt) for prompt in configured[:n]]

    trigger = str(vocab.get("trigger_word") or vocab.get("trigger") or "seinfeld scene").strip()
    scenes = list((vocab.get("scenes") or {}).keys())
    chars = list((vocab.get("characters") or {}).keys())
    scene = scenes[0] if scenes else "jerrys_apt"
    first_char = chars[0].capitalize() if chars else "Jerry"
    prompts = [
        (
            f"{trigger}, Scene: A medium two-shot in {scene}, near the kitchen counter. "
            "Jerry stands beside a cereal shelf while George gestures anxiously with both hands. "
            "Speech: \"You alphabetized the cereal?\" -- Jerry, dry. "
            "\"It is not alphabetized, it is emotionally indexed.\" -- George, defensive. "
            "Sounds: quiet apartment room tone and a short studio audience laugh. Style: 90s NBC sitcom lighting."
        ),
        (
            f"{trigger}, Scene: A wide living-room shot in {scene}, facing the couch and doorway. "
            "Elaine enters with a shopping bag as Kramer slides through the door and Jerry turns from the kitchen. "
            "Speech: \"You brought the bag back?\" -- Jerry, suspicious. \"The bag has history.\" -- Elaine, firm. "
            "\"I know a bag guy.\" -- Kramer, confident. Sounds: door movement, apartment ambience, audience laughter."
        ),
        (
            f"{trigger}, Scene: A wide shot in {scene}. Jerry sits on the couch with a TV remote, "
            "George stands near the coffee table, Elaine leans on the couch, and Kramer hovers near the door. "
            "Speech: \"Nobody touched the remote?\" -- Jerry, skeptical. \"I respected the remote.\" -- George, nervous. "
            "\"You feared the remote.\" -- Elaine, amused. Sounds: room tone and studio audience laugh."
        ),
        (
            f"{trigger}, Scene: A medium shot in {scene} by the stereo and bookshelves. "
            "Kramer taps along to tinny music while George winces and Jerry reaches for the volume knob. "
            "Speech: \"That is not music, that is a drawer opening.\" -- Jerry, deadpan. "
            "\"It has movement.\" -- Kramer, excited. \"So does panic.\" -- George, irritated."
        ),
        (
            f"{trigger}, Scene: A medium-wide shot in {scene}. A small orange cat sits on the coffee table "
            "while Jerry, Elaine, George, and Kramer argue around it. Speech: \"Why is there a cat on my table?\" "
            "-- Jerry, annoyed. \"It chose you.\" -- Kramer, reverent. Sounds: soft meow and audience laugh."
        ),
        (
            f"{trigger}, Scene: A medium shot in {scene}. {first_char} pauses mid-argument, "
            "then points toward the kitchen with a suspicious look. Speech: \"This is how it starts.\" "
            "Sounds: apartment room tone and a small laugh from the audience. Style: 90s multi-camera sitcom."
        ),
    ]
    return prompts[:n]


def _render_index_html(prompts: list[str], buckets: list[str], grid_dir: Path) -> str:
    rows: list[str] = []
    for pi, prompt in enumerate(prompts):
        cells: list[str] = []
        for b in buckets:
            mp4 = f"{b}/prompt_{pi:02d}.mp4"
            cells.append(
                f'<td><div class="lbl">{html.escape(b)}</div>'
                f'<video src="{html.escape(mp4)}" controls width="320"></video></td>'
            )
        rows.append(
            f"<tr><td class='prompt'>{html.escape(prompt)}</td>{''.join(cells)}</tr>"
        )
    head_cells = "<th>prompt</th>" + "".join(f"<th>{html.escape(b)}</th>" for b in buckets)
    return (
        "<!doctype html><html><head><meta charset='utf-8'>"
        "<title>Seinfeld LoRA Eval Grid</title>"
        "<style>body{font-family:sans-serif}td{vertical-align:top;padding:6px}"
        ".prompt{max-width:260px;font-size:13px}.lbl{font-size:11px;color:#666}"
        "table{border-collapse:collapse}</style></head><body>"
        "<h1>Seinfeld LoRA Eval Grid</h1>"
        f"<table><thead><tr>{head_cells}</tr></thead><tbody>"
        f"{''.join(rows)}</tbody></table></body></html>\n"
    )


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Run baseline + per-checkpoint samples and build a grid.")
    p.add_argument("--pod-handle", type=Path, required=True)
    p.add_argument("--checkpoint-manifest", type=Path, required=True)
    p.add_argument("--vocabulary", type=Path, required=True)
    p.add_argument("--produces-dir", type=Path, required=True)
    p.add_argument("--smoke", action="store_true")
    p.add_argument("--dry-run", action="store_true")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    produces = args.produces_dir
    grid_dir = produces / "eval_grid"
    grid_dir.mkdir(parents=True, exist_ok=True)

    if yaml is None:
        print("ERROR: PyYAML required", file=sys.stderr)
        return 3

    with args.vocabulary.open("r", encoding="utf-8") as f:
        vocab = yaml.safe_load(f) or {}
    prompts = _build_prompts(vocab, smoke=args.smoke)
    (grid_dir / "prompts.json").write_text(
        json.dumps(prompts, indent=2) + "\n", encoding="utf-8"
    )

    manifest = json.loads(args.checkpoint_manifest.read_text(encoding="utf-8"))
    checkpoints = manifest.get("checkpoints", []) if isinstance(manifest, dict) else []

    buckets = ["baseline"]
    if not args.smoke:
        buckets += [f"step_{c['step']}" for c in checkpoints]

    for b in buckets:
        (grid_dir / b).mkdir(parents=True, exist_ok=True)

    if args.dry_run:
        (grid_dir / "index.html").write_text(
            _render_index_html(prompts, buckets, grid_dir), encoding="utf-8"
        )
        return 0

    repo_root = Path(__file__).resolve().parents[4]
    # Prevent runpod exec from uploading the repository cwd for each eval sample.
    empty_local_root = grid_dir / "_empty_local_root"
    empty_local_root.mkdir(parents=True, exist_ok=True)

    # Run inference on the pod. The inference command is a placeholder; ai-toolkit
    # provides a `run.py` infer mode and an HTTP API — verify exact entrypoint at impl time.
    for bucket in buckets:
        ckpt_arg = "" if bucket == "baseline" else f"--lora /workspace/output/{bucket}.safetensors"
        for i, prompt in enumerate(prompts):
            remote_mp4 = f"/workspace/eval/{bucket}/prompt_{i:02d}.mp4"
            cmd = (
                f"mkdir -p /workspace/eval/{bucket}; "
                f"python3 /workspace/ai-toolkit/infer.py {ckpt_arg} "
                f"--prompt {json.dumps(prompt)} --out {remote_mp4} || true"
            )
            eval_produces = grid_dir / "_exec" / bucket / f"prompt_{i:02d}"
            eval_produces.mkdir(parents=True, exist_ok=True)
            subprocess.run(
                [
                    sys.executable, "-m", "astrid.packs.external.runpod.run", "exec",
                    "--produces-dir", str(eval_produces),
                    "--pod-handle", str(args.pod_handle),
                    "--local-root", str(empty_local_root),
                    "--remote-script", cmd,
                ],
                cwd=repo_root,
            )
            # TODO: download of remote_mp4 → grid_dir not yet implemented.
            # external.runpod.exec's artifact_dir auto-copies /workspace recursively;
            # would need a follow-up exec that consolidates eval outputs or a dedicated
            # --pull-file flag added upstream. For now, eval mp4s stay on the pod.
            # The grid_dir/index.html will reference paths that won't resolve locally.

    (grid_dir / "index.html").write_text(
        _render_index_html(prompts, buckets, grid_dir), encoding="utf-8"
    )
    print(f"lora_eval_grid: wrote {grid_dir / 'index.html'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
