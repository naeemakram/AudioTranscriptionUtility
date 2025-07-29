import os
from openai import OpenAI
import sys


def format_transcript(text):
    """
    Format the transcript with proper punctuation and line breaks
    """
    import re

    # Remove extra whitespace
    text = re.sub(r'\s+', ' ', text.strip())

    # Add periods at the end of sentences if missing
    # Look for sentence endings without punctuation
    text = re.sub(r'([a-zA-Z0-9])\s+([A-Z])', r'\1. \2', text)

    # Ensure the text ends with a period
    if text and not text.endswith(('.', '!', '?')):
        text += '.'

    # Split into sentences and put each on a new line
    sentences = re.split(r'([.!?])\s*', text)
    formatted_lines = []

    for i in range(0, len(sentences) - 1, 2):
        if i + 1 < len(sentences):
            sentence = sentences[i] + sentences[i + 1]
            if sentence.strip():
                formatted_lines.append(sentence.strip())

    return '\n'.join(formatted_lines)


def transcribe_audio(file_path, api_key):
    """
    Transcribe audio file using OpenAI Whisper API
    """
    try:
        # Initialize OpenAI client
        client = OpenAI(api_key=api_key)

        # Open and transcribe the audio file
        with open(file_path, "rb") as audio_file:
            transcript = client.audio.transcriptions.create(
                model="whisper-1",
                file=audio_file,
                response_format="text",
                language="en",
            )

        # Format the transcript with proper punctuation and line breaks
        formatted_transcript = format_transcript(transcript)
        return formatted_transcript

    except FileNotFoundError:
        return f"Error: Audio file '{file_path}' not found."
    except Exception as e:
        return f"Error during transcription: {str(e)}"


def main():
    print("🎵 OpenAI Whisper Audio Transcription Tool")
    print("=" * 45)

    # Get API key from environment variable
    api_key = os.getenv('OPENAI_API_KEY')

    if not api_key:
        print("❌ Error: OPENAI_API_KEY environment variable not set.")
        print("Please set your OpenAI API key in the Secrets tool.")
        return

    # Get audio file path from user
    if len(sys.argv) > 1:
        file_path = sys.argv[1]
    else:
        file_path = input("Enter the path to your audio file: ").strip()

    if not file_path:
        print("❌ Error: No file path provided.")
        return

    # Check if file exists
    if not os.path.exists(file_path):
        print(f"❌ Error: File '{file_path}' does not exist.")
        return

    print(f"🔄 Transcribing audio file: {file_path}")
    print("Please wait...")

    # Transcribe the audio
    result = transcribe_audio(file_path, api_key)

    print("\n" + "=" * 45)
    print("📝 TRANSCRIPTION RESULT:")
    print("=" * 45)
    print(result)
    print("=" * 45)

    # Option to save transcription to file
    save_option = input(
        "\n💾 Save transcription to file? (y/n): ").strip().lower()
    if save_option in ['y', 'yes']:
        output_file = f"{os.path.splitext(file_path)[0]}_transcription.txt"
        try:
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(result)
            print(f"✅ Transcription saved to: {output_file}")
        except Exception as e:
            print(f"❌ Error saving file: {str(e)}")


if __name__ == "__main__":
    main()
