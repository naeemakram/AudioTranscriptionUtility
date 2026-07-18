import os
import json
import datetime
from openai import OpenAI
import sys
import argparse


DEFAULT_CONFIG = {
    # Must stay whisper-1: it's the only OpenAI transcription model that
    # returns segment-level timestamps (response_format="verbose_json"),
    # which the chapter-heading and --srt features both depend on.
    "transcription_model": "whisper-1",
    "format_model": "gpt-5.6-luna",
    "json_model": "gpt-5.6-luna",
    "format_system_prompt": "You are a professional text editor. Format transcribed text with proper punctuation, capitalization, paragraph breaks, and detect paragraph subject to mark every paragraph with proper paragraph headings.",
    "format_user_prompt": """You are an expert in making text data look readable by only changing it's formatting and punctionation without adding any new content. Keep only the human readable part. Please format the following transcribed text with proper punctuation, capitalization, and paragraph breaks. Make it readable and well-structured. Add pargraph headings with starting timestamps. Keep timestamps only for paragraph headings, keep paragraph body clean text. <text>

{{transcript}}
</text>
Return only the formatted text without any additional commentary.""",
    "udemy_format_system_prompt": "You are an expert technical editor who converts raw lecture transcripts into clean, well-structured Markdown study notes. You never invent, summarize away, or omit content — you only reformat.",
    "udemy_format_user_prompt": """You are formatting a raw lecture transcript into clean Markdown. The input text is prefixed per line with [MM:SS] timestamps taken from the audio — use those timestamps only to detect where one topic ends and a new one begins. Do not include any timestamps, time codes, or [MM:SS] markers anywhere in your output.

Convert the transcript into well-structured Markdown:
- Use "##" for major topic/chapter headings and "###" for sub-topics within a chapter, based on natural topic breaks in the lecture.
- Write clear, descriptive heading titles based on what is actually discussed in that section (do not use timestamps as headings).
- Keep the body text as clean, readable prose or bullet lists where appropriate, with correct punctuation and capitalization.
- Do not add any promotional or marketing language, calls to action, hashtags, or tags — this is lecture material, not video marketing copy.
- Do not invent, add, or embellish any content that is not present in the transcript; only reformat what is there.
<text>

{{transcript}}
</text>
Return only the Markdown-formatted lecture notes, with no additional commentary before or after.""",
    "json_system_prompt": "You are a helpful assistant that formats text into JSON.",
    "json_user_prompt": "You're a gen-z copywriter with great information and experience of writing viral content for the internet youtube etc. Write youtube video title, description, tags  for a video based to the supplied text. Return data in json format. with keys title, description, tags. Keep tags a string with comma separated tags.<text>{{transcript}}</text>",
    # $ pricing per model, used to estimate cost in the end-of-run usage summary.
    # Chat models: input_per_1m_tokens / output_per_1m_tokens. Whisper: per_minute
    # (billed by audio duration, not tokens). A model missing here is reported as
    # "price unknown" rather than assumed free.
    "pricing": {
        "whisper-1": {"per_minute": 0.006},
        "gpt-5.6-luna": {"input_per_1m_tokens": 0, "output_per_1m_tokens": 0},
    },
}
CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")
USAGE_LOG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "usage_log.txt")


def load_config():
    """
    Load model configuration from config.json next to this script,
    falling back to DEFAULT_CONFIG for any missing keys.
    """
    config = DEFAULT_CONFIG.copy()
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            config.update(json.load(f))
    except FileNotFoundError:
        pass
    except json.JSONDecodeError as e:
        print(f"Warning: config.json is invalid ({str(e)}). Using default models.")
    return config


CONFIG = load_config()

# One dict per successful OpenAI call made during this process run, used to
# build the end-of-run usage/cost summary.
USAGE_RECORDS = []


