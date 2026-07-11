After returning to content creation I noticed that I needed to extract text from my videos to upcycle my content into other formats such as slide decks and posts. 
I'd read about OpenAI whisper library so I quickly created this script for extracting text from a variety of file formats.
Cost of transcribing an 18 minutes long, English audio file in m4a format cost me 11 cents.
I then sent it over to OpenAI again and got it formatted with another prompt. All calls and prompts in this example can be seen in my code. 
The API keys are hidden away for obvious security reasons. 

## Setup

1. Install dependencies:
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

## Usage

```
python main.py <path> [--srt]
```

`<path>` can be an audio file, a folder of audio files, or a plain-text transcript. What happens depends on which one you give it:

### 1. A single audio file

```
python main.py meeting.m4a
```

Supported audio formats: `.mp3`, `.mp4`, `.mpeg`, `.mpga`, `.m4a`, `.wav`, `.webm`.

This transcribes the audio with Whisper, then uses GPT-4o to clean it up into readable text with punctuation, capitalization, and timestamped paragraph headings. Two files are written next to the source audio:

- `meeting_transcription.txt` — the formatted transcript
- `meeting_json.txt` — a generated YouTube title/description/tags JSON, based on the transcript

### 2. A folder of audio files

```
python main.py path/to/folder
```

Every audio file directly inside the folder (matching the extensions above) is transcribed and formatted one at a time. Output files for each recording are written into the same folder, next to their source file, following the naming pattern above. Files that fail to process are reported at the end without stopping the rest of the batch.

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

If you already have a plain-text transcript, pass the `.txt` file directly to skip transcription and just run it through the AI formatting step. The formatted result is printed to the console (no output file is written for this mode).
