"""Command line interface for banodoco-social."""

from __future__ import annotations

import argparse
import json
import sys

from .models import PublishError
from .youtube import publish_youtube_video


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="banodoco-social")
    subparsers = parser.add_subparsers(dest="command", required=True)

    youtube = subparsers.add_parser("youtube", help="Publish a YouTube video via Zapier")
    youtube.add_argument(
        "--video-url",
        "--video",
        dest="video_url",
        required=True,
        help="Reachable http(s) video URL to publish.",
    )
    youtube.add_argument("--title", required=True, help="YouTube video title.")
    youtube.add_argument(
        "--description",
        required=True,
        help="YouTube video description.",
    )
    youtube.add_argument(
        "--tag",
        action="append",
        default=[],
        help="YouTube tag. May be repeated.",
    )
    youtube.add_argument(
        "--tags",
        action="append",
        default=[],
        help="Comma-separated YouTube tags.",
    )
    youtube.add_argument(
        "--privacy-status",
        default="private",
        help="YouTube privacy status: private, unlisted, or public.",
    )
    youtube.add_argument("--playlist-id", help="Optional YouTube playlist ID.")
    youtube.add_argument(
        "--made-for-kids",
        action="store_true",
        help="Mark the video as made for kids.",
    )
    youtube.set_defaults(func=_run_youtube)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


def _run_youtube(args: argparse.Namespace) -> int:
    try:
        result = publish_youtube_video(
            video_url=args.video_url,
            title=args.title,
            description=args.description,
            tags=[*args.tag, *args.tags],
            privacy_status=args.privacy_status,
            playlist_id=args.playlist_id,
            made_for_kids=args.made_for_kids,
        )
    except PublishError as exc:
        print(f"banodoco-social: {exc}", file=sys.stderr)
        return 1

    print(json.dumps(result.as_dict(), separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
