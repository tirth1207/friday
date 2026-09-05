"use client"

import { useEffect, useRef, useState } from "react"
import ReactMarkdown from "react-markdown"
import remarkGfm from "remark-gfm"

// ============================================================
// TYPES
// ============================================================

type Message = {
  id: string
  role: "user" | "assistant"
  content: string
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

// ============================================================
// CONFIG
// ============================================================

const API_BASE_URL = "http://127.0.0.1:8000"
const WS_URL = "ws://127.0.0.1:8000/ws"

// ============================================================
// CODE BLOCK
// ============================================================

function CodeBlock({
  language,
  code,
}: {
  language: string
  code: string
}) {
  const [copied, setCopied] = useState(false)

  async function copyCode() {
    try {
      await navigator.clipboard.writeText(code)

      setCopied(true)

      setTimeout(() => {
        setCopied(false)
      }, 1500)
    } catch {
      console.warn("[FRIDAY] Clipboard unavailable")
    }
  }

  return (
    <div className="my-5 overflow-hidden rounded-xl border border-white/10 bg-[#080808]">
      <div className="flex items-center justify-between border-b border-white/10 bg-white/[0.025] px-3 py-2">
        <span className="text-[11px] uppercase tracking-wider text-white/35">
          {language}
        </span>

        <button
          onClick={copyCode}
          className="text-[11px] text-white/35 transition hover:text-white"
        >
          {copied ? "Copied" : "Copy"}
        </button>
      </div>

      <pre className="overflow-x-auto p-4">
        <code className="font-mono text-[13px] leading-6 text-white/80">
          {code}
        </code>
      </pre>
    </div>
  )
}

// ============================================================
// MARKDOWN
// ============================================================

function MarkdownMessage({
  content,
}: {
  content: string
}) {
  return (
    <div className="friday-markdown">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          h1: ({ children }) => (
            <h1 className="mt-6 mb-3 text-2xl font-semibold tracking-tight first:mt-0">
              {children}
            </h1>
          ),

          h2: ({ children }) => (
            <h2 className="mt-6 mb-3 text-xl font-semibold tracking-tight first:mt-0">
              {children}
            </h2>
          ),

          h3: ({ children }) => (
            <h3 className="mt-5 mb-2 text-base font-semibold">
              {children}
            </h3>
          ),

          p: ({ children }) => (
            <p className="mb-4 text-[14px] leading-7 text-white/85 last:mb-0">
              {children}
            </p>
          ),

          ul: ({ children }) => (
            <ul className="mb-4 list-disc space-y-2 pl-5 text-[14px] text-white/80">
              {children}
            </ul>
          ),

          ol: ({ children }) => (
            <ol className="mb-4 list-decimal space-y-2 pl-5 text-[14px] text-white/80">
              {children}
            </ol>
          ),

          li: ({ children }) => (
            <li className="pl-1 leading-6">
              {children}
            </li>
          ),

          strong: ({ children }) => (
            <strong className="font-semibold text-white">
              {children}
            </strong>
          ),

          em: ({ children }) => (
            <em className="text-white/70">
              {children}
            </em>
          ),

          blockquote: ({ children }) => (
            <blockquote className="my-4 border-l-2 border-blue-500/60 pl-4 italic text-white/55">
              {children}
            </blockquote>
          ),

          a: ({ href, children }) => (
            <a
              href={href}
              target="_blank"
              rel="noopener noreferrer"
              className="text-blue-400 underline decoration-blue-400/30 underline-offset-4 transition hover:text-blue-300"
            >
              {children}
            </a>
          ),

          hr: () => (
            <hr className="my-6 border-white/10" />
          ),

          table: ({ children }) => (
            <div className="my-5 overflow-x-auto rounded-xl border border-white/10">
              <table className="w-full text-sm">
                {children}
              </table>
            </div>
          ),

          thead: ({ children }) => (
            <thead className="bg-white/[0.04]">
              {children}
            </thead>
          ),

          th: ({ children }) => (
            <th className="border-b border-white/10 px-4 py-3 text-left font-medium text-white">
              {children}
            </th>
          ),

          td: ({ children }) => (
            <td className="border-b border-white/[0.06] px-4 py-3 text-white/70">
              {children}
            </td>
          ),

          code: ({ className, children }) => {
            const isBlock = Boolean(className)

            if (!isBlock) {
              return (
                <code className="rounded-md border border-white/10 bg-white/[0.08] px-1.5 py-0.5 text-[13px] text-blue-300">
                  {children}
                </code>
              )
            }

            const language =
              className?.replace("language-", "") || "code"

            const code = String(children).replace(/\n$/, "")

            return (
              <CodeBlock
                language={language}
                code={code}
              />
            )
          },
        }}
      >
        {content}
      </ReactMarkdown>
    </div>
  )
}

