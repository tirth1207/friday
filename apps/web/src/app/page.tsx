"use client"

import { useCallback, useEffect, useMemo, useRef, useState } from "react"
import ReactMarkdown from "react-markdown"
import remarkGfm from "remark-gfm"
import {
  Activity,
  AlertCircle,
  Bot,
  Check,
  ChevronDown,
  ChevronRight,
  Clipboard,
  Copy,
  PanelRight,
  Plus,
  RotateCcw,
  Send,
  ShieldCheck,
  Sparkles,
  Terminal,
  Trash2,
  Wifi,
  WifiOff,
  X,
  Zap,
} from "lucide-react"

type Message = {
  id: string
  role: "user" | "assistant"
  content: string
  createdAt: number
}

type Repository = {
  name: string
  full_name: string
  private: boolean
  default_branch?: string
  archived?: boolean
  description?: string | null
  language?: string | null
  html_url?: string | null
}

type FridayEvent = {
  id: string
  type:
    | "thinking"
    | "planning"
    | "agent_created"
    | "agent_started"
    | "agent_completed"
    | "tool_started"
    | "tool_completed"
    | "tool_error"
    | "verification"
    | "message"
    | "error"
  timestamp: string
  title: string
  description?: string
  agent?: string
  tool?: string
  status?: string
  metadata?: Record<string, unknown>
}

const API_BASE_URL = process.env.NEXT_PUBLIC_FRIDAY_API_URL || "http://127.0.0.1:8000"
const WS_URL = process.env.NEXT_PUBLIC_FRIDAY_WS_URL || "ws://127.0.0.1:8000/ws"

const starterPrompts = [
  { label: "Explain something", text: "Explain a difficult concept to me in simple terms." },
  { label: "Write code", text: "Help me design a clean solution for a coding problem." },
  { label: "Inspect a project", text: "Analyze my project architecture and tell me what I should improve." },
]

function cn(...classes: Array<string | false | null | undefined>) {
  return classes.filter(Boolean).join(" ")
}

function formatTime(value?: string | number) {
  if (!value) return ""
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return ""
  return date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })
}

function getEventLabel(event: FridayEvent) {
  switch (event.type) {
    case "thinking": return "THINKING"
    case "planning":
    case "agent_created":
    case "agent_started":
    case "agent_completed": return "AGENT"
    case "tool_started":
    case "tool_completed": return "TOOL"
    case "tool_error": return "TOOL ERROR"
    case "verification": return "VERIFY"
    case "message": return "SYSTEM"
    case "error": return "ERROR"
    default: return "EVENT"
  }
}

function isFailure(event: FridayEvent) {
  return event.status === "failed" || event.type === "tool_error" || event.type === "error"
}

function isComplete(event: FridayEvent) {
  return event.status === "completed" || event.status === "success" || event.type === "agent_completed" || event.type === "tool_completed"
}

function isRunning(event: FridayEvent) {
  return event.status === "running" || event.type === "thinking" || event.type === "planning" || event.type === "agent_started" || event.type === "tool_started"
}

function EventStatusIcon({ event }: { event: FridayEvent }) {
  if (isFailure(event)) {
    return <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-red-500/10 text-red-400"><X size={13} /></span>
  }
  if (isComplete(event)) {
    return <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-blue-500/10 text-blue-400"><Check size={13} /></span>
  }
  if (isRunning(event)) {
    return <span className="flex h-6 w-6 shrink-0 items-center justify-center"><span className="h-2.5 w-2.5 animate-pulse rounded-full bg-blue-400 shadow-[0_0_14px_rgba(59,130,246,.9)]" /></span>
  }
  return <span className="flex h-6 w-6 shrink-0 items-center justify-center text-white/20"><span className="h-1.5 w-1.5 rounded-full bg-white/20" /></span>
}

