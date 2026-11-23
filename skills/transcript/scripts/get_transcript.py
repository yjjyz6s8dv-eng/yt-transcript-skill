#!/usr/bin/env python3
"""Fetch the transcript of a YouTube video and print it as plain UTF-8 text.

Usage:
    python get_transcript.py <youtube-url-or-video-id>

Caption priority:
    1. Original video language (the language of YouTube's auto-generated
       track, which reflects the spoken audio; a manually created track in
       that language is preferred over the auto-generated one)
    2. Czech (cs)
    3. English (en)
    4. Any auto-generated captions
    5. Any captions at all

    Note: YouTube does not expose the spoken language of a video directly.
    It is inferred from the auto-generated track; videos with only manually
    uploaded captions fall straight through to cs -> en -> first track.

Exit codes:
    0  success
    1  transcript could not be retrieved (no captions, unavailable video, ...)
    2  invalid usage or URL
"""

from __future__ import annotations

import re
import sys
from urllib.parse import parse_qs, urlparse

try:
    from youtube_transcript_api import (
        CouldNotRetrieveTranscript,
        YouTubeTranscriptApi,
    )
except ImportError:  # pragma: no cover
    sys.stderr.write(
        "Error: youtube-transcript-api is not installed. "
        "Run: pip install -r requirements.txt\n"
    )
    sys.exit(1)

VIDEO_ID_RE = re.compile(r"^[A-Za-z0-9_-]{11}$")
YOUTUBE_HOSTS = {
    "youtube.com",
    "www.youtube.com",
    "m.youtube.com",
    "music.youtube.com",
    "youtube-nocookie.com",
    "www.youtube-nocookie.com",
}
FALLBACK_LANGUAGES = ("cs", "en")


def extract_video_id(url: str) -> str | None:
    """Return the 11-character video ID from a YouTube URL, or None."""
    url = url.strip()
    if VIDEO_ID_RE.match(url):
        return url

    if not re.match(r"^https?://", url, re.IGNORECASE):
        url = "https://" + url

    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    path_parts = [p for p in parsed.path.split("/") if p]

    candidate = None
    if host in ("youtu.be", "www.youtu.be"):
        candidate = path_parts[0] if path_parts else None
    elif host in YOUTUBE_HOSTS:
        if parsed.path == "/watch":
            candidate = parse_qs(parsed.query).get("v", [None])[0]
        elif len(path_parts) >= 2 and path_parts[0] in ("shorts", "embed", "live", "v"):
            candidate = path_parts[1]

    if candidate and VIDEO_ID_RE.match(candidate):
        return candidate
    return None


def pick_transcript(transcript_list):
    """Choose a transcript according to the priority described above."""
    transcripts = list(transcript_list)
    if not transcripts:
        return None

    manual = [t for t in transcripts if not t.is_generated]
    generated = [t for t in transcripts if t.is_generated]

    def find(lang: str):
        for group in (manual, generated):
            for t in group:
                if t.language_code == lang or t.language_code.split("-")[0] == lang:
                    return t
        return None

    # 1. Original language: the auto-generated track follows the spoken audio.
    if generated:
        original = find(generated[0].language_code)
        if original:
            return original

    # 2-3. Czech, then English.
    for lang in FALLBACK_LANGUAGES:
        t = find(lang)
        if t:
            return t

    # 4. Any auto-generated captions, 5. anything left.
    return (generated or manual)[0]


def main(argv: list[str]) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")

    if len(argv) != 2 or not argv[1].strip():
        sys.stderr.write("Usage: python get_transcript.py <youtube-url>\n")
        return 2

    video_id = extract_video_id(argv[1])
    if not video_id:
        sys.stderr.write(
            f"Error: '{argv[1]}' is not a valid YouTube video URL. Supported formats: "
            "youtube.com/watch?v=ID, youtu.be/ID, youtube.com/shorts/ID\n"
        )
        return 2

    try:
        transcript_list = YouTubeTranscriptApi().list(video_id)
        transcript = pick_transcript(transcript_list)
        if transcript is None:
            sys.stderr.write(f"Error: video {video_id} has no captions available.\n")
            return 1
        fetched = transcript.fetch()
    except CouldNotRetrieveTranscript as exc:
        reason = str(exc).strip().splitlines()
        sys.stderr.write(
            f"Error: could not retrieve a transcript for video {video_id} "
            f"({type(exc).__name__}).\n"
        )
        if reason:
            sys.stderr.write("\n".join(reason) + "\n")
        return 1
    except Exception as exc:  # network errors etc.
        sys.stderr.write(f"Error: failed to fetch transcript for {video_id}: {exc}\n")
        return 1

    lines = []
    for snippet in fetched:
        text = " ".join(snippet.text.replace("\n", " ").split())
        if text:
            lines.append(text)

    if not lines:
        sys.stderr.write(f"Error: the transcript for video {video_id} is empty.\n")
        return 1

    kind = "auto-generated" if transcript.is_generated else "manual"
    sys.stderr.write(
        f"[transcript] video={video_id} language={transcript.language_code} "
        f"({transcript.language}, {kind})\n"
    )
    sys.stdout.write("\n".join(lines) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