// ============================================================
// THINKING INDICATOR
// ============================================================

function ThinkingIndicator() {
  return (
    <div className="flex items-center gap-3">
      <div className="flex items-center gap-1">
        <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-blue-400" />

        <span
          className="h-1.5 w-1.5 animate-pulse rounded-full bg-blue-400"
          style={{
            animationDelay: "150ms",
          }}
        />

        <span
          className="h-1.5 w-1.5 animate-pulse rounded-full bg-blue-400"
          style={{
            animationDelay: "300ms",
          }}
        />
      </div>

      <span className="text-xs text-white/35">
        FRIDAY is working
      </span>
    </div>
  )
}

// ============================================================
// EVENT STATUS ICON
// ============================================================

function EventStatusIcon({
  event,
}: {
  event: FridayEvent
}) {
  if (
    event.status === "completed" ||
    event.status === "success"
  ) {
    return (
      <div className="flex h-5 w-5 items-center justify-center rounded-full bg-blue-500/10 text-[11px] text-blue-400">
        ✓
      </div>
    )
  }

  if (
    event.status === "failed" ||
    event.type === "tool_error" ||
    event.type === "error"
  ) {
    return (
      <div className="flex h-5 w-5 items-center justify-center rounded-full bg-red-500/10 text-[11px] text-red-400">
        ×
      </div>
    )
  }

  if (
    event.status === "running" ||
    event.type === "thinking" ||
    event.type === "planning"
  ) {
    return (
      <div className="flex h-5 w-5 items-center justify-center">
        <div className="h-2 w-2 animate-pulse rounded-full bg-blue-400 shadow-[0_0_10px_rgba(59,130,246,0.8)]" />
      </div>
    )
  }

  return (
    <div className="flex h-5 w-5 items-center justify-center text-white/20">
      ○
    </div>
  )
}

// ============================================================
// EVENT TYPE LABEL
// ============================================================

function getEventLabel(event: FridayEvent) {
  switch (event.type) {
    case "thinking":
      return "THINKING"

    case "planning":
      return "PLANNING"

    case "agent_created":
    case "agent_started":
    case "agent_completed":
      return "AGENT"

    case "tool_started":
    case "tool_completed":
      return "TOOL"

    case "tool_error":
      return "TOOL ERROR"

    case "verification":
      return "VERIFY"

    case "message":
      return "SYSTEM"

    case "error":
      return "ERROR"

    default:
      return "EVENT"
  }
}

// ============================================================
// EXECUTION EVENT
// ============================================================