function CodeBlock({ language, code }: { language: string; code: string }) {
  const [copied, setCopied] = useState(false)
  const copyCode = async () => {
    try {
      await navigator.clipboard.writeText(code)
      setCopied(true)
      window.setTimeout(() => setCopied(false), 1400)
    } catch { console.warn("[FRIDAY] Clipboard unavailable") }
  }
  return (
    <div className="my-5 overflow-hidden rounded-xl border border-white/10 bg-[#07090d] shadow-2xl shadow-black/20">
      <div className="flex items-center justify-between border-b border-white/[0.07] px-3.5 py-2.5">
        <div className="flex items-center gap-2"><Terminal size={12} className="text-blue-400/70" /><span className="font-mono text-[10px] uppercase tracking-[0.16em] text-white/35">{language || "code"}</span></div>
        <button onClick={copyCode} className="flex items-center gap-1.5 rounded-md px-2 py-1 text-[10px] text-white/35 transition hover:bg-white/[0.05] hover:text-white/70">{copied ? <Check size={12} /> : <Copy size={12} />}{copied ? "Copied" : "Copy"}</button>
      </div>
      <pre className="overflow-x-auto p-4"><code className="font-mono text-[12px] leading-6 text-white/75">{code}</code></pre>
    </div>
  )
}

function MarkdownMessage({ content }: { content: string }) {
  return (
    <div className="friday-markdown max-w-none text-[14px] leading-7 text-white/80">
      <ReactMarkdown remarkPlugins={[remarkGfm]} components={{
        h1: ({ children }) => <h1 className="mb-4 mt-7 text-2xl font-semibold tracking-tight text-white first:mt-0">{children}</h1>,
        h2: ({ children }) => <h2 className="mb-3 mt-7 text-xl font-semibold tracking-tight text-white first:mt-0">{children}</h2>,
        h3: ({ children }) => <h3 className="mb-2 mt-5 text-base font-semibold text-white">{children}</h3>,
        p: ({ children }) => <p className="mb-4 leading-7 last:mb-0">{children}</p>,
        ul: ({ children }) => <ul className="mb-4 list-disc space-y-1.5 pl-5">{children}</ul>,
        ol: ({ children }) => <ol className="mb-4 list-decimal space-y-1.5 pl-5">{children}</ol>,
        li: ({ children }) => <li className="pl-1 leading-6">{children}</li>,
        strong: ({ children }) => <strong className="font-semibold text-white">{children}</strong>,
        em: ({ children }) => <em className="text-white/65">{children}</em>,
        blockquote: ({ children }) => <blockquote className="my-5 border-l-2 border-blue-500/60 pl-4 italic text-white/55">{children}</blockquote>,
        a: ({ href, children }) => <a href={href} target="_blank" rel="noopener noreferrer" className="text-blue-400 underline decoration-blue-400/30 underline-offset-4 transition hover:text-blue-300">{children}</a>,
        hr: () => <hr className="my-7 border-white/[0.08]" />,
        table: ({ children }) => <div className="my-5 overflow-x-auto rounded-xl border border-white/10"><table className="w-full text-sm">{children}</table></div>,
        thead: ({ children }) => <thead className="bg-white/[0.035]">{children}</thead>,
        th: ({ children }) => <th className="border-b border-white/10 px-4 py-3 text-left font-medium text-white">{children}</th>,
        td: ({ children }) => <td className="border-b border-white/[0.06] px-4 py-3 text-white/65">{children}</td>,
        code: ({ className, children }) => {
          const block = Boolean(className)
          if (!block) return <code className="rounded-md border border-white/10 bg-white/[0.07] px-1.5 py-0.5 font-mono text-[12px] text-blue-300">{children}</code>
          return <CodeBlock language={className?.replace("language-", "") || "code"} code={String(children).replace(/\n$/, "")} />
        },
      }}>{content}</ReactMarkdown>
    </div>
  )
}

