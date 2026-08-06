import { useEffect, useState } from "react";


function ChatInput({
  onSend,
  disabled,
  transcribedText,
  onTranscribedTextUsed,
}) {
  const [message, setMessage] = useState("");

  useEffect(() => {
    if (!transcribedText) {
      return;
    }

    setMessage(transcribedText);
    onTranscribedTextUsed();
  }, [transcribedText, onTranscribedTextUsed]);

  const handleSubmit = (event) => {
    event.preventDefault();

    const cleanedMessage = message.trim();

    if (!cleanedMessage || disabled) {
      return;
    }

    onSend(cleanedMessage);
    setMessage("");
  };

  return (
    <form
      className="chat-input-form"
      onSubmit={handleSubmit}
    >
      <input
        type="text"
        value={message}
        placeholder="Describe what kind of book you want..."
        disabled={disabled}
        onChange={(event) => setMessage(event.target.value)}
      />

      <button
        type="submit"
        disabled={disabled}
      >
        Send
      </button>
    </form>
  );
}

export default ChatInput;