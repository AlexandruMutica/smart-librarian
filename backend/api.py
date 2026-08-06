import tempfile
from pathlib import Path
from uuid import uuid4

from fastapi import (
    FastAPI,
    File,
    HTTPException,
    UploadFile,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel

from src.chatbot import SmartLibrarianChat
from src.speech_to_text import transcribe_audio
from src.text_to_speech import create_speech_file

app = FastAPI(
    title="Smart Librarian API",
    version="1.0.0",
)

# Allowing the React development server to call the backend.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChatRequest(BaseModel):
    message: str


class ChatResponse(BaseModel):
    answer: str

class TextToSpeechRequest(BaseModel):
    text: str

librarian = SmartLibrarianChat()


@app.get("/health")
def health_check() -> dict[str, str]:
    return {
        "status": "ok",
    }


@app.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest) -> ChatResponse:
    answer = librarian.chat(request.message)

    return ChatResponse(
        answer=answer,
    )


@app.post("/reset")
def reset_conversation() -> dict[str, str]:
    librarian.reset()

    return {
        "message": "Conversation reset successfully.",
    }

@app.post("/text-to-speech")
def text_to_speech(
    request: TextToSpeechRequest,
) -> FileResponse:
    cleaned_text = request.text.strip()

    if not cleaned_text:
        raise HTTPException(
            status_code=400,
            detail="The text cannot be empty.",
        )

    audio_directory = (
        Path(tempfile.gettempdir())
        / "smart_librarian_audio"
    )

    audio_path = (
        audio_directory
        / f"{uuid4().hex}.mp3"
    )

    try:
        create_speech_file(
            text=cleaned_text,
            output_path=audio_path,
        )

    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=f"Speech generation failed: {error}",
        ) from error

    return FileResponse(
        path=audio_path,
        media_type="audio/mpeg",
        filename="recommendation.mp3",
    )

@app.post("/speech-to-text")
async def speech_to_text(
    audio: UploadFile = File(...),
) -> dict[str, str]:
    if not audio.filename:
        raise HTTPException(
            status_code=400,
            detail="No audio file was provided.",
        )

    suffix = Path(audio.filename).suffix or ".webm"

    with tempfile.NamedTemporaryFile(
        delete=False,
        suffix=suffix,
    ) as temporary_file:
        temporary_path = Path(temporary_file.name)
        temporary_file.write(await audio.read())

    try:
        transcript = transcribe_audio(
            temporary_path
        )

    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=f"Audio transcription failed: {error}",
        ) from error

    finally:
        temporary_path.unlink(
            missing_ok=True
        )

    return {
        "text": transcript,
    }