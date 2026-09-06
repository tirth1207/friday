"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import {
  Activity,
  Check,
  ChevronDown,
  ChevronRight,
  Copy,
  GiftIcon as Github,
  History,
  Menu,
  PanelLeft,
  PanelRight,
  Plus,
  Send,
  ShieldCheck,
  Sparkles,
  Trash2,
  UserRound,
  Wrench,
  X,
  Zap,
} from "lucide-react";

type Message = {
  id: string;
  role: "user" | "assistant";
  content: string;
  createdAt: number;
};
type Repository = {
  name: string;
  full_name: string;
  private: boolean;
  language?: string | null;
};
type FridayEvent = {
  id: string;
  type: string;
  timestamp: string;
  title: string;
  description?: string;
  agent?: string;
  tool?: string;
  status?: string;
  metadata?: Record<string, unknown>;
};
type HistoryItem = {
  id: number;
  role: string;
  content: string;
  timestamp: string;
};
type GithubStatus = {
  connected?: boolean;
  login?: string;
  configured?: boolean;
};

const API = process.env.NEXT_PUBLIC_FRIDAY_API_URL || "http://127.0.0.1:8000";
const WS = process.env.NEXT_PUBLIC_FRIDAY_WS_URL || "ws://127.0.0.1:8000/ws";
const starterPrompts = [
  [
    "Inspect a project",
    "Analyze my selected repository architecture and tell me what I should improve.",
  ],
  [
    "Build something",
    "Inspect the current project, make a plan, then implement the next highest-value improvement.",
  ],
  [
    "Teach me",
    "Teach me one advanced software engineering concept I should know as a professional engineer.",
  ],
];
function cn(...classes: Array<string | false | null | undefined>) {
  return classes.filter(Boolean).join(" ");
}
function formatTime(value?: string | number) {
  const d = value ? new Date(value) : null;
  return d && !Number.isNaN(d.getTime())
    ? d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })
    : "";
}
function formatHistoryDate(value: string) {
  const d = new Date(value);
  return Number.isNaN(d.getTime())
    ? ""
    : d.toLocaleDateString([], { month: "short", day: "numeric" });
}

function MarkdownMessage({ content }: { content: string }) {
  return (
    <div className="friday-markdown text-[14px] leading-7 text-white/80">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          h1: ({ children }) => (
            <h1 className="mb-4 mt-7 text-2xl font-semibold text-white first:mt-0">
              {children}
            </h1>
          ),
          h2: ({ children }) => (
            <h2 className="mb-3 mt-7 text-xl font-semibold text-white">
              {children}
            </h2>
          ),
          h3: ({ children }) => (
            <h3 className="mb-2 mt-5 font-semibold text-white">{children}</h3>
          ),
          p: ({ children }) => <p className="mb-4 last:mb-0">{children}</p>,
          ul: ({ children }) => (
            <ul className="mb-4 list-disc space-y-1.5 pl-5">{children}</ul>
          ),
          ol: ({ children }) => (
            <ol className="mb-4 list-decimal space-y-1.5 pl-5">{children}</ol>
          ),
          li: ({ children }) => <li>{children}</li>,
          strong: ({ children }) => (
            <strong className="font-semibold text-white">{children}</strong>
          ),
          a: ({ href, children }) => (
            <a
              href={href}
              target="_blank"
              rel="noreferrer"
              className="text-blue-400 underline underline-offset-4"
            >
              {children}
            </a>
          ),
          blockquote: ({ children }) => (
            <blockquote className="my-5 border-l-2 border-blue-500/50 pl-4 italic text-white/50">
              {children}
            </blockquote>
          ),
          code: ({ className, children }) =>
            className ? (
              <pre className="my-5 overflow-x-auto rounded-xl border border-white/10 bg-[#080a0e] p-4">
                <code className="font-mono text-[12px] leading-6 text-white/75">
                  {String(children).replace(/\n$/, "")}
                </code>
              </pre>
            ) : (
              <code className="rounded bg-white/[0.07] px-1.5 py-0.5 font-mono text-[12px] text-blue-300">
                {children}
              </code>
            ),
          table: ({ children }) => (
            <div className="my-5 overflow-x-auto rounded-xl border border-white/10">
              <table className="w-full text-sm">{children}</table>
            </div>
          ),
          th: ({ children }) => (
            <th className="border-b border-white/10 px-4 py-3 text-left text-white">
              {children}
            </th>
          ),
          td: ({ children }) => (
            <td className="border-b border-white/[0.06] px-4 py-3 text-white/65">
              {children}
            </td>
          ),
        }}
      >
        {content}
      </ReactMarkdown>
    </div>
  );
}

