import { useEffect, useState } from "react";
import { api } from "./api";
import Dashboard from "./pages/Dashboard";
import History from "./pages/History";
import type { Run } from "./types";

type Tab = "dashboard" | "history";

export default function App() {
  const [tab, setTab] = useState<Tab>("dashboard");
  const [run, setRun] = useState<Run | null>(null);
  const [triggering, setTriggering] = useState(false);

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

  const trigger = async () => {
    setTriggering(true);
    try {
      await api.triggerRun();
      setTimeout(refreshRun, 1000);
    } finally {
      setTriggering(false);
    }
  };

  const running = run?.status === "running";

  return (
    <div className="min-h-full">
      <header className="bg-white border-b border-gray-200 sticky top-0 z-10">
        <div className="max-w-[1400px] mx-auto flex items-center gap-6 px-6 h-14">
          <div className="font-bold text-linkedin text-lg">QuantrixLabs</div>
          <span className="text-xs text-gray-400 -ml-4">LinkedIn Agent</span>

          <nav className="flex gap-1 ml-4">
            {(["dashboard", "history"] as Tab[]).map((t) => (
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

      {tab === "dashboard" ? <Dashboard /> : <History />}
    </div>
  );
}