function ExecutionEvent({ event }: { event: FridayEvent }) {
  const [expanded, setExpanded] = useState(false)
  const hasDetails = Boolean(event.description || event.tool || event.agent || (event.metadata && Object.keys(event.metadata).length))
  return (
    <div className="group border-b border-white/[0.045] last:border-0">
      <button type="button" disabled={!hasDetails} onClick={() => hasDetails && setExpanded(value => !value)} className={cn("flex w-full items-start gap-3 px-4 py-3 text-left transition", hasDetails && "hover:bg-white/[0.025]")}>
        <EventStatusIcon event={event} />
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2"><span className="truncate text-[12px] font-medium text-white/75">{event.title}</span><span className="shrink-0 rounded-md border border-white/[0.06] px-1.5 py-0.5 text-[8px] uppercase tracking-[0.14em] text-white/25">{getEventLabel(event)}</span></div>
          <div className="mt-1 flex items-center gap-2 text-[10px] text-white/25">{event.agent && <span className="text-blue-400/65">{event.agent}</span>}{event.tool && <><ChevronRight size={10} /><span className="font-mono">{event.tool}</span></>}{!event.agent && !event.tool && event.description && <span className="truncate">{event.description}</span>}</div>
        </div>
        <div className="flex shrink-0 items-center gap-2 text-[9px] text-white/15">{formatTime(event.timestamp)}{hasDetails && (expanded ? <ChevronDown size={13} /> : <ChevronRight size={13} />)}</div>
      </button>
      {expanded && <div className="mx-4 mb-3 ml-13 rounded-lg border border-white/[0.06] bg-black/20 p-3">{event.description && <div className="mb-3 text-[11px] leading-5 text-white/45">{event.description}</div>}<div className="grid grid-cols-2 gap-3 text-[10px]">{event.agent && <div><div className="mb-1 uppercase tracking-wider text-white/20">Agent</div><div className="text-blue-300/65">{event.agent}</div></div>}{event.tool && <div><div className="mb-1 uppercase tracking-wider text-white/20">Tool</div><div className="font-mono text-white/45">{event.tool}</div></div>}{event.status && <div><div className="mb-1 uppercase tracking-wider text-white/20">Status</div><div className="text-white/45">{event.status}</div></div>}</div>{event.metadata && Object.keys(event.metadata).length > 0 && <pre className="mt-3 overflow-x-auto rounded-md border border-white/[0.05] bg-black/25 p-2 font-mono text-[9px] leading-5 text-white/30">{JSON.stringify(event.metadata, null, 2)}</pre>}</div>}
    </div>
  )
}

function ExecutionPanel({ events, open, setOpen, onClear }: { events: FridayEvent[]; open: boolean; setOpen: (value: boolean) => void; onClear: () => void }) {
  const completed = events.filter(isComplete).length
  const running = events.filter(isRunning).length
  const failed = events.filter(isFailure).length
  if (!events.length) return null
  return (
    <aside className={cn("fixed bottom-4 right-4 z-30 w-[min(390px,calc(100vw-2rem))] overflow-hidden rounded-2xl border border-white/10 bg-[#0a0c10]/95 shadow-2xl shadow-black/50 backdrop-blur-2xl transition-all", !open && "w-auto")}>
      <div className="flex items-center gap-3 px-4 py-3"><button type="button" onClick={() => setOpen(!open)} className="flex min-w-0 flex-1 items-center gap-3 text-left"><div className="relative flex h-8 w-8 shrink-0 items-center justify-center rounded-lg border border-blue-500/20 bg-blue-500/10 text-blue-400"><Activity size={15} />{running > 0 && <span className="absolute -right-0.5 -top-0.5 h-1.5 w-1.5 animate-pulse rounded-full bg-blue-400" />}</div>{open && <div className="min-w-0"><div className="text-[12px] font-medium text-white/80">Execution trace</div><div className="mt-0.5 flex items-center gap-2 text-[9px] text-white/25"><span>{events.length} events</span>{completed > 0 && <span className="text-blue-400/60">{completed} done</span>}{running > 0 && <span className="text-blue-400">{running} running</span>}{failed > 0 && <span className="text-red-400">{failed} failed</span>}</div></div>}{!open && <span className="text-[10px] font-medium text-white/45">{events.length}</span>}</button>{open && <button type="button" onClick={onClear} aria-label="Clear execution trace" className="rounded-md p-1.5 text-white/25 transition hover:bg-white/[0.05] hover:text-white/60"><Trash2 size={13} /></button>}<button type="button" onClick={() => setOpen(!open)} aria-label="Toggle execution trace" className="rounded-md p-1.5 text-white/25 transition hover:bg-white/[0.05] hover:text-white/60">{open ? <ChevronDown size={14} /> : <PanelRight size={14} />}</button></div>
      {open && <div className="max-h-[52vh] overflow-y-auto border-t border-white/[0.07]"><div>{events.map(event => <ExecutionEvent key={event.id} event={event} />)}</div></div>}
    </aside>
  )
}

