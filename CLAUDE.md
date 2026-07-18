# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A personal CLI utility that transcribes audio files via the OpenAI Whisper API, then uses a configurable OpenAI chat model to reformat the raw transcript into readable, punctuated text with paragraph headings and timestamps (useful for turning YouTube video audio into chaptered, SEO-friendly text). It also generates a YouTube title/description/tags JSON blob from the result, via another configurable model.

It supports two output modes: a YouTube mode (default) that produces timestamped, chaptered plain text plus title/description/tags metadata JSON, and a `--udemy` mode that instead produces clean Markdown lecture notes with chapter headings and no timestamps, with no metadata JSON step at all.

The entire application logic lives in `main.py` — there is no package structure, no tests, and no web server. `tts.py` is an unrelated scratch script for OpenAI text-to-speech and is not wired into the CLI. Which OpenAI models are used is controlled by `config.json` — see Model configuration below.

## Running

Requires `OPENAI_API_KEY` to be set as an environment variable.

```bash
python main.py <path-to-audio-file>          # transcribe + AI-format + generate YouTube metadata JSON
python main.py <path-to-audio-file> --srt    # also emit a .srt subtitle file alongside the transcript
python main.py <path-to-audio-file> --udemy  # transcribe + format as Markdown lecture notes, skip YouTube JSON metadata step
python main.py <path-to-text-file.txt>       # skip transcription, just AI-format an existing .txt transcript
python main.py <path-to-folder>              # batch: process every audio file directly inside the folder
```

`--srt` and `--udemy` are independent flags and can be combined.

Dependencies are declared in both `pyproject.toml` (Poetry) and `requirements.txt` (plain pip); only dependency is `openai`. Install with either:

```bash
poetry install
# or
pip install -r requirements.txt
```

There is no test suite, linter, or build step configured in this repo.

## Architecture / control flow

`main()` in `main.py` branches on the input path:

- **`.txt` input** — reads the file as an already-transcribed plain string and pipes it directly into `format_transcript_with_ai()`, printing the result. No transcription or JSON metadata step happens on this path. `--udemy` still applies here (it changes which prompt pair is used, so the printed result is Markdown lecture notes instead of timestamped plain text) — but this path never writes a file, in either mode.
- **Folder input** — `process_folder()` scans the folder (non-recursive) for files matching `AUDIO_EXTENSIONS`, then calls `process_audio_file()` on each in turn, continuing past individual failures and printing a succeeded/failed summary at the end.
- **Audio input (anything else)** — `process_audio_file()` runs the full pipeline via `transcribe_audio()`:
  1. Calls `client.audio.transcriptions.create()` with `model=CONFIG["transcription_model"]`, `response_format="verbose_json"`, `timestamp_granularities=["segment"]`, `language="en"` — this returns a `TranscriptionVerbose` object with per-segment start/end timestamps, not just plain text. This only works with `whisper-1`; see Model configuration below.
  2. Passes the transcript into `format_transcript_with_ai()`, which special-cases `TranscriptionVerbose` objects: it rebuilds the text as `[MM:SS] segment text` lines before sending to `CONFIG["format_model"]`, so the model can anchor paragraph headings to real timestamps. Plain strings (from the `.txt` path) skip this step and go straight into the prompt. Which prompt pair is used depends on the `udemy` flag: `format_system_prompt`/`format_user_prompt` (default) or `udemy_format_system_prompt`/`udemy_format_user_prompt` (`--udemy`) — see Prompt configuration below.
  3. If `--srt` was passed, independently converts the same segments to `.srt` format via `format_to_srt()` / `format_srt_timestamp()` and writes `<input>.srt`. This is unaffected by `--udemy`.
  4. Writes the AI-formatted transcript to `<input>_transcription.txt`, or `<input>_transcription.md` when `--udemy` was passed.
  5. **Default mode only** — feeds the formatted transcript to `format_text_to_json()` (`CONFIG["json_model"]`) to produce a title/description/tags JSON string for YouTube, and writes it to `<input>_json.txt`. This step is skipped entirely in `--udemy` mode — `process_audio_file()` returns right after step 4, so no `_json.txt` is produced.

All three OpenAI-calling functions (`format_transcript_with_ai`, `format_text_to_json`, `transcribe_audio`) catch exceptions internally and return an error string or empty string rather than raising — callers print whatever comes back rather than handling failures explicitly. Keep this pattern if extending them, since `main()` doesn't do its own try/except around these calls.

`format_text_to_json()` asks the model to return JSON as a plain string; it is not parsed or validated before being written to disk, so downstream consumers of `*_json.txt` should not assume it's valid JSON.

## Model configuration

Model names are not hardcoded — `main.py` loads them from `config.json` (same directory as the script) into the module-level `CONFIG` dict via `load_config()`. Keys: `transcription_model`, `format_model`, `json_model`. If `config.json` is missing or has invalid JSON, `load_config()` falls back to `DEFAULT_CONFIG` (printing a warning on invalid JSON) rather than raising — keep that fallback behavior if you touch this code.

To change which model is used for formatting or JSON generation, edit `config.json` directly; no code change needed.

`transcription_model` should stay `whisper-1` — it's the only OpenAI transcription model that supports `response_format="verbose_json"` with segment-level timestamps, which the chapter-heading formatting and `--srt` output both depend on. Newer transcription models (e.g. `gpt-4o-transcribe`) drop that capability.

## Prompt configuration

The system/user prompts sent to `format_model` and `json_model` are also config-driven, via the same `CONFIG`/`DEFAULT_CONFIG`/`load_config()` mechanism as the model keys: `format_system_prompt`, `format_user_prompt`, `json_system_prompt`, `json_user_prompt`, plus the `--udemy`-mode equivalents `udemy_format_system_prompt`, `udemy_format_user_prompt`. Any subset (including none) may be present in `config.json` — missing keys fall back to `DEFAULT_CONFIG`.

`format_user_prompt`, `udemy_format_user_prompt`, and `json_user_prompt` are templates: the literal token `{{transcript}}` marks where the transcript text is substituted in, via `str.replace()` (not `str.format()`/f-strings, so custom prompts containing `{`/`}` don't break substitution). If a custom template omits `{{transcript}}`, the transcript simply won't be included in the request — that's a user error, not something the code guards against.

Note that the segment-derived input text built in `format_transcript_with_ai()` (the `[MM:SS] segment text` lines) is the same regardless of `udemy`, so it still carries timestamp prefixes even in `--udemy` mode. It's `udemy_format_user_prompt`'s job — not the code's — to instruct the model to use those timestamps only to detect topic breaks and exclude them from its Markdown output.
