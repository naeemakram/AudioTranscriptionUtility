import os
from openai import OpenAI
import sys
import argparse


def format_transcript_with_ai(transcript, client):
    """
    Use OpenAI to format the transcript with proper punctuation and structure
    Can handle both plain text strings and TranscriptionVerbose objects
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

        prompt = f"""You are an expert in making text data look readable by only changing it's formatting and punctionation without adding any new content. Keep only the human readable part. Please format the following transcribed text with proper punctuation, capitalization, and paragraph breaks. Make it readable and well-structured. Add pargraph headings with starting timestamps. Keep timestamps only for paragraph headings, keep paragraph body clean text. <text>

{text_to_format}
</text>
Return only the formatted text without any additional commentary."""
        print("🤖 Formatting text with AI...")
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[{
                "role":
                "system",
                "content":
                "You are a professional text editor. Format transcribed text with proper punctuation, capitalization, paragraph breaks, and detect paragraph subject to mark every paragraph with proper paragraph headings."
            }, {
                "role": "user",
                "content": prompt
            }],
            temperature=1)

        return response.choices[0].message.content.strip()

    except Exception as e:
        print(
            f"⚠️ Warning: AI formatting failed ({str(e)}). Using basic formatting instead."
        )
        return ""


def format_text_to_json(text, api_key):
    """
    Convert formatted text to JSON using OpenAI's completion API.
    """
    try:
        client = OpenAI(api_key=api_key)

        prompt = f"You're a gen-z copywriter with great information and experience of writing viral content for the internet youtube etc. Write youtube video title, description, tags  for a video based to the supplied text. Return data in json format. with keys title, description, tags. Keep tags a string with comma separated tags.<text>{text}</text>"

        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{
                "role":
                "system",
                "content":
                "You are a helpful assistant that formats text into JSON."
            }, {
                "role": "user",
                "content": prompt
            }],
            max_tokens=2500,
            temperature=0.2)

        formatted_json = response.choices[0].message.content.strip()

        return formatted_json

    except Exception as e:
        print(
            f"⚠️ Warning: Conversion to JSON failed ({str(e)}). Returning None."
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


def transcribe_audio(file_path, api_key, srt_output=False):
    """
    Transcribe audio file using OpenAI Whisper API
    """
    try:
        client = OpenAI(api_key=api_key)

        with open(file_path, "rb") as audio_file:
            transcript = client.audio.transcriptions.create(
                model="whisper-1",
                file=audio_file,
                response_format="verbose_json",
                timestamp_granularities=["segment"],
                language="en")

        print("🤖 Formatting text with AI...")

        if not transcript or (hasattr(transcript, 'text')
                              and not transcript.text):
            print("⚠️ Warning: Transcript is empty. Skipping formatting.")
            return ""



        formatted_transcript = format_transcript_with_ai(transcript, client)
        
        # Create SRT file if requested
        if srt_output:
            srt_content = format_to_srt(transcript)
            if srt_content:
                srt_file = f"{os.path.splitext(file_path)[0]}.srt"
                try:
                    with open(srt_file, 'w', encoding='utf-8') as f:
                        f.write(srt_content)
                    print(f"✅ SRT file saved to: {srt_file}")
                except Exception as e:
                    print(f"❌ Error saving SRT file: {str(e)}")
        
        return formatted_transcript

    except FileNotFoundError:
        return f"Error: Audio file '{file_path}' not found."
    except Exception as e:
        return f"Error during transcription: {str(e)}"


def main():
    print("🎵 OpenAI Whisper Audio Transcription Tool")
    print("=" * 45)
    
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="Transcribe audio files using OpenAI Whisper API")
    parser.add_argument("file_path", help="Path to the audio file to transcribe")
    parser.add_argument("--srt", action="store_true", help="Generate SRT subtitle file")
    
    args = parser.parse_args()
    
    api_key = os.getenv('OPENAI_API_KEY')

    if not api_key:
        print("❌ Error: OPENAI_API_KEY environment variable not set.")
        print("Please set your OpenAI API key in the Secrets tool.")
        return

    file_path = args.file_path.strip()
    if not file_path:
        print("✖ Error: File path cannot be empty.")
        return

    # Check if file exists
    if not os.path.exists(file_path):
        print(f"❌ Error: File '{file_path}' does not exist.")
        return

    if file_path.endswith(".txt"):
        print("Formatting text file with AI...")
        transcript = ""
        with open(file_path, 'r', encoding='utf-8') as text_file:
            transcript = text_file.read().strip()
        client = OpenAI(api_key=api_key)
        result = format_transcript_with_ai(transcript, client)
        print("\n" + "=" * 45)
        print("📝 TRANSCRIPTION RESULT:")
        print("=" * 45)
        print(result)
        return

    print(f"🔄 Transcribing audio file: {file_path}")
    print("Please wait...")

    result = transcribe_audio(file_path, api_key, args.srt)

    print("\n" + "=" * 45)
    print("📝 TRANSCRIPTION RESULT:")
    print("=" * 45)
    print(result)
    print("=" * 45)

    if (result.startswith("Error: during transcription: Error code:")):
        print(
            "❌ Error: Transcription failed. Please check your API key and file format."
        )
        return

    output_file = f"{os.path.splitext(file_path)[0]}_transcription.txt"
    try:
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(result)
        print(f"✅ Transcription saved to: {output_file}")
    except Exception as e:
        print(f"❌ Error saving file: {str(e)}")

    print("📝 JSON RESULT:")
    print("=" * 45)
    json_result = format_text_to_json(result, api_key)
    print(json_result)
    print("=" * 45)

    output_file = f"{os.path.splitext(file_path)[0]}_json.txt"
    try:
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(json_result or "{}")
        print(f"✅ Transcription saved to: {output_file}")
    except Exception as e:
        print(f"❌ Error saving file: {str(e)}")


if __name__ == "__main__":
    main()
