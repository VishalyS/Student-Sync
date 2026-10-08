import React, { useState, useEffect, useRef } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { 
  FiMessageSquare, 
  FiX, 
  FiSend, 
  FiCompass, 
  FiRefreshCw, 
  FiCheckCircle, 
  FiAlertTriangle, 
  FiArrowRight, 
  FiCalendar, 
  FiAward, 
  FiLayers, 
  FiZap,
  FiChevronDown
} from 'react-icons/fi';

const QUICK_PROMPTS = [
  { icon: '📊', label: 'Overall Attendance', query: 'What is my overall attendance?' },
  { icon: '☁️', label: 'Cloud Computing', query: 'What is my attendance in Cloud Computing?' },
  { icon: '🚪', label: 'Can I Bunk?', query: 'How many classes can I bunk in Cloud Computing?' },
  { icon: '🗓️', label: "Today's Classes", query: 'What classes do I have today?' },
  { icon: '🎓', label: 'My CGPA', query: 'What is my CGPA?' },
  { icon: '🧭', label: 'Go to Schedule', query: 'Take me to schedule' },
  { icon: '⚠️', label: 'Subjects < 75%', query: 'Which subjects are below 75%?' },
  { icon: '📝', label: 'CA Marks', query: 'Show my CA marks' }
];

const INITIAL_GREETING = {
  id: 'init-1',
  sender: 'bot',
  text: "Hi there! 👋 I am **SyncBot**, your Student Sync AI Assistant.\n\nI can help you navigate across the portal and answer questions about your **attendance**, **safe bunks**, **CA marks**, **timetable**, and **exam seating**.\n\nWhat would you like to know today?",
  suggestions: [
    "What is my overall attendance?",
    "What classes do I have today?",
    "Can I bunk Cloud Computing?",
    "Take me to Attendance"
  ]
};

