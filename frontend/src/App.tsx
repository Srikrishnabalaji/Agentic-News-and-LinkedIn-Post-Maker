import { useEffect, useRef, useState } from "react";
import { api } from "./api";
import Dashboard from "./pages/Dashboard";
import History from "./pages/History";
import Search from "./pages/Search";
import Sources from "./pages/Sources";
import type { Run } from "./types";

type Tab = "dashboard" | "history" | "sources" | "search";
const TABS: Tab[] = ["dashboard", "history", "sources", "search"];

export default function App() {
  const [tab, setTab] = useState<Tab>("dashboard");
  const [run, setRun] = useState<Run | null>(null);
  const [triggering, setTriggering] = useState(false);
  const [dashboardRefresh, setDashboardRefresh] = useState(0);
  const [focusPostId, setFocusPostId] = useState<number | null>(null);
  const prevRunStatus = useRef<string | null>(null);

  const refreshRun = () => api.latestRun().then(setRun).catch(() => {});

  useEffect(() => {
    refreshRun();
  }, []);

  // While a run is in progress, poll until it finishes.
  useEffect(() => {
    if (run?.status !== "running") return;
    const t = setInterval(refreshRun, 4000);
    return () => clearInterval(t);
  }, [run?.status]);

  // When a run transitions running → completed, reload Dashboard posts.
  useEffect(() => {
    if (prevRunStatus.current === "running" && run?.status === "completed") {
      setDashboardRefresh((n) => n + 1);
    }
    prevRunStatus.current = run?.status ?? null;
  }, [run?.status]);

  const trigger = async () => {
    setTriggering(true);
    try {
      await api.triggerRun();
      setTimeout(refreshRun, 1000);
    } finally {
      setTriggering(false);
    }
  };

  // Jump to the Dashboard editor with a specific post selected (re-induction
  // of an old draft / opening a search or history result).
  const openInEditor = (postId: number) => {
    setFocusPostId(postId);
    setTab("dashboard");
  };

  const running = run?.status === "running";

  return (
    <div className="min-h-full">
      <header className="bg-white border-b border-gray-200 sticky top-0 z-10">
        <div className="max-w-[1400px] mx-auto flex items-center gap-6 px-6 h-14">
          <div className="font-bold text-linkedin text-lg">QuantrixLabs</div>
          <span className="text-xs text-gray-400 -ml-4">LinkedIn Agent</span>

          <nav className="flex gap-1 ml-4">
            {TABS.map((t) => (
              <button
                key={t}
                onClick={() => setTab(t)}
                className={`text-sm px-3 py-1.5 rounded-md capitalize ${
                  tab === t
                    ? "bg-blue-50 text-linkedin font-semibold"
                    : "text-gray-500 hover:bg-gray-100"
                }`}
              >
                {t}
              </button>
            ))}
          </nav>

          <div className="ml-auto flex items-center gap-3">
            {run && (
              <span className="text-xs text-gray-500">
                Last run #{run.id} · {run.num_posts} posts ·{" "}
                <span
                  className={
                    running
                      ? "text-amber-600"
                      : run.status === "failed"
                      ? "text-red-600"
                      : "text-green-600"
                  }
                >
                  {run.status}
                </span>
              </span>
            )}
            <button
              onClick={trigger}
              disabled={triggering || running}
              className="text-sm px-4 py-1.5 rounded-full bg-linkedin text-white font-semibold disabled:opacity-50"
            >
              {running ? "Running…" : triggering ? "Starting…" : "▶ Run now"}
            </button>
          </div>
        </div>
      </header>

      {tab === "dashboard" && (
        <Dashboard
          refreshTrigger={dashboardRefresh}
          focusPostId={focusPostId}
          onFocusHandled={() => setFocusPostId(null)}
        />
      )}
      {tab === "history" && <History onOpenInEditor={openInEditor} />}
      {tab === "sources" && <Sources />}
      {tab === "search" && <Search onOpenInEditor={openInEditor} />}
    </div>
  );
}