def format_transcript_with_ai(transcript, client, udemy=False):
    """
    Use OpenAI to format the transcript with proper punctuation and structure
    Can handle both plain text strings and TranscriptionVerbose objects.
    When udemy=True, formats as Markdown lecture notes (no timestamps in
    output) instead of the default YouTube-style timestamped headings.
    """
    try:
        # Handle TranscriptionVerbose object
        if hasattr(transcript, 'segments') and hasattr(transcript, 'text'):
            # Build formatted text with timestamps from segments
            segments_text = ""
            for segment in transcript.segments:
                start_time = int(segment.start)
                minutes = start_time // 60
                seconds = start_time % 60
                timestamp = f"[{minutes:02d}:{seconds:02d}]"
                segments_text += f"{timestamp} {segment.text}\n"

            text_to_format = segments_text
        else:
            # Handle plain text string
            text_to_format = str(transcript)

        system_prompt_key = "udemy_format_system_prompt" if udemy else "format_system_prompt"
        user_prompt_key = "udemy_format_user_prompt" if udemy else "format_user_prompt"

        prompt = CONFIG[user_prompt_key].replace("{{transcript}}", text_to_format)
        print("Formatting text with AI...")
        response = client.chat.completions.create(
            model=CONFIG["format_model"],
            messages=[{
                "role": "system",
                "content": CONFIG[system_prompt_key]
            }, {
                "role": "user",
                "content": prompt
            }],
            temperature=1)

        if response.usage:
            USAGE_RECORDS.append({
                "type": "chat",
                "model": CONFIG["format_model"],
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
            })

        return response.choices[0].message.content.strip()

    except Exception as e:
        print(
            f"Warning: AI formatting failed ({str(e)}). Using basic formatting instead."
        )
        return ""


def format_text_to_json(text, api_key):
    """
    Convert formatted text to JSON using OpenAI's completion API.
    """
    try:
        client = OpenAI(api_key=api_key)

        prompt = CONFIG["json_user_prompt"].replace("{{transcript}}", text)

        response = client.chat.completions.create(
            model=CONFIG["json_model"],
            messages=[{
                "role": "system",
                "content": CONFIG["json_system_prompt"]
            }, {
                "role": "user",
                "content": prompt
            }],
            max_tokens=2500,
            temperature=0.2)

        if response.usage:
            USAGE_RECORDS.append({
                "type": "chat",
                "model": CONFIG["json_model"],
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
            })

        formatted_json = response.choices[0].message.content.strip()

        return formatted_json

    except Exception as e:
        print(
            f"Warning: Conversion to JSON failed ({str(e)}). Returning None."
        )
        return None


def format_to_srt(transcript):
    """
    Convert transcript segments to SRT format
    """
    if not hasattr(transcript, 'segments'):
        return ""
    
    srt_content = ""
    for i, segment in enumerate(transcript.segments, 1):
        # Convert seconds to SRT time format (HH:MM:SS,mmm)
        start_seconds = segment.start
        end_seconds = segment.end
        
        start_time = format_srt_timestamp(start_seconds)
        end_time = format_srt_timestamp(end_seconds)
        
        # SRT format: sequence number, timestamp, text, blank line
        srt_content += f"{i}\n{start_time} --> {end_time}\n{segment.text.strip()}\n\n"
    
    return srt_content


def format_srt_timestamp(seconds):
    """
    Convert seconds to SRT timestamp format (HH:MM:SS,mmm)
    """
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    milliseconds = int((seconds % 1) * 1000)
    
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{milliseconds:03d}"


def calculate_cost(record):
    """
    Estimate the $ cost of a single usage record from CONFIG["pricing"].
    Returns None if the record's model has no pricing entry, or has an
    all-zero placeholder entry (not yet filled in with real rates).
    """
    pricing = CONFIG.get("pricing", {}).get(record["model"])
    if not pricing:
        return None

    if record["type"] == "transcription":
        per_minute = pricing.get("per_minute", 0)
        if not per_minute:
            return None
        return record["minutes"] * per_minute

    input_rate = pricing.get("input_per_1m_tokens", 0)
    output_rate = pricing.get("output_per_1m_tokens", 0)
    if not input_rate and not output_rate:
        return None
    return (record["prompt_tokens"] / 1_000_000) * input_rate \
        + (record["completion_tokens"] / 1_000_000) * output_rate


def build_usage_summary():
    """
    Aggregate USAGE_RECORDS by model into a formatted summary string.
    Used for both the console printout and the usage_log.txt entry.
    """
    if not USAGE_RECORDS:
        return None

    by_model = {}
    for record in USAGE_RECORDS:
        by_model.setdefault(record["model"], []).append(record)

    lines = []
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    lines.append("=" * 45)
    lines.append(f"USAGE SUMMARY — {timestamp}")
    lines.append("=" * 45)

    total_cost = 0
    any_unknown_pricing = False

    for model, records in by_model.items():
        cost = 0
        unknown_pricing = False
        for record in records:
            record_cost = calculate_cost(record)
            if record_cost is None:
                unknown_pricing = True
            else:
                cost += record_cost

        if records[0]["type"] == "transcription":
            minutes = sum(r["minutes"] for r in records)
            usage_desc = f"{minutes:.1f} min"
        else:
            prompt_tokens = sum(r["prompt_tokens"] for r in records)
            completion_tokens = sum(r["completion_tokens"] for r in records)
            usage_desc = f"{prompt_tokens:,} in / {completion_tokens:,} out tokens ({len(records)} call{'s' if len(records) != 1 else ''})"

        if unknown_pricing:
            any_unknown_pricing = True
            cost_desc = 'price unknown (add "pricing" entry in config.json)'
        else:
            cost_desc = f"${cost:.4f}"
            total_cost += cost

        lines.append(f"{model:<15} {usage_desc:<45} {cost_desc}")

    lines.append("-" * 45)
    total_desc = f"Estimated total: ${total_cost:.4f}"
    if any_unknown_pricing:
        total_desc += " (+ unknown-priced usage above)"
    lines.append(total_desc)
    lines.append("=" * 45)

    return "\n".join(lines)