function Trace({
  events,
  open,
  onToggle,
  onClear,
}: {
  events: FridayEvent[];
  open: boolean;
  onToggle: () => void;
  onClear: () => void;
}) {
  if (!events.length) return null;
  const active = events.filter(
    (e) =>
      e.status === "running" ||
      e.type === "thinking" ||
      e.type === "tool_started",
  ).length;
  return (
    <aside
      className={cn(
        "fixed bottom-4 right-4 z-50 overflow-hidden rounded-2xl border border-white/10 bg-[#0b0d11]/95 shadow-2xl backdrop-blur-xl",
        open ? "w-[min(400px,calc(100vw-2rem))]" : "w-auto",
      )}
    >
      <div className="flex items-center gap-2 p-2.5">
        <button
          onClick={onToggle}
          className="flex min-w-0 flex-1 items-center gap-2.5 rounded-xl px-2 py-1.5 text-left hover:bg-white/[0.04]"
        >
          <div className="flex h-7 w-7 items-center justify-center rounded-lg border border-blue-500/20 bg-blue-500/10 text-blue-400">
            <Activity size={14} />
          </div>
          {open ? (
            <div>
              <div className="text-[11px] font-medium text-white/75">
                Execution trace
              </div>
              <div className="text-[9px] text-white/25">
                {events.length} events{active ? ` · ${active} active` : ""}
              </div>
            </div>
          ) : (
            <span className="text-[10px] text-white/35">{events.length}</span>
          )}
        </button>
        {open && (
          <button
            onClick={onClear}
            className="rounded-lg p-2 text-white/20 hover:bg-white/[0.05]"
          >
            <Trash2 size={13} />
          </button>
        )}
        <button
          onClick={onToggle}
          className="rounded-lg p-2 text-white/20 hover:bg-white/[0.05]"
        >
          {open ? <ChevronDown size={14} /> : <PanelRight size={14} />}
        </button>
      </div>
      {open && (
        <div className="max-h-[48vh] overflow-y-auto border-t border-white/[0.07]">
          {events.map((e) => (
            <div
              key={e.id}
              className="flex gap-3 border-b border-white/[0.045] px-4 py-3"
            >
              <span
                className={cn(
                  "mt-1.5 h-2 w-2 shrink-0 rounded-full",
                  e.status === "failed" || e.type === "error"
                    ? "bg-red-400"
                    : e.status === "running" ||
                        e.type === "thinking" ||
                        e.type === "tool_started"
                      ? "animate-pulse bg-blue-400"
                      : "bg-white/20",
                )}
              />
              <div className="min-w-0 flex-1">
                <div className="text-[11px] font-medium text-white/70">
                  {e.title}
                </div>
                <div className="mt-1 truncate text-[9px] text-white/25">
                  {e.agent}
                  {e.tool ? ` · ${e.tool}` : ""}
                  {e.description ? ` · ${e.description}` : ""}
                </div>
              </div>
              <span className="shrink-0 text-[8px] text-white/15">
                {formatTime(e.timestamp)}
              </span>
            </div>
          ))}
        </div>
      )}
    </aside>
  );
}

