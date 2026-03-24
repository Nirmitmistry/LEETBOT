import { useState, useRef, useEffect } from 'react';
import { useAuth } from '../context/AuthContext';
import { sendChatMessage } from '../api/chat';
import { createSession } from '../api/sessions';
import { getHint } from '../api/hints';
import { analyzeComplexity } from '../api/complexity';
import { useLocation } from 'react-router-dom';
import './Chat.css';

function Message({ msg, userAvatar }) {
  const isUser = msg.role === 'user';

  return (
    <div className={`message-row ${isUser ? 'user-row' : 'assistant-row'}`}>
      <div className="message-content-wrapper">
        <div className={`avatar ${isUser ? 'user-avatar' : 'assistant-avatar'}`}>
          {isUser ? (
            userAvatar
          ) : (
            <svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
              <path d="M16.102 17.93l-2.697 2.607c-.466.467-1.111.662-1.823.662s-1.357-.195-1.824-.662l-4.332-4.363c-.467-.467-.702-1.15-.702-1.863s.235-1.357.702-1.824l4.319-4.38c.467-.467 1.125-.645 1.837-.645s1.357.195 1.823.662l2.697 2.606c.514.515 1.365.497 1.9-.038.535-.536.553-1.387.038-1.901l-2.609-2.636a5.055 5.055 0 00-3.849-1.593 5.073 5.073 0 00-3.849 1.593l-4.306 4.38C1.112 12.97.9 13.627.9 14.337s.195 1.394.662 1.86l4.332 4.364c1.07 1.07 2.496 1.593 3.849 1.593s2.779-.523 3.849-1.593l2.697-2.607c.514-.514.496-1.365-.039-1.9s-1.386-.553-1.9-.039l-.248-.085z" fill="currentColor" />
            </svg>
          )}
        </div>
        <div className="message-bubble" style={{ whiteSpace: 'pre-wrap' }}>
          {msg.content}
        </div>
      </div>
    </div>
  );
}