export default function App() {
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState("")
  const [loading, setLoading] = useState(false)
  const [events, setEvents] = useState<FridayEvent[]>([])
  const [executionOpen, setExecutionOpen] = useState(true)
  const [socketConnected, setSocketConnected] = useState(false)
  const [socketStatus, setSocketStatus] = useState("Connecting")
  const [apiHealthy, setApiHealthy] = useState<boolean | null>(null)
  const [copiedMessage, setCopiedMessage] = useState<string | null>(null)
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const [repositories, setRepositories] = useState<Repository[]>([])
  const [selectedRepository, setSelectedRepository] = useState("")
  const [repositoryLoading, setRepositoryLoading] = useState(true)
  const [repositoryError, setRepositoryError] = useState<string | null>(null)

  const socketRef = useRef<WebSocket | null>(null)
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const reconnectAttemptRef = useRef(0)
  const stoppedRef = useRef(false)
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  const loadRepositories = useCallback(async () => {
    setRepositoryLoading(true)
    setRepositoryError(null)
    try {
      const response = await fetch(`${API_BASE_URL}/auth/github/repositories`, { cache: "no-store" })
      if (!response.ok) throw new Error(`GitHub repository list returned ${response.status}`)
      const data = await response.json()
      const items = Array.isArray(data.repositories) ? data.repositories : []
      setRepositories(items)
      const active = typeof data.active_repository === "string" ? data.active_repository : ""
      setSelectedRepository(active || (items[0]?.full_name ?? ""))
    } catch (error) {
      setRepositoryError(error instanceof Error ? error.message : "Unable to load repositories")
    } finally {
      setRepositoryLoading(false)
    }
  }, [])

  const chooseRepository = async (value: string) => {
    setSelectedRepository(value)
    setRepositoryError(null)
    try {
      const response = await fetch(`${API_BASE_URL}/auth/github/repository-context`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ repository: value || null }),
      })
      if (!response.ok) {
        const data = await response.json().catch(() => ({}))
        throw new Error(data.detail || `Repository selection returned ${response.status}`)
      }
      const data = await response.json()
      setSelectedRepository(typeof data.repository === "string" ? data.repository : "")
    } catch (error) {
      setRepositoryError(error instanceof Error ? error.message : "Unable to select repository")
    }
  }

  useEffect(() => {
    loadRepositories()
  }, [loadRepositories])

  const connectSocket = useCallback(() => {
    if (stoppedRef.current) return
    const current = socketRef.current
    if (current && (current.readyState === WebSocket.OPEN || current.readyState === WebSocket.CONNECTING)) return
    setSocketStatus("Connecting")
    let socket: WebSocket
    try { socket = new WebSocket(WS_URL) } catch { setSocketConnected(false); setSocketStatus("Offline"); return }
    socketRef.current = socket
    socket.onopen = () => { if (stoppedRef.current) { socket.close(); return }; reconnectAttemptRef.current = 0; setSocketConnected(true); setSocketStatus("Connected") }
    socket.onmessage = event => { try { const data = JSON.parse(event.data) as FridayEvent; if (!data?.id || !data?.type || !data?.title) return; setEvents(previous => previous.some(item => item.id === data.id) ? previous : [...previous, data]) } catch { console.warn("[FRIDAY] Invalid execution event") } }
    socket.onerror = () => { setSocketConnected(false); setSocketStatus("Connection error") }
    socket.onclose = () => { setSocketConnected(false); if (stoppedRef.current) { setSocketStatus("Offline"); return }; setSocketStatus("Disconnected"); const attempt = reconnectAttemptRef.current; const delay = Math.min(1000 * 2 ** attempt, 10000); reconnectAttemptRef.current = attempt + 1; reconnectTimerRef.current = setTimeout(() => { reconnectTimerRef.current = null; connectSocket() }, delay) }
  }, [])

  useEffect(() => {
    stoppedRef.current = false
    connectSocket()
    return () => { stoppedRef.current = true; if (reconnectTimerRef.current) clearTimeout(reconnectTimerRef.current); const socket = socketRef.current; socketRef.current = null; if (socket) { socket.onopen = null; socket.onmessage = null; socket.onerror = null; socket.onclose = null; socket.close() } }
  }, [connectSocket])

  useEffect(() => {
    const checkHealth = async () => { try { const response = await fetch(`${API_BASE_URL}/health`, { cache: "no-store" }); setApiHealthy(response.ok) } catch { setApiHealthy(false) } }
    checkHealth()
    const timer = window.setInterval(checkHealth, 15000)
    return () => window.clearInterval(timer)
  }, [])

  useEffect(() => { requestAnimationFrame(() => messagesEndRef.current?.scrollIntoView({ behavior: "smooth", block: "end" })) }, [messages, loading])
  useEffect(() => { const textarea = textareaRef.current; if (!textarea) return; textarea.style.height = "auto"; textarea.style.height = `${Math.min(textarea.scrollHeight, 180)}px` }, [input])
  const lastAssistant = useMemo(() => [...messages].reverse().find(message => message.role === "assistant"), [messages])

  async function sendMessage() {
    const message = input.trim()
    if (!message || loading) return
    setEvents([])
    setExecutionOpen(true)
    setMessages(previous => [...previous, { id: crypto.randomUUID(), role: "user", content: message, createdAt: Date.now() }])
    setInput("")
    setLoading(true)
    try {
      const response = await fetch(`${API_BASE_URL}/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message, repository: selectedRepository || null }),
      })
      if (!response.ok) throw new Error(`FRIDAY backend returned ${response.status}`)
      const data = await response.json()
      if (typeof data.repository === "string" && data.repository) setSelectedRepository(data.repository)
      setMessages(previous => [...previous, { id: crypto.randomUUID(), role: "assistant", content: data.response || "FRIDAY did not return a response.", createdAt: Date.now() }])
      setApiHealthy(true)
    } catch (error) {
      console.error("[FRIDAY] Request failed:", error)
      setApiHealthy(false)
      setMessages(previous => [...previous, { id: crypto.randomUUID(), role: "assistant", content: "### Connection error\n\nI couldn't reach **FRIDAY Core**. Make sure the backend is running on `127.0.0.1:8000` and try again.", createdAt: Date.now() }])
    } finally { setLoading(false); window.setTimeout(() => textareaRef.current?.focus(), 0) }
  }

  async function copyMessage(message: Message) { try { await navigator.clipboard.writeText(message.content); setCopiedMessage(message.id); window.setTimeout(() => setCopiedMessage(null), 1400) } catch { console.warn("[FRIDAY] Clipboard unavailable") } }
  function clearConversation() { setMessages([]); setEvents([]); setInput(""); setSidebarOpen(false) }
  function handleKeyDown(event: React.KeyboardEvent<HTMLTextAreaElement>) { if (event.key === "Enter" && !event.shiftKey) { event.preventDefault(); sendMessage() } }

  return (
    <main className="min-h-screen bg-[#050608] text-white selection:bg-blue-500/30">
      <div className="pointer-events-none fixed inset-0 bg-[radial-gradient(circle_at_50%_-10%,rgba(37,99,235,.12),transparent_38%)]" />
      <header className="sticky top-0 z-40 h-16 border-b border-white/[0.07] bg-[#050608]/85 backdrop-blur-2xl">
        <div className="mx-auto flex h-full max-w-5xl items-center gap-3 px-4 sm:px-6">
          <button type="button" onClick={() => setSidebarOpen(true)} aria-label="Open menu" className="mr-1 rounded-lg p-2 text-white/30 transition hover:bg-white/[0.05] hover:text-white/70 sm:hidden"><Bot size={17} /></button>
          <div className="flex items-center gap-3"><div className="relative flex h-8 w-8 items-center justify-center rounded-xl border border-blue-500/20 bg-blue-500/10"><div className="h-2 w-2 rounded-full bg-blue-400 shadow-[0_0_18px_rgba(59,130,246,.9)]" /></div><div><div className="text-[13px] font-semibold tracking-[0.16em]">FRIDAY</div><div className="hidden text-[9px] tracking-wide text-white/25 sm:block">PERSONAL AI OPERATING ASSISTANT</div></div></div>
          <div className="ml-auto flex items-center gap-2 sm:gap-4">
            <div className="flex items-center gap-1.5 rounded-full border border-white/[0.06] bg-white/[0.02] px-2.5 py-1.5">{apiHealthy === false ? <AlertCircle size={11} className="text-red-400" /> : <ShieldCheck size={11} className={apiHealthy ? "text-emerald-400" : "text-white/25"} />}<span className="hidden text-[9px] uppercase tracking-wider text-white/30 sm:block">Core</span><span className={cn("h-1.5 w-1.5 rounded-full", apiHealthy === false ? "bg-red-400" : apiHealthy ? "bg-emerald-400" : "bg-white/20")} /></div>
            <div className="flex items-center gap-1.5 text-[9px] text-white/25">{socketConnected ? <Wifi size={11} className="text-blue-400/80" /> : <WifiOff size={11} />}<span className="hidden sm:block">{socketStatus}</span></div>
            <button type="button" onClick={clearConversation} title="New conversation" className="rounded-lg border border-white/[0.06] p-2 text-white/30 transition hover:bg-white/[0.05] hover:text-white/70"><Plus size={15} /></button>
          </div>
        </div>
      </header>

      <section className="relative mx-auto flex min-h-[calc(100vh-4rem)] max-w-5xl flex-col px-4 sm:px-6">
        <div className="mx-auto flex w-full max-w-3xl flex-1 flex-col">
          {messages.length === 0 ? (
            <div className="flex flex-1 flex-col items-center justify-center pb-36 pt-20 text-center">
              <div className="relative mb-8"><div className="absolute -inset-8 rounded-full bg-blue-500/10 blur-3xl" /><div className="relative flex h-16 w-16 items-center justify-center rounded-2xl border border-white/10 bg-white/[0.035] shadow-2xl shadow-black/30"><Sparkles size={24} className="text-blue-400" /></div></div>
              <p className="mb-2 text-[10px] font-medium uppercase tracking-[0.25em] text-blue-400/60">FRIDAY / READY</p>
              <h1 className="text-3xl font-semibold tracking-[-0.03em] text-white sm:text-4xl">What are we building?</h1>
              <p className="mt-4 max-w-lg text-sm leading-6 text-white/30">Ask FRIDAY to reason through a problem, write code, inspect your project, or orchestrate a task.</p>
              <div className="mt-8 w-full max-w-2xl text-left">
                <div className="mb-2 flex items-center justify-between"><div className="text-[9px] font-medium uppercase tracking-[0.2em] text-white/25">GitHub workspace</div>{repositoryLoading ? <span className="text-[9px] text-white/20">Loading repositories…</span> : <span className="text-[9px] text-white/20">{repositories.length} available</span>}</div>
                <div className="relative">
                  <select value={selectedRepository} onChange={event => chooseRepository(event.target.value)} disabled={repositoryLoading || repositories.length === 0} className="w-full appearance-none rounded-xl border border-white/[0.08] bg-white/[0.025] px-4 py-3 pr-10 text-sm text-white/75 outline-none transition hover:border-white/15 focus:border-blue-500/30 disabled:cursor-not-allowed disabled:opacity-50">
                    <option value="" className="bg-[#0b0d11]">No repository selected</option>
                    {repositories.map(repo => <option key={repo.full_name} value={repo.full_name} className="bg-[#0b0d11]">{repo.full_name}{repo.private ? " · private" : ""}</option>)}
                  </select>
                  <ChevronDown size={15} className="pointer-events-none absolute right-4 top-1/2 -translate-y-1/2 text-white/25" />
                </div>
                {repositoryError && <p className="mt-2 text-xs text-red-300/70">{repositoryError}</p>}
                {selectedRepository && <p className="mt-2 text-[10px] text-white/20">Selected repository is sent explicitly with every chat request.</p>}
              </div>
              <div className="mt-8 grid w-full max-w-2xl gap-2 sm:grid-cols-3">{starterPrompts.map(prompt => <button key={prompt.label} type="button" onClick={() => setInput(prompt.text)} className="group rounded-xl border border-white/[0.07] bg-white/[0.018] p-4 text-left transition hover:-translate-y-0.5 hover:border-blue-500/20 hover:bg-blue-500/[0.035]"><div className="mb-3 flex h-7 w-7 items-center justify-center rounded-lg bg-white/[0.045] text-white/40 transition group-hover:bg-blue-500/10 group-hover:text-blue-400"><Zap size={13} /></div><div className="text-[11px] font-medium text-white/55 group-hover:text-white/80">{prompt.label}</div><div className="mt-1 line-clamp-2 text-[10px] leading-4 text-white/20">{prompt.text}</div></button>)}</div>
            </div>
          ) : (
            <div className="space-y-10 pb-44 pt-8">
              {selectedRepository && <div className="sticky top-20 z-10 flex items-center justify-between rounded-xl border border-white/[0.07] bg-[#0a0c10]/90 px-3 py-2 text-[10px] backdrop-blur-xl"><span className="text-white/25">Repository</span><span className="font-mono text-white/55">{selectedRepository}</span></div>}
              {messages.map((message, index) => { const isUser = message.role === "user"; return <article key={message.id} className={cn("group", isUser ? "flex justify-end" : "flex justify-start")}>{isUser ? <div className="max-w-[88%] sm:max-w-[76%]"><div className="rounded-2xl rounded-br-md border border-blue-400/10 bg-blue-600 px-4 py-3 text-[13px] leading-6 text-white shadow-xl shadow-blue-950/20">{message.content}</div><div className="mt-1.5 text-right text-[9px] text-white/15">{formatTime(message.createdAt)}</div></div> : <div className="w-full"><div className="mb-3 flex items-center gap-2"><div className="flex h-6 w-6 items-center justify-center rounded-lg border border-blue-500/15 bg-blue-500/[0.07]"><span className="text-[9px] font-bold text-blue-400">F</span></div><span className="text-[10px] font-medium tracking-[0.14em] text-white/35">FRIDAY</span><span className="text-[9px] text-white/15">{formatTime(message.createdAt)}</span><div className="ml-auto flex items-center gap-1 opacity-0 transition group-hover:opacity-100"><button type="button" onClick={() => copyMessage(message)} className="rounded-md p-1.5 text-white/20 hover:bg-white/[0.04] hover:text-white/60">{copiedMessage === message.id ? <Check size={12} /> : <Clipboard size={12} />}</button>{index === messages.length - 1 && !loading && <button type="button" onClick={() => setInput("Please refine your last answer with more detail.")} className="rounded-md p-1.5 text-white/20 hover:bg-white/[0.04] hover:text-white/60"><RotateCcw size={12} /></button>}</div></div><MarkdownMessage content={message.content} /></div>}</article> })}
              {loading && <div className="flex items-center gap-3"><div className="flex h-6 w-6 items-center justify-center rounded-lg border border-blue-500/15 bg-blue-500/[0.07]"><span className="text-[9px] font-bold text-blue-400">F</span></div><div className="flex items-center gap-2 text-[11px] text-white/30"><span className="flex gap-1"><i className="h-1.5 w-1.5 animate-pulse rounded-full bg-blue-400" /><i className="h-1.5 w-1.5 animate-pulse rounded-full bg-blue-400 [animation-delay:150ms]" /><i className="h-1.5 w-1.5 animate-pulse rounded-full bg-blue-400 [animation-delay:300ms]" /></span>FRIDAY is working</div></div>}
              <div ref={messagesEndRef} />
            </div>
          )}
        </div>
      </section>

      <footer className="fixed bottom-0 left-0 right-0 z-20 bg-gradient-to-t from-[#050608] via-[#050608]/95 to-transparent pt-8">
        <div className="mx-auto max-w-3xl px-4 pb-4 sm:px-6 sm:pb-5">
          <div className="rounded-2xl border border-white/10 bg-[#0b0d11]/95 shadow-2xl shadow-black/50 backdrop-blur-xl transition focus-within:border-blue-500/30 focus-within:shadow-blue-950/10">
            <textarea ref={textareaRef} value={input} onChange={event => setInput(event.target.value)} onKeyDown={handleKeyDown} placeholder={selectedRepository ? `Ask about ${selectedRepository}…` : "Message FRIDAY..."} rows={1} disabled={loading} className="block max-h-[180px] min-h-[56px] w-full resize-none bg-transparent px-4 pb-12 pt-4 pr-14 text-sm leading-6 outline-none placeholder:text-white/20 disabled:opacity-50" />
            <div className="flex items-center justify-between px-4 pb-3"><div className="flex items-center gap-2 text-[9px] text-white/15"><span className="hidden sm:inline">Enter to send</span><span className="hidden sm:inline">·</span><span>Shift + Enter for new line</span></div><button type="button" onClick={sendMessage} disabled={!input.trim() || loading} aria-label="Send message" className="flex h-8 w-8 items-center justify-center rounded-lg bg-blue-600 text-white shadow-lg shadow-blue-950/30 transition hover:bg-blue-500 active:scale-95 disabled:cursor-not-allowed disabled:opacity-20"><Send size={14} /></button></div>
          </div>
          <div className="mt-2 text-center text-[9px] text-white/10">FRIDAY may make mistakes. Verify important information.</div>
        </div>
      </footer>

      <ExecutionPanel events={events} open={executionOpen} setOpen={setExecutionOpen} onClear={() => setEvents([])} />
      {sidebarOpen && <div className="fixed inset-0 z-50 sm:hidden"><button type="button" aria-label="Close menu" onClick={() => setSidebarOpen(false)} className="absolute inset-0 bg-black/70 backdrop-blur-sm" /><div className="relative h-full w-[280px] border-r border-white/10 bg-[#090b0f] p-5 shadow-2xl"><div className="mb-8 flex items-center justify-between"><div className="text-xs font-semibold tracking-[0.18em]">FRIDAY</div><button onClick={() => setSidebarOpen(false)} className="rounded-lg p-2 text-white/30 hover:bg-white/[0.05]"><X size={15} /></button></div><div className="space-y-2"><button onClick={clearConversation} className="flex w-full items-center gap-3 rounded-xl border border-white/[0.06] bg-white/[0.025] px-3 py-3 text-left text-xs text-white/55 hover:bg-white/[0.05]"><Plus size={14} />New conversation</button><div className="mt-6 px-1 text-[9px] uppercase tracking-[0.18em] text-white/20">System</div><div className="mt-2 rounded-xl border border-white/[0.06] bg-white/[0.018] p-3"><div className="flex items-center gap-2 text-[10px] text-white/35"><Activity size={12} />Execution events</div><div className="mt-2 text-[9px] text-white/20">{socketConnected ? "Live event stream connected" : "Event stream offline"}</div></div></div></div></div>}
    </main>
  )
}
