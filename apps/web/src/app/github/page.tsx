"use client"

import { useEffect, useMemo, useState } from "react"

const API_BASE_URL = process.env.NEXT_PUBLIC_FRIDAY_API_URL || "http://127.0.0.1:8000"

type Status = {
  configured: boolean
  connected: boolean
  login?: string
}

type Diagnostic = {
  id: string
  label: string
  permission: string
  method: string
  needs_repo: boolean
}

type DiagnosticResult = Diagnostic & {
  path?: string
  status?: number
  ok: boolean
  message: string
  note?: string
  reason?: string
}

const fallbackDiagnostics: Diagnostic[] = [
  { id: "identity", label: "Account identity", permission: "OAuth identity", method: "GET", needs_repo: false },
  { id: "repositories", label: "List repositories", permission: "Metadata", method: "GET", needs_repo: false },
  { id: "metadata", label: "Repository metadata", permission: "Metadata", method: "GET", needs_repo: true },
  { id: "contents", label: "Repository contents", permission: "Contents", method: "GET", needs_repo: true },
  { id: "pull_requests", label: "Pull requests", permission: "Pull requests", method: "GET", needs_repo: true },
  { id: "issues", label: "Issues", permission: "Issues", method: "GET", needs_repo: true },
  { id: "checks", label: "Check runs", permission: "Checks", method: "GET", needs_repo: true },
  { id: "statuses", label: "Commit statuses", permission: "Commit statuses", method: "GET", needs_repo: true },
  { id: "actions", label: "Actions workflow runs", permission: "Actions", method: "GET", needs_repo: true },
  { id: "code_scanning", label: "Code scanning alerts", permission: "Code scanning alerts", method: "GET", needs_repo: true },
  { id: "dependabot", label: "Dependabot alerts", permission: "Dependabot alerts", method: "GET", needs_repo: true },
  { id: "secret_scanning", label: "Secret scanning alerts", permission: "Secret scanning alerts", method: "GET", needs_repo: true },
  { id: "security_advisories", label: "Repository security advisories", permission: "Repository security advisories", method: "GET", needs_repo: true },
  { id: "deployments", label: "Deployments", permission: "Deployments", method: "GET", needs_repo: true },
  { id: "packages", label: "Packages", permission: "Packages", method: "GET", needs_repo: false },
  { id: "pages", label: "GitHub Pages", permission: "Pages", method: "GET", needs_repo: true },
]

