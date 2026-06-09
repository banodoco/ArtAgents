"""Download a YouTube video's audio (MP3) or video (MP4) — via search or direct URL."""


from __future__ import annotations

from astrid.core.contracts.errors import AstridError
from astrid.core.pack.entrypoint import guard_canonical_entrypoint

guard_canonical_entrypoint('youtube.youtube_audio')
import argparse
import shutil
import subprocess
import sys
from datetime import datetime, timezone  # noqa: E402
from pathlib import Path
from typing import Any

from astrid.core._shared.result_manifest import write_manifest  # noqa: E402
from astrid.core.cli_choices import add_choice_arg  # noqa: E402
from astrid.core.pack.entrypoint import run_pack_main  # noqa: E402


from astrid.core.contracts.die import pack_die


def _die(msg: str, code: int = 2) -> None:
    pack_die(
        msg,
        recovery_command="install the missing dependency or fix the YouTube download inputs, then rerun",
        state_snapshot={"exit_code": code},
    )


def main(argv: list[str] | None = None) -> int:
    def _run() -> int:
        parser = argparse.ArgumentParser(description=__doc__)
        src = parser.add_mutually_exclusive_group(required=True)
        src.add_argument("--query", help="YouTube search query; the top hit is used. If this is a direct http(s) URL, it is downloaded directly.")
        src.add_argument("--url", help="Direct YouTube URL; skips search.")
        add_choice_arg(
            parser,
            "--mode",
            values=("audio", "video"),
            default="audio",
            help="audio: extract to MP3 (default, legacy behaviour). video: download MP4 without audio extraction.",
        )
        parser.add_argument(
            "--out",
            required=True,
            type=Path,
            help="Output path. Extension is appended to match --mode if missing.",
        )
        parser.add_argument(
            "--audio-format",
            default="mp3",
            help="Audio format passed to yt-dlp --audio-format (audio mode only).",
        )
        parser.add_argument(
            "--audio-quality",
            default="0",
            help="yt-dlp --audio-quality (audio mode only, 0 = best for VBR).",
        )
        parser.add_argument(
            "--video-format",
            default="bv*[ext=mp4]+ba[ext=m4a]/b[ext=mp4]/bv*+ba/b",
            help="yt-dlp -f selector (video mode only). Default prefers mp4 but falls back to merging best A+V.",
        )
        parser.add_argument(
            "--merge-output-format",
            default="mp4",
            help="yt-dlp --merge-output-format (video mode only); ensures final container is mp4.",
        )
        args = parser.parse_args(argv)

        if not shutil.which("yt-dlp"):
            _die("yt-dlp not found on PATH. Install via `pip install yt-dlp`.")
        if args.mode == "audio" and not shutil.which("ffmpeg"):
            _die("ffmpeg not found on PATH. yt-dlp needs it to extract audio.")

        out = args.out
        default_ext = args.audio_format if args.mode == "audio" else "mp4"
        if out.suffix == "":
            out = out.with_suffix(f".{default_ext}")
        out.parent.mkdir(parents=True, exist_ok=True)

        output_template = str(out.with_suffix(".%(ext)s"))
        if args.url:
            target = args.url
        elif args.query and args.query.startswith(("http://", "https://")):
            target = args.query
        else:
            target = f"ytsearch1:{args.query}"

        cmd = ["yt-dlp", "--no-warnings", "--output", output_template]
        if args.mode == "audio":
            cmd += [
                "--extract-audio",
                f"--audio-format={args.audio_format}",
                f"--audio-quality={args.audio_quality}",
            ]
        else:
            cmd += ["-f", args.video_format, "--merge-output-format", args.merge_output_format]
        cmd.append(target)

        print(f"[youtube_audio] {' '.join(cmd)}", file=sys.stderr)
        proc = subprocess.run(cmd, capture_output=True, text=True)
        if proc.returncode != 0:
            raise AstridError(
                f"yt-dlp failed (exit {proc.returncode})",
                recovery_command="inspect the YouTube URL/query and retry the download",
                state_snapshot={"stdout": proc.stdout, "stderr": proc.stderr},
            )

        if not out.exists():
            raise AstridError(
                f"yt-dlp returned success but expected output {out} is missing",
                recovery_command="re-run youtube.youtube_audio and inspect the yt-dlp output",
                state_snapshot={"stdout": proc.stdout, "stderr": proc.stderr},
            )

        print(f"Downloaded: {out} ({out.stat().st_size:,} bytes)", file=sys.stderr)

        # --- universal result manifest (output-contract M2) -----------------------
        manifest_path = out.parent / "manifest.json"
        manifest: dict[str, Any] = {
            "schema_version": 1,
            "kind": "youtube_audio",
            "inputs": {
                "target": target,
                "mode": args.mode,
            },
            "outputs": [
                {"path": out.name, "type": "file"},
            ],
            "created": datetime.now(timezone.utc).isoformat(),
            "warnings": [],
        }
        write_manifest(manifest_path, manifest)
        # -------------------------------------------------------------------------

        return 0

    return run_pack_main("youtube.youtube_audio", _run, argv=argv)


if __name__ == "__main__":
    raise SystemExit(main())