def report_usage_summary():
    """
    Print the end-of-run usage/cost summary and append it to usage_log.txt.
    No-op if no OpenAI calls were made this run.
    """
    summary = build_usage_summary()
    if not summary:
        return

    print("\n" + summary)

    try:
        with open(USAGE_LOG_PATH, "a", encoding="utf-8") as f:
            f.write(summary + "\n\n")
    except Exception as e:
        print(f"Warning: Failed to write usage log ({str(e)}).")


AUDIO_EXTENSIONS = {".mp3", ".mp4", ".mpeg", ".mpga", ".m4a", ".wav", ".webm"}


def transcribe_audio(file_path, api_key, srt_output=False, udemy=False, output_dir=None):
    """
    Transcribe audio file using OpenAI Whisper API
    """
    try:
        client = OpenAI(api_key=api_key)

        with open(file_path, "rb") as audio_file:
            transcript = client.audio.transcriptions.create(
                model=CONFIG["transcription_model"],
                file=audio_file,
                response_format="verbose_json",
                timestamp_granularities=["segment"],
                language="en")

        USAGE_RECORDS.append({
            "type": "transcription",
            "model": CONFIG["transcription_model"],
            "minutes": getattr(transcript, "duration", 0) / 60,
        })

        print("Formatting text with AI...")

        if not transcript or (hasattr(transcript, 'text')
                              and not transcript.text):
            print("Warning: Transcript is empty. Skipping formatting.")
            return ""



        formatted_transcript = format_transcript_with_ai(transcript, client, udemy=udemy)

        # Create SRT file if requested
        if srt_output:
            srt_content = format_to_srt(transcript)
            if srt_content:
                base_path = os.path.join(output_dir, os.path.splitext(os.path.basename(file_path))[0]) if output_dir else os.path.splitext(file_path)[0]
                srt_file = f"{base_path}.srt"
                try:
                    with open(srt_file, 'w', encoding='utf-8') as f:
                        f.write(srt_content)
                    print(f"SRT file saved to: {srt_file}")
                except Exception as e:
                    print(f"Error saving SRT file: {str(e)}")
        
        return formatted_transcript

    except FileNotFoundError:
        return f"Error: Audio file '{file_path}' not found."
    except Exception as e:
        return f"Error during transcription: {str(e)}"


def process_audio_file(file_path, api_key, srt_output=False, udemy=False, output_dir=None):
    """
    Run the full transcribe -> AI-format [-> YouTube-JSON] pipeline for a
    single audio file and save the results next to it, or into output_dir
    if provided. Returns True on success. When udemy=True, formats as
    Markdown and skips the YouTube JSON metadata step entirely.
    """
    print(f"Transcribing audio file: {file_path}")
    print("Please wait...")

    result = transcribe_audio(file_path, api_key, srt_output, udemy, output_dir)

    print("\n" + "=" * 45)
    print("TRANSCRIPTION RESULT:")
    print("=" * 45)
    print(result)
    print("=" * 45)

    if result.startswith("Error: during transcription: Error code:") or result.startswith("Error during transcription:"):
        print(
            "Error: Transcription failed. Please check your API key and file format."
        )
        return False

    base_path = os.path.join(output_dir, os.path.splitext(os.path.basename(file_path))[0]) if output_dir else os.path.splitext(file_path)[0]

    output_extension = "_transcription.md" if udemy else "_transcription.txt"
    output_file = f"{base_path}{output_extension}"
    try:
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(result)
        print(f"Transcription saved to: {output_file}")
    except Exception as e:
        print(f"Error saving file: {str(e)}")

    if udemy:
        return True

    print("JSON RESULT:")
    print("=" * 45)
    json_result = format_text_to_json(result, api_key)
    print(json_result)
    print("=" * 45)

    output_file = f"{base_path}_json.txt"
    try:
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(json_result or "{}")
        print(f"Transcription saved to: {output_file}")
    except Exception as e:
        print(f"Error saving file: {str(e)}")

    return True


