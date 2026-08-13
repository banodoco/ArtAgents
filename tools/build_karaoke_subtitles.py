#!/usr/bin/env python3
"""Build a two-line karaoke ASS track from the narration clips in an Astrid run.

The source run is intentionally kept immutable.  Whisper word timings are
collected from each narration WAV, canonical script text is aligned to those
timings, and short phrase events are emitted with a muted next-phrase preview.
"""

from __future__ import annotations

import argparse
import difflib
import json
import re
from pathlib import Path
from typing import Any


# These are editorial caption phrases, not a raw transcript.  The spoken
# audio is still the timing source, but the on-screen copy uses normal product
# spelling (SDXL, VAE, CFG, 1.5) and breaks only at sensible clauses.
PHRASES: dict[str, list[str]] = {
    "opener": [
        "VibeComfy is a tool for agents to easily understand and work with Comfy workflows.",
    ],
    "hivemind-intro": [
        "While Hivemind lets agents understand, use, and contribute to knowledge in the ecosystem.",
        "I'm going to show how they can be combined in Comfy!",
    ],
    "sd15": [
        "Ask for a basic Stable Diffusion 1.5 workflow, and it builds the familiar model, prompts, sampler, latent, and output graph.",
    ],
    "sdxl": [
        "Now convert that same graph to SDXL. This isn't just swapping a checkpoint: it updates the model family, image size, conditioning, sampler settings, and everything that needs to stay compatible.",
    ],
    "img2img": [
        "Next, turn it into image-to-image. VibeComfy removes the empty latent, adds an image and VAE encoding path, and reconnects that encoded latent to the sampler.",
    ],
    "qwen": [
        "Then we get more specific: make this Qwen workflow run as fast as possible. It uses community knowledge to choose a Lightning LoRA and adjust the model, steps, CFG, and other settings together.",
    ],
    "upscalers": [
        "Finally, here's a more complex example: take one upscaling workflow and turn it into a proper comparison. It adds several upscaler models, creates parallel branches, and wires the outputs so you can judge every result side by side.",
    ],
    "behind-scenes": [
        "Behind the scenes, whenever you request a change, VibeComfy converts the workflow into a Python format that's easy for agents to understand. It then uses Hivemind to search across existing references and community knowledge for relevant examples and techniques.",
    ],
    "close": [
        "The goal is to turn all of that information into actionable knowledge the agent can apply directly to your workflow.",
        "It's still early, so many queries won't return the right result yet.",
        "But this is a path to unlocking the community's collective intelligence inside Comfy!",
        "The Hivemind repository is open source, and all of its knowledge is openly available on Hugging Face and in our public database.",
        "You can use it inside Comfy with your existing Claude Code or Codex subscription, or directly with your CLI agent.",
        "You can find installation instructions on the VibeComfy repo.",
    ],
    "thank-you": [
        "Thank you for checking it out. You can find more details in the post.",
    ],
}

SCRIPT: dict[str, str] = {section: " ".join(phrases) for section, phrases in PHRASES.items()}


def norm(word: str) -> str:
    """Normalize a token for loose canonical/transcript alignment."""

    return re.sub(r"[^a-z0-9]+", "", word.lower().replace("’", "'"))


def display_tokens(text: str) -> list[str]:
    """Return whitespace-delimited display tokens, preserving punctuation."""

    return re.findall(r"\S+", text.strip())


def align_tokens(canonical: list[str], words: list[dict[str, Any]], duration: float) -> list[dict[str, float | str]]:
    """Align canonical display words to Whisper timings.

    The narration is known, so canonical spelling is preferable for captions
    (e.g. ``VibeComfy`` and ``S D X L``), while Whisper supplies timing.  Exact
    runs are mapped directly and unmatched runs are distributed monotonically
    between their surrounding timing anchors.
    """

    clean_words = [str(w.get("word", "")).strip() for w in words if str(w.get("word", "")).strip()]
    clean_times = [(float(w.get("start", 0.0)), float(w.get("end", 0.0))) for w in words if str(w.get("word", "")).strip()]
    if not canonical:
        return []
    if not clean_words:
        # This fallback is only used for an unusually silent/failed clip.
        step = duration / max(len(canonical), 1)
        return [{"word": token, "start": i * step, "end": (i + 1) * step} for i, token in enumerate(canonical)]

    a = [norm(t) for t in canonical]
    b = [norm(t) for t in clean_words]
    matcher = difflib.SequenceMatcher(a=a, b=b, autojunk=False)
    mapping: dict[int, tuple[float, float]] = {}
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            for ci, tj in zip(range(i1, i2), range(j1, j2)):
                mapping[ci] = clean_times[tj]
        elif i1 < i2:
            # Use the nearest transcript window for replacements/insertions.
            left = clean_times[j1 - 1][1] if j1 > 0 else 0.0
            right = clean_times[j2][0] if j2 < len(clean_times) else duration
            if j1 == j2 and j1 < len(clean_times):
                right = clean_times[j1][1]
            span = max(right - left, 0.02)
            count = i2 - i1
            for offset, ci in enumerate(range(i1, i2)):
                start = left + span * offset / count
                end = left + span * (offset + 1) / count
                mapping[ci] = (start, max(end, start + 0.02))

    # Defensive fill for any odd matcher edge case.
    for i in range(len(canonical)):
        if i in mapping:
            continue
        left = mapping.get(i - 1, (0.0, 0.0))[1]
        right = next((mapping[j][0] for j in range(i + 1, len(canonical)) if j in mapping), duration)
        mapping[i] = (left, max(right, left + 0.02))

    out: list[dict[str, float | str]] = []
    for i, token in enumerate(canonical):
        start, end = mapping[i]
        out.append({"word": token, "start": max(0.0, start), "end": min(duration, max(end, start + 0.02))})
    return out