function ExecutionEvent({
  event,
}: {
  event: FridayEvent
}) {
  const [expanded, setExpanded] = useState(false)

  const hasDetails =
    Boolean(event.description) ||
    Boolean(event.tool) ||
    Boolean(event.agent) ||
    Boolean(
      event.metadata &&
        Object.keys(event.metadata).length > 0
    )

  return (
    <div className="group">
      <button
        onClick={() => {
          if (hasDetails) {
            setExpanded((value) => !value)
          }
        }}
        className="flex w-full items-start gap-3 rounded-xl px-2 py-2 text-left transition hover:bg-white/[0.025]"
      >
        <div className="mt-0.5 shrink-0">
          <EventStatusIcon event={event} />
        </div>

        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-[13px] font-medium text-white/80">
              {event.title}
            </span>

            <span className="text-[9px] uppercase tracking-wider text-white/20">
              {getEventLabel(event)}
            </span>
          </div>

          {event.agent && (
            <div className="mt-1 flex items-center gap-2">
              <span className="text-[11px] text-blue-400/70">
                {event.agent}
              </span>

              {event.tool && (
                <>
                  <span className="text-white/15">
                    →
                  </span>

                  <span className="font-mono text-[10px] text-white/35">
                    {event.tool}
                  </span>
                </>
              )}
            </div>
          )}

          {event.description && !expanded && (
            <div className="mt-1 truncate text-[11px] text-white/30">
              {event.description}
            </div>
          )}
        </div>

        {hasDetails && (
          <span className="mt-1 text-[10px] text-white/15 transition group-hover:text-white/35">
            {expanded ? "⌃" : "⌄"}
          </span>
        )}
      </button>

      {expanded && (
        <div className="ml-10 mb-2 rounded-lg border border-white/[0.06] bg-white/[0.02] px-3 py-2">
          {event.description && (
            <div className="mb-2">
              <div className="mb-1 text-[9px] uppercase tracking-wider text-white/20">
                Description
              </div>

              <div className="text-[11px] leading-5 text-white/45">
                {event.description}
              </div>
            </div>
          )}

          {event.tool && (
            <div className="mb-2">
              <div className="mb-1 text-[9px] uppercase tracking-wider text-white/20">
                Tool
              </div>

              <code className="font-mono text-[11px] text-blue-300/70">
                {event.tool}
              </code>
            </div>
          )}

          {event.agent && (
            <div className="mb-2">
              <div className="mb-1 text-[9px] uppercase tracking-wider text-white/20">
                Agent
              </div>

              <span className="text-[11px] text-blue-300/70">
                {event.agent}
              </span>
            </div>
          )}

          {event.status && (
            <div className="mb-2">
              <div className="mb-1 text-[9px] uppercase tracking-wider text-white/20">
                Status
              </div>

              <span className="text-[11px] text-white/45">
                {event.status}
              </span>
            </div>
          )}

          {event.metadata &&
            Object.keys(event.metadata).length > 0 && (
              <div>
                <div className="mb-1 text-[9px] uppercase tracking-wider text-white/20">
                  Result
                </div>

                <pre className="overflow-x-auto whitespace-pre-wrap font-mono text-[10px] leading-5 text-white/35">
                  {JSON.stringify(
                    event.metadata,
                    null,
                    2
                  )}
                </pre>
              </div>
            )}
        </div>
      )}
    </div>
  )
}

// ============================================================
// EXECUTION PANEL
// ============================================================

