from elevenlabs.client import ElevenLabs
from elevenlabs import save
import os
from dotenv import load_dotenv
from pathlib import Path

load_dotenv()

client = ElevenLabs(api_key=os.getenv("ELEVENLABS_API_KEY"))

def run(text):
    audio = client.text_to_speech.convert(
        voice_id="onwK4e9ZLuTAKqWW03F9",
        output_format="mp3_44100_128",
        text=text,
        model_id="eleven_multilingual_v2",
    )


    save(audio, "/home/bryson/code_projects/ControllerV1/daily-digest/podcast.mp3")
    return "podcast.mp3"