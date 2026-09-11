import Link from "next/link";
import {
  ArrowLeft,
  Bot,
  Brain,
  Check,
  Code2,
  FileText,
  FolderOpen,
  Github,
  Globe,
  Laptop,
  Music2,
  Search,
  Shield,
  Terminal,
  Wrench,
  Zap,
} from "lucide-react";

type ToolGroup = {
  name: string;
  description: string;
  icon: React.ComponentType<{ size?: number; strokeWidth?: number }>;
  tools: Array<{ name: string; description: string; permission?: "safe" | "approval" }>;
};

const groups: ToolGroup[] = [
  {
    name: "Filesystem",
    description: "Work with files and directories inside FRIDAY's configured workspace.",
    icon: FolderOpen,
    tools: [
      { name: "filesystem.list", description: "List files and directories.", permission: "safe" },
      { name: "filesystem.search", description: "Search workspace files.", permission: "safe" },
      { name: "filesystem.read", description: "Read a workspace file.", permission: "safe" },
      { name: "filesystem.write", description: "Write file contents.", permission: "approval" },
      { name: "filesystem.create", description: "Create a new file.", permission: "approval" },
      { name: "filesystem.exists", description: "Check whether a path exists.", permission: "safe" },
    ],
  },
  {
    name: "Terminal & Git",
    description: "Inspect, modify, verify, commit, and deliver software changes.",
    icon: Terminal,
    tools: [
      { name: "terminal.execute", description: "Execute a workspace terminal command.", permission: "approval" },
      { name: "git.status", description: "Inspect working tree status.", permission: "safe" },
      { name: "git.diff", description: "Inspect current changes.", permission: "safe" },
      { name: "git.log", description: "Read commit history.", permission: "safe" },
      { name: "git.branch", description: "Inspect branches.", permission: "safe" },
      { name: "git.add", description: "Stage explicit repository paths.", permission: "approval" },
      { name: "git.commit", description: "Create a commit from staged changes.", permission: "approval" },
      { name: "git.push", description: "Push a configured remote/ref.", permission: "approval" },
      { name: "developer.run", description: "Run the bounded inspect → implement → verify → deliver loop.", permission: "approval" },
    ],
  },
  {
    name: "GitHub",
    description: "Understand and work with accessible GitHub repositories and their code.",
    icon: Github,
    tools: [
      { name: "github.profile", description: "Fetch a GitHub profile.", permission: "safe" },
      { name: "github.repositories", description: "List accessible repositories.", permission: "safe" },
      { name: "github.repository", description: "Fetch repository metadata.", permission: "safe" },
      { name: "github.analyze", description: "Build a bounded repository analysis dossier.", permission: "safe" },
      { name: "github.commits", description: "Fetch recent repository commits.", permission: "safe" },
      { name: "github.contents", description: "Fetch a repository file or directory listing.", permission: "safe" },
      { name: "github.file.read", description: "Read a UTF-8 repository file.", permission: "safe" },
      { name: "github.directory.list", description: "List a GitHub directory.", permission: "safe" },
      { name: "github.file.metadata", description: "Inspect file metadata.", permission: "safe" },
      { name: "github.tree", description: "Fetch a repository tree.", permission: "safe" },
      { name: "github.code.search", description: "Search code in accessible repositories.", permission: "safe" },
      { name: "github.branches", description: "List repository branches.", permission: "safe" },
      { name: "github.commit", description: "Inspect one commit and its changed files.", permission: "safe" },
      { name: "github.api", description: "Call the supported GitHub REST API surface.", permission: "approval" },
    ],
  },
  {
    name: "Research & Browser",
    description: "Find public information and interact with webpages when a task requires it.",
    icon: Globe,
    tools: [
      { name: "research.web.search", description: "Search the public web.", permission: "safe" },
      { name: "research.web.fetch", description: "Fetch and extract readable webpage text.", permission: "safe" },
      { name: "browser.navigate", description: "Navigate a headless browser.", permission: "safe" },
      { name: "browser.read_page", description: "Read the current browser page.", permission: "safe" },
      { name: "browser.click", description: "Click a page element.", permission: "approval" },
      { name: "browser.type", description: "Type into a deterministic browser input.", permission: "approval" },
      { name: "browser.screenshot", description: "Capture the current browser page.", permission: "safe" },
      { name: "browser.close", description: "Close the current browser session.", permission: "safe" },
    ],
  },
  {
    name: "OS Operations",
    description: "Inspect and manage supported local operating-system state.",
    icon: Laptop,
    tools: [
      { name: "os.system_info", description: "Inspect system information.", permission: "safe" },
      { name: "os.list_processes", description: "List running processes.", permission: "safe" },
      { name: "os.disk_usage", description: "Inspect disk usage.", permission: "safe" },
      { name: "os.list_drives", description: "List available drives.", permission: "safe" },
      { name: "os.read_file", description: "Read a local OS file.", permission: "safe" },
      { name: "os.write_file", description: "Write a local OS file.", permission: "approval" },
      { name: "os.list_directory", description: "List a local directory.", permission: "safe" },
      { name: "os.create_directory", description: "Create a local directory.", permission: "approval" },
      { name: "os.path_exists", description: "Check a local path.", permission: "safe" },
      { name: "os.delete_path", description: "Delete a local path.", permission: "approval" },
    ],
  },
  {
    name: "OSIRIS Intelligence",
    description: "Read-only situational intelligence feeds for current-data tasks.",
    icon: Search,
    tools: [
      { name: "osiris.endpoint_catalog", description: "List the allow-listed endpoint catalog.", permission: "safe" },
      { name: "osiris.health", description: "Check OSIRIS reachability.", permission: "safe" },
      { name: "osiris.stats", description: "Fetch feed counters.", permission: "safe" },
      { name: "osiris.intelligence", description: "Call an allow-listed intelligence endpoint.", permission: "safe" },
      { name: "osiris.intelligence_brief", description: "Build a bounded multi-feed snapshot.", permission: "safe" },
      { name: "osiris.news", description: "Fetch aggregated news.", permission: "safe" },
      { name: "osiris.live_news", description: "Fetch live news.", permission: "safe" },
      { name: "osiris.weather", description: "Fetch weather and natural-event data.", permission: "safe" },
      { name: "osiris.air_quality", description: "Fetch air-quality observations.", permission: "safe" },
      { name: "osiris.radar", description: "Fetch radar and weather metadata.", permission: "safe" },
      { name: "osiris.conflicts", description: "Fetch active conflict data.", permission: "safe" },
      { name: "osiris.frontlines", description: "Fetch conflict-frontline data.", permission: "safe" },
      { name: "osiris.satellites", description: "Fetch tracked orbital objects.", permission: "safe" },
      { name: "osiris.flights", description: "Fetch live aircraft data.", permission: "safe" },
      { name: "osiris.earthquakes", description: "Fetch recent seismic events.", permission: "safe" },
      { name: "osiris.fires", description: "Fetch active wildfire hotspots.", permission: "safe" },
      { name: "osiris.space_weather", description: "Fetch solar and geomagnetic conditions.", permission: "safe" },
      { name: "osiris.gdelt", description: "Fetch geocoded world events.", permission: "safe" },
      { name: "osiris.country_risk", description: "Fetch country risk scoring data.", permission: "safe" },
      { name: "osiris.markets", description: "Fetch defence-sector equities and commodities.", permission: "safe" },
      { name: "osiris.crypto", description: "Fetch cryptocurrency market data.", permission: "safe" },
      { name: "osiris.maritime", description: "Fetch maritime intelligence.", permission: "safe" },
      { name: "osiris.infrastructure", description: "Fetch infrastructure intelligence.", permission: "safe" },
      { name: "osiris.cyber_threats", description: "Fetch cyber-threat intelligence.", permission: "safe" },
      { name: "osiris.cyber_attacks", description: "Fetch reported cyber-attack data.", permission: "safe" },
      { name: "osiris.region_dossier", description: "Fetch composite intelligence around coordinates.", permission: "safe" },
    ],
  },
  {
    name: "Memory & Cognition",
    description: "Give FRIDAY continuity, reusable lessons, and task checkpoints.",
    icon: Brain,
    tools: [
      { name: "memory.remember", description: "Persist an explicit user preference or behavior fact.", permission: "safe" },
      { name: "memory.recall", description: "Recall saved user preferences and behavior facts.", permission: "safe" },
      { name: "cognition.learn", description: "Store reusable lessons from completed work.", permission: "safe" },
      { name: "cognition.recall", description: "Recall reusable experiences.", permission: "safe" },
      { name: "cognition.curiosity", description: "Explore a bounded curiosity probe.", permission: "safe" },
      { name: "cognition.checkpoint", description: "Record a task checkpoint.", permission: "safe" },
    ],
  },
  {
    name: "Agents & Self-Improvement",
    description: "Specialist coordination and controlled FRIDAY engineering capabilities.",
    icon: Bot,
    tools: [
      { name: "agent.create", description: "Create a specialist definition from existing tools.", permission: "safe" },
      { name: "agent.list", description: "List dynamic specialist definitions.", permission: "safe" },
      { name: "self.inspect", description: "Inspect FRIDAY source and tests.", permission: "safe" },
      { name: "self.file.read", description: "Read a non-sensitive FRIDAY source/config file.", permission: "safe" },
    ],
  },
  {
    name: "Music",
    description: "Control Spotify playback through the configured integration.",
    icon: Music2,
    tools: [
      { name: "music.play", description: "Search Spotify and start the top matching track.", permission: "approval" },
      { name: "music.pause", description: "Pause Spotify playback.", permission: "approval" },
      { name: "music.next", description: "Skip to the next track.", permission: "approval" },
      { name: "music.current", description: "Read the current playback state.", permission: "safe" },
    ],
  },
];

