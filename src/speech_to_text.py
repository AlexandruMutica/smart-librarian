from pathlib import Path

from src.openai_client import get_openai_client


TRANSCRIPTION_MODEL = "gpt-4o-mini-transcribe"


# Transcribing the uploaded recording into text.
def transcribe_audio(audio_path: Path) -> str:
    if not audio_path.exists():
        raise FileNotFoundError(
            f"Audio file was not found: {audio_path}"
        )

    if not audio_path.is_file():
        raise ValueError(
            f"The provided path is not a file: {audio_path}"
        )

    client = get_openai_client()

    with audio_path.open("rb") as audio_file:
        transcription = client.audio.transcriptions.create(
            model=TRANSCRIPTION_MODEL,
            file=audio_file,
        )

    return transcription.text.strip()