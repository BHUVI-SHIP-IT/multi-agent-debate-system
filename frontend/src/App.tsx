import React, { useState, useEffect, useRef } from 'react';
import { Shield, ThumbsUp, ThumbsDown, Search, Gavel, Play } from 'lucide-react';

type AgentRole = 'moderator' | 'pro' | 'opponent' | 'fact_checker' | 'verdict';

interface Message {
  id: number;
  agent: string;
  role: AgentRole;
  content: string;
  type?: 'agent_message' | 'verdict';
}

function App() {
  const [topic, setTopic] = useState('');
  const [messages, setMessages] = useState<Message[]>([]);
  const [ws, setWs] = useState<WebSocket | null>(null);
  const [isDebating, setIsDebating] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  useEffect(() => {
    const socket = new WebSocket('ws://localhost:8000/ws/debate');

    socket.onopen = () => console.log('WebSocket connected');

    socket.onmessage = (event) => {
      const data = JSON.parse(event.data);
      if (data.type === 'agent_message') {
        setMessages((prev) => [...prev, {
          id: Date.now() + Math.random(),
          agent: data.agent,
          role: data.role as AgentRole,
          content: data.content
        }]);
      } else if (data.type === 'verdict') {
        setMessages((prev) => [...prev, {
          id: Date.now() + Math.random(),
          agent: 'verdict_agent',
          role: 'verdict',
          content: data.content,
          type: 'verdict'
        }]);
        setIsDebating(false);
      }
    };

    socket.onclose = () => console.log('WebSocket disconnected');

    setWs(socket);

    return () => {
      socket.close();
    };
  }, []);

  const handleStart = (e: React.FormEvent) => {
    e.preventDefault();
    if (!topic.trim() || !ws) return;

    setMessages([]);
    setIsDebating(true);
    ws.send(JSON.stringify({ topic }));
  };

  const getAgentIcon = (role: AgentRole) => {
    switch (role) {
      case 'moderator': return <Shield className="w-6 h-6 text-gray-700" />;
      case 'pro': return <ThumbsUp className="w-6 h-6 text-blue-600" />;
      case 'opponent': return <ThumbsDown className="w-6 h-6 text-red-600" />;
      case 'fact_checker': return <Search className="w-6 h-6 text-yellow-600" />;
      case 'verdict': return <Gavel className="w-6 h-6 text-purple-600" />;
      default: return null;
    }
  };

  const getAgentColor = (role: AgentRole) => {
    switch (role) {
      case 'moderator': return 'bg-gray-100 border-gray-300';
      case 'pro': return 'bg-blue-50 border-blue-300';
      case 'opponent': return 'bg-red-50 border-red-300';
      case 'fact_checker': return 'bg-yellow-50 border-yellow-300';
      case 'verdict': return 'bg-purple-100 border-purple-400';
      default: return 'bg-white border-gray-200';
    }
  };

  const getAgentName = (role: AgentRole) => {
    switch (role) {
      case 'moderator': return 'Moderator';
      case 'pro': return 'Pro Agent';
      case 'opponent': return 'Opponent Agent';
      case 'fact_checker': return 'Fact Checker';
      case 'verdict': return 'Verdict';
      default: return 'Unknown';
    }
  };

  return (
    <div className="flex flex-col h-screen w-full max-w-4xl mx-auto bg-white shadow-xl rounded-xl overflow-hidden border border-gray-200 my-4 flex-grow">
      {/* Header */}
      <div className="p-6 border-b border-gray-200 bg-slate-50">
        <h1 className="text-2xl font-bold text-slate-800 mb-2 flex items-center gap-2">
          <Gavel className="w-8 h-8 text-indigo-600" />
          AI Debate System
        </h1>
        <form onSubmit={handleStart} className="flex gap-4">
          <input
            type="text"
            className="flex-1 p-3 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500 transition-all font-medium text-slate-700"
            placeholder="Enter a topic... e.g., Should AI replace programmers?"
            value={topic}
            onChange={(e) => setTopic(e.target.value)}
            disabled={isDebating}
          />
          <button
            type="submit"
            disabled={isDebating || !topic.trim()}
            className="px-6 py-3 bg-indigo-600 text-white font-semibold rounded-lg hover:bg-indigo-700 disabled:opacity-50 flex items-center gap-2 transition-all shadow-md"
          >
            <Play className="w-5 h-5" />
            Start Debate
          </button>
        </form>
      </div>

      {/* Chat Area */}
      <div className="flex-1 overflow-y-auto p-6 space-y-6 bg-slate-50/50">
        {messages.length === 0 && !isDebating ? (
          <div className="h-full flex flex-col items-center justify-center text-gray-400">
            <Shield className="w-16 h-16 mb-4 text-gray-300" />
            <p className="text-lg font-medium">Waiting for a topic to begin the debate...</p>
          </div>
        ) : null}

        {messages.map((msg) => (
          <div
            key={msg.id}
            className={`flex flex-col p-5 rounded-2xl border shadow-sm transition-all duration-300 ${getAgentColor(msg.role)} 
               ${msg.type === 'verdict' ? 'ring-2 ring-purple-400 transform scale-[1.02]' : ''}`}
          >
            <div className="flex items-center gap-3 mb-3 border-b pb-2 border-opacity-20 border-black">
              <div className="p-2 bg-white rounded-full shadow-sm">
                {getAgentIcon(msg.role)}
              </div>
              <h3 className="font-bold text-lg text-slate-800 tracking-tight">
                {getAgentName(msg.role)}
              </h3>
            </div>
            <p className="text-slate-700 whitespace-pre-wrap leading-relaxed text-[15px]">
              {msg.content}
            </p>
          </div>
        ))}
        {isDebating && (
          <div className="flex justify-center items-center py-4">
            <span className="flex items-center gap-2 text-indigo-500 font-medium">
              <div className="w-2 h-2 rounded-full bg-indigo-500 animate-bounce"></div>
              <div className="w-2 h-2 rounded-full bg-indigo-500 animate-bounce" style={{ animationDelay: '0.2s' }}></div>
              <div className="w-2 h-2 rounded-full bg-indigo-500 animate-bounce" style={{ animationDelay: '0.4s' }}></div>
              <span>Agents are thinking...</span>
            </span>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>
    </div>
  );
}

export default App;
