from pathlib import Path

from src.openai_client import get_openai_client


AUDIO_MODEL = "gpt-4o-mini-tts"
DEFAULT_VOICE = "alloy"


# Creating an audio file from the generated recommendation.
def create_speech_file(
    text: str,
    output_path: Path,
) -> Path:
    if not isinstance(text, str):
        raise TypeError("The text must be a string.")

    cleaned_text = text.strip()

    if not cleaned_text:
        raise ValueError("The text cannot be empty.")

    client = get_openai_client()

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    # Streaming the response directly to disk avoids keeping the full file in memory.
    with client.audio.speech.with_streaming_response.create(
        model=AUDIO_MODEL,
        voice=DEFAULT_VOICE,
        input=cleaned_text,
    ) as response:
        response.stream_to_file(output_path)

    return output_path