def ass_time(seconds: float) -> str:
    seconds = max(0.0, seconds)
    hours = int(seconds // 3600)
    minutes = int((seconds - hours * 3600) // 60)
    whole = seconds - hours * 3600 - minutes * 60
    sec = int(whole)
    centis = min(99, int(round((whole - sec) * 100)))
    if centis == 100:
        centis = 0
        sec += 1
    return f"{hours}:{minutes:02d}:{sec:02d}.{centis:02d}"


def ass_escape(text: str) -> str:
    return text.replace("\\", r"\\").replace("{", r"\{").replace("}", r"\}")


def phrase_chunks(section: str, tokens: list[dict[str, float | str]]) -> list[list[dict[str, float | str]]]:
    """Use editorial clause boundaries instead of arbitrary word-count cuts."""

    phrase_texts = PHRASES[section]
    expected = display_tokens(SCRIPT[section])
    actual = [str(item["word"]) for item in tokens]
    if len(expected) != len(actual):
        raise ValueError(f"{section}: caption token count {len(expected)} != aligned token count {len(actual)}")
    result: list[list[dict[str, float | str]]] = []
    offset = 0
    for text in phrase_texts:
        count = len(display_tokens(text))
        result.append(tokens[offset : offset + count])
        offset += count
    if offset != len(tokens):
        raise ValueError(f"{section}: phrase boundaries do not consume all tokens")
    return result


def wrap_words(words: list[str], max_chars: int = 55, prefix: str = "") -> str:
    """Wrap a complete caption block without changing its event/timing."""

    lines: list[str] = []
    current = prefix.strip()
    for word in words:
        candidate = f"{current} {word}".strip()
        if current and len(candidate) > max_chars:
            lines.append(current)
            current = word
        else:
            current = candidate
    if current:
        lines.append(current)
    return r"\N".join(lines)


def karaoke_text(phrase: list[dict[str, float | str]], event_end: float) -> str:
    pieces: list[str] = []
    line: list[str] = []
    line_chars = 0
    for i, item in enumerate(phrase):
        start = float(item["start"])
        if i + 1 < len(phrase):
            next_start = float(phrase[i + 1]["start"])
            duration = max(0.02, next_start - start)
        else:
            duration = max(0.02, min(event_end, float(item["end"])) - start)
        # ASS karaoke units are centiseconds; keep a visible minimum for tiny
        # function words while never making the tags negative.
        centis = max(2, int(round(duration * 100)))
        # ASS override tags must be wrapped in braces; without them libass
        # correctly treats the karaoke command as literal on-screen text.
        token = "{\\kf" + str(centis) + "}" + ass_escape(str(item["word"]))
        token_chars = len(str(item["word"])) + (1 if line else 0)
        if line and line_chars + token_chars > 68:
            pieces.append(" ".join(line))
            pieces.append(r"\N")
            line = [token]
            line_chars = len(str(item["word"]))
        else:
            line.append(token)
            line_chars += token_chars
    if line:
        pieces.append(" ".join(line))
    return "".join(pieces)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-run", type=Path, required=True)
    parser.add_argument("--out-run", type=Path, required=True)
    parser.add_argument("--model", default="tiny.en")
    args = parser.parse_args()

    source = args.source_run.resolve()
    out = args.out_run.resolve()
    out.mkdir(parents=True, exist_ok=True)
    (out / "render").mkdir(exist_ok=True)
    (out / "audio").mkdir(exist_ok=True)

    timeline = json.loads((source / "hype.timeline.json").read_text())
    assets = json.loads((source / "hype.assets.json").read_text())["assets"]
    audio_clips = [c for c in timeline["clips"] if c.get("id", "").startswith("audio_")]

    # Import only when building so the subtitle renderer itself remains a
    # plain ffmpeg/libass operation after this artifact has been produced.
    import whisper  # type: ignore

    model = whisper.load_model(args.model)
    transcript: dict[str, Any] = {"model": args.model, "sections": {}}
    global_chunks: list[dict[str, Any]] = []

    for clip in audio_clips:
        section = clip["id"][len("audio_") :]
        asset = assets[clip["asset"]]
        audio_path = Path(asset["file"])
        if not audio_path.exists():
            raise FileNotFoundError(audio_path)
        duration = float(clip["to"]) - float(clip.get("from", 0.0))
        result = model.transcribe(
            str(audio_path),
            language="en",
            task="transcribe",
            word_timestamps=True,
            fp16=False,
            temperature=0.0,
            condition_on_previous_text=False,
            initial_prompt=SCRIPT[section],
            verbose=False,
        )
        whisper_words = [w for seg in result.get("segments", []) for w in seg.get("words", [])]
        aligned = align_tokens(display_tokens(SCRIPT[section]), whisper_words, duration)
        transcript["sections"][section] = {
            "at": float(clip["at"]),
            "duration": duration,
            "asset": str(audio_path),
            "whisper_text": result.get("text", "").strip(),
            "whisper_words": whisper_words,
            "aligned_words": aligned,
        }
        for phrase in phrase_chunks(section, aligned):
            global_chunks.append({
                "section": section,
                "at": float(clip["at"]),
                "phrase": phrase,
            })

    # Copy the source-of-truth timeline pair and script into the new revision.
    for name in ("hype.timeline.json", "hype.assets.json", "actual-source-manifest.json", "script.md"):
        (out / name).write_bytes((source / name).read_bytes())
    (out / "whisper-word-timestamps.json").write_text(json.dumps(transcript, indent=2) + "\n")
    caption_script = "\n\n".join(
        f"## {section}\n\n" + "\n".join(f"- {phrase}" for phrase in PHRASES[section])
        for section in PHRASES
    )
    (out / "caption-script.md").write_text(caption_script + "\n")

    # ASS is deliberately generated rather than relying on a player-side
    # caption renderer: the delivered MP4 will look the same everywhere.
    header = r"""[Script Info]
ScriptType: v4.00+
PlayResX: 1280
PlayResY: 720
ScaledBorderAndShadow: yes
WrapStyle: 2
Collisions: Normal

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Current,Aptos,30,&H0000D7FF,&H00FFFFFF,&HCC000000,&H00000000,-1,0,0,0,100,100,0,0,1,4,1,2,64,64,0,1
Style: Next,Aptos,22,&H00B8B8B8,&H00B8B8B8,&HCC000000,&H00000000,0,0,0,0,100,100,0,0,1,3,1,8,64,64,0,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    lines = [header]
    for idx, item in enumerate(global_chunks):
        phrase = item["phrase"]
        start = item["at"] + float(phrase[0]["start"])
        # Hold the current phrase until the next phrase begins; this is useful
        # during natural pauses and keeps the lyric line readable.
        if idx + 1 < len(global_chunks):
            next_item = global_chunks[idx + 1]
            next_start = next_item["at"] + float(next_item["phrase"][0]["start"])
        else:
            next_start = start + max(0.35, float(phrase[-1]["end"]) - float(phrase[0]["start"]) + 0.55)
        end = max(start + 0.25, min(next_start, item["at"] + max(float(transcript["sections"][item["section"]]["duration"]), 0.25)))
        current = karaoke_text(phrase, end - item["at"])
        lines.append(
            f"Dialogue: 1,{ass_time(start)},{ass_time(end)},Current,,0,0,0,,{{\\an2\\pos(640,610)}}{current}\n"
        )
        if idx + 1 < len(global_chunks):
            next_phrase = global_chunks[idx + 1]["phrase"]
            preview = wrap_words(
                [ass_escape(str(w["word"])) for w in next_phrase],
                max_chars=90,
                prefix="UP NEXT  ›",
            )
            lines.append(
                f"Dialogue: 0,{ass_time(start)},{ass_time(end)},Next,,0,0,0,,{{\\an8\\pos(640,630)}}{preview}\n"
            )

    (out / "karaoke.ass").write_text("".join(lines))
    manifest = {
        "source_run": str(source),
        "source_video": str(source / "render" / "hype.mp4"),
        "subtitle_file": str(out / "karaoke.ass"),
        "subtitle_mode": "karaoke_current_phrase_with_up_next_preview",
        "word_timing_model": args.model,
        "render_filter": "ffmpeg ass/libass (burned-in)",
        "notes": "Editorial caption copy is displayed; local Whisper timings drive the word highlight. See caption-script.md for the polished phrasing.",
    }
    (out / "karaoke.manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps({"out_run": str(out), "subtitle_file": str(out / "karaoke.ass"), "sections": len(audio_clips), "phrases": len(global_chunks)}, indent=2))


if __name__ == "__main__":
    main()
