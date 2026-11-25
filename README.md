# yt-transcript — Claude Code plugin

A Claude Code plugin with a `/transcript` skill. You give it a YouTube URL, it fetches the video's captions and Claude turns them into readable paragraphs with proper punctuation. The transcript stays in its original language, and nothing is cut or made up.

## Features

- Supported URL formats: `youtube.com/watch?v=…`, `youtu.be/…` and `youtube.com/shorts/…` (`/embed/` and `/live/` also work)
- Caption priority: the original video language first, then Czech (`cs`), then English (`en`), then any auto-generated track. If a video has one auto-generated track, that track's language is taken as the original. Auto-dubbed videos get one auto-generated track per dubbed language, so for those the script uses the audio track YouTube marks as the original. For videos that only have manually uploaded captions, it goes straight to cs → en.
- `--lang CODE` forces a specific caption language, e.g. `python skills/transcript/scripts/get_transcript.py URL --lang en`
- Clean UTF-8 output on every platform, including Windows consoles, so diacritics display correctly
- Clear errors and a non-zero exit code when a URL is invalid or a video has no captions

## Requirements

- Python 3.9+
- [`youtube-transcript-api`](https://pypi.org/project/youtube-transcript-api/) 1.2+

```bash
python -m pip install -r requirements.txt
```

## Installation

### As a plugin (from GitHub)

In Claude Code:

```
/plugin marketplace add <github-user>/yt-transcript-skill
/plugin install yt-transcript@yt-transcript-skill
```

The repository is its own marketplace: [`.claude-plugin/marketplace.json`](.claude-plugin/marketplace.json) lists the `yt-transcript` plugin, which sits at the repository root.

### Local test without installing

```bash
claude --plugin-dir /path/to/yt-transcript-skill
```

## Usage

```
/transcript https://www.youtube.com/watch?v=dQw4w9WgXcQ
```

If you only want the script:

```bash
python skills/transcript/scripts/get_transcript.py "https://youtu.be/dQw4w9WgXcQ"
```

The raw transcript goes to stdout. Diagnostics and errors go to stderr.

| Exit code | Meaning |
|-----------|---------|
| 0 | Transcript printed |
| 1 | No captions, video unavailable, or a network or YouTube error |
| 2 | Missing argument or invalid URL |

## Structure

```
.claude-plugin/plugin.json          plugin manifest
.claude-plugin/marketplace.json     marketplace listing (for /plugin marketplace add)
skills/transcript/SKILL.md          skill instructions for Claude
skills/transcript/scripts/get_transcript.py
requirements.txt
```