function ExecutionPanel({
  events,
  open,
  setOpen,
}: {
  events: FridayEvent[]
  open: boolean
  setOpen: (value: boolean) => void
}) {
  if (events.length === 0) {
    return null
  }

  const completed = events.filter(
    (event) =>
      event.status === "completed" ||
      event.status === "success"
  ).length

  const running = events.filter(
    (event) =>
      event.status === "running"
  ).length

  const failed = events.filter(
    (event) =>
      event.status === "failed" ||
      event.type === "tool_error" ||
      event.type === "error"
  ).length

  return (
    <div className="mb-8 overflow-hidden rounded-2xl border border-white/10 bg-white/[0.025]">
      <button
        onClick={() => setOpen(!open)}
        className="flex w-full items-center justify-between px-4 py-3 transition hover:bg-white/[0.025]"
      >
        <div className="flex items-center gap-3">
          <div className="relative flex h-7 w-7 items-center justify-center rounded-lg border border-blue-500/20 bg-blue-500/10">
            <span className="text-xs text-blue-400">
              ✦
            </span>

            {running > 0 && (
              <span className="absolute -right-0.5 -top-0.5 h-1.5 w-1.5 animate-pulse rounded-full bg-blue-400" />
            )}
          </div>

          <div className="text-left">
            <div className="text-[13px] font-medium text-white/80">
              Execution
            </div>

            <div className="mt-0.5 flex items-center gap-2 text-[10px] text-white/25">
              <span>
                {events.length} events
              </span>

              {completed > 0 && (
                <>
                  <span>·</span>
                  <span className="text-blue-400/60">
                    {completed} completed
                  </span>
                </>
              )}

              {running > 0 && (
                <>
                  <span>·</span>
                  <span className="text-blue-400">
                    {running} running
                  </span>
                </>
              )}

              {failed > 0 && (
                <>
                  <span>·</span>
                  <span className="text-red-400">
                    {failed} failed
                  </span>
                </>
              )}
            </div>
          </div>
        </div>

        <span className="text-xs text-white/25">
          {open ? "⌃" : "⌄"}
        </span>
      </button>

      {open && (
        <div className="border-t border-white/10 px-3 py-3">
          <div className="space-y-0.5">
            {events.map((event) => (
              <ExecutionEvent
                key={event.id}
                event={event}
              />
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

// ============================================================
// APP
// ============================================================

export default function App() {
  const [messages, setMessages] =
    useState<Message[]>([])

  const [input, setInput] =
    useState("")

  const [loading, setLoading] =
    useState(false)

  const [events, setEvents] =
    useState<FridayEvent[]>([])

  const [executionOpen, setExecutionOpen] =
    useState(true)

  const [socketConnected, setSocketConnected] =
    useState(false)

  const [socketStatus, setSocketStatus] =
    useState("Connecting")

  const socketRef =
    useRef<WebSocket | null>(null)

  const reconnectTimerRef =
    useRef<ReturnType<typeof setTimeout> | null>(null)

  const reconnectAttemptRef =
    useRef(0)

  const stoppedRef =
    useRef(false)

  const chatContainerRef =
    useRef<HTMLDivElement>(null)

  const messagesEndRef =
    useRef<HTMLDivElement>(null)

  const textareaRef =
    useRef<HTMLTextAreaElement>(null)

  // ==========================================================
  // WEBSOCKET
  // ==========================================================

  useEffect(() => {
    stoppedRef.current = false

    const connect = () => {
      if (stoppedRef.current) {
        return
      }

      const existingSocket =
        socketRef.current

      if (
        existingSocket &&
        (
          existingSocket.readyState ===
            WebSocket.OPEN ||
          existingSocket.readyState ===
            WebSocket.CONNECTING
        )
      ) {
        return
      }

      setSocketStatus("Connecting")

      console.log(
        "[FRIDAY] Connecting execution WebSocket:",
        WS_URL
      )

      let socket: WebSocket

      try {
        socket = new WebSocket(WS_URL)
      } catch (error) {
        console.error(
          "[FRIDAY] Could not create WebSocket:",
          error
        )

        setSocketConnected(false)
        setSocketStatus("Offline")

        scheduleReconnect()

        return
      }

      socketRef.current = socket

      socket.onopen = () => {
        if (stoppedRef.current) {
          socket.close()
          return
        }

        reconnectAttemptRef.current = 0

        setSocketConnected(true)
        setSocketStatus("Connected")

        console.log(
          "[FRIDAY] Execution WebSocket connected"
        )
      }

      socket.onmessage = (event) => {
        try {
          const data =
            JSON.parse(event.data) as FridayEvent

          console.log(
            "[FRIDAY EVENT]",
            data
          )

          setEvents((previous) => {
            // Prevent duplicate events.
            if (
              previous.some(
                (item) => item.id === data.id
              )
            ) {
              return previous
            }

            return [
              ...previous,
              data,
            ]
          })
        } catch (error) {
          console.error(
            "[FRIDAY] Failed to parse execution event:",
            error
          )
        }
      }

      socket.onerror = () => {
        // Browser intentionally gives very little
        // information in a WebSocket error event.
        //
        // Do NOT print the raw Event because it becomes:
        // [object Event]
        console.warn(
          "[FRIDAY] Execution WebSocket connection error"
        )

        setSocketConnected(false)
        setSocketStatus("Connection error")
      }

      socket.onclose = (event) => {
        setSocketConnected(false)

        if (stoppedRef.current) {
          setSocketStatus("Offline")
          return
        }

        setSocketStatus("Disconnected")

        console.warn(
          "[FRIDAY] Execution WebSocket closed:",
          {
            code: event.code,
            reason:
              event.reason || "No reason provided",
            wasClean: event.wasClean,
          }
        )

        scheduleReconnect()
      }
    }

    const scheduleReconnect = () => {
      if (stoppedRef.current) {
        return
      }

      if (
        reconnectTimerRef.current
      ) {
        return
      }

      const attempt =
        reconnectAttemptRef.current

      const delay = Math.min(
        1000 * Math.pow(2, attempt),
        10000
      )

      reconnectAttemptRef.current =
        attempt + 1

      console.log(
        `[FRIDAY] Reconnecting WebSocket in ${delay}ms`
      )

      reconnectTimerRef.current =
        setTimeout(() => {
          reconnectTimerRef.current = null
          connect()
        }, delay)
    }

    connect()

    return () => {
      stoppedRef.current = true

      if (
        reconnectTimerRef.current
      ) {
        clearTimeout(
          reconnectTimerRef.current
        )

        reconnectTimerRef.current = null
      }

      const socket =
        socketRef.current

      socketRef.current = null

      if (socket) {
        socket.onopen = null
        socket.onmessage = null
        socket.onerror = null
        socket.onclose = null

        if (
          socket.readyState ===
            WebSocket.OPEN ||
          socket.readyState ===
            WebSocket.CONNECTING
        ) {
          socket.close()
        }
      }

      setSocketConnected(false)
      setSocketStatus("Offline")
    }
  }, [])

  // ==========================================================
  // AUTO SCROLL
  // ==========================================================

  useEffect(() => {
    requestAnimationFrame(() => {
      messagesEndRef.current?.scrollIntoView({
        behavior: "smooth",
        block: "end",
      })
    })
  }, [
    messages,
    loading,
    events,
  ])

  // ==========================================================
  // AUTO GROW TEXTAREA
  // ==========================================================

  useEffect(() => {
    const textarea =
      textareaRef.current

    if (!textarea) {
      return
    }

    textarea.style.height = "auto"

    textarea.style.height =
      `${Math.min(
        textarea.scrollHeight,
        180
      )}px`
  }, [input])

  // ==========================================================
  // SEND MESSAGE
  // ==========================================================

  async function sendMessage() {
    const message =
      input.trim()

    if (
      !message ||
      loading
    ) {
      return
    }

    // Clear previous execution trace.
    setEvents([])
    setExecutionOpen(true)

    // Add user message immediately.
    setMessages((previous) => [
      ...previous,
      {
        id: crypto.randomUUID(),
        role: "user",
        content: message,
      },
    ])

    setInput("")
    setLoading(true)

    try {
      const response =
        await fetch(
          `${API_BASE_URL}/chat`,
          {
            method: "POST",

            headers: {
              "Content-Type":
                "application/json",
            },

            body: JSON.stringify({
              message,
            }),
          }
        )

      if (!response.ok) {
        throw new Error(
          `FRIDAY backend returned ${response.status}`
        )
      }

      const data =
        await response.json()

      setMessages((previous) => [
        ...previous,
        {
          id: crypto.randomUUID(),
          role: "assistant",
          content:
            data.response ||
            "FRIDAY did not return a response.",
        },
      ])
    } catch (error) {
      console.error(
        "[FRIDAY] Request failed:",
        error
      )

      setMessages((previous) => [
        ...previous,
        {
          id: crypto.randomUUID(),
          role: "assistant",
          content:
            "### Connection error\n\nI couldn't connect to **FRIDAY Core**. Make sure the backend is running on `127.0.0.1:8000`.",
        },
      ])
    } finally {
      setLoading(false)

      setTimeout(() => {
        textareaRef.current?.focus()
      }, 0)
    }
  }

  // ==========================================================
  // KEYBOARD
  // ==========================================================

  function handleKeyDown(
    event: React.KeyboardEvent<HTMLTextAreaElement>
  ) {
    if (
      event.key === "Enter" &&
      !event.shiftKey
    ) {
      event.preventDefault()

      sendMessage()
    }
  }

  // ==========================================================
  // UI
  // ==========================================================

  return (
    <main className="flex h-screen flex-col overflow-hidden bg-black text-white">

      {/* ====================================================
          HEADER
      ==================================================== */}

      <header className="h-16 shrink-0 border-b border-white/[0.08]">
        <div className="mx-auto flex h-full max-w-4xl items-center px-5">

          <div className="flex items-center gap-3">

            <div className="relative flex h-8 w-8 items-center justify-center rounded-lg border border-white/10 bg-white/[0.04]">
              <div className="h-2 w-2 rounded-full bg-blue-500 shadow-[0_0_16px_rgba(59,130,246,0.9)]" />
            </div>

            <div>
              <div className="text-sm font-semibold tracking-wide">
                FRIDAY
              </div>

              <div className="text-[10px] text-white/30">
                Personal AI Operating Assistant
              </div>
            </div>

          </div>

          <div className="ml-auto flex items-center gap-3">

            {/* WebSocket status */}

            <div className="flex items-center gap-1.5">
              <span
                className={`h-1.5 w-1.5 rounded-full ${
                  socketConnected
                    ? "bg-emerald-400"
                    : "bg-red-400"
                }`}
              />

              <span className="text-[10px] text-white/25">
                {socketStatus}
              </span>
            </div>

            {/* Assistant status */}

            <div className="h-3 w-px bg-white/10" />

            <div className="flex items-center gap-2">

              <span
                className={`h-1.5 w-1.5 rounded-full ${
                  loading
                    ? "animate-pulse bg-blue-400"
                    : "bg-emerald-400"
                }`}
              />

              <span className="text-[11px] text-white/35">
                {loading
                  ? "Working"
                  : "Online"}
              </span>

            </div>

          </div>

        </div>
      </header>

      {/* ====================================================
          CHAT
      ==================================================== */}

      <section
        ref={chatContainerRef}
        className="min-h-0 flex-1 overflow-y-auto overscroll-contain"
      >

        <div className="mx-auto max-w-3xl px-5 py-10">

          {/* EMPTY STATE */}

          {messages.length === 0 ? (

            <div className="flex min-h-[calc(100vh-10rem)] flex-col items-center justify-center text-center">

              <div className="relative mb-7">

                <div className="absolute inset-0 rounded-3xl bg-blue-500/10 blur-2xl" />

                <div className="relative flex h-16 w-16 items-center justify-center rounded-2xl border border-white/10 bg-white/[0.04]">

                  <span className="text-xl font-semibold text-blue-400">
                    F
                  </span>

                </div>

              </div>

              <h1 className="text-3xl font-semibold tracking-tight">
                How can I help?
              </h1>

              <p className="mt-3 max-w-md text-sm leading-6 text-white/35">
                Ask FRIDAY to explain something,
                write code, analyze a project,
                or eventually control your machine.
              </p>

              {!socketConnected && (
                <div className="mt-6 rounded-xl border border-red-500/10 bg-red-500/[0.04] px-4 py-3 text-[11px] text-red-300/60">
                  Execution events are currently offline.
                  <br />
                  Make sure FRIDAY Core is running.
                </div>
              )}

            </div>

          ) : (

            <div className="space-y-9">

              {/* =================================================
                  MESSAGES
              ================================================= */}

              {messages.map((message) => {

                const isUser =
                  message.role === "user"

                return (
                  <div
                    key={message.id}
                    className={`flex ${
                      isUser
                        ? "justify-end"
                        : "justify-start"
                    }`}
                  >

                    {isUser ? (

                      <div className="max-w-[78%] rounded-2xl rounded-br-md bg-blue-600 px-4 py-3 text-[14px] leading-6 text-white shadow-lg shadow-blue-950/20">
                        {message.content}
                      </div>

                    ) : (

                      <div className="w-full">

                        {/* FRIDAY LABEL */}

                        <div className="mb-3 flex items-center gap-2">

                          <div className="flex h-5 w-5 items-center justify-center rounded-md border border-white/10 bg-white/[0.04]">

                            <span className="text-[9px] font-semibold text-blue-400">
                              F
                            </span>

                          </div>

                          <span className="text-[11px] font-medium text-white/40">
                            FRIDAY
                          </span>

                        </div>

                        <MarkdownMessage
                          content={
                            message.content
                          }
                        />

                      </div>
                    )}

                  </div>
                )
              })}

              {/* =================================================
                  EXECUTION PANEL
              ================================================= */}

              {events.length > 0 && (
                <ExecutionPanel
                  events={events}
                  open={executionOpen}
                  setOpen={
                    setExecutionOpen
                  }
                />
              )}

              {/* =================================================
                  THINKING
              ================================================= */}

              {loading && (
                <div className="flex items-center gap-2">

                  <div className="flex h-5 w-5 items-center justify-center rounded-md border border-white/10 bg-white/[0.04]">

                    <span className="text-[9px] font-semibold text-blue-400">
                      F
                    </span>

                  </div>

                  <ThinkingIndicator />

                </div>
              )}

              {/* =================================================
                  SCROLL TARGET
              ================================================= */}

              <div
                ref={messagesEndRef}
                className="h-px"
              />

            </div>
          )}

        </div>
      </section>

      {/* ====================================================
          FIXED BOTTOM COMPOSER
      ==================================================== */}

      <footer className="shrink-0 bg-black/95 backdrop-blur-xl">

        <div className="mx-auto max-w-3xl px-5 pb-5 pt-3">

          <div className="relative rounded-2xl border border-white/10 bg-white/[0.035] shadow-2xl shadow-black/40 transition-all focus-within:border-blue-500/40 focus-within:bg-white/[0.045]">

            <textarea
              ref={textareaRef}
              value={input}
              onChange={(event) =>
                setInput(
                  event.target.value
                )
              }
              onKeyDown={handleKeyDown}
              placeholder="Message FRIDAY..."
              rows={1}
              disabled={loading}
              className="block max-h-[180px] w-full resize-none bg-transparent px-4 pb-12 pt-4 pr-14 text-sm leading-6 outline-none placeholder:text-white/25 disabled:opacity-50"
            />

            <button
              onClick={sendMessage}
              disabled={
                !input.trim() ||
                loading
              }
              aria-label="Send message"
              className="absolute bottom-3 right-3 flex h-8 w-8 items-center justify-center rounded-lg bg-blue-600 text-sm text-white transition-all hover:bg-blue-500 active:scale-95 disabled:cursor-not-allowed disabled:opacity-20"
            >
              ↑
            </button>

            <div className="absolute bottom-3 left-4 text-[10px] text-white/20">
              Enter to send · Shift + Enter for new line
            </div>

          </div>

          <p className="mt-3 text-center text-[10px] text-white/15">
            FRIDAY can make mistakes. Verify important information.
          </p>

        </div>
      </footer>

    </main>
  )
}