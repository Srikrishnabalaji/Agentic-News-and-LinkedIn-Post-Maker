import { useState } from "react";
import { api } from "../api";
import StatusBadge from "../components/StatusBadge";
import { FORMAT_LABELS, type LiveSearchResult, type Post } from "../types";

interface Props {
  onOpenInEditor?: (postId: number) => void;
}

export default function Search({ onOpenInEditor }: Props) {
  const [q, setQ] = useState("");
  const [subTab, setSubTab] = useState<"stored" | "live">("stored");
  const [stored, setStored] = useState<Post[]>([]);
  const [live, setLive] = useState<LiveSearchResult[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [noKey, setNoKey] = useState(false);
  const [searched, setSearched] = useState(false);
  const [liveCategory, setLiveCategory] = useState("security");
  const [genUrl, setGenUrl] = useState<string | null>(null);
  const [generated, setGenerated] = useState<Record<string, number>>({});

  const run = async () => {
    if (!q.trim()) return;
    setLoading(true);
    setError(null);
    setNoKey(false);
    setSearched(true);
    try {
      if (subTab === "stored") {
        setStored(await api.searchStored(q.trim()));
      } else {
        setLive(await api.searchLive(q.trim()));
      }
    } catch (e) {
      const msg = (e as Error).message;
      if (msg.startsWith("503")) setNoKey(true);
      else setError(msg.includes(":") ? msg.split(":").slice(1).join(":").trim() : msg);
    } finally {
      setLoading(false);
    }
  };

  const switchTab = (t: "stored" | "live") => {
    setSubTab(t);
    setError(null);
    setNoKey(false);
    setSearched(false);
  };

  const generate = async (r: LiveSearchResult) => {
    setGenUrl(r.url);
    setError(null);
    try {
      const post = await api.generateFromSearch({
        url: r.url,
        title: r.title,
        summary: r.content,
        category: liveCategory,
      });
      setGenerated((m) => ({ ...m, [r.url]: post.id }));
    } catch (e) {
      const msg = (e as Error).message;
      setError(msg.includes(":") ? msg.split(":").slice(1).join(":").trim() : msg);
    } finally {
      setGenUrl(null);
    }
  };

  return (
    <div className="max-w-3xl mx-auto p-6">
      <h2 className="text-lg font-semibold text-gray-800 mb-3">Search</h2>

      <div className="flex gap-2 mb-3">
        <input
          value={q}
          onChange={(e) => setQ(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && run()}
          placeholder={
            subTab === "stored"
              ? "Search your generated posts…"
              : "Search the live web for stories…"
          }
          className="flex-1 text-sm border border-gray-200 rounded-lg px-3 py-2 outline-none focus:border-linkedin"
        />
        <button
          onClick={run}
          disabled={loading || !q.trim()}
          className="text-sm px-4 py-2 rounded-lg bg-linkedin text-white font-semibold disabled:opacity-40"
        >
          {loading ? "Searching…" : "Search"}
        </button>
      </div>

      <div className="flex items-center gap-1 mb-4">
        {(["stored", "live"] as const).map((t) => (
          <button
            key={t}
            onClick={() => switchTab(t)}
            className={`text-sm px-3 py-1 rounded-full capitalize ${
              subTab === t
                ? "bg-linkedin text-white"
                : "bg-white text-gray-600 hover:bg-gray-100"
            }`}
          >
            {t}
          </button>
        ))}
        {subTab === "live" && (
          <select
            value={liveCategory}
            onChange={(e) => setLiveCategory(e.target.value)}
            className="ml-2 text-sm border border-gray-200 rounded-md px-2 py-1 outline-none focus:border-linkedin"
            title="Category for generated drafts"
          >
            <option value="security">Security</option>
            <option value="finance">Finance</option>
          </select>
        )}
      </div>

      {error && <div className="text-sm text-red-600 mb-3">{error}</div>}

      {noKey && (
        <div className="text-sm text-gray-500 bg-gray-50 border border-gray-200 rounded-lg p-4">
          Live web search isn't configured. Add a{" "}
          <code className="text-xs bg-gray-100 px-1 rounded">TAVILY_API_KEY</code>{" "}
          to your <code className="text-xs bg-gray-100 px-1 rounded">.env</code> to
          enable it.
        </div>
      )}

      {/* Stored results */}
      {subTab === "stored" && !noKey && (
        <div className="space-y-2">
          {stored.map((p) => (
            <button
              key={p.id}
              onClick={() => onOpenInEditor?.(p.id)}
              className="w-full text-left flex items-center gap-3 bg-white rounded-lg border border-gray-200 p-3 hover:border-linkedin"
            >
              <span className="text-[10px] uppercase tracking-wide text-linkedin font-semibold w-24 shrink-0">
                {FORMAT_LABELS[p.format_type] ?? p.format_type}
              </span>
              <span className="flex-1 text-sm text-gray-800 truncate">
                {p.headline}
              </span>
              <span className="text-[10px] text-gray-400 capitalize">{p.category}</span>
              <span className="text-xs text-gray-400">
                {new Date(p.created_at).toLocaleDateString()}
              </span>
              <StatusBadge status={p.status} />
            </button>
          ))}
          {searched && !loading && !stored.length && (
            <div className="text-sm text-gray-400 p-6 text-center">
              No posts match your search.
            </div>
          )}
        </div>
      )}

      {/* Live results */}
      {subTab === "live" && !noKey && (
        <div className="space-y-2">
          {live.map((r) => {
            const postId = generated[r.url];
            return (
              <div
                key={r.url}
                className="bg-white rounded-lg border border-gray-200 p-3"
              >
                <div className="flex items-start gap-3">
                  <div className="min-w-0 flex-1">
                    <a
                      href={r.url}
                      target="_blank"
                      rel="noreferrer"
                      className="text-sm font-medium text-gray-800 hover:text-linkedin"
                    >
                      {r.title}
                    </a>
                    <div className="text-[11px] text-gray-400 mt-0.5">
                      {r.source}
                      {r.published_date ? ` · ${r.published_date}` : ""}
                    </div>
                    {r.content && (
                      <div className="text-xs text-gray-500 line-clamp-2 mt-1">
                        {r.content}
                      </div>
                    )}
                  </div>
                  {postId ? (
                    <button
                      onClick={() => onOpenInEditor?.(postId)}
                      className="shrink-0 text-xs px-3 py-1 rounded-full border border-green-600 text-green-700 font-semibold"
                    >
                      Open draft →
                    </button>
                  ) : (
                    <button
                      onClick={() => generate(r)}
                      disabled={genUrl === r.url}
                      className="shrink-0 text-xs px-3 py-1 rounded-full bg-linkedin text-white font-semibold disabled:opacity-50"
                    >
                      {genUrl === r.url ? "Generating…" : "Generate post →"}
                    </button>
                  )}
                </div>
              </div>
            );
          })}
          {searched && !loading && !live.length && (
            <div className="text-sm text-gray-400 p-6 text-center">
              No live results found.
            </div>
          )}
        </div>
      )}
    </div>
  );
}