export default function GitHubConnectionPage() {
  const [status, setStatus] = useState<Status | null>(null)
  const [loading, setLoading] = useState(true)
  const [diagnostics, setDiagnostics] = useState<Diagnostic[]>([])
  const [repository, setRepository] = useState("tirth1207/Orbit")
  const [results, setResults] = useState<Record<string, DiagnosticResult>>({})
  const [running, setRunning] = useState<Record<string, boolean>>({})
  const [runningAll, setRunningAll] = useState(false)

  const groupedDiagnostics = useMemo(() => {
    const source = diagnostics.length ? diagnostics : fallbackDiagnostics
    return source.reduce<Record<string, Diagnostic[]>>((groups, item) => {
      const key = item.permission
      groups[key] = [...(groups[key] || []), item]
      return groups
    }, {})
  }, [diagnostics])

  const loadStatus = async () => {
    try {
      const response = await fetch(`${API_BASE_URL}/auth/github/status`)
      setStatus(await response.json())
    } catch {
      setStatus({ configured: false, connected: false })
    } finally {
      setLoading(false)
    }
  }

  const loadDiagnostics = async () => {
    try {
      const response = await fetch(`${API_BASE_URL}/auth/github/diagnostics`)
      const data = await response.json()
      if (response.ok && Array.isArray(data.tests)) setDiagnostics(data.tests)
    } catch {
      // The fallback list keeps the UI useful even if the API is temporarily unavailable.
    }
  }

  useEffect(() => {
    loadStatus()
    loadDiagnostics()
  }, [])

  const disconnect = async () => {
    await fetch(`${API_BASE_URL}/auth/github/disconnect`, { method: "POST" })
    setStatus({ configured: status?.configured ?? true, connected: false })
    setResults({})
  }

  const runTest = async (test: Diagnostic) => {
    if (test.needs_repo && !repository.trim()) return
    setRunning(current => ({ ...current, [test.id]: true }))
    try {
      const query = test.needs_repo ? `?repository=${encodeURIComponent(repository.trim())}` : ""
      const response = await fetch(`${API_BASE_URL}/auth/github/diagnostics/${test.id}${query}`)
      const data = await response.json()
      const result: DiagnosticResult = response.ok
        ? data
        : { ...test, ok: false, message: data.detail || `HTTP ${response.status}` }
      setResults(current => ({ ...current, [test.id]: result }))
    } catch (error) {
      setResults(current => ({
        ...current,
        [test.id]: { ...test, ok: false, message: error instanceof Error ? error.message : "Network error" },
      }))
    } finally {
      setRunning(current => ({ ...current, [test.id]: false }))
    }
  }

  const runAll = async () => {
    const tests = diagnostics.length ? diagnostics : fallbackDiagnostics
    setRunningAll(true)
    for (const test of tests) {
      await runTest(test)
    }
    setRunningAll(false)
  }

  const testCount = Object.keys(results).length
  const passCount = Object.values(results).filter(result => result.ok).length
  const failCount = Object.values(results).filter(result => !result.ok).length

  if (loading) return <main className="min-h-screen bg-[#07090d] p-10 text-white/60">Checking GitHub connection…</main>

  return (
    <main className="min-h-screen bg-[#07090d] px-6 py-16 text-white">
      <div className="mx-auto max-w-5xl">
        <div className="mb-10">
          <p className="mb-3 text-xs uppercase tracking-[0.25em] text-blue-400/70">FRIDAY / Integrations</p>
          <div className="flex flex-col justify-between gap-5 md:flex-row md:items-end">
            <div>
              <h1 className="text-4xl font-semibold tracking-tight">GitHub</h1>
              <p className="mt-4 max-w-2xl leading-7 text-white/45">
                Connect FRIDAY to your GitHub account and test the underlying GitHub APIs directly, without the AI or agent layer.
              </p>
            </div>
            {status?.connected && (
              <div className="rounded-xl border border-emerald-400/15 bg-emerald-400/[0.05] px-4 py-3 text-sm">
                <div className="flex items-center gap-2">
                  <span className="h-2 w-2 rounded-full bg-emerald-400" />
                  <span className="text-emerald-300">Connected</span>
                </div>
                <div className="mt-1 text-white/45">@{status.login}</div>
              </div>
            )}
          </div>
        </div>

        <section className="mb-8 rounded-2xl border border-white/10 bg-white/[0.03] p-6 shadow-2xl shadow-black/20">
          {!status?.configured ? (
            <>
              <div className="text-sm font-medium text-amber-300">GitHub App OAuth is not configured</div>
              <p className="mt-2 text-sm leading-6 text-white/45">
                Add the GitHub App environment variables to FRIDAY's backend `.env`, then restart the API.
              </p>
            </>
          ) : status.connected ? (
            <div className="flex flex-col gap-5 md:flex-row md:items-end md:justify-between">
              <div>
                <div className="text-sm font-medium text-white/80">GitHub account connected</div>
                <p className="mt-2 text-sm text-white/45">The diagnostics below use the stored GitHub App user token directly.</p>
              </div>
              <button onClick={disconnect} className="rounded-lg border border-white/10 px-4 py-2 text-sm text-white/60 transition hover:bg-white/[0.06] hover:text-white">
                Disconnect GitHub
              </button>
            </div>
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

        {status?.connected && (
          <section className="rounded-2xl border border-white/10 bg-white/[0.03] p-6 shadow-2xl shadow-black/20">
            <div className="flex flex-col gap-5 border-b border-white/10 pb-6 lg:flex-row lg:items-end lg:justify-between">
              <div>
                <p className="text-xs uppercase tracking-[0.2em] text-white/30">Direct API diagnostics</p>
                <h2 className="mt-2 text-2xl font-semibold">GitHub permission tester</h2>
                <p className="mt-2 max-w-3xl text-sm leading-6 text-white/45">
                  Every Test button makes one GET request from the FRIDAY backend to GitHub. It does not call NVIDIA, the supervisor, an agent, or an LLM.
                </p>
              </div>
              <div className="flex flex-wrap gap-2 text-xs">
                <span className="rounded-full border border-white/10 px-3 py-1.5 text-white/45">{testCount} tested</span>
                <span className="rounded-full border border-emerald-400/20 px-3 py-1.5 text-emerald-300/80">{passCount} passed</span>
                <span className="rounded-full border border-red-400/20 px-3 py-1.5 text-red-300/80">{failCount} failed</span>
              </div>
            </div>

            <div className="mt-6 flex flex-col gap-3 md:flex-row">
              <input
                value={repository}
                onChange={event => setRepository(event.target.value)}
                placeholder="owner/repository"
                className="min-w-0 flex-1 rounded-lg border border-white/10 bg-black/20 px-4 py-2.5 text-sm text-white outline-none placeholder:text-white/20 focus:border-white/25"
              />
              <button
                onClick={runAll}
                disabled={runningAll}
                className="rounded-lg bg-white px-5 py-2.5 text-sm font-medium text-black transition hover:bg-white/85 disabled:cursor-not-allowed disabled:opacity-50"
              >
                {runningAll ? "Testing…" : "Run all tests"}
              </button>
            </div>
            <p className="mt-2 text-xs text-white/25">Repository tests use the repository above. Account-level tests do not need it.</p>

            <div className="mt-8 space-y-8">
              {Object.entries(groupedDiagnostics).map(([permission, tests]) => (
                <div key={permission}>
                  <div className="mb-3 flex items-center gap-3">
                    <h3 className="text-sm font-medium text-white/70">{permission}</h3>
                    <div className="h-px flex-1 bg-white/10" />
                  </div>
                  <div className="grid gap-3 md:grid-cols-2">
                    {tests.map(test => {
                      const result = results[test.id]
                      const isRunning = running[test.id]
                      return (
                        <div key={test.id} className="rounded-xl border border-white/10 bg-black/15 p-4">
                          <div className="flex items-start justify-between gap-4">
                            <div className="min-w-0">
                              <div className="flex items-center gap-2">
                                <span className="text-sm font-medium text-white/80">{test.label}</span>
                                <span className="rounded border border-white/10 px-1.5 py-0.5 text-[10px] text-white/30">{test.method}</span>
                              </div>
                              <div className="mt-1 text-xs text-white/30">{test.permission}</div>
                            </div>
                            <button
                              onClick={() => runTest(test)}
                              disabled={isRunning || runningAll || (test.needs_repo && !repository.trim())}
                              className="shrink-0 rounded-md border border-white/10 px-3 py-1.5 text-xs text-white/65 transition hover:bg-white/[0.06] hover:text-white disabled:cursor-not-allowed disabled:opacity-40"
                            >
                              {isRunning ? "Testing…" : "Test"}
                            </button>
                          </div>

                          {result && (
                            <div className={`mt-3 rounded-lg border p-3 ${result.ok ? "border-emerald-400/15 bg-emerald-400/[0.04]" : "border-red-400/15 bg-red-400/[0.04]"}`}>
                              <div className="flex items-center gap-2 text-xs font-medium">
                                <span className={result.ok ? "text-emerald-300" : "text-red-300"}>{result.ok ? "PASS" : "FAIL"}</span>
                                {result.status !== undefined && <span className="text-white/35">HTTP {result.status}</span>}
                              </div>
                              <p className="mt-1 break-words text-xs leading-5 text-white/55">{result.message}</p>
                              {result.path && <code className="mt-2 block break-all text-[10px] leading-4 text-white/25">{result.method} {result.path}</code>}
                              {result.note && <p className="mt-2 text-[10px] leading-4 text-white/25">{result.note}</p>}
                            </div>
                          )}
                        </div>
                      )
                    })}
                  </div>
                </div>
              ))}
            </div>
          </section>
        )}
      </div>
    </main>
  )
}
