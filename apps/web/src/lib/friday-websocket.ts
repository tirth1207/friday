export type FridaySocketStatus =
  | "connecting"
  | "connected"
  | "reconnecting"
  | "disconnected"
  | "error"

export type FridayWebSocketOptions = {
  url: string
  onMessage?: (data: unknown) => void
  onStatusChange?: (status: FridaySocketStatus) => void
  onError?: (error: Event) => void
}

const INITIAL_RECONNECT_DELAY = 1000
const MAX_RECONNECT_DELAY = 15000
const MAX_RECONNECT_ATTEMPTS = Infinity

export class FridayWebSocket {
  private socket: WebSocket | null = null
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null

  private reconnectAttempt = 0
  private intentionalClose = false
  private connecting = false

  private readonly url: string
  private readonly onMessage?: (data: unknown) => void
  private readonly onStatusChange?: (status: FridaySocketStatus) => void
  private readonly onError?: (error: Event) => void

  constructor(options: FridayWebSocketOptions) {
    this.url = options.url
    this.onMessage = options.onMessage
    this.onStatusChange = options.onStatusChange
    this.onError = options.onError
  }

  connect() {
    this.intentionalClose = false

    if (
      this.socket &&
      (
        this.socket.readyState === WebSocket.OPEN ||
        this.socket.readyState === WebSocket.CONNECTING
      )
    ) {
      return
    }

    if (this.connecting) {
      return
    }

    this.connecting = true

    this.setStatus(
      this.reconnectAttempt > 0
        ? "reconnecting"
        : "connecting",
    )

    console.log(
      "[FRIDAY WS] Connecting...",
      this.url,
    )

    let socket: WebSocket

    try {
      socket = new WebSocket(this.url)
    } catch (error) {
      this.connecting = false

      console.error(
        "[FRIDAY WS] Failed to create WebSocket:",
        error,
      )

      this.setStatus("error")
      this.scheduleReconnect()

      return
    }

    this.socket = socket

    socket.onopen = () => {
      this.connecting = false
      this.reconnectAttempt = 0

      console.log(
        "[FRIDAY WS] Connected",
      )

      this.setStatus("connected")
    }

    socket.onmessage = (event) => {
      try {
        const parsed = JSON.parse(event.data)

        this.onMessage?.(parsed)
      } catch {
        // Some websocket servers may send plain text.
        this.onMessage?.(event.data)
      }
    }

    socket.onerror = (event) => {
      console.warn(
        "[FRIDAY WS] Connection error",
        event,
      )

      this.onError?.(event)

      this.setStatus("error")
    }

    socket.onclose = (event) => {
      this.connecting = false

      console.warn(
        "[FRIDAY WS] Closed:",
        {
          code: event.code,
          reason: event.reason,
          wasClean: event.wasClean,
        },
      )

      // Ignore stale socket close events.
      if (this.socket !== socket) {
        return
      }

      this.socket = null

      if (this.intentionalClose) {
        this.setStatus("disconnected")
        return
      }

      this.setStatus("reconnecting")
      this.scheduleReconnect()
    }
  }

  private scheduleReconnect() {
    if (this.intentionalClose) {
      return
    }

    if (this.reconnectTimer) {
      return
    }

    if (
      this.reconnectAttempt >= MAX_RECONNECT_ATTEMPTS
    ) {
      this.setStatus("disconnected")
      return
    }

    const exponent = Math.min(
      this.reconnectAttempt,
      4,
    )

    const delay = Math.min(
      INITIAL_RECONNECT_DELAY * 2 ** exponent,
      MAX_RECONNECT_DELAY,
    )

    const jitter = Math.round(
      Math.random() * 300,
    )

    const totalDelay = delay + jitter

    this.reconnectAttempt += 1

    console.log(
      `[FRIDAY WS] Reconnecting in ${totalDelay}ms ` +
      `(attempt ${this.reconnectAttempt})`,
    )

    this.reconnectTimer = setTimeout(() => {
      this.reconnectTimer = null

      if (!this.intentionalClose) {
        this.connect()
      }
    }, totalDelay)
  }

  send(data: unknown): boolean {
    if (
      !this.socket ||
      this.socket.readyState !== WebSocket.OPEN
    ) {
      console.warn(
        "[FRIDAY WS] Cannot send: socket is not connected",
      )

      return false
    }

    try {
      this.socket.send(
        typeof data === "string"
          ? data
          : JSON.stringify(data),
      )

      return true
    } catch (error) {
      console.error(
        "[FRIDAY WS] Send failed:",
        error,
      )

      return false
    }
  }

  close() {
    this.intentionalClose = true
    this.connecting = false

    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer)
      this.reconnectTimer = null
    }

    const socket = this.socket
    this.socket = null

    if (!socket) {
      this.setStatus("disconnected")
      return
    }

    try {
      socket.close(
        1000,
        "FRIDAY client closed connection",
      )
    } catch {
      // Socket may already be closed.
    }

    this.setStatus("disconnected")
  }

  reconnect() {
    this.close()

    this.intentionalClose = false
    this.reconnectAttempt = 0

    this.connect()
  }

  isConnected() {
    return (
      this.socket?.readyState ===
      WebSocket.OPEN
    )
  }

  private setStatus(
    status: FridaySocketStatus,
  ) {
    this.onStatusChange?.(status)
  }
}