const agentSummary = [
  ["Planner Agent", "Breaks complex goals into verifiable steps."],
  ["Developer Agent", "Inspects, implements, verifies, repairs, commits and pushes approved changes."],
  ["Research Agent", "Researches public sources and synthesizes evidence."],
  ["Browser Agent", "Navigates and interacts with webpages under permission controls."],
  ["Music Agent", "Controls Spotify playback."],
  ["GitHub Agent", "Understands accessible GitHub repositories and code."],
  ["OS Agent", "Inspects supported operating-system state."],
  ["Self-Improvement Agent", "Inspects and improves FRIDAY with explicit approval for mutations."],
  ["QA Agent", "Verifies execution results and requested changes."],
  ["Cognition Agent", "Maintains reusable experiences and explicit profile memory."],
];

export default function ToolsPage() {
  const toolCount = groups.reduce((total, group) => total + group.tools.length, 0);

  return (
    <main className="min-h-screen bg-[#07080a] text-white">
      <div className="mx-auto max-w-7xl px-6 py-10 md:px-10 md:py-14">
        <header className="mb-14">
          <Link
            href="/"
            className="mb-10 inline-flex items-center gap-2 text-sm text-white/40 transition hover:text-white"
          >
            <ArrowLeft size={15} />
            Back to FRIDAY
          </Link>

          <div className="max-w-4xl">
            <div className="mb-4 flex items-center gap-3 text-xs font-medium uppercase tracking-[0.2em] text-blue-400">
              <Wrench size={15} />
              FRIDAY capabilities
            </div>
            <h1 className="text-4xl font-semibold tracking-tight md:text-6xl">
              Tools that let FRIDAY act.
            </h1>
            <p className="mt-5 max-w-2xl text-base leading-7 text-white/45 md:text-lg">
              A complete showcase of the registered capabilities FRIDAY can use to
              research, understand, build, operate, and improve software.
            </p>
          </div>

          <div className="mt-9 flex flex-wrap gap-3">
            <Stat value={String(toolCount)} label="registered tools" />
            <Stat value={String(groups.length)} label="capability groups" />
            <Stat value={String(agentSummary.length)} label="specialist agents" />
          </div>
        </header>

        <section className="mb-16">
          <div className="mb-6 flex items-end justify-between gap-4">
            <div>
              <p className="text-xs uppercase tracking-[0.18em] text-white/25">Specialists</p>
              <h2 className="mt-2 text-2xl font-semibold">The agents behind the work</h2>
            </div>
          </div>
          <div className="grid gap-px overflow-hidden rounded-2xl border border-white/10 bg-white/10 md:grid-cols-2 lg:grid-cols-5">
            {agentSummary.map(([name, description]) => (
              <div key={name} className="bg-[#0b0d10] p-5">
                <Bot size={17} className="mb-5 text-white/35" />
                <h3 className="text-sm font-medium">{name}</h3>
                <p className="mt-2 text-xs leading-5 text-white/35">{description}</p>
              </div>
            ))}
          </div>
        </section>

        <section>
          <div className="mb-7">
            <p className="text-xs uppercase tracking-[0.18em] text-white/25">Registry</p>
            <h2 className="mt-2 text-2xl font-semibold">Every capability, in one place</h2>
          </div>

          <div className="space-y-4">
            {groups.map((group) => {
              const Icon = group.icon;
              return (
                <article key={group.name} className="overflow-hidden rounded-2xl border border-white/10 bg-[#0b0d10]">
                  <div className="flex items-start gap-4 border-b border-white/[0.07] p-5 md:p-6">
                    <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl border border-white/10 bg-white/[0.03] text-white/50">
                      <Icon size={18} />
                    </div>
                    <div className="min-w-0 flex-1">
                      <div className="flex flex-wrap items-center gap-3">
                        <h3 className="font-medium">{group.name}</h3>
                        <span className="rounded-full border border-white/10 px-2 py-0.5 text-[10px] text-white/30">
                          {group.tools.length} tools
                        </span>
                      </div>
                      <p className="mt-1 text-sm text-white/35">{group.description}</p>
                    </div>
                  </div>

                  <div className="grid divide-y divide-white/[0.06] md:grid-cols-2 md:divide-x md:divide-y-0 lg:grid-cols-3">
                    {group.tools.map((tool) => (
                      <div key={tool.name} className="border-b border-white/[0.06] p-5 last:border-b-0 md:border-b-0 lg:border-b-0">
                        <div className="flex items-start justify-between gap-3">
                          <code className="font-mono text-xs text-blue-300/80">{tool.name}</code>
                          <Permission permission={tool.permission} />
                        </div>
                        <p className="mt-2 text-xs leading-5 text-white/35">{tool.description}</p>
                      </div>
                    ))}
                  </div>
                </article>
              );
            })}
          </div>
        </section>

        <footer className="mt-16 flex flex-col gap-3 border-t border-white/[0.07] pt-6 text-xs text-white/25 md:flex-row md:items-center md:justify-between">
          <p>FRIDAY · capability registry showcase</p>
          <div className="flex items-center gap-4">
            <span className="inline-flex items-center gap-1.5"><Check size={12} /> Safe operations are read-only by default</span>
            <span className="inline-flex items-center gap-1.5"><Shield size={12} /> Mutations require approval</span>
          </div>
        </footer>
      </div>
    </main>
  );
}

function Stat({ value, label }: { value: string; label: string }) {
  return (
    <div className="rounded-xl border border-white/10 bg-white/[0.025] px-4 py-3">
      <div className="text-lg font-semibold">{value}</div>
      <div className="text-[10px] uppercase tracking-[0.14em] text-white/25">{label}</div>
    </div>
  );
}

function Permission({ permission }: { permission?: "safe" | "approval" }) {
  return permission === "approval" ? (
    <span className="shrink-0 rounded-full border border-amber-400/15 bg-amber-400/[0.05] px-2 py-0.5 text-[9px] uppercase tracking-wider text-amber-300/60">
      approval
    </span>
  ) : (
    <span className="shrink-0 rounded-full border border-emerald-400/15 bg-emerald-400/[0.05] px-2 py-0.5 text-[9px] uppercase tracking-wider text-emerald-300/60">
      safe
    </span>
  );
}
