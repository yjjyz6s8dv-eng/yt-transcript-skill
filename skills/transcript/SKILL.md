---
name: transcript
description: Fetch the full transcript of a YouTube video (watch?v=, youtu.be/ or /shorts/ URL) and return it as clean, readable paragraphs in the video's original language. Use when the user runs /transcript, pastes a YouTube link and asks for its transcript, captions, subtitles or "what was said" in the video.
argument-hint: <youtube-url> [language]
allowed-tools: Bash(python:*), Bash(python3:*), Bash(py:*), PowerShell
---

# YouTube transcript

Arguments: `$ARGUMENTS`

## Steps

1. Take the YouTube URL from the arguments. If there is none, ask the user for one
   and stop. If the user also named a caption language (for example "en",
   "in Czech"), note its ISO code for step 2; otherwise use none.
2. Run the bundled script with Python, passing the URL as a single quoted argument
   (add `--lang <code>` only if the user asked for a specific language):

   ```
   python "${CLAUDE_SKILL_DIR}/scripts/get_transcript.py" "<url>"
   ```

   By default the script picks the video's **original spoken language** itself,
   including auto-dubbed videos that offer many auto-generated languages. Do not
   pass `--lang` to "help" it.

   - If `python` is not found, try `python3` (macOS/Linux) or `py` (Windows).
   - If the script reports that `youtube-transcript-api` is missing, install it with
     `python -m pip install -r "${CLAUDE_SKILL_DIR}/../../requirements.txt"`
     (or `python -m pip install youtube-transcript-api`), then run it again.
   - stdout contains the raw transcript, one caption line per row. stderr contains a
     `[transcript]` line naming the language used, or an error message.
3. If the script exits with a non-zero status, show the user the error from stderr
   (for example: invalid URL, captions disabled, video unavailable) and stop. Do not
   guess or make up a transcript.
3a. Sanity-check the language: if the `[transcript]` line's language clearly does
   not match the video (for example the title or the user says it is English, but
   Arabic captions came back), rerun the script with `--lang <correct code>`
   instead of translating the text yourself, and mention it in the header.
4. Format the raw transcript into readable text:
   - Join the caption fragments into full sentences and group them into logical
     paragraphs (a new paragraph when the topic or speaker changes).
   - Add correct punctuation and capitalization, and remove caption artifacts such
     as duplicated fragments, `[Music]`/`[Hudba]` style tags and `♪` markers when they break the
     flow, and stray line breaks.
   - **Always keep the original language of the transcript.** Do not translate it.
   - **Do not shorten, summarize, paraphrase or add content.** Every spoken
     sentence must stay in. Fix only obvious caption spelling errors.
   - Only summarize, translate or shorten if the user explicitly asks for it.
5. Reply with a one-line header noting the video and the caption language (and
   whether it was auto-generated), followed by the formatted transcript.
