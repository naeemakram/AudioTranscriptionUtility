from pathlib import Path
from openai import OpenAI

client = OpenAI()
speech_file_path = Path(__file__).parent / "speech.mp3"

with client.audio.speech.with_streaming_response.create(
    model="whisper-1",
    voice="coral",
    input="السلام علیکم، آج کا دن بہت اچھا ہے۔ میں آج بہت خوش ہوں۔ الحمد للہ۔",
    instructions="Speak in a cheerful and positive tone.",
) as response:
    response.stream_to_file(speech_file_path)