export default function App() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [events, setEvents] = useState<FridayEvent[]>([]);
  const [traceOpen, setTraceOpen] = useState(true);
  const [leftOpen, setLeftOpen] = useState(true);
  const [rightOpen, setRightOpen] = useState(false);
  const [mobileLeft, setMobileLeft] = useState(false);
  const [repositories, setRepositories] = useState<Repository[]>([]);
  const [selectedRepository, setSelectedRepository] = useState("");
  const [repoError, setRepoError] = useState<string | null>(null);
  const [github, setGithub] = useState<GithubStatus>({});
  const [history, setHistory] = useState<HistoryItem[]>([]);
  const [historyLoading, setHistoryLoading] = useState(true);
  const [apiHealthy, setApiHealthy] = useState<boolean | null>(null);
  const socketRef = useRef<WebSocket | null>(null);
  const reconnectRef = useRef<number | null>(null);
  const endRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  const loadWorkspace = useCallback(async () => {
    try {
      const [reposResponse, statusResponse, historyResponse] =
        await Promise.all([
          fetch(`${API}/auth/github/repositories`, { cache: "no-store" }),
          fetch(`${API}/auth/github/status`, { cache: "no-store" }),
          fetch(`${API}/conversations?limit=80`, { cache: "no-store" }),
        ]);
      if (reposResponse.ok) {
        const d = await reposResponse.json();
        const items = Array.isArray(d.repositories) ? d.repositories : [];
        setRepositories(items);
        setSelectedRepository(d.active_repository || items[0]?.full_name || "");
      }
      if (statusResponse.ok) setGithub(await statusResponse.json());
      if (historyResponse.ok) {
        const d = await historyResponse.json();
        setHistory(Array.isArray(d.conversations) ? d.conversations : []);
      }
    } catch (e) {
      setRepoError(e instanceof Error ? e.message : "Workspace unavailable");
    } finally {
      setHistoryLoading(false);
    }
  }, []);
  useEffect(() => {
    loadWorkspace();
  }, [loadWorkspace]);
  useEffect(() => {
    const check = async () => {
      try {
        setApiHealthy((await fetch(`${API}/health`, { cache: "no-store" })).ok);
      } catch {
        setApiHealthy(false);
      }
    };
    check();
    const id = window.setInterval(check, 15000);
    return () => window.clearInterval(id);
  }, []);
  useEffect(() => {
    let stopped = false;
    const connect = () => {
      if (stopped) return;
      try {
        const ws = new WebSocket(WS);
        socketRef.current = ws;
        ws.onmessage = (e) => {
          try {
            const event = JSON.parse(e.data);
            if (event?.id)
              setEvents((prev) =>
                prev.some((x) => x.id === event.id) ? prev : [...prev, event],
              );
          } catch {}
        };
        ws.onclose = () => {
          if (!stopped) reconnectRef.current = window.setTimeout(connect, 3000);
        };
      } catch {
        reconnectRef.current = window.setTimeout(connect, 3000);
      }
    };
    connect();
    return () => {
      stopped = true;
      if (reconnectRef.current) clearTimeout(reconnectRef.current);
      socketRef.current?.close();
    };
  }, []);
  useEffect(() => {
    requestAnimationFrame(() =>
      endRef.current?.scrollIntoView({ behavior: "smooth" }),
    );
  }, [messages, loading]);
  useEffect(() => {
    const el = inputRef.current;
    if (el) {
      el.style.height = "auto";
      el.style.height = `${Math.min(el.scrollHeight, 180)}px`;
    }
  }, [input]);

  async function chooseRepository(value: string) {
    setSelectedRepository(value);
    setRepoError(null);
    try {
      const r = await fetch(`${API}/auth/github/repository-context`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ repository: value || null }),
      });
      if (!r.ok) throw new Error(`Repository selection returned ${r.status}`);
    } catch (e) {
      setRepoError(
        e instanceof Error ? e.message : "Unable to select repository",
      );
    }
  }
  async function sendMessage() {
    const message = input.trim();
    if (!message || loading) return;
    setEvents([]);
    setTraceOpen(true);
    setLoading(true);
    setInput("");
    setMessages((prev) => [
      ...prev,
      {
        id: crypto.randomUUID(),
        role: "user",
        content: message,
        createdAt: Date.now(),
      },
    ]);
    try {
      const r = await fetch(`${API}/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          message,
          repository: selectedRepository || null,
        }),
      });
      const d = await r.json();
      if (d.repository) setSelectedRepository(d.repository);
      setMessages((prev) => [
        ...prev,
        {
          id: crypto.randomUUID(),
          role: "assistant",
          content: d.response || "FRIDAY returned no response.",
          createdAt: Date.now(),
        },
      ]);
      setApiHealthy(true);
      const h = await fetch(`${API}/conversations?limit=80`);
      if (h.ok) {
        const hd = await h.json();
        setHistory(hd.conversations || []);
      }
    } catch {
      setApiHealthy(false);
      setMessages((prev) => [
        ...prev,
        {
          id: crypto.randomUUID(),
          role: "assistant",
          content:
            "### Connection error\n\nI couldn't reach FRIDAY Core. Make sure the backend is running on `127.0.0.1:8000`.",
          createdAt: Date.now(),
        },
      ]);
    } finally {
      setLoading(false);
      inputRef.current?.focus();
    }
  }
  function newChat() {
    setMessages([]);
    setEvents([]);
    setInput("");
  }
  function keyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  }
  const visibleHistory = useMemo(
    () => history.filter((x) => x.role === "user"),
    [history],
  );

  return (
    <main className="min-h-screen bg-[#050608] text-white">
      <div className="pointer-events-none fixed inset-0 bg-[radial-gradient(circle_at_50%_-10%,rgba(37,99,235,.10),transparent_40%)]" />
      <header className="fixed left-0 right-0 top-0 z-40 h-14 border-b border-white/[0.07] bg-[#07080b]/90 backdrop-blur-xl">
        <div className="flex h-full items-center gap-2 px-3">
          <button
            onClick={() => setLeftOpen((v) => !v)}
            className="hidden rounded-lg p-2 text-white/35 hover:bg-white/[0.05] md:block"
            title="Toggle conversations"
          >
            {leftOpen ? <PanelLeft size={16} /> : <Menu size={16} />}
          </button>
          <button
            onClick={() => setMobileLeft(true)}
            className="rounded-lg p-2 text-white/35 md:hidden"
          >
            <Menu size={17} />
          </button>
          <div className="flex items-center gap-2.5">
            <div className="flex h-7 w-7 items-center justify-center rounded-lg border border-blue-500/20 bg-blue-500/10">
              <span className="h-1.5 w-1.5 rounded-full bg-blue-400 shadow-[0_0_15px_rgba(59,130,246,.9)]" />
            </div>
            <span className="text-[12px] font-semibold tracking-[0.18em]">
              FRIDAY
            </span>
          </div>
          <div className="ml-auto flex items-center gap-2">
            <div className="hidden items-center gap-1.5 rounded-full border border-white/[0.06] px-2.5 py-1.5 sm:flex">
              <ShieldCheck
                size={11}
                className={apiHealthy ? "text-emerald-400" : "text-white/25"}
              />
              <span className="text-[9px] text-white/30">Core</span>
              <span
                className={cn(
                  "h-1.5 w-1.5 rounded-full",
                  apiHealthy ? "bg-emerald-400" : "bg-white/20",
                )}
              />
            </div>
            <button
              onClick={() => setRightOpen((v) => !v)}
              className="rounded-lg p-2 text-white/30 hover:bg-white/[0.05]"
              title="Toggle tools"
            >
              {rightOpen ? <ChevronRight size={16} /> : <Wrench size={15} />}
            </button>
            <button
              onClick={newChat}
              className="rounded-lg border border-white/[0.07] p-2 text-white/30 hover:bg-white/[0.05]"
              title="New conversation"
            >
              <Plus size={15} />
            </button>
          </div>
        </div>
      </header>
      <div className="flex min-h-screen pt-14">
        <aside
          className={cn(
            "fixed bottom-0 left-0 top-14 z-30 border-r border-white/[0.07] bg-[#090a0d]/95 backdrop-blur-xl transition-all duration-200 md:sticky md:top-14 md:h-[calc(100vh-3.5rem)]",
            leftOpen ? "w-64" : "w-0 overflow-hidden",
            mobileLeft ? "translate-x-0" : "-translate-x-full md:translate-x-0",
          )}
        >
          {leftOpen && (
            <div className="flex h-full w-64 flex-col">
              <div className="flex items-center justify-between px-3 py-3">
                <span className="text-[10px] font-medium uppercase tracking-[0.18em] text-white/30">
                  Conversations
                </span>
                <button
                  onClick={newChat}
                  className="rounded-md p-1.5 text-white/25 hover:bg-white/[0.05]"
                >
                  <Plus size={14} />
                </button>
              </div>
              <div className="flex-1 overflow-y-auto px-2">
                {historyLoading && !visibleHistory.length ? (
                  <div className="px-2 py-5 text-[10px] text-white/20">
                    Loading history…
                  </div>
                ) : visibleHistory.length ? (
                  visibleHistory.map((item) => (
                    <button
                      key={item.id}
                      onClick={() => {
                        setInput(item.content);
                        setMobileLeft(false);
                      }}
                      className="mb-0.5 w-full rounded-lg px-2.5 py-2.5 text-left hover:bg-white/[0.04]"
                    >
                      <div className="flex items-center gap-2">
                        <History size={11} className="shrink-0 text-white/20" />
                        <span className="line-clamp-1 text-[11px] text-white/55">
                          {item.content}
                        </span>
                      </div>
                      <div className="mt-1 pl-5 text-[8px] text-white/15">
                        {formatHistoryDate(item.timestamp)}
                      </div>
                    </button>
                  ))
                ) : (
                  <div className="px-2 py-5 text-[10px] text-white/20">
                    No conversations yet.
                  </div>
                )}
              </div>
              <div className="border-t border-white/[0.07] p-3">
                <div className="mb-2 text-[9px] uppercase tracking-[0.18em] text-white/20">
                  GitHub profile
                </div>
                <a
                  href={
                    github.connected
                      ? `https://github.com/${github.login}`
                      : "/github"
                  }
                  target={github.connected ? "_blank" : undefined}
                  rel="noreferrer"
                  className="flex items-center gap-2.5 rounded-xl border border-white/[0.07] bg-white/[0.02] p-2.5 hover:bg-white/[0.04]"
                >
                  <div className="flex h-8 w-8 items-center justify-center rounded-full border border-white/10 bg-white/[0.05]">
                    <Github size={15} className="text-white/50" />
                  </div>
                  <div className="min-w-0 flex-1">
                    <div className="truncate text-[11px] font-medium text-white/65">
                      {github.connected
                        ? `@${github.login || "GitHub"}`
                        : "Connect GitHub"}
                    </div>
                    <div className="text-[9px] text-white/20">
                      {github.connected
                        ? "Connected account"
                        : "Open GitHub settings"}
                    </div>
                  </div>
                  <ChevronRight size={12} className="text-white/20" />
                </a>
                <div className="mt-2 flex items-center gap-2 px-1 text-[9px] text-white/20">
                  <UserRound size={10} /> {repositories.length} repositories
                  available
                </div>
              </div>
            </div>
          )}
        </aside>
        {mobileLeft && (
          <button
            aria-label="Close sidebar"
            onClick={() => setMobileLeft(false)}
            className="fixed inset-0 z-20 bg-black/60 md:hidden"
          />
        )}
        <section className="min-w-0 flex-1">
          <div className="mx-auto flex min-h-[calc(100vh-3.5rem)] max-w-3xl flex-col px-4 sm:px-6">
            {messages.length === 0 ? (
              <div className="flex flex-1 flex-col items-center justify-center pb-32 pt-16 text-center">
                <div className="relative mb-7">
                  <div className="absolute -inset-8 rounded-full bg-blue-500/10 blur-3xl" />
                  <div className="relative flex h-16 w-16 items-center justify-center rounded-2xl border border-white/10 bg-white/[0.035]">
                    <Sparkles size={24} className="text-blue-400" />
                  </div>
                </div>
                <div className="text-[10px] font-medium uppercase tracking-[0.25em] text-blue-400/60">
                  FRIDAY / READY
                </div>
                <h1 className="mt-2 text-3xl font-semibold tracking-[-0.03em] sm:text-4xl">
                  What are we building?
                </h1>
                <p className="mt-4 max-w-xl text-sm leading-6 text-white/30">
                  A personal operating layer that can understand, research,
                  code, verify, learn from experience, and keep going.
                </p>
                <div className="mt-8 w-full max-w-2xl rounded-2xl border border-white/[0.07] bg-white/[0.018] p-3 text-left">
                  <div className="mb-2 flex items-center justify-between px-1">
                    <span className="text-[9px] uppercase tracking-[0.2em] text-white/25">
                      Workspace
                    </span>
                    <span className="text-[9px] text-white/20">
                      {repositories.length} repos
                    </span>
                  </div>
                  <div className="relative">
                    <select
                      value={selectedRepository}
                      onChange={(e) => chooseRepository(e.target.value)}
                      className="w-full appearance-none rounded-xl border border-white/[0.08] bg-[#0a0c10] px-3 py-2.5 pr-9 text-[12px] text-white/65 outline-none focus:border-blue-500/30"
                    >
                      <option value="">No repository selected</option>
                      {repositories.map((r) => (
                        <option key={r.full_name} value={r.full_name}>
                          {r.full_name}
                          {r.private ? " · private" : ""}
                        </option>
                      ))}
                    </select>
                    <ChevronDown
                      size={14}
                      className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-white/20"
                    />
                  </div>
                  {repoError && (
                    <div className="mt-2 text-[10px] text-red-300/70">
                      {repoError}
                    </div>
                  )}
                </div>
                <div className="mt-3 grid w-full max-w-2xl gap-2 sm:grid-cols-3">
                  {starterPrompts.map(([label, text]) => (
                    <button
                      key={label}
                      onClick={() => setInput(text)}
                      className="rounded-xl border border-white/[0.07] bg-white/[0.018] p-3.5 text-left transition hover:-translate-y-0.5 hover:border-blue-500/20 hover:bg-blue-500/[0.035]"
                    >
                      <div className="mb-3 flex h-7 w-7 items-center justify-center rounded-lg bg-white/[0.045] text-white/35">
                        <Zap size={13} />
                      </div>
                      <div className="text-[11px] font-medium text-white/60">
                        {label}
                      </div>
                      <div className="mt-1 line-clamp-2 text-[9px] leading-4 text-white/20">
                        {text}
                      </div>
                    </button>
                  ))}
                </div>
              </div>
            ) : (
              <div className="space-y-9 pb-40 pt-8">
                {selectedRepository && (
                  <div className="sticky top-16 z-10 flex items-center justify-between rounded-xl border border-white/[0.07] bg-[#090b0f]/90 px-3 py-2 backdrop-blur-xl">
                    <span className="text-[9px] uppercase tracking-wider text-white/20">
                      Repository
                    </span>
                    <span className="font-mono text-[10px] text-white/45">
                      {selectedRepository}
                    </span>
                  </div>
                )}
                {messages.map((m) => (
                  <article
                    key={m.id}
                    className={
                      m.role === "user"
                        ? "flex justify-end"
                        : "flex justify-start"
                    }
                  >
                    {m.role === "user" ? (
                      <div className="max-w-[85%] rounded-2xl rounded-br-md border border-blue-400/10 bg-blue-600 px-4 py-3 text-[13px] leading-6 text-white">
                        {m.content}
                      </div>
                    ) : (
                      <div className="w-full">
                        <div className="mb-3 flex items-center gap-2">
                          <div className="flex h-6 w-6 items-center justify-center rounded-lg border border-blue-500/15 bg-blue-500/[0.07]">
                            <span className="text-[9px] font-bold text-blue-400">
                              F
                            </span>
                          </div>
                          <span className="text-[10px] font-medium tracking-[0.14em] text-white/35">
                            FRIDAY
                          </span>
                          <span className="text-[9px] text-white/15">
                            {formatTime(m.createdAt)}
                          </span>
                        </div>
                        <MarkdownMessage content={m.content} />
                      </div>
                    )}
                  </article>
                ))}
                {loading && (
                  <div className="flex items-center gap-3 text-[11px] text-white/25">
                    <span className="flex gap-1">
                      <i className="h-1.5 w-1.5 animate-pulse rounded-full bg-blue-400" />
                      <i className="h-1.5 w-1.5 animate-pulse rounded-full bg-blue-400 [animation-delay:150ms]" />
                      <i className="h-1.5 w-1.5 animate-pulse rounded-full bg-blue-400 [animation-delay:300ms]" />
                    </span>
                    FRIDAY is working…
                  </div>
                )}
                <div ref={endRef} />
              </div>
            )}
          </div>
        </section>
        <aside
          className={cn(
            "fixed bottom-0 right-0 top-14 z-30 border-l border-white/[0.07] bg-[#090a0d]/95 backdrop-blur-xl transition-all duration-200 md:sticky md:top-14 md:h-[calc(100vh-3.5rem)]",
            rightOpen ? "w-64" : "w-0 overflow-hidden",
          )}
        >
          {rightOpen && (
            <div className="flex h-full w-64 flex-col">
              <div className="flex items-center justify-between px-3 py-3">
                <span className="text-[10px] font-medium uppercase tracking-[0.18em] text-white/30">
                  Tools
                </span>
                <button
                  onClick={() => setRightOpen(false)}
                  className="rounded-md p-1.5 text-white/25 hover:bg-white/[0.05]"
                >
                  <X size={13} />
                </button>
              </div>
              <div className="flex flex-1 flex-col items-center justify-center px-6 text-center">
                <div className="mb-3 flex h-10 w-10 items-center justify-center rounded-xl border border-white/[0.07] bg-white/[0.025]">
                  <Wrench size={16} className="text-white/25" />
                </div>
                <div className="text-[11px] text-white/45">Tool workspace</div>
                <p className="mt-1 text-[9px] leading-4 text-white/20">
                  Intentionally empty for now. Future FRIDAY tools can live
                  here.
                </p>
              </div>
            </div>
          )}
        </aside>
      </div>
      <footer className="fixed bottom-0 left-0 right-0 z-20 bg-gradient-to-t from-[#050608] via-[#050608]/95 to-transparent pt-8">
        <div className="mx-auto max-w-3xl px-4 pb-4 sm:px-6">
          <div className="rounded-2xl border border-white/[0.09] bg-[#0b0d11]/95 p-2 shadow-2xl backdrop-blur-xl">
            <div className="flex items-end gap-2">
              <textarea
                ref={inputRef}
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={keyDown}
                rows={1}
                placeholder={
                  selectedRepository
                    ? `Ask FRIDAY about ${selectedRepository}…`
                    : "Ask FRIDAY anything…"
                }
                className="max-h-44 min-h-11 flex-1 resize-none bg-transparent px-3 py-2.5 text-[13px] leading-6 text-white outline-none placeholder:text-white/20"
              />
              <button
                onClick={sendMessage}
                disabled={!input.trim() || loading}
                className="mb-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-blue-600 text-white hover:bg-blue-500 disabled:cursor-not-allowed disabled:bg-white/[0.05] disabled:text-white/20"
              >
                <Send size={15} />
              </button>
            </div>
            <div className="flex items-center gap-3 px-3 pb-1 pt-1">
              <span className="text-[8px] text-white/15">
                Enter to send · Shift+Enter for newline
              </span>
              {selectedRepository && (
                <span className="ml-auto truncate text-[8px] font-mono text-white/15">
                  {selectedRepository}
                </span>
              )}
            </div>
          </div>
        </div>
      </footer>
      <Trace
        events={events}
        open={traceOpen}
        onToggle={() => setTraceOpen((v) => !v)}
        onClear={() => setEvents([])}
      />
    </main>
  );
}
