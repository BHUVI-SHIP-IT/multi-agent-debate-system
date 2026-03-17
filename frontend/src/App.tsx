import React, { useState, useEffect, useRef } from 'react';
import { Shield, ThumbsUp, ThumbsDown, Search, Gavel, Play } from 'lucide-react';

type AgentRole = 'moderator' | 'researcher' | 'pro' | 'opponent' | 'fact_checker' | 'verdict';

type Winner = 'pro' | 'opponent' | 'tie';

interface SideScores {
  argument_quality: number;
  evidence_use: number;
  rebuttal_effectiveness: number;
  factual_accuracy: number;
  clarity: number;
  total: number;
}

interface SidePenalties {
  false_claims: number;
  repeated_partial_true: number;
  points_deducted: number;
}

interface VerdictData {
  scores: {
    pro: SideScores;
    opponent: SideScores;
  };
  winner: Winner;
  rationale: string;
  confidence: number;
  key_errors: {
    pro: string[];
    opponent: string[];
  };
  summary: string;
  penalties?: {
    pro: SidePenalties;
    opponent: SidePenalties;
  };
}

interface Message {
  id: number;
  agent: string;
  role: AgentRole;
  content: string;
  type?: 'agent_message' | 'verdict';
  verdictData?: VerdictData;
}

interface RoleTheme {
  card: string;
  icon: string;
  chip: string;
  accent: string;
}

const CRITERIA: Array<{ key: keyof SideScores; label: string; max?: number }> = [
  { key: 'argument_quality', label: 'Argument quality', max: 25 },
  { key: 'evidence_use', label: 'Evidence use', max: 25 },
  { key: 'rebuttal_effectiveness', label: 'Rebuttal effectiveness', max: 20 },
  { key: 'factual_accuracy', label: 'Factual accuracy', max: 20 },
  { key: 'clarity', label: 'Clarity', max: 10 },
  { key: 'total', label: 'Total' },
];

function parseVerdictData(raw: unknown): VerdictData | undefined {
  if (!raw || typeof raw !== 'object') return undefined;

  const data = raw as Partial<VerdictData> & Record<string, unknown>;
  const rawScores = data.scores;
  if (!rawScores || typeof rawScores !== 'object') return undefined;

  const parseSideScores = (sideRaw: unknown): SideScores => {
    const side = (sideRaw && typeof sideRaw === 'object') ? sideRaw as Record<string, unknown> : {};
    const toNum = (value: unknown): number => (typeof value === 'number' && Number.isFinite(value) ? value : 0);

    return {
      argument_quality: toNum(side.argument_quality),
      evidence_use: toNum(side.evidence_use),
      rebuttal_effectiveness: toNum(side.rebuttal_effectiveness),
      factual_accuracy: toNum(side.factual_accuracy),
      clarity: toNum(side.clarity),
      total: toNum(side.total),
    };
  };

  const scoresObj = rawScores as { pro?: unknown; opponent?: unknown };
  const winnerRaw = typeof data.winner === 'string' ? data.winner : 'tie';
  const winner: Winner = winnerRaw === 'pro' || winnerRaw === 'opponent' || winnerRaw === 'tie' ? winnerRaw : 'tie';

  const rawPenalties = (data.penalties && typeof data.penalties === 'object')
    ? data.penalties as { pro?: unknown; opponent?: unknown }
    : undefined;

  const rawKeyErrors = (data.key_errors && typeof data.key_errors === 'object')
    ? data.key_errors as { pro?: unknown; opponent?: unknown }
    : undefined;

  const parsePenalty = (penaltyRaw: unknown): SidePenalties => {
    const p = (penaltyRaw && typeof penaltyRaw === 'object') ? penaltyRaw as Record<string, unknown> : {};
    const toNum = (value: unknown): number => (typeof value === 'number' && Number.isFinite(value) ? value : 0);
    return {
      false_claims: toNum(p.false_claims),
      repeated_partial_true: toNum(p.repeated_partial_true),
      points_deducted: toNum(p.points_deducted),
    };
  };

  return {
    scores: {
      pro: parseSideScores(scoresObj.pro),
      opponent: parseSideScores(scoresObj.opponent),
    },
    winner,
    rationale: typeof data.rationale === 'string' ? data.rationale : '',
    confidence: typeof data.confidence === 'number' && Number.isFinite(data.confidence) ? data.confidence : 0,
    key_errors: {
      pro: Array.isArray(rawKeyErrors?.pro) ? rawKeyErrors.pro.filter((err): err is string => typeof err === 'string') : [],
      opponent: Array.isArray(rawKeyErrors?.opponent) ? rawKeyErrors.opponent.filter((err): err is string => typeof err === 'string') : [],
    },
    summary: typeof data.summary === 'string' ? data.summary : '',
    penalties: rawPenalties ? {
      pro: parsePenalty(rawPenalties.pro),
      opponent: parsePenalty(rawPenalties.opponent),
    } : undefined,
  };
}

