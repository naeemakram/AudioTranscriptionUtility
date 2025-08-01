import os
from openai import OpenAI
import sys


def format_transcript_with_ai(text, client):
    """
    Use OpenAI to format the transcript with proper punctuation and structure
    """
    try:
        prompt = f"""Please format the following transcribed text with proper punctuation, capitalization, and paragraph breaks. Make it readable and well-structured.:

{text}

Return only the formatted text without any additional commentary."""

        response = client.chat.completions.create(
            model="gpt-5",
            messages=[{
                "role":
                "system",
                "content":
                "You are a professional text editor. Format transcribed text with proper punctuation, capitalization, paragraph breaks, and paragraph headings."
            }, {
                "role": "user",
                "content": prompt
            }],
            temperature=0.1)

        return response.choices[0].message.content.strip()

    except Exception as e:
        print(
            f"⚠️ Warning: AI formatting failed ({str(e)}). Using basic formatting instead."
        )
        return text


def format_text_to_json(text, api_key):
    """
    Convert formatted text to JSON using OpenAI's completion API.

    :param text: The input text to be converted to JSON.
    :param client: The OpenAI client instance to call the model.
    :return: JSON object of the formatted text.
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

        # Extract and parse the JSON content from the response
        formatted_json = response.choices[0].message.content.strip()
        return formatted_json

    except Exception as e:
        print(
            f"⚠️ Warning: Conversion to JSON failed ({str(e)}). Returning None."
        )
        return None


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
                language="en")

        print("🤖 Formatting text with AI...")

        if not transcript:
            print("⚠️ Warning: Transcript is empty. Skipping formatting.")
            return ""
        # Format the transcript using OpenAI's text completion
        formatted_transcript = format_transcript_with_ai(transcript, client)
        return formatted_transcript

    except FileNotFoundError:
        return f"Error: Audio file '{file_path}' not found."
    except Exception as e:
        return f"Error during transcription: {str(e)}"


def main():
    print("🎵 OpenAI Whisper Audio Transcription Tool")
    print("=" * 45)

    # Get API key from environment variable
    api_key = "OPENAI_API_KEY_REDACTED"  #os.getenv('OPENAI_API_KEY')

    if not api_key:
        print("❌ Error: OPENAI_API_KEY environment variable not set.")
        print("Please set your OpenAI API key in the Secrets tool.")
        return

    # Get audio file path from command line argument
    if len(sys.argv) < 2:
        print("❌ Error: No file path provided.")
        print("Usage: python main.py <audio_file_path>")
        print("Example: python main.py audio.mp3")
        return

    file_path = sys.argv[1].strip()

    if not file_path:
        print("❌ Error: File path cannot be empty.")
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

    # Transcribe the audio
    result = transcribe_audio(file_path, api_key)

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