const ChatbotWidget = () => {
  const [isOpen, setIsOpen] = useState(false);
  const [inputMessage, setInputMessage] = useState('');
  const [messages, setMessages] = useState([INITIAL_GREETING]);
  const [isTyping, setIsTyping] = useState(false);
  const [currentUser, setCurrentUser] = useState(null);

  const messagesEndRef = useRef(null);
  const inputRef = useRef(null);
  const navigate = useNavigate();
  const location = useLocation();

  // Load current student from localStorage
  useEffect(() => {
    const raw = localStorage.getItem('student_sync_user');
    if (raw) {
      try {
        const parsed = JSON.parse(raw);
        setCurrentUser(parsed);
      } catch (e) {
        setCurrentUser(null);
      }
    }
  }, [location.pathname]);

  // Auto-scroll messages
  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    if (isOpen) {
      scrollToBottom();
      setTimeout(() => inputRef.current?.focus(), 150);
    }
  }, [messages, isOpen]);

  const handleSendMessage = async (textToSend) => {
    const query = (textToSend || inputMessage).trim();
    if (!query) return;

    const userMsg = {
      id: `usr-${Date.now()}`,
      sender: 'user',
      text: query,
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
    };

    setMessages((prev) => [...prev, userMsg]);
    setInputMessage('');
    setIsTyping(true);

    const rollNo = currentUser?.rollNo || '25MX232';
    const authToken = currentUser?.auth_token;

    try {
      const headers = { 'Content-Type': 'application/json' };
      if (authToken) {
        headers['Authorization'] = `Bearer ${authToken}`;
      } else if (rollNo) {
        headers['X-Roll-No'] = rollNo;
      }

      const response = await fetch('http://127.0.0.1:5000/api/chat', {
        method: 'POST',
        headers,
        body: JSON.stringify({
          message: query,
          rollNo: rollNo
        })
      });

      if (response.ok) {
        const data = await response.json();
        const botMsg = {
          id: `bot-${Date.now()}`,
          sender: 'bot',
          text: data.reply || "I couldn't process that query. Please try again.",
          navigation: data.navigation,
          dataCard: data.data_card,
          suggestions: data.suggestions || [],
          timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
        };
        setMessages((prev) => [...prev, botMsg]);
      } else {
        setMessages((prev) => [
          ...prev,
          {
            id: `bot-${Date.now()}`,
            sender: 'bot',
            text: "⚠️ Sorry, I encountered an error contacting the academic intelligence server. Please verify your connection.",
            suggestions: ["What is my overall attendance?", "Take me to Dashboard"]
          }
        ]);
      }
    } catch (err) {
      setMessages((prev) => [
        ...prev,
        {
          id: `bot-${Date.now()}`,
          sender: 'bot',
          text: "📡 Network connection to backend server failed. Make sure the server is running on port 5000.",
          suggestions: ["Retry query", "Take me to Login"]
        }
      ]);
    } finally {
      setIsTyping(false);
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSendMessage();
    }
  };

  const handleNavigate = (path) => {
    if (!path) return;
    navigate(path);
  };

  const clearChat = () => {
    setMessages([INITIAL_GREETING]);
  };

  // Helper to render markdown-like formatting (bold, bullet points, headers)
  const formatText = (text) => {
    if (!text) return null;
    const lines = text.split('\n');

    return lines.map((line, idx) => {
      // Header 3 (###)
      if (line.startsWith('### ')) {
        return (
          <h4 key={idx} className="font-bold text-white text-sm mt-2 mb-1 flex items-center gap-1.5">
            {line.replace('### ', '')}
          </h4>
        );
      }
      // Bullet points
      if (line.trim().startsWith('- ')) {
        const content = line.trim().substring(2);
        return (
          <div key={idx} className="flex items-start gap-1.5 text-xs text-gray-300 ml-1 my-0.5 leading-relaxed">
            <span className="text-purple-400 mt-1">•</span>
            <span>{parseInlineBold(content)}</span>
          </div>
        );
      }
      // Empty line
      if (!line.trim()) {
        return <div key={idx} className="h-1.5" />;
      }
      // Standard line
      return (
        <p key={idx} className="text-xs text-gray-300 leading-relaxed my-0.5">
          {parseInlineBold(line)}
        </p>
      );
    });
  };

  // Parses **bold** and `code` in text strings
  const parseInlineBold = (str) => {
    if (!str) return '';
    const parts = str.split(/(\*\*.*?\*\*|`.*?`|\*.*?\*)/g);
    return parts.map((part, i) => {
      if (part.startsWith('**') && part.endsWith('**')) {
        return <strong key={i} className="text-white font-semibold">{part.slice(2, -2)}</strong>;
      }
      if (part.startsWith('`') && part.endsWith('`')) {
        return <code key={i} className="font-mono text-[11px] bg-[#0d1017] px-1 py-0.5 rounded border border-[#232738] text-purple-300">{part.slice(1, -1)}</code>;
      }
      if (part.startsWith('*') && part.endsWith('*')) {
        return <em key={i} className="text-gray-400 italic">{part.slice(1, -1)}</em>;
      }
      return part;
    });
  };

  return (
    <div className="fixed bottom-5 right-5 z-50 font-sans">
      {/* Floating Launcher Button */}
      {!isOpen && (
        <button
          onClick={() => setIsOpen(true)}
          className="group relative flex items-center gap-2.5 px-4 py-3 rounded-full bg-gradient-to-r from-purple-600 via-indigo-600 to-purple-700 text-white font-medium text-xs shadow-xl shadow-purple-600/30 hover:shadow-purple-600/50 hover:scale-105 active:scale-95 transition-all duration-200 border border-purple-400/30"
          title="Ask SyncBot (AI Student Assistant)"
        >
          <span className="relative flex h-2.5 w-2.5">
            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
            <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-emerald-400"></span>
          </span>
          <FiZap className="text-sm animate-pulse text-amber-300" />
          <span className="font-semibold tracking-wide">Ask SyncBot</span>
          <span className="hidden sm:inline text-[10px] bg-white/20 px-2 py-0.5 rounded-full font-mono">
            AI Navigator
          </span>
        </button>
      )}

      {/* Chatbot Window */}
      {isOpen && (
        <div className="w-[375px] sm:w-[420px] h-[580px] max-h-[85vh] bg-[#121520]/95 backdrop-blur-xl border border-[#262c3e] rounded-2xl shadow-2xl flex flex-col overflow-hidden animate-in fade-in zoom-in-95 duration-200">
          
          {/* Header */}
          <div className="px-4 py-3.5 bg-[#161a29]/90 border-b border-[#232738] flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="relative">
                <div className="w-9 h-9 rounded-xl bg-gradient-to-tr from-purple-600 to-indigo-600 flex items-center justify-center text-white shadow-md shadow-purple-600/30">
                  <FiCompass className="text-lg" />
                </div>
                <span className="absolute -bottom-0.5 -right-0.5 w-2.5 h-2.5 bg-emerald-400 border-2 border-[#161a29] rounded-full"></span>
              </div>
              <div>
                <div className="flex items-center gap-1.5">
                  <h3 className="text-sm font-bold text-white tracking-tight">SyncBot</h3>
                  <span className="text-[9px] bg-purple-500/20 text-purple-300 border border-purple-500/30 px-1.5 py-0.2 rounded font-semibold uppercase tracking-wider">
                    AI Navigator
                  </span>
                </div>
                <p className="text-[10px] text-gray-400">
                  {currentUser ? (
                    <span>Logged in as <strong className="text-gray-300 font-mono">{currentUser.rollNo}</strong></span>
                  ) : (
                    <span>PSG Tech Academic Guide</span>
                  )}
                </p>
              </div>
            </div>

            <div className="flex items-center gap-1">
              <button
                onClick={clearChat}
                className="p-1.5 text-gray-400 hover:text-gray-200 hover:bg-[#202538] rounded-lg text-xs transition-colors"
                title="Restart conversation"
              >
                <FiRefreshCw size={13} />
              </button>
              <button
                onClick={() => setIsOpen(false)}
                className="p-1.5 text-gray-400 hover:text-white hover:bg-[#202538] rounded-lg text-xs transition-colors"
                title="Minimize assistant"
              >
                <FiChevronDown size={17} />
              </button>
            </div>
          </div>

          {/* Quick Prompts Bar */}
          <div className="px-3 py-2 bg-[#0e111a] border-b border-[#1f2434] overflow-x-auto flex gap-1.5 scrollbar-thin scrollbar-thumb-gray-800">
            {QUICK_PROMPTS.map((chip, idx) => (
              <button
                key={idx}
                onClick={() => handleSendMessage(chip.query)}
                disabled={isTyping}
                className="flex items-center gap-1 px-2.5 py-1 rounded-full bg-[#181c2b] hover:bg-purple-600/20 hover:border-purple-500/40 border border-[#262c3e] text-[11px] text-gray-300 hover:text-purple-200 whitespace-nowrap transition-colors disabled:opacity-50 flex-shrink-0"
              >
                <span>{chip.icon}</span>
                <span>{chip.label}</span>
              </button>
            ))}
          </div>

          {/* Messages Container */}
          <div className="flex-1 overflow-y-auto p-4 space-y-4">
            {messages.map((msg) => (
              <div
                key={msg.id}
                className={`flex flex-col ${msg.sender === 'user' ? 'items-end' : 'items-start'}`}
              >
                {/* Message Bubble */}
                <div
                  className={`max-w-[88%] rounded-2xl p-3.5 shadow-sm text-xs ${
                    msg.sender === 'user'
                      ? 'bg-gradient-to-r from-purple-600 to-indigo-600 text-white rounded-tr-none'
                      : 'bg-[#181c2b] border border-[#262c3e] text-gray-200 rounded-tl-none space-y-2'
                  }`}
                >
                  <div>{formatText(msg.text)}</div>

                  {/* Optional Interactive Data Card */}
                  {msg.dataCard && msg.dataCard.type === 'subject_attendance' && (
                    <div className="mt-2.5 p-2.5 rounded-xl bg-[#0e111a] border border-[#23283a] space-y-1.5">
                      <div className="flex justify-between items-center text-[11px]">
                        <span className="font-semibold text-white truncate max-w-[170px]">{msg.dataCard.name}</span>
                        <span className={`font-mono font-bold ${msg.dataCard.percentage >= 75 ? 'text-emerald-400' : 'text-rose-400'}`}>
                          {msg.dataCard.percentage.toFixed(1)}%
                        </span>
                      </div>
                      <div className="w-full bg-[#1f2434] h-1.5 rounded-full overflow-hidden">
                        <div 
                          className={`h-full rounded-full ${msg.dataCard.percentage >= 75 ? 'bg-emerald-500' : 'bg-rose-500'}`}
                          style={{ width: `${Math.min(msg.dataCard.percentage, 100)}%` }}
                        />
                      </div>
                      <div className="flex justify-between items-center text-[10px] text-gray-400 pt-0.5">
                        <span>Attended: {msg.dataCard.attended}/{msg.dataCard.conducted}</span>
                        <span className="font-semibold text-purple-300">
                          {msg.dataCard.safe_bunks > 0 ? `${msg.dataCard.safe_bunks} Safe Bunks` : `Need ${msg.dataCard.required_classes} classes`}
                        </span>
                      </div>
                    </div>
                  )}

                  {/* Optional Direct Navigation Action Button */}
                  {msg.navigation && (
                    <div className="pt-2">
                      <button
                        onClick={() => handleNavigate(msg.navigation.path)}
                        className="w-full py-2 px-3 rounded-lg bg-gradient-to-r from-purple-600/30 to-indigo-600/30 hover:from-purple-600/50 hover:to-indigo-600/50 border border-purple-500/40 text-purple-200 hover:text-white font-medium text-xs flex items-center justify-between transition-colors shadow-sm"
                      >
                        <div className="flex items-center gap-1.5">
                          <FiCompass className="text-purple-400 text-sm" />
                          <span>{msg.navigation.label}</span>
                        </div>
                        <FiArrowRight className="text-xs" />
                      </button>
                    </div>
                  )}
                </div>

                {/* Follow-up Suggestion Chips */}
                {msg.sender === 'bot' && msg.suggestions && msg.suggestions.length > 0 && (
                  <div className="flex flex-wrap gap-1 mt-2 max-w-[90%]">
                    {msg.suggestions.slice(0, 3).map((sugg, sIdx) => (
                      <button
                        key={sIdx}
                        onClick={() => handleSendMessage(sugg)}
                        disabled={isTyping}
                        className="text-[10px] bg-[#141824] hover:bg-[#1d2233] border border-[#23283a] text-purple-300 hover:text-white px-2 py-0.5 rounded-full transition-colors disabled:opacity-50 text-left"
                      >
                        {sugg}
                      </button>
                    ))}
                  </div>
                )}
              </div>
            ))}

            {/* Typing Indicator */}
            {isTyping && (
              <div className="flex items-center gap-2 text-xs text-gray-400">
                <div className="w-7 h-7 rounded-lg bg-[#181c2b] border border-[#262c3e] flex items-center justify-center text-purple-400">
                  <FiCompass className="animate-spin text-xs" />
                </div>
                <div className="p-2.5 rounded-xl bg-[#181c2b] border border-[#262c3e] flex items-center gap-1">
                  <span className="w-1.5 h-1.5 bg-purple-400 rounded-full animate-bounce"></span>
                  <span className="w-1.5 h-1.5 bg-purple-400 rounded-full animate-bounce [animation-delay:0.2s]"></span>
                  <span className="w-1.5 h-1.5 bg-purple-400 rounded-full animate-bounce [animation-delay:0.4s]"></span>
                </div>
              </div>
            )}

            <div ref={messagesEndRef} />
          </div>

          {/* Input Form */}
          <div className="p-3 bg-[#141724] border-t border-[#232738]">
            <div className="relative flex items-center">
              <input
                ref={inputRef}
                type="text"
                value={inputMessage}
                onChange={(e) => setInputMessage(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="Ask about attendance, bunks, timetable..."
                className="w-full pl-3.5 pr-10 py-2.5 bg-[#0b0d13] border border-[#282d3f] rounded-xl text-xs text-white placeholder:text-gray-500 focus:border-purple-500 focus:outline-none transition-colors"
                disabled={isTyping}
              />
              <button
                onClick={() => handleSendMessage()}
                disabled={!inputMessage.trim() || isTyping}
                className="absolute right-1.5 p-2 rounded-lg bg-purple-600 hover:bg-purple-500 disabled:opacity-30 disabled:hover:bg-purple-600 text-white text-xs transition-colors"
                title="Send Message"
              >
                <FiSend size={12} />
              </button>
            </div>
            <div className="text-[9px] text-gray-500 text-center mt-1.5">
              SyncBot is connected directly to your PSG Tech portal data.
            </div>
          </div>

        </div>
      )}
    </div>
  );
};

export default ChatbotWidget;
