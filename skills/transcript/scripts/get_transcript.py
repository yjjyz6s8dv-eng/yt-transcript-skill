#!/usr/bin/env python3
"""Fetch the transcript of a YouTube video and print it as plain UTF-8 text.

Usage:
    python get_transcript.py <youtube-url-or-video-id> [--lang CODE]

Caption priority:
    0. --lang CODE, if given (e.g. --lang en)
    1. Original video language (a manually created track in that language is
       preferred over the auto-generated one). It is determined like this:
       - one auto-generated track: its language is the spoken language;
       - several auto-generated tracks (YouTube auto-dubbing adds one per
         dubbed audio track, listed alphabetically, so the first one is NOT
         the original): the language of the audio track YouTube marks as
         the original/default.
    2. Czech (cs)
    3. English (en)
    4. Any auto-generated captions
    5. Any captions at all

    Videos with only manually uploaded captions have no reliable spoken-
    language signal and fall straight through to cs -> en -> first track.

Exit codes:
    0  success
    1  transcript could not be retrieved (no captions, unavailable video, ...)
    2  invalid usage or URL
"""

from __future__ import annotations

import argparse
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


def _base_lang(code: str) -> str:
    return code.split(".")[0].split("-")[0].lower()


def detect_original_audio_language(api, video_id: str) -> str | None:
    """Best effort: return the language of the video's original audio track.

    Only needed for auto-dubbed videos (several audio tracks). Reads YouTube's
    player data through the library's internal fetcher; returns None if that
    is unavailable or the data has no usable signal, so callers must cope.
    """
    try:
        fetcher = api._fetcher
        html = fetcher._fetch_video_html(video_id)
        data = fetcher._fetch_innertube_data(
            video_id, fetcher._extract_innertube_api_key(html, video_id)
        )
    except Exception:
        return None

    # Signal 1: the stream whose audio track is flagged as the default one.
    for fmt in (data.get("streamingData") or {}).get("adaptiveFormats") or []:
        track = fmt.get("audioTrack") or {}
        if track.get("audioIsDefault") and track.get("id"):
            return _base_lang(track["id"])

    # Signal 2: the default entry in the captions' audio-track list.
    captions = (data.get("captions") or {}).get("playerCaptionsTracklistRenderer") or {}
    tracks = captions.get("audioTracks") or []
    index = captions.get("defaultAudioTrackIndex")
    if isinstance(index, int) and 0 <= index < len(tracks):
        track_id = tracks[index].get("audioTrackId")
        if track_id:
            return _base_lang(track_id)
    return None


def pick_transcript(transcript_list, preferred: str | None = None, original_lang_fn=None):
    """Choose a transcript according to the priority described above.

    original_lang_fn is called (without arguments) only when the original
    language cannot be read from the track list itself.
    """
    transcripts = list(transcript_list)
    if not transcripts:
        return None

    manual = [t for t in transcripts if not t.is_generated]
    generated = [t for t in transcripts if t.is_generated]

    def find(lang: str):
        lang = _base_lang(lang)
        for group in (manual, generated):
            for t in group:
                if _base_lang(t.language_code) == lang:
                    return t
        return None

    # 0. Explicit request.
    if preferred:
        t = find(preferred)
        if t:
            return t
        sys.stderr.write(
            f"[transcript] warning: no '{preferred}' captions; available: "
            + ", ".join(t.language_code for t in transcripts)
            + "\n"
        )

    # 1. Original language.
    original_lang = None
    if len(generated) == 1:
        # A single auto-generated track transcribes the original audio.
        original_lang = generated[0].language_code
    elif len(generated) > 1 and original_lang_fn is not None:
        # Auto-dubbed video: the track order says nothing; ask YouTube.
        original_lang = original_lang_fn()
    if original_lang:
        original = find(original_lang)
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

    parser = argparse.ArgumentParser(
        description="Print the transcript of a YouTube video as plain text."
    )
    parser.add_argument("url", help="YouTube URL (watch?v=, youtu.be/, /shorts/) or video ID")
    parser.add_argument(
        "--lang", help="caption language to prefer, e.g. en or cs (default: original language)"
    )
    args = parser.parse_args(argv[1:])

    video_id = extract_video_id(args.url) if args.url.strip() else None
    if not video_id:
        sys.stderr.write(
            f"Error: '{args.url}' is not a valid YouTube video URL. Supported formats: "
            "youtube.com/watch?v=ID, youtu.be/ID, youtube.com/shorts/ID\n"
        )
        return 2

    try:
        api = YouTubeTranscriptApi()
        transcript_list = api.list(video_id)
        transcript = pick_transcript(
            transcript_list,
            preferred=args.lang,
            original_lang_fn=lambda: detect_original_audio_language(api, video_id),
        )
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
