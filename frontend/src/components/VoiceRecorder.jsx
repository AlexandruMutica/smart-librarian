import { useRef, useState } from "react";

import { transcribeAudio } from "../services/api";


function VoiceRecorder({
  onTranscription,
  disabled,
  onError,
}) {
  const mediaRecorderRef = useRef(null);
  const audioChunksRef = useRef([]);

  const [isRecording, setIsRecording] = useState(false);
  const [isTranscribing, setIsTranscribing] = useState(false);

  const startRecording = async () => {
    if (disabled || isRecording || isTranscribing) {
      return;
    }

    try {
      onError("");

      const stream = await navigator.mediaDevices.getUserMedia({
        audio: true,
      });

      const mediaRecorder = new MediaRecorder(stream);

      mediaRecorderRef.current = mediaRecorder;
      audioChunksRef.current = [];

      mediaRecorder.addEventListener("dataavailable", (event) => {
        if (event.data.size > 0) {
          audioChunksRef.current.push(event.data);
        }
      });

      mediaRecorder.addEventListener("stop", async () => {
        stream.getTracks().forEach((track) => track.stop());

        const audioBlob = new Blob(
          audioChunksRef.current,
          {
            type: mediaRecorder.mimeType || "audio/webm",
          },
        );

        if (audioBlob.size === 0) {
          onError("No audio was recorded.");
          return;
        }

        try {
          setIsTranscribing(true);

          const response = await transcribeAudio(audioBlob);

          if (response.text) {
            onTranscription(response.text);
          }
        } catch (error) {
          onError(error.message);
        } finally {
          setIsTranscribing(false);
        }
      });

      mediaRecorder.start();
      setIsRecording(true);
    } catch {
      onError(
        "Microphone access was denied or is not available.",
      );
    }
  };

  const stopRecording = () => {
    const mediaRecorder = mediaRecorderRef.current;

    if (
      mediaRecorder &&
      mediaRecorder.state !== "inactive"
    ) {
      mediaRecorder.stop();
    }

    setIsRecording(false);
  };

  return (
    <div className="voice-recorder">
      {!isRecording ? (
        <button
          type="button"
          className="microphone-button"
          disabled={disabled || isTranscribing}
          onClick={startRecording}
        >
          {isTranscribing ? "Transcribing..." : "Speak"}
        </button>
      ) : (
        <button
          type="button"
          className="stop-recording-button"
          onClick={stopRecording}
        >
          Stop recording
        </button>
      )}
    </div>
  );
}

export default VoiceRecorder;