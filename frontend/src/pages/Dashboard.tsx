import { useEffect, useState } from "react";
import { api } from "../api";
import PostEditor from "../components/PostEditor";
import StatusBadge from "../components/StatusBadge";
import { FORMAT_LABELS, type Post } from "../types";

export default function Dashboard() {
  const [posts, setPosts] = useState<Post[]>([]);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await api.today();
      setPosts(data);
      if (data.length && selectedId === null) setSelectedId(data[0].id);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const onChange = (updated: Post) =>
    setPosts((ps) => ps.map((p) => (p.id === updated.id ? updated : p)));

  const selected = posts.find((p) => p.id === selectedId) ?? null;

  if (loading) return <div className="p-8 text-gray-500">Loading today's drafts…</div>;
  if (error) return <div className="p-8 text-red-600">Error: {error}</div>;
  if (!posts.length)
    return (
      <div className="p-8 text-gray-500">
        No drafts yet. Trigger a run from the top bar to generate today's posts.
      </div>
    );

  return (
    <div className="flex gap-6 p-6 max-w-[1400px] mx-auto">
      {/* Left rail: the 5 drafts */}
      <aside className="w-64 shrink-0 space-y-2">
        <h2 className="text-xs font-semibold text-gray-400 uppercase px-1">
          Today · {posts.length} drafts
        </h2>
        {posts.map((p) => (
          <button
            key={p.id}
            onClick={() => setSelectedId(p.id)}
            className={`w-full text-left p-3 rounded-lg border transition ${
              p.id === selectedId
                ? "border-linkedin bg-white shadow-sm"
                : "border-transparent bg-white/60 hover:bg-white"
            }`}
          >
            <div className="flex items-center justify-between mb-1">
              <span className="text-[10px] uppercase tracking-wide text-linkedin font-semibold">
                {FORMAT_LABELS[p.format_type] ?? p.format_type}
              </span>
              <StatusBadge status={p.status} />
            </div>
            <div className="text-sm text-gray-800 line-clamp-2 leading-snug">
              {p.is_pivotal && "⚡ "}
              {p.headline}
            </div>
            <div className="text-[11px] text-gray-400 mt-1">{p.source_name}</div>
          </button>
        ))}
      </aside>

      {/* Main editor */}
      <main className="flex-1 bg-white rounded-xl shadow-sm p-6 min-w-0">
        {selected && <PostEditor post={selected} onChange={onChange} />}
      </main>
    </div>
  );
}
