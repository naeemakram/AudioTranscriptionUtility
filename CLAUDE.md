# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A personal CLI utility that transcribes audio files via the OpenAI Whisper API, then uses GPT-4o to reformat the raw transcript into readable, punctuated text with paragraph headings and timestamps (useful for turning YouTube video audio into chaptered, SEO-friendly text). It also generates a YouTube title/description/tags JSON blob from the result via GPT-3.5-turbo.

The entire application logic lives in `main.py` — there is no package structure, no tests, and no web server. `tts.py` is an unrelated scratch script for OpenAI text-to-speech and is not wired into the CLI.

## Running

Requires `OPENAI_API_KEY` to be set as an environment variable.

```bash
python main.py <path-to-audio-file>          # transcribe + AI-format + generate YouTube metadata JSON
python main.py <path-to-audio-file> --srt    # also emit a .srt subtitle file alongside the transcript
python main.py <path-to-text-file.txt>       # skip transcription, just AI-format an existing .txt transcript
```

Dependencies are declared in both `pyproject.toml` (Poetry) and `requirements.txt` (plain pip); only dependency is `openai`. Install with either:

```bash
poetry install
# or
pip install -r requirements.txt
```

There is no test suite, linter, or build step configured in this repo.

## Architecture / control flow

`main()` in `main.py` branches on the input file's extension:

- **`.txt` input** — reads the file as an already-transcribed plain string and pipes it directly into `format_transcript_with_ai()`, printing the result. No transcription or JSON metadata step happens on this path.
- **Audio input (anything else)** — runs the full pipeline in `transcribe_audio()`:
  1. Calls `client.audio.transcriptions.create()` with `model="whisper-1"`, `response_format="verbose_json"`, `timestamp_granularities=["segment"]`, `language="en"` — this returns a `TranscriptionVerbose` object with per-segment start/end timestamps, not just plain text.
  2. Passes the transcript into `format_transcript_with_ai()`, which special-cases `TranscriptionVerbose` objects: it rebuilds the text as `[MM:SS] segment text` lines before sending to GPT-4o, so the model can anchor paragraph headings to real timestamps. Plain strings (from the `.txt` path) skip this step and go straight into the prompt.
  3. If `--srt` was passed, independently converts the same segments to `.srt` format via `format_to_srt()` / `format_srt_timestamp()` and writes `<input>.srt`.
  4. Writes the AI-formatted transcript to `<input>_transcription.txt`.
  5. Feeds the formatted transcript to `format_text_to_json()` (GPT-3.5-turbo) to produce a title/description/tags JSON string for YouTube, and writes it to `<input>_json.txt`.

All three OpenAI-calling functions (`format_transcript_with_ai`, `format_text_to_json`, `transcribe_audio`) catch exceptions internally and return an error string or empty string rather than raising — callers print whatever comes back rather than handling failures explicitly. Keep this pattern if extending them, since `main()` doesn't do its own try/except around these calls.

`format_text_to_json()` asks the model to return JSON as a plain string; it is not parsed or validated before being written to disk, so downstream consumers of `*_json.txt` should not assume it's valid JSON.
