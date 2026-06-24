import { useCallback, useEffect, useRef, useState } from "react";
import { api, type HistoryParams } from "../api";
import MetricsPanel from "../components/MetricsPanel";
import StatusBadge from "../components/StatusBadge";
import { FORMAT_LABELS, type Post, type PostStatus } from "../types";

const FILTERS: (PostStatus | "all")[] = ["all", "draft", "approved", "posted"];
const CATEGORIES: { value: string; label: string }[] = [
  { value: "", label: "All topics" },
  { value: "security", label: "Security" },
  { value: "finance", label: "Finance" },
];
const SORTS: { value: HistoryParams["sort_by"]; label: string }[] = [
  { value: "date", label: "Newest" },
  { value: "date_asc", label: "Oldest" },
  { value: "engagement", label: "Most engaged" },
];

const PAGE = 50;

interface Props {
  onOpenInEditor?: (postId: number) => void;
}

export default function History({ onOpenInEditor }: Props) {
  const [posts, setPosts] = useState<Post[]>([]);
  const [filter, setFilter] = useState<PostStatus | "all">("all");
  const [category, setCategory] = useState("");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [qInput, setQInput] = useState("");
  const [q, setQ] = useState("");
  const [sortBy, setSortBy] = useState<HistoryParams["sort_by"]>("date");
  const [open, setOpen] = useState<number | null>(null);
  const [loading, setLoading] = useState(false);
  const [hasMore, setHasMore] = useState(false);

  // Debounce the free-text search so we don't refetch on every keystroke.
  useEffect(() => {
    const t = setTimeout(() => setQ(qInput), 300);
    return () => clearTimeout(t);
  }, [qInput]);

  const params = useCallback(
    (offset: number): HistoryParams => ({
      status: filter === "all" ? undefined : filter,
      category: category || undefined,
      date_from: dateFrom || undefined,
      date_to: dateTo || undefined,
      q: q || undefined,
      sort_by: sortBy,
      limit: PAGE,
      offset,
    }),
    [filter, category, dateFrom, dateTo, q, sortBy]
  );

  // Refetch from the start whenever any filter changes.
  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    api
      .history(params(0))
      .then((data) => {
        if (cancelled) return;
        setPosts(data);
        setHasMore(data.length === PAGE);
      })
      .finally(() => !cancelled && setLoading(false));
    return () => {
      cancelled = true;
    };
  }, [params]);

  const loadingMore = useRef(false);
  const loadMore = async () => {
    if (loadingMore.current) return;
    loadingMore.current = true;
    try {
      const next = await api.history(params(posts.length));
      setPosts((ps) => [...ps, ...next]);
      setHasMore(next.length === PAGE);
    } finally {
      loadingMore.current = false;
    }
  };

  const onMetrics = (postId: number, m: Post["metrics"]) =>
    setPosts((ps) => ps.map((p) => (p.id === postId ? { ...p, metrics: m } : p)));

  return (
    <div className="max-w-4xl mx-auto p-6">
      <h2 className="text-lg font-semibold text-gray-800 mb-3">Post history</h2>

      {/* Filter bar */}
      <div className="bg-white rounded-lg border border-gray-200 p-3 mb-4 space-y-3">
        <div className="flex flex-wrap items-center gap-2">
          {FILTERS.map((f) => (
            <button
              key={f}
              onClick={() => setFilter(f)}
              className={`text-sm px-3 py-1 rounded-full capitalize ${
                filter === f
                  ? "bg-linkedin text-white"
                  : "bg-gray-50 text-gray-600 hover:bg-gray-100"
              }`}
            >
              {f}
            </button>
          ))}
          <div className="ml-auto flex items-center gap-2">
            <select
              value={category}
              onChange={(e) => setCategory(e.target.value)}
              className="text-sm border border-gray-200 rounded-md px-2 py-1 outline-none focus:border-linkedin"
            >
              {CATEGORIES.map((c) => (
                <option key={c.value} value={c.value}>
                  {c.label}
                </option>
              ))}
            </select>
            <select
              value={sortBy}
              onChange={(e) =>
                setSortBy(e.target.value as HistoryParams["sort_by"])
              }
              className="text-sm border border-gray-200 rounded-md px-2 py-1 outline-none focus:border-linkedin"
            >
              {SORTS.map((s) => (
                <option key={s.value} value={s.value}>
                  {s.label}
                </option>
              ))}
            </select>
          </div>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <input
            value={qInput}
            onChange={(e) => setQInput(e.target.value)}
            placeholder="Search headline or body…"
            className="flex-1 min-w-[200px] text-sm border border-gray-200 rounded-md px-3 py-1.5 outline-none focus:border-linkedin"
          />
          <label className="text-xs text-gray-500 flex items-center gap-1">
            From
            <input
              type="date"
              value={dateFrom}
              onChange={(e) => setDateFrom(e.target.value)}
              className="text-sm border border-gray-200 rounded-md px-2 py-1 outline-none focus:border-linkedin"
            />
          </label>
          <label className="text-xs text-gray-500 flex items-center gap-1">
            To
            <input
              type="date"
              value={dateTo}
              onChange={(e) => setDateTo(e.target.value)}
              className="text-sm border border-gray-200 rounded-md px-2 py-1 outline-none focus:border-linkedin"
            />
          </label>
          {(dateFrom || dateTo || qInput) && (
            <button
              onClick={() => {
                setDateFrom("");
                setDateTo("");
                setQInput("");
              }}
              className="text-xs text-gray-400 hover:text-gray-600 px-2 py-1"
            >
              Clear
            </button>
          )}
        </div>
      </div>

      <p className="text-xs text-gray-400 mb-3">
        Posts are retained for ~2 weeks. Topics posted in the last week are
        auto-skipped by the generator (unless flagged pivotal).
      </p>

      <div className="space-y-2">
        {posts.map((p) => (
          <div key={p.id} className="bg-white rounded-lg border border-gray-200">
            <button
              onClick={() => setOpen(open === p.id ? null : p.id)}
              className="w-full flex items-center gap-3 p-3 text-left"
            >
              <span className="text-[10px] uppercase tracking-wide text-linkedin font-semibold w-28 shrink-0">
                {FORMAT_LABELS[p.format_type] ?? p.format_type}
              </span>
              <span className="flex-1 text-sm text-gray-800 truncate">
                {p.is_pivotal && "⚡ "}
                {p.headline}
                {p.is_update && (
                  <span className="ml-1.5 text-[9px] font-bold uppercase tracking-wider px-1 py-0.5 rounded bg-amber-100 text-amber-700 align-middle">
                    Update
                  </span>
                )}
              </span>
              {p.metrics && (
                <span className="text-[11px] text-gray-400 shrink-0">
                  {p.metrics.impressions.toLocaleString()} impr
                </span>
              )}
              <span className="text-xs text-gray-400 shrink-0">
                {new Date(p.created_at).toLocaleDateString()}
              </span>
              <StatusBadge status={p.status} />
            </button>
            {open === p.id && (
              <div className="px-3 pb-3 text-sm text-gray-700 whitespace-pre-wrap border-t border-gray-100 pt-2">
                {p.body}
                <div className="mt-2 text-linkedin text-xs">
                  {p.hashtags.map((h) => `#${h}`).join(" ")}
                </div>
                <div className="flex items-center gap-3 mt-2">
                  {p.source_url && (
                    <a
                      href={p.source_url}
                      target="_blank"
                      rel="noreferrer"
                      className="text-xs text-gray-400 hover:underline inline-block"
                    >
                      Source: {p.source_name} ↗
                    </a>
                  )}
                  {onOpenInEditor && (
                    <button
                      onClick={() => onOpenInEditor(p.id)}
                      className="text-xs text-linkedin hover:underline font-semibold"
                    >
                      Open in editor →
                    </button>
                  )}
                </div>
                {p.status === "posted" && (
                  <div className="mt-3">
                    <MetricsPanel
                      post={p}
                      onSaved={(m) => onMetrics(p.id, m)}
                    />
                  </div>
                )}
              </div>
            )}
          </div>
        ))}
        {loading && (
          <div className="text-gray-400 text-sm p-6 text-center">Loading…</div>
        )}
        {!loading && !posts.length && (
          <div className="text-gray-400 text-sm p-6 text-center">
            No posts match these filters.
          </div>
        )}
        {hasMore && !loading && (
          <button
            onClick={loadMore}
            className="w-full text-sm py-2 rounded-lg border border-gray-200 bg-white text-gray-600 hover:bg-gray-50"
          >
            Load more
          </button>
        )}
      </div>
    </div>
  );
}
