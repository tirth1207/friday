"use client"

import { useEffect, useState } from "react"

const API_BASE_URL = process.env.NEXT_PUBLIC_FRIDAY_API_URL || "http://127.0.0.1:8000"

type Status = {
  configured: boolean
  connected: boolean
  login?: string
}

export default function GitHubConnectionPage() {
  const [status, setStatus] = useState<Status | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    fetch(`${API_BASE_URL}/auth/github/status`)
      .then(response => response.json())
      .then(setStatus)
      .catch(() => setStatus({ configured: false, connected: false }))
      .finally(() => setLoading(false))
  }, [])

  const disconnect = async () => {
    await fetch(`${API_BASE_URL}/auth/github/disconnect`, { method: "POST" })
    setStatus({ configured: status?.configured ?? true, connected: false })
  }

  if (loading) return <main className="min-h-screen bg-[#07090d] p-10 text-white/60">Checking GitHub connection…</main>

  return (
    <main className="min-h-screen bg-[#07090d] px-6 py-16 text-white">
      <div className="mx-auto max-w-xl">
        <div className="mb-10">
          <p className="mb-3 text-xs uppercase tracking-[0.25em] text-blue-400/70">FRIDAY / Integrations</p>
          <h1 className="text-4xl font-semibold tracking-tight">GitHub</h1>
          <p className="mt-4 leading-7 text-white/45">
            Connect FRIDAY to your GitHub account so the GitHub Agent can inspect repositories you are authorized to access.
          </p>
        </div>

        <section className="rounded-2xl border border-white/10 bg-white/[0.03] p-6 shadow-2xl shadow-black/20">
          {!status?.configured ? (
            <>
              <div className="text-sm font-medium text-amber-300">GitHub App OAuth is not configured</div>
              <p className="mt-2 text-sm leading-6 text-white/45">
                Add the GitHub App environment variables to FRIDAY's backend `.env`, then restart the API.
              </p>
            </>
          ) : status.connected ? (
            <>
              <div className="flex items-center gap-3">
                <span className="h-2.5 w-2.5 rounded-full bg-emerald-400 shadow-[0_0_12px_rgba(52,211,153,.7)]" />
                <span className="font-medium text-white/85">Connected</span>
              </div>
              <p className="mt-3 text-sm text-white/45">GitHub account: <span className="text-white/75">@{status.login}</span></p>
              <button onClick={disconnect} className="mt-6 rounded-lg border border-white/10 px-4 py-2 text-sm text-white/60 transition hover:bg-white/[0.06] hover:text-white">
                Disconnect GitHub
              </button>
            </>
          ) : (
            <>
              <div className="text-sm font-medium text-white/80">Connect your GitHub account</div>
              <p className="mt-2 text-sm leading-6 text-white/45">
                GitHub will show the permissions requested by the FRIDAY GitHub App before you approve access.
              </p>
              <a href={`${API_BASE_URL}/auth/github`} className="mt-6 inline-flex rounded-lg bg-white px-5 py-2.5 text-sm font-medium text-black transition hover:bg-white/85">
                Connect GitHub
              </a>
            </>
          )}
        </section>
      </div>
    </main>
  )
}
