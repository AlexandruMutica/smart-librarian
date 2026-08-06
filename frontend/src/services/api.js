const API_BASE_URL = "http://127.0.0.1:8000";


export async function sendChatMessage(message) {
  const response = await fetch(`${API_BASE_URL}/chat`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      message,
    }),
  });

  if (!response.ok) {
    throw new Error("The chat request failed.");
  }

  return response.json();
}


export async function resetConversation() {
  const response = await fetch(`${API_BASE_URL}/reset`, {
    method: "POST",
  });

  if (!response.ok) {
    throw new Error("The conversation could not be reset.");
  }

  return response.json();
}


export async function createSpeech(text) {
  const response = await fetch(`${API_BASE_URL}/text-to-speech`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      text,
    }),
  });

  if (!response.ok) {
    throw new Error("The audio could not be generated.");
  }

  return response.blob();
}


export async function transcribeAudio(audioBlob) {
  const formData = new FormData();

  formData.append(
    "audio",
    audioBlob,
    "recording.webm",
  );

  const response = await fetch(`${API_BASE_URL}/speech-to-text`, {
    method: "POST",
    body: formData,
  });

  if (!response.ok) {
    throw new Error("The audio could not be transcribed.");
  }

  return response.json();
}