def process_folder(folder_path, api_key, srt_output=False, udemy=False, output_folder=None):
    """
    Find audio files directly inside folder_path and process each one in turn.
    If output_folder is not given, results are saved into a new
    'output_<folder_name>' folder created next to folder_path.
    """
    audio_files = sorted(
        entry.path
        for entry in os.scandir(folder_path)
        if entry.is_file()
        and os.path.splitext(entry.name)[1].lower() in AUDIO_EXTENSIONS)

    if not audio_files:
        print(f"No audio files found in folder: {folder_path}")
        return

    if not output_folder:
        abs_folder_path = os.path.abspath(folder_path.rstrip(os.sep))
        output_folder = os.path.join(
            os.path.dirname(abs_folder_path),
            f"output_{os.path.basename(abs_folder_path)}")

    os.makedirs(output_folder, exist_ok=True)

    print(f"Found {len(audio_files)} audio file(s) in: {folder_path}")
    print(f"Saving processed files to: {output_folder}")

    succeeded = 0
    failed = 0
    for index, audio_file in enumerate(audio_files, 1):
        print("\n" + "=" * 45)
        print(f"[{index}/{len(audio_files)}] Processing: {audio_file}")
        print("=" * 45)
        try:
            if process_audio_file(audio_file, api_key, srt_output, udemy, output_folder):
                succeeded += 1
            else:
                failed += 1
        except Exception as e:
            failed += 1
            print(f"Error: Failed to process '{audio_file}': {str(e)}")

    print("\n" + "=" * 45)
    print(f"Batch complete: {succeeded} succeeded, {failed} failed.")
    print("=" * 45)


def print_sample_commands():
    """
    Print sample usage commands, shown when the user passes "?" as the file path.
    """
    print("Sample commands:")
    print("  python main.py audio.mp3")
    print("      Transcribe + AI-format + generate YouTube metadata JSON")
    print()
    print("  python main.py audio.mp3 --srt")
    print("      Also emit a .srt subtitle file alongside the transcript")
    print()
    print("  python main.py lecture.mp3 --udemy")
    print("      Transcribe + format as Markdown lecture notes, skip YouTube JSON metadata")
    print()
    print("  python main.py transcript.txt")
    print("      Skip transcription, just AI-format an existing .txt transcript")
    print()
    print("  python main.py my_audio_folder")
    print("      Batch: process every audio file directly inside the folder,")
    print("      saving results into 'output_my_audio_folder' next to it")
    print()
    print("  python main.py my_audio_folder --output-folder results")
    print("      Batch: process the folder, saving results into 'results' instead")


def main():
    print("OpenAI Whisper Audio Transcription Tool")
    print("=" * 45)

    # Parse command line arguments
    parser = argparse.ArgumentParser(description="Transcribe audio files using OpenAI Whisper API")
    parser.add_argument("file_path", help="Path to an audio file, a .txt transcript, or a folder of audio files")
    parser.add_argument("--srt", action="store_true", help="Generate SRT subtitle file(s)")
    parser.add_argument("--udemy", action="store_true", help="Format as Markdown lecture notes (no timestamps, headings only) and skip YouTube metadata JSON generation")
    parser.add_argument("--output-folder", help="Folder to save processed files into when processing a folder of audio files (default: creates 'output_<folder_name>' next to the input folder)")

    args = parser.parse_args()

    if args.file_path.strip() == "?":
        print_sample_commands()
        return

    api_key = os.getenv('OPENAI_API_KEY')

    if not api_key:
        print("Error: OPENAI_API_KEY environment variable not set.")
        print("Please set your OpenAI API key in the Secrets tool.")
        return

    file_path = args.file_path.strip()
    if not file_path:
        print("Error: File path cannot be empty.")
        return

    # Check if path exists
    if not os.path.exists(file_path):
        print(f"Error: Path '{file_path}' does not exist.")
        return

    if os.path.isdir(file_path):
        process_folder(file_path, api_key, args.srt, args.udemy, args.output_folder)
    elif file_path.endswith(".txt"):
        print("Formatting text file with AI...")
        transcript = ""
        with open(file_path, 'r', encoding='utf-8') as text_file:
            transcript = text_file.read().strip()
        client = OpenAI(api_key=api_key)
        result = format_transcript_with_ai(transcript, client, udemy=args.udemy)
        print("\n" + "=" * 45)
        print("TRANSCRIPTION RESULT:")
        print("=" * 45)
        print(result)
    else:
        process_audio_file(file_path, api_key, args.srt, args.udemy)

    report_usage_summary()


if __name__ == "__main__":
    main()
