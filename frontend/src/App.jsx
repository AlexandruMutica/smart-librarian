import {
  useCallback,
  useRef,
  useState,
} from "react";

import ChatInput from "./components/ChatInput";
import ChatMessage from "./components/ChatMessage";
import VoiceRecorder from "./components/VoiceRecorder";

import {
  createSpeech,
  resetConversation,
  sendChatMessage,
} from "./services/api";

import "./App.css";


function App() {
  const [messages, setMessages] = useState([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState("");
  const [playingMessageIndex, setPlayingMessageIndex] =
    useState(null);
  const [transcribedText, setTranscribedText] =
    useState("");

  const activeAudioRef = useRef(null);
  const activeAudioUrlRef = useRef(null);

  const stopCurrentAudio = useCallback(() => {
    if (activeAudioRef.current) {
      activeAudioRef.current.pause();
      activeAudioRef.current.currentTime = 0;
      activeAudioRef.current = null;
    }

    if (activeAudioUrlRef.current) {
      URL.revokeObjectURL(activeAudioUrlRef.current);
      activeAudioUrlRef.current = null;
    }

    setPlayingMessageIndex(null);
  }, []);

  const handleSendMessage = async (message) => {
    setError("");
    setIsLoading(true);
    stopCurrentAudio();

    setMessages((currentMessages) => [
      ...currentMessages,
      {
        role: "user",
        content: message,
      },
    ]);

    try {
      const response = await sendChatMessage(message);

      setMessages((currentMessages) => [
        ...currentMessages,
        {
          role: "assistant",
          content: response.answer,
        },
      ]);
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setIsLoading(false);
    }
  };

  const handleReset = async () => {
    setError("");
    stopCurrentAudio();

    try {
      await resetConversation();
      setMessages([]);
      setTranscribedText("");
    } catch (requestError) {
      setError(requestError.message);
    }
  };

  const handlePlayAudio = async (
    text,
    messageIndex,
  ) => {
    setError("");
    stopCurrentAudio();

    try {
      const audioBlob = await createSpeech(text);
      const audioUrl = URL.createObjectURL(audioBlob);
      const audio = new Audio(audioUrl);

      activeAudioRef.current = audio;
      activeAudioUrlRef.current = audioUrl;

      setPlayingMessageIndex(messageIndex);

      audio.addEventListener("ended", () => {
        stopCurrentAudio();
      });

      audio.addEventListener("error", () => {
        stopCurrentAudio();
        setError("The audio could not be played.");
      });

      await audio.play();
    } catch (requestError) {
      stopCurrentAudio();
      setError(requestError.message);
    }
  };

  const handleTranscription = (text) => {
    setTranscribedText(text);
  };

  const clearTranscribedText = useCallback(() => {
    setTranscribedText("");
  }, []);

  return (
    <div className="app-shell">
      <div className="background-glow background-glow-one" />
      <div className="background-glow background-glow-two" />

      <div className="app-layout">
        <aside className="sidebar">
          <div className="brand">
            <div className="brand-icon">
              SL
            </div>

            <div>
              <div className="brand-title">
                Smart Librarian
              </div>

              <div className="brand-subtitle">
                AI reading assistant
              </div>
            </div>
          </div>

          <div className="sidebar-content">
            <div className="sidebar-label">
              DISCOVER
            </div>

            <button
              className="sidebar-action active"
              type="button"
            >
              <span className="sidebar-action-icon">
                ✦
              </span>
              Book recommendations
            </button>

            <button
              className="sidebar-action"
              type="button"
              onClick={handleReset}
            >
              <span className="sidebar-action-icon">
                ↻
              </span>
              New conversation
            </button>
          </div>

          <div className="sidebar-footer">
            <div className="status-dot" />
            <span>Connected to Smart Librarian</span>
          </div>
        </aside>

        <main className="chat-panel">
          <header className="chat-header">
            <div>
              <div className="eyebrow">
                PERSONAL BOOK GUIDE
              </div>

              <h1>
                Find a story worth remembering.
              </h1>

              <p>
                Describe a mood, a theme or an idea.
                Smart Librarian will search your collection
                and recommend the right book.
              </p>
            </div>

            <button
              type="button"
              className="new-conversation-button"
              onClick={handleReset}
            >
              New conversation
            </button>
          </header>

          <section className="conversation-card">
            <div className="messages-container">
              {messages.length === 0 && (
                <div className="empty-state">
                  <div className="empty-state-orb">
                    <span>✦</span>
                  </div>

                  <h2>
                    What would you like to read?
                  </h2>

                  <p>
                    Try asking for a story about magic,
                    freedom, war, friendship or adventure.
                  </p>

                  <div className="suggestion-grid">
                    <button
                      type="button"
                      onClick={() =>
                        handleSendMessage(
                          "Vreau o carte despre libertate și control social.",
                        )
                      }
                    >
                      <span>Freedom</span>
                      <small>
                        Society, control and rebellion
                      </small>
                    </button>

                    <button
                      type="button"
                      onClick={() =>
                        handleSendMessage(
                          "Vreau o carte despre magie și aventură.",
                        )
                      }
                    >
                      <span>Fantasy</span>
                      <small>
                        Magic, quests and strange worlds
                      </small>
                    </button>

                    <button
                      type="button"
                      onClick={() =>
                        handleSendMessage(
                          "Recomandă-mi o carte despre prietenie.",
                        )
                      }
                    >
                      <span>Friendship</span>
                      <small>
                        Connection, loyalty and growth
                      </small>
                    </button>
                  </div>
                </div>
              )}

              {messages.map((message, index) => (
                <ChatMessage
                  key={`${message.role}-${index}`}
                  role={message.role}
                  content={message.content}
                  isPlaying={
                    playingMessageIndex === index
                  }
                  onPlayAudio={(text) =>
                    handlePlayAudio(text, index)
                  }
                  onStopAudio={stopCurrentAudio}
                />
              ))}

              {isLoading && (
                <div className="assistant-thinking">
                  <div className="thinking-avatar">
                    ✦
                  </div>

                  <div>
                    <div className="thinking-title">
                      Smart Librarian is searching
                    </div>

                    <div className="thinking-dots">
                      <span />
                      <span />
                      <span />
                    </div>
                  </div>
                </div>
              )}

              {error && (
                <div className="error-message">
                  {error}
                </div>
              )}
            </div>

            <div className="composer">
              <VoiceRecorder
                disabled={isLoading}
                onTranscription={handleTranscription}
                onError={setError}
              />

              <ChatInput
                onSend={handleSendMessage}
                disabled={isLoading}
                transcribedText={transcribedText}
                onTranscribedTextUsed={
                  clearTranscribedText
                }
              />
            </div>
          </section>

          <footer className="page-footer">
            Powered by OpenAI, ChromaDB and your local
            book collection.
          </footer>
        </main>
      </div>
    </div>
  );
}

export default App;