export default function Chat() {
  const { API, user } = useAuth();
  const location = useLocation();
  const problemContext = location.state?.problemContext || {};

  const userAvatar = user?.username
    ? user.username.substring(0, 2).toUpperCase()
    : user?.email?.substring(0, 2).toUpperCase() || 'U';

  const [messages, setMessages] = useState([
    {
      role: 'assistant',
      content: problemContext.title
        ? `Hey! I can see you're working on **${problemContext.title}**. What do you need help with?`
        : "Hey! I'm your coding assistant. Ask me anything about DSA, algorithms, or LeetCode problems.",
    },
  ]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [sessionId, setSessionId] = useState(null);

  const bottomRef = useRef(null);
  const inputRef = useRef(null);

  // Initialize Session
  useEffect(() => {
    const initSession = async () => {
      if (problemContext.slug) {
        try {
          const res = await createSession(API, problemContext.slug);
          setSessionId(res.data.session_id);
        } catch (err) {
          console.error("Failed to initialize hint session:", err);
        }
      }
    };
    initSession();
  }, [problemContext.slug, API]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, loading]);

  useEffect(() => {
    inputRef.current?.focus();
  }, []);

  const adjustTextareaHeight = (e) => {
    e.target.style.height = 'auto';
    e.target.style.height = `${Math.min(e.target.scrollHeight, 160)}px`;
  };

  const sendMessage = async () => {
    const text = input.trim();
    if (!text || loading) return;

    const newMessages = [...messages, { role: 'user', content: text }];
    setMessages(newMessages);
    setInput('');
    if (inputRef.current) inputRef.current.style.height = 'auto';
    setLoading(true);

    try {
      const res = await sendChatMessage(
        API,
        newMessages.filter(m => m.role !== 'system'),
        problemContext
      );
      setMessages([...newMessages, { role: 'assistant', content: res.data.reply }]);
    } catch {
      setMessages([
        ...newMessages,
        { role: 'assistant', content: 'Something went wrong. Please try again.' },
      ]);
    } finally {
      setLoading(false);
    }
  };

  const handleGetHint = async () => {
    if (!problemContext.slug || !sessionId || loading) return;
    setLoading(true);

    // Add optimistic user message to context
    const text = "Can I get a hint or see the solution approach?";
    const newMessages = [...messages, { role: 'user', content: text }];
    setMessages(newMessages);

    try {
      const res = await getHint(API, problemContext.slug, sessionId);
      const stageText = res.data.stage === 6
        ? "🌟 **Editorial & Solution (Stage 6)**:\n"
        : `💡 **Hint ${res.data.stage} of 6**:\n`;

      setMessages([...newMessages, { role: 'assistant', content: stageText + res.data.hint }]);
    } catch (err) {
      const errorMsg = err.response?.data?.detail === "All hint stages already unlocked."
        ? "You've already unlocked all the hints and the solution!"
        : "Failed to fetch hint.";
      setMessages([...newMessages, { role: 'assistant', content: errorMsg }]);
    } finally {
      setLoading(false);
    }
  };

  const handleAnalyzeComplexity = async () => {
    const code = input.trim();
    if (!code || loading) {
      alert("Please paste your code in the input box first to analyze its complexity.");
      return;
    }
    setLoading(true);
    const text = `Analyze the complexity for this approach:\n\n\`\`\`\n${code}\n\`\`\``;
    const newMessages = [...messages, { role: 'user', content: text }];
    setMessages(newMessages);
    setInput('');
    if (inputRef.current) inputRef.current.style.height = 'auto';

    try {
      const res = await analyzeComplexity(API, code);
      const analysisReply = `📊 **Complexity Analysis**:\n\n**Time Complexity**: ${res.data.time_complexity}\n**Space Complexity**: ${res.data.space_complexity}\n\n**Explanation**: ${res.data.explanation}`;
      setMessages([...newMessages, { role: 'assistant', content: analysisReply }]);
    } catch (err) {
      setMessages([...newMessages, { role: 'assistant', content: 'Failed to analyze complexity. Please try again.' }]);
    } finally {
      setLoading(false);
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  return (
    <div className="chat-container">
      {/* Header */}
      <div className="chat-header">
        <h1 className="chat-title">
          {problemContext.title ? `Chat — ${problemContext.title}` : 'Coding Assistant'}
        </h1>
        <p className="chat-subtitle">Powered by qwen2.5-coder:7b</p>

        {/* Action Buttons for Contextual Tools */}
        <div className="chat-header-actions" style={{ marginTop: '1rem', display: 'flex', gap: '0.5rem' }}>
          {problemContext.slug && sessionId && (
            <button
              onClick={handleGetHint}
              disabled={loading}
              className="action-btn hint-btn"
              style={{ padding: '0.4rem 0.8rem', background: 'rgba(255, 161, 22, 0.15)', color: '#ffa116', border: '1px solid #ffa116', borderRadius: '4px', cursor: 'pointer', fontSize: '0.9rem' }}
            >
              💡 Next Hint
            </button>
          )}tr
          <button
            onClick={handleAnalyzeComplexity}
            disabled={loading || !input.trim()}
            className="action-btn complexity-btn"
            style={{ padding: '0.4rem 0.8rem', background: 'rgba(0, 184, 163, 0.15)', color: '#00b8a3', border: '1px solid #00b8a3', borderRadius: '4px', cursor: 'pointer', fontSize: '0.9rem' }}
            title="Type or paste code in the input below, then click here!"
          >
            📊 Analyze Complexity
          </button>
        </div>
      </div>

      {/* Messages Area */}
      <div className="chat-messages">
        {messages.map((msg, i) => (
          <Message key={i} msg={msg} userAvatar={userAvatar} />
        ))}

        {loading && (
          <div className="message-row assistant-row">
            <div className="message-content-wrapper">
              <div className="avatar assistant-avatar">
                <svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                  <path d="M16.102 17.93l-2.697 2.607c-.466.467-1.111.662-1.823.662s-1.357-.195-1.824-.662l-4.332-4.363c-.467-.467-.702-1.15-.702-1.863s.235-1.357.702-1.824l4.319-4.38c.467-.467 1.125-.645 1.837-.645s1.357.195 1.823.662l2.697 2.606c.514.515 1.365.497 1.9-.038.535-.536.553-1.387.038-1.901l-2.609-2.636a5.055 5.055 0 00-3.849-1.593 5.073 5.073 0 00-3.849 1.593l-4.306 4.38C1.112 12.97.9 13.627.9 14.337s.195 1.394.662 1.86l4.332 4.364c1.07 1.07 2.496 1.593 3.849 1.593s2.779-.523 3.849-1.593l2.697-2.607c.514-.514.496-1.365-.039-1.9s-1.386-.553-1.9-.039l-.248-.085z" fill="currentColor" />
                </svg>
              </div>
              <div className="message-bubble">
                <div className="typing-indicator">
                  <span className="typing-dot"></span>
                  <span className="typing-dot"></span>
                  <span className="typing-dot"></span>
                </div>
              </div>
            </div>
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      {/* Input Area */}
      <div className="chat-input-container">
        <div className="chat-input-wrapper">
          <textarea
            ref={inputRef}
            rows={1}
            className="chat-input"
            placeholder="Ask anything or paste code to analyze..."
            value={input}
            onChange={(e) => {
              setInput(e.target.value);
              adjustTextareaHeight(e);
            }}
            onKeyDown={handleKeyDown}
          />
          <button
            onClick={sendMessage}
            disabled={!input.trim() || loading}
            className="send-btn"
            title="Send Message"
          >
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <line x1="22" y1="2" x2="11" y2="13"></line>
              <polygon points="22 2 15 22 11 13 2 9 22 2"></polygon>
            </svg>
          </button>
        </div>
        <div className="chat-footer">
          Shift + Enter for new line · Enter to send
        </div>
      </div>
    </div>
  );
}