function winnerLabel(winner: Winner): string {
  if (winner === 'pro') return 'Pro wins';
  if (winner === 'opponent') return 'Opponent wins';
  return 'Tie';
}

function winnerStyle(winner: Winner): string {
  if (winner === 'pro') return 'bg-cyan-100 text-cyan-900 border-cyan-300';
  if (winner === 'opponent') return 'bg-rose-100 text-rose-900 border-rose-300';
  return 'bg-slate-200 text-slate-900 border-slate-300';
}

function getRoleTheme(role: AgentRole): RoleTheme {
  switch (role) {
    case 'moderator':
      return {
        card: 'bg-slate-50/90 border-slate-300',
        icon: 'text-slate-700',
        chip: 'bg-slate-200 text-slate-700',
        accent: 'from-slate-500 to-slate-300',
      };
    case 'researcher':
      return {
        card: 'bg-teal-50/90 border-teal-300',
        icon: 'text-teal-700',
        chip: 'bg-teal-100 text-teal-700',
        accent: 'from-teal-500 to-cyan-300',
      };
    case 'pro':
      return {
        card: 'bg-cyan-50/90 border-cyan-300',
        icon: 'text-cyan-700',
        chip: 'bg-cyan-100 text-cyan-700',
        accent: 'from-cyan-500 to-sky-300',
      };
    case 'opponent':
      return {
        card: 'bg-rose-50/90 border-rose-300',
        icon: 'text-rose-700',
        chip: 'bg-rose-100 text-rose-700',
        accent: 'from-rose-500 to-orange-300',
      };
    case 'fact_checker':
      return {
        card: 'bg-amber-50/90 border-amber-300',
        icon: 'text-amber-700',
        chip: 'bg-amber-100 text-amber-700',
        accent: 'from-amber-500 to-yellow-300',
      };
    case 'verdict':
      return {
        card: 'bg-emerald-50/90 border-emerald-300',
        icon: 'text-emerald-700',
        chip: 'bg-emerald-100 text-emerald-700',
        accent: 'from-emerald-500 to-lime-300',
      };
    default:
      return {
        card: 'bg-white border-slate-200',
        icon: 'text-slate-700',
        chip: 'bg-slate-100 text-slate-700',
        accent: 'from-slate-500 to-slate-300',
      };
  }
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
    const envWsUrl = import.meta.env.VITE_WS_URL as string | undefined;
    const fallbackWsUrl = `${window.location.protocol === 'https:' ? 'wss' : 'ws'}://${window.location.host}/ws/debate`;
    const socket = new WebSocket(envWsUrl || fallbackWsUrl);

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
        const verdictData = parseVerdictData(data.verdict_data);
        setMessages((prev) => [...prev, {
          id: Date.now() + Math.random(),
          agent: 'verdict_agent',
          role: 'verdict',
          content: data.content,
          type: 'verdict',
          verdictData
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
    const iconClass = `w-5 h-5 ${getRoleTheme(role).icon}`;
    switch (role) {
      case 'moderator': return <Shield className={iconClass} />;
      case 'researcher': return <Search className={iconClass} />;
      case 'pro': return <ThumbsUp className={iconClass} />;
      case 'opponent': return <ThumbsDown className={iconClass} />;
      case 'fact_checker': return <Search className={iconClass} />;
      case 'verdict': return <Gavel className={iconClass} />;
      default: return null;
    }
  };

  const getAgentName = (role: AgentRole) => {
    switch (role) {
      case 'moderator': return 'Moderator';
      case 'researcher': return 'Researcher';
      case 'pro': return 'Pro Agent';
      case 'opponent': return 'Opponent Agent';
      case 'fact_checker': return 'Fact Checker';
      case 'verdict': return 'Verdict';
      default: return 'Unknown';
    }
  };

  return (
    <div className="relative flex flex-col min-h-[92vh] w-full max-w-5xl mx-auto bg-white/80 shadow-[0_20px_80px_rgba(7,35,54,0.16)] rounded-[28px] overflow-hidden border border-[color:var(--line)] my-4 backdrop-blur-sm">
      <div className="pointer-events-none absolute -top-24 -left-16 w-64 h-64 rounded-full bg-cyan-200/50 blur-3xl" />
      <div className="pointer-events-none absolute -bottom-20 -right-12 w-72 h-72 rounded-full bg-amber-200/45 blur-3xl" />

      <div className="relative p-5 sm:p-7 border-b border-[color:var(--line)] bg-gradient-to-r from-amber-50/80 via-white/70 to-cyan-50/70">
        <div className="flex flex-wrap items-center justify-between gap-3 mb-4">
          <h1 className="text-[clamp(1.35rem,1.8vw,2rem)] font-bold text-slate-900 tracking-tight flex items-center gap-2" style={{ fontFamily: 'var(--font-display)' }}>
            <Gavel className="w-7 h-7 text-cyan-700" />
            Deliberation Engine
          </h1>
          <div className="flex items-center gap-2 text-xs sm:text-sm">
            <span className="px-2.5 py-1 rounded-full bg-cyan-100 text-cyan-800 border border-cyan-200 font-medium">Live Debate</span>
            <span className="px-2.5 py-1 rounded-full bg-amber-100 text-amber-800 border border-amber-200 font-medium">LLM + Fact Check</span>
          </div>
        </div>

        <p className="text-slate-700 text-sm sm:text-base mb-4 max-w-3xl">
          Enter a topic and watch each agent argue, challenge, verify, and score the final verdict with transparent judging criteria.
        </p>

        <form onSubmit={handleStart} className="flex flex-col sm:flex-row gap-3">
          <input
            type="text"
            className="flex-1 px-4 py-3 border border-slate-300 rounded-xl focus:outline-none focus:ring-2 focus:ring-cyan-500 transition-all font-medium text-slate-800 bg-white/90"
            placeholder="Try: Should AI write production code without human review?"
            value={topic}
            onChange={(e) => setTopic(e.target.value)}
            disabled={isDebating}
          />
          <button
            type="submit"
            disabled={isDebating || !topic.trim()}
            className="px-5 py-3 bg-gradient-to-r from-cyan-600 to-teal-600 text-white font-semibold rounded-xl hover:from-cyan-700 hover:to-teal-700 disabled:opacity-50 flex items-center justify-center gap-2 transition-all shadow-md"
          >
            <Play className="w-5 h-5" />
            Start Debate
          </button>
        </form>
      </div>

      <div className="flex-1 overflow-y-auto p-4 sm:p-6 space-y-4 bg-white/50">
        {messages.length === 0 && !isDebating ? (
          <div className="h-full min-h-[280px] flex flex-col items-center justify-center text-slate-500 bg-white/70 border border-dashed border-slate-300 rounded-2xl">
            <Shield className="w-14 h-14 mb-3 text-slate-400" />
            <p className="text-base sm:text-lg font-medium">No debate started yet</p>
            <p className="text-sm mt-1">Set a topic above to generate a multi-agent debate.</p>
          </div>
        ) : null}

        {messages.map((msg) => (
          <div key={msg.id} className={`relative flex flex-col p-4 sm:p-5 rounded-2xl border shadow-sm transition-all duration-300 hover:-translate-y-[1px] hover:shadow-md ${getRoleTheme(msg.role).card} ${msg.type === 'verdict' ? 'ring-2 ring-emerald-400/70' : ''}`}>
            <div className={`absolute top-0 left-0 right-0 h-1 rounded-t-2xl bg-gradient-to-r ${getRoleTheme(msg.role).accent}`} />

            <div className="flex items-center justify-between gap-2 mb-3 border-b border-black/10 pb-2">
              <div className="flex items-center gap-2">
                <div className="p-2 bg-white rounded-full shadow-sm border border-slate-200">
                {getAgentIcon(msg.role)}
                </div>
                <h3 className="font-semibold text-base sm:text-lg text-slate-900 tracking-tight" style={{ fontFamily: 'var(--font-display)' }}>
                  {getAgentName(msg.role)}
                </h3>
              </div>
              <span className={`text-xs px-2 py-1 rounded-full font-medium ${getRoleTheme(msg.role).chip}`}>{msg.role.replace('_', ' ')}</span>
            </div>

            {msg.type === 'verdict' && msg.verdictData ? (
              <div className="space-y-4">
                <div className="flex flex-wrap items-center gap-2">
                  <span className={`px-3 py-1 rounded-full text-sm font-semibold border ${winnerStyle(msg.verdictData.winner)}`}>
                    {winnerLabel(msg.verdictData.winner)}
                  </span>
                  <span className="px-3 py-1 rounded-full text-sm font-medium bg-slate-100 text-slate-800 border border-slate-300">
                    Confidence: {msg.verdictData.confidence}
                  </span>
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  <div className="p-3 rounded-xl border border-cyan-200 bg-cyan-50">
                    <p className="text-xs uppercase tracking-wide text-cyan-700 font-semibold mb-1">Pro Total</p>
                    <p className="text-2xl font-bold text-cyan-900">{msg.verdictData.scores.pro.total}</p>
                  </div>
                  <div className="p-3 rounded-xl border border-rose-200 bg-rose-50">
                    <p className="text-xs uppercase tracking-wide text-rose-700 font-semibold mb-1">Opponent Total</p>
                    <p className="text-2xl font-bold text-rose-900">{msg.verdictData.scores.opponent.total}</p>
                  </div>
                </div>

                <div className="rounded-xl border border-slate-200 bg-white p-3 space-y-3">
                  {CRITERIA.filter((criterion) => criterion.key !== 'total').map((criterion) => {
                    const max = criterion.max ?? 1;
                    const proScore = msg.verdictData?.scores.pro[criterion.key] ?? 0;
                    const opponentScore = msg.verdictData?.scores.opponent[criterion.key] ?? 0;
                    const proWidth = `${Math.min(100, (proScore / max) * 100)}%`;
                    const opponentWidth = `${Math.min(100, (opponentScore / max) * 100)}%`;

                    return (
                      <div key={criterion.key}>
                        <div className="flex justify-between text-xs sm:text-sm text-slate-700 mb-1">
                          <span className="font-medium">{criterion.label} ({max})</span>
                          <span>Pro {proScore} | Opponent {opponentScore}</span>
                        </div>
                        <div className="grid grid-cols-2 gap-2">
                          <div className="h-2.5 bg-slate-100 rounded-full overflow-hidden">
                            <div className="h-full bg-cyan-500" style={{ width: proWidth }} />
                          </div>
                          <div className="h-2.5 bg-slate-100 rounded-full overflow-hidden">
                            <div className="h-full bg-rose-500" style={{ width: opponentWidth }} />
                          </div>
                        </div>
                      </div>
                    );
                  })}
                </div>

                {msg.verdictData.penalties ? (
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-sm">
                    <div className="p-3 rounded-xl border border-cyan-200 bg-cyan-50 text-slate-800">
                      <p className="font-semibold mb-1">Pro penalties</p>
                      <p>False claims: {msg.verdictData.penalties.pro.false_claims}</p>
                      <p>Repeated Partially True: {msg.verdictData.penalties.pro.repeated_partial_true}</p>
                      <p>Points deducted: {msg.verdictData.penalties.pro.points_deducted}</p>
                    </div>
                    <div className="p-3 rounded-xl border border-rose-200 bg-rose-50 text-slate-800">
                      <p className="font-semibold mb-1">Opponent penalties</p>
                      <p>False claims: {msg.verdictData.penalties.opponent.false_claims}</p>
                      <p>Repeated Partially True: {msg.verdictData.penalties.opponent.repeated_partial_true}</p>
                      <p>Points deducted: {msg.verdictData.penalties.opponent.points_deducted}</p>
                    </div>
                  </div>
                ) : null}

                <div className="text-slate-700 leading-relaxed text-[15px] space-y-2 p-3 rounded-xl border border-slate-200 bg-white">
                  <p><span className="font-semibold">Summary:</span> {msg.verdictData.summary}</p>
                  <p><span className="font-semibold">Rationale:</span> {msg.verdictData.rationale}</p>
                </div>

                {(msg.verdictData.key_errors.pro.length > 0 || msg.verdictData.key_errors.opponent.length > 0) ? (
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-sm text-slate-700">
                    <div className="p-3 rounded-xl border border-slate-200 bg-slate-50">
                      <p className="font-semibold mb-1">Pro key errors</p>
                      <p>{msg.verdictData.key_errors.pro.length ? msg.verdictData.key_errors.pro.join('; ') : 'None'}</p>
                    </div>
                    <div className="p-3 rounded-xl border border-slate-200 bg-slate-50">
                      <p className="font-semibold mb-1">Opponent key errors</p>
                      <p>{msg.verdictData.key_errors.opponent.length ? msg.verdictData.key_errors.opponent.join('; ') : 'None'}</p>
                    </div>
                  </div>
                ) : null}
              </div>
            ) : (
              <p className="text-slate-700 whitespace-pre-wrap leading-relaxed text-[15px]">
                {msg.content}
              </p>
            )}
          </div>
        ))}
        {isDebating && (
          <div className="flex justify-center items-center py-4">
            <span className="flex items-center gap-2 text-cyan-700 font-medium px-4 py-2 rounded-full bg-cyan-50 border border-cyan-200">
              <div className="w-2 h-2 rounded-full bg-cyan-600 animate-bounce"></div>
              <div className="w-2 h-2 rounded-full bg-cyan-600 animate-bounce" style={{ animationDelay: '0.2s' }}></div>
              <div className="w-2 h-2 rounded-full bg-cyan-600 animate-bounce" style={{ animationDelay: '0.4s' }}></div>
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
