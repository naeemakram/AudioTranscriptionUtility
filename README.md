# Audio Transcription Utility

A lightweight Python CLI that turns audio recordings into clean, readable, **SEO-ready** text using the **OpenAI Whisper** and **GPT-4o** APIs. Built for content creators who want to upcycle video and podcast audio into blog posts, slide decks, social captions, and **timestamped YouTube chapters** — automatically.

**Keywords:** audio transcription, speech-to-text, OpenAI Whisper, GPT-4o, Python CLI, YouTube chapters, SRT subtitles, video SEO, content repurposing, batch transcription.

---

## Why this exists

After returning to content creation, I needed a fast way to extract text from my videos so I could repurpose that content into other formats. I'd been reading about OpenAI's Whisper model, so I built this script to transcribe a variety of audio formats and then hand the raw output back to OpenAI for AI-powered cleanup.

For context on cost: transcribing an 18-minute English audio file in `.m4a` format cost roughly **11 cents**. All API calls and prompts are visible in the source (`main.py`); API keys are read from the environment and never committed.

## Features

- **Accurate transcription** via OpenAI Whisper (`whisper-1`) with per-segment timestamps.
- **AI-formatted output** — GPT-4o adds punctuation, capitalization, and paragraph breaks, and inserts **timestamped paragraph headings** ideal for auto-generating YouTube chapters and improving video SEO.
- **YouTube metadata generation** — automatically drafts a title, description, and tags (as JSON) from the transcript.
- **Optional `.srt` subtitles** — export standards-compliant subtitle files from the same Whisper segments.
- **Single file, folder batch, or existing transcript** — point it at one recording, a whole folder, or a `.txt` you already have.
- **Resilient batch processing** — in folder mode, a file that fails is reported at the end without stopping the rest.

## Setup

1. Install dependencies (only dependency is `openai`):
   ```
   pip install -r requirements.txt
   ```
   or, if you use Poetry:
   ```
   poetry install
   ```
2. Set your OpenAI API key as an environment variable:
   ```
   set OPENAI_API_KEY=sk-...        # Windows cmd
   $env:OPENAI_API_KEY = "sk-..."   # PowerShell
   export OPENAI_API_KEY=sk-...     # macOS/Linux
   ```
3. (Optional) Copy `sample_config.json` to `config.json` and edit it to change which OpenAI models are used, and/or customize the prompts sent to them:
   ```
   cp sample_config.json config.json
   ```
   Leave `transcription_model` as `whisper-1` — it's the only OpenAI transcription model that returns the segment timestamps this tool needs for chapter headings and `--srt` output.

   `config.json` also supports `format_system_prompt`, `format_user_prompt`, `json_system_prompt`, and `json_user_prompt` for customizing the formatting/JSON prompts. Any subset (including none) may be set — missing keys fall back to the built-in defaults. In `format_user_prompt` and `json_user_prompt`, the literal token `{{transcript}}` marks where the transcript is inserted.

## Usage

```
python main.py <path> [--srt]
```

`<path>` can be an audio file, a folder of audio files, or a plain-text transcript. Behavior depends on which one you give it.

### 1. A single audio file

```
python main.py meeting.m4a
```

Supported audio formats: `.mp3`, `.mp4`, `.mpeg`, `.mpga`, `.m4a`, `.wav`, `.webm`.

This transcribes the audio with Whisper, then uses an OpenAI chat model to clean it up into readable text with punctuation, capitalization, and timestamped paragraph headings (which model is used is configurable — see below). Two files are written next to the source audio:

- `meeting_transcription.txt` — the AI-formatted transcript
- `meeting_json.txt` — generated YouTube title/description/tags (JSON), based on the transcript

### 2. A folder of audio files

```
python main.py path/to/folder
```

Every supported audio file directly inside the folder is transcribed and formatted one at a time. Output files for each recording are written into the same folder, next to their source, following the naming pattern above. Files that fail to process are reported in a summary at the end without halting the batch.

### 3. Add `--srt` to also generate subtitles

```
python main.py meeting.m4a --srt
python main.py path/to/folder --srt
```

Produces an additional `.srt` subtitle file (e.g. `meeting.srt`) alongside the transcript, using the same timestamped segments returned by Whisper. Works for both single files and folder batches.

### 4. Reformat an existing transcript

```
python main.py notes.txt
```

If you already have a plain-text transcript, pass the `.txt` file directly to skip transcription and just run the AI formatting step. The formatted result is printed to the console (no output file is written in this mode).

## How it works

| Stage | Model | Purpose |
| --- | --- | --- |
| Transcription | `whisper-1` (`verbose_json`, segment timestamps) | Speech-to-text with per-segment start/end times |
| Formatting | `format_model` (configurable, see `config.json`) | Punctuation, paragraphs, timestamped headings |
| YouTube metadata | `json_model` (configurable, see `config.json`) | Title, description, and tags as JSON |

Both the models and their prompts are configurable via `config.json` (see Setup above) — no code change needed. All logic lives in a single `main.py` — no framework, no server, easy to read and adapt.

## Notes

- Requires Python 3 and a valid `OPENAI_API_KEY`.
- The generated `*_json.txt` is produced by the model as text and is not strictly validated, so treat it as a draft rather than guaranteed-parseable JSON.
