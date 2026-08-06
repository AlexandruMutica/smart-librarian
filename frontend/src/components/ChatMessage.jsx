function ChatMessage({
  role,
  content,
  onPlayAudio,
  onStopAudio,
  isPlaying,
}) {
  const isAssistant = role === "assistant";

  return (
    <div className={`message-row ${role}`}>
      <div className="message-bubble">
        <div className="message-role">
          {isAssistant ? "Smart Librarian" : "You"}
        </div>

        <div className="message-content">
          {content}
        </div>

        {isAssistant && (
          <div className="audio-controls">
            <button
              className="audio-button"
              type="button"
              disabled={isPlaying}
              onClick={() => onPlayAudio(content)}
            >
              {isPlaying ? "Playing..." : "Listen"}
            </button>

            {isPlaying && (
              <button
                className="stop-audio-button"
                type="button"
                onClick={onStopAudio}
              >
                Stop
              </button>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

export default ChatMessage;