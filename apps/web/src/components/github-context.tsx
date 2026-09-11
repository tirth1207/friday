"use client";

import { useEffect, useMemo, useState } from "react";
import { Check, ChevronRight, Github, Plus, X } from "lucide-react";

const API = process.env.NEXT_PUBLIC_FRIDAY_API_URL || "http://127.0.0.1:8000";
const STORAGE_KEY = "friday.chat.github-context";

type Repository = {
  full_name: string;
  private: boolean;
  language?: string | null;
};

type GithubStatus = {
  connected?: boolean;
  login?: string;
};

export default function GithubContext() {
  const [open, setOpen] = useState(false);
  const [repositories, setRepositories] = useState<Repository[]>([]);
  const [attached, setAttached] = useState("");
  const [github, setGithub] = useState<GithubStatus>({});
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    try {
      setAttached(localStorage.getItem(STORAGE_KEY) || "");
    } catch {}

    const originalFetch = window.fetch.bind(window);
    window.fetch = async (input, init) => {
      const requestUrl = typeof input === "string" ? input : input instanceof Request ? input.url : String(input);
      if (!requestUrl.endsWith("/chat")) return originalFetch(input, init);

      let body = init?.body;
      if (typeof body === "string") {
        try {
          const payload = JSON.parse(body);
          const repo = localStorage.getItem(STORAGE_KEY) || "";
          payload.repository_attached = Boolean(repo);
          if (repo) payload.repository = repo;
          body = JSON.stringify(payload);
          init = { ...init, body };
        } catch {}
      }
      return originalFetch(input, init);
    };

    return () => {
      window.fetch = originalFetch;
    };
  }, []);

  async function openPicker() {
    setOpen((value) => !value);
    if (open || repositories.length) return;
    setLoading(true);
    try {
      const [reposResponse, statusResponse] = await Promise.all([
        fetch(`${API}/auth/github/repositories`, { cache: "no-store" }),
        fetch(`${API}/auth/github/status`, { cache: "no-store" }),
      ]);
      if (reposResponse.ok) {
        const data = await reposResponse.json();
        setRepositories(Array.isArray(data.repositories) ? data.repositories : []);
      }
      if (statusResponse.ok) setGithub(await statusResponse.json());
    } finally {
      setLoading(false);
    }
  }

  function attach(repository: string) {
    setAttached(repository);
    try {
      if (repository) localStorage.setItem(STORAGE_KEY, repository);
      else localStorage.removeItem(STORAGE_KEY);
    } catch {}
    setOpen(false);
  }

  const label = useMemo(() => {
    if (!attached) return "Add context";
    return attached.split("/").pop() || attached;
  }, [attached]);

  return (
    <div className="fixed bottom-[22px] left-[max(12px,calc(50% - 370px))] z-50">
      {open && (
        <div className="absolute bottom-12 left-0 w-[min(340px,calc(100vw-24px))] overflow-hidden rounded-2xl border border-white/10 bg-[#0b0d11]/98 shadow-2xl backdrop-blur-xl">
          <div className="flex items-center gap-2 border-b border-white/[0.07] px-3 py-2.5">
            <div className="flex h-7 w-7 items-center justify-center rounded-lg border border-white/10 bg-white/[0.04]">
              <Github size={14} className="text-white/60" />
            </div>
            <div className="min-w-0 flex-1">
              <div className="text-[11px] font-medium text-white/75">GitHub context</div>
              <div className="text-[9px] text-white/25">Only used when you attach it to the chat</div>
            </div>
            <button onClick={() => setOpen(false)} className="rounded-md p-1.5 text-white/25 hover:bg-white/[0.05]" aria-label="Close GitHub context">
              <X size={13} />
            </button>
          </div>

          {!github.connected && repositories.length === 0 && !loading ? (
            <div className="p-4">
              <p className="text-[10px] leading-4 text-white/30">Connect GitHub to attach a repository when you actually need code context.</p>
              <a href="/github" className="mt-3 flex items-center justify-between rounded-xl border border-white/[0.07] bg-white/[0.025] px-3 py-2.5 text-[11px] text-white/60 hover:bg-white/[0.05]">
                Connect GitHub
                <ChevronRight size={13} className="text-white/25" />
              </a>
            </div>
          ) : (
            <div className="max-h-72 overflow-y-auto p-1.5">
              <button
                onClick={() => attach("")}
                className="flex w-full items-center gap-2 rounded-xl px-3 py-2.5 text-left hover:bg-white/[0.05]"
              >
                <div className="h-4 w-4 rounded-full border border-white/15" />
                <span className="text-[11px] text-white/55">No GitHub context</span>
                {!attached && <Check size={13} className="ml-auto text-blue-400" />}
              </button>
              {repositories.map((repository) => {
                const active = attached === repository.full_name;
                return (
                  <button
                    key={repository.full_name}
                    onClick={() => attach(repository.full_name)}
                    className="flex w-full items-center gap-2 rounded-xl px-3 py-2.5 text-left hover:bg-white/[0.05]"
                  >
                    <div className="flex h-6 w-6 items-center justify-center rounded-lg bg-white/[0.04]">
                      <Github size={12} className="text-white/35" />
                    </div>
                    <div className="min-w-0 flex-1">
                      <div className="truncate text-[11px] text-white/60">{repository.full_name}</div>
                      <div className="text-[8px] text-white/20">
                        {repository.private ? "Private" : "Public"}{repository.language ? ` · ${repository.language}` : ""}
                      </div>
                    </div>
                    {active && <Check size={13} className="shrink-0 text-blue-400" />}
                  </button>
                );
              })}
            </div>
          )}
        </div>
      )}

      <button
        onClick={openPicker}
        aria-label={attached ? `GitHub context: ${attached}` : "Add chat context"}
        title={attached ? `GitHub: ${attached}` : "Add context"}
        className={`flex h-9 items-center gap-1.5 rounded-xl border px-2.5 shadow-xl backdrop-blur-xl transition ${
          attached
            ? "border-blue-500/25 bg-blue-500/10 text-blue-300"
            : "border-white/[0.09] bg-[#0b0d11]/95 text-white/35 hover:text-white/60"
        }`}
      >
        {attached ? <Github size={14} /> : <Plus size={14} />}
        <span className="max-w-32 truncate text-[9px] font-medium">{label}</span>
      </button>
    </div>
  );
}
