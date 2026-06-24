import { useEffect, useState } from "react";
import { api } from "../api";
import CandidateDrawer from "../components/CandidateDrawer";
import PostEditor from "../components/PostEditor";
import StatusBadge from "../components/StatusBadge";
import { FORMAT_LABELS, type Post } from "../types";

interface Props {
  refreshTrigger?: number;
  focusPostId?: number | null;
  onFocusHandled?: () => void;
}

export default function Dashboard({
  refreshTrigger,
  focusPostId,
  onFocusHandled,
}: Props) {
  const [posts, setPosts] = useState<Post[]>([]);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [openDrawer, setOpenDrawer] = useState<string | null>(null);

  const load = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await api.today();
      const todayIds = new Set(data.map((p) => p.id));
      // Merge: keep any injected posts (e.g. opened from History) that aren't
      // in today's list so a concurrent focusPostId fetch isn't wiped out.
      setPosts((prev) => {
        const extras = prev.filter((p) => !todayIds.has(p.id));
        return [...extras, ...data];
      });
      // Default-select the first post, but never clobber an existing
      // selection (e.g. one set by an "Open in editor" focus request).
      setSelectedId((cur) => cur ?? (data.length ? data[0].id : null));
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [refreshTrigger]);

  // Open a specific post in the editor (from History / Search), fetching it
  // if it isn't part of today's run.
  useEffect(() => {
    if (focusPostId == null) return;
    let cancelled = false;
    (async () => {
      const existing = posts.find((p) => p.id === focusPostId);
      if (existing) {
        setSelectedId(focusPostId);
      } else {
        try {
          const p = await api.getPost(focusPostId);
          if (cancelled) return;
          setPosts((ps) => (ps.some((x) => x.id === p.id) ? ps : [p, ...ps]));
          setSelectedId(focusPostId);
        } catch {
          /* ignore */
        }
      }
      onFocusHandled?.();
    })();
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [focusPostId]);

  const onChange = (updated: Post) =>
    setPosts((ps) => ps.map((p) => (p.id === updated.id ? updated : p)));

  const onGenerated = (newPosts: Post[]) => {
    if (!newPosts.length) return;
    setPosts((ps) => {
      const existingIds = new Set(ps.map((p) => p.id));
      const fresh = newPosts.filter((p) => !existingIds.has(p.id));
      return [...ps, ...fresh];
    });
    setSelectedId(newPosts[0].id);
  };

  const selected = posts.find((p) => p.id === selectedId) ?? null;

  if (loading) return <div className="p-8 text-gray-500">Loading today's drafts…</div>;
  if (error) return <div className="p-8 text-red-600">Error: {error}</div>;

  const securityPosts = posts.filter((p) => p.category === "security");
  const financePosts = posts.filter((p) => p.category === "finance");

  const sections = [
    { key: "security", label: "Security", color: "text-linkedin", posts: securityPosts },
    { key: "finance", label: "Finance", color: "text-emerald-600", posts: financePosts },
  ];

  const anyPosts = posts.length > 0;

  return (
    <div className="flex gap-6 p-6 max-w-[1400px] mx-auto">
      {/* Left rail: two sections */}
      <aside className="w-72 shrink-0 space-y-5">
        {!anyPosts && (
          <div className="text-sm text-gray-500">
            No drafts yet. Trigger a run from the top bar, or pull stories below.
          </div>
        )}
        {sections.map((section) => (
          <div key={section.key}>
            <h2 className="text-xs font-semibold text-gray-400 uppercase px-1 mb-2">
              {section.label} · {section.posts.length} drafts
            </h2>
            <div className="space-y-2">
              {section.posts.map((p) => (
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
                    <span className={`text-[10px] uppercase tracking-wide font-semibold ${section.color}`}>
                      {FORMAT_LABELS[p.format_type] ?? p.format_type}
                    </span>
                    <StatusBadge status={p.status} />
                  </div>
                  <div className="text-sm text-gray-800 line-clamp-2 leading-snug">
                    {p.is_pivotal && "⚡ "}
                    {p.headline}
                  </div>
                  {p.is_update && (
                    <span className="inline-block mt-1 text-[9px] font-bold uppercase tracking-wider px-1.5 py-0.5 rounded bg-amber-100 text-amber-700">
                      Update
                    </span>
                  )}
                  <div className="text-[11px] text-gray-400 mt-1">{p.source_name}</div>
                </button>
              ))}
            </div>

            <button
              onClick={() =>
                setOpenDrawer((d) => (d === section.key ? null : section.key))
              }
              className="mt-2 w-full text-xs text-linkedin hover:bg-blue-50 rounded-md py-1.5 font-semibold"
            >
              {openDrawer === section.key ? "− Hide stories" : "+ Get more stories"}
            </button>
            {openDrawer === section.key && (
              <CandidateDrawer
                category={section.key}
                onGenerated={onGenerated}
                onClose={() => setOpenDrawer(null)}
              />
            )}
          </div>
        ))}
      </aside>

      {/* Main editor */}
      <main className="flex-1 bg-white rounded-xl shadow-sm p-6 min-w-0">
        {selected ? (
          <PostEditor post={selected} onChange={onChange} />
        ) : (
          <div className="text-gray-400 text-sm">
            Select a draft, or pull in new stories from the left.
          </div>
        )}
      </main>
    </div>
  );
}
