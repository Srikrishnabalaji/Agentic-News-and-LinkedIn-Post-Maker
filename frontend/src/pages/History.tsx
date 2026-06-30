import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { api, type HistoryParams } from "../api";
import StatusBadge from "../components/StatusBadge";
import { FORMAT_LABELS, type Post, type PostMetrics, type PostStatus } from "../types";

const CATEGORIES = [
  { value: "", label: "All categories" },
  { value: "security", label: "Security" },
  { value: "finance", label: "Finance" },
];

const STATUS_OPTIONS: { value: PostStatus | ""; label: string }[] = [
  { value: "", label: "All statuses" },
  { value: "draft", label: "Draft" },
  { value: "approved", label: "Approved" },
  { value: "posted", label: "Posted" },
];

const PAGE = 50;

type MetricKey = keyof Pick<PostMetrics, "reactions" | "comments" | "impressions" | "reposts">;
type SortCol = "date" | MetricKey;
type SortDir = "asc" | "desc";

interface Props {
  onOpenInEditor?: (postId: number) => void;
}

function fmt(n: number | null | undefined): string {
  if (n == null) return "—";
  if (n >= 1000) return `${(n / 1000).toFixed(1)}k`;
  return String(n);
}

interface ColHeaderProps {
  col: SortCol;
  sortCol: SortCol;
  sortDir: SortDir;
  onSort: (col: SortCol) => void;
  children: React.ReactNode;
  align?: "left" | "right";
}

function SortableHeader({ col, sortCol, sortDir, onSort, children, align = "left" }: ColHeaderProps) {
  const active = sortCol === col;
  return (
    <button
      onClick={() => onSort(col)}
      className={`flex items-center gap-0.5 hover:text-gray-800 ${align === "right" ? "ml-auto" : ""} ${active ? "text-linkedin" : ""}`}
    >
      {children}
      {active ? (
        <span className="text-linkedin ml-0.5">{sortDir === "desc" ? "↓" : "↑"}</span>
      ) : (
        <span className="text-gray-300 ml-0.5">↕</span>
      )}
    </button>
  );
}

export default function History({ onOpenInEditor }: Props) {
  const [posts, setPosts] = useState<Post[]>([]);
  const [statusFilter, setStatusFilter] = useState<PostStatus | "">("");
  const [category, setCategory] = useState("");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [qInput, setQInput] = useState("");
  const [q, setQ] = useState("");
  const [sortCol, setSortCol] = useState<SortCol>("date");
  const [sortDir, setSortDir] = useState<SortDir>("desc");
  const [loading, setLoading] = useState(false);
  const [hasMore, setHasMore] = useState(false);
  const [selected, setSelected] = useState<Set<number>>(new Set());
  const [bulkLoading, setBulkLoading] = useState(false);
  const [statusMenuOpen, setStatusMenuOpen] = useState(false);
  const [catMenuOpen, setCatMenuOpen] = useState(false);

  useEffect(() => {
    const t = setTimeout(() => setQ(qInput), 300);
    return () => clearTimeout(t);
  }, [qInput]);

  const apiSortBy = useCallback((): HistoryParams["sort_by"] => {
    if (sortCol === "date") return sortDir === "desc" ? "date" : "date_asc";
    // For metric columns, pre-fetch by engagement (impressions desc); client-side refines.
    return "engagement";
  }, [sortCol, sortDir]);

  const params = useCallback(
    (offset: number): HistoryParams => ({
      status: statusFilter || undefined,
      category: category || undefined,
      date_from: dateFrom || undefined,
      date_to: dateTo || undefined,
      q: q || undefined,
      sort_by: apiSortBy(),
      limit: PAGE,
      offset,
    }),
    [statusFilter, category, dateFrom, dateTo, q, apiSortBy]
  );

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setSelected(new Set());
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

  // Client-side sort for engagement metric columns.
  const sortedPosts = useMemo(() => {
    if (sortCol === "date") return posts;
    const col = sortCol as MetricKey;
    return [...posts].sort((a, b) => {
      const va = a.metrics?.[col] ?? -1;
      const vb = b.metrics?.[col] ?? -1;
      return sortDir === "desc" ? vb - va : va - vb;
    });
  }, [posts, sortCol, sortDir]);

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

  const toggleSort = (col: SortCol) => {
    if (sortCol === col) {
      setSortDir((d) => (d === "desc" ? "asc" : "desc"));
    } else {
      setSortCol(col);
      setSortDir("desc");
    }
  };

  const toggleRow = (e: React.MouseEvent, id: number) => {
    e.stopPropagation();
    setSelected((s) => {
      const n = new Set(s);
      n.has(id) ? n.delete(id) : n.add(id);
      return n;
    });
  };

  const toggleAll = () => {
    setSelected(selected.size === posts.length ? new Set() : new Set(posts.map((p) => p.id)));
  };

  const bulkSetStatus = async (status: PostStatus) => {
    setBulkLoading(true);
    try {
      await Promise.all(Array.from(selected).map((id) => api.setStatus(id, status)));
      setPosts((ps) => ps.map((p) => (selected.has(p.id) ? { ...p, status } : p)));
      setSelected(new Set());
    } finally {
      setBulkLoading(false);
    }
  };

  const allChecked = posts.length > 0 && selected.size === posts.length;
  const someChecked = selected.size > 0 && selected.size < posts.length;

  const sharedColProps = { sortCol, sortDir, onSort: toggleSort };

  return (
    <div className="max-w-[1300px] mx-auto p-6">
      <h2 className="text-lg font-semibold text-gray-800 mb-3">Post history</h2>

      {/* Search + date range */}
      <div className="bg-white rounded-lg border border-gray-200 p-3 mb-4 flex flex-wrap items-center gap-2">
        <input
          value={qInput}
          onChange={(e) => setQInput(e.target.value)}
          placeholder="Search posts…"
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
            onClick={() => { setDateFrom(""); setDateTo(""); setQInput(""); }}
            className="text-xs text-gray-400 hover:text-gray-600 px-2 py-1"
          >
            Clear
          </button>
        )}
      </div>

      {/* Table */}
      <div className="bg-white rounded-lg border border-gray-200 overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-gray-100 bg-gray-50 text-left">
              <th className="w-10 px-3 py-3">
                <input
                  type="checkbox"
                  checked={allChecked}
                  ref={(el) => { if (el) el.indeterminate = someChecked; }}
                  onChange={toggleAll}
                  className="accent-linkedin cursor-pointer"
                />
              </th>

              <th className="px-3 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wide">
                Post
              </th>

              {/* Status — filter dropdown */}
              <th className="px-3 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wide relative whitespace-nowrap">
                <button
                  onClick={() => { setStatusMenuOpen((v) => !v); setCatMenuOpen(false); }}
                  className="flex items-center gap-1 hover:text-gray-800"
                >
                  Status
                  {statusFilter && <span className="text-linkedin leading-none">•</span>}
                  <span className="text-gray-400 text-[10px]">▾</span>
                </button>
                {statusMenuOpen && (
                  <>
                    {/* Backdrop closes the menu when clicking anywhere else */}
                    <div className="fixed inset-0 z-10" onClick={() => setStatusMenuOpen(false)} />
                    <div className="absolute top-full left-0 mt-1 bg-white border border-gray-200 rounded-lg shadow-lg z-20 py-1 min-w-[140px]">
                      {STATUS_OPTIONS.map(({ value, label }) => (
                        <button
                          key={value}
                          onClick={(e) => { e.stopPropagation(); setStatusFilter(value); setStatusMenuOpen(false); }}
                          className={`w-full text-left px-3 py-1.5 text-sm hover:bg-gray-50 ${
                            statusFilter === value ? "text-linkedin font-semibold" : "text-gray-700"
                          }`}
                        >
                          {label}
                        </button>
                      ))}
                    </div>
                  </>
                )}
              </th>

              {/* Category — filter dropdown */}
              <th className="px-3 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wide relative whitespace-nowrap">
                <button
                  onClick={() => { setCatMenuOpen((v) => !v); setStatusMenuOpen(false); }}
                  className="flex items-center gap-1 hover:text-gray-800"
                >
                  Category
                  {category && <span className="text-linkedin leading-none">•</span>}
                  <span className="text-gray-400 text-[10px]">▾</span>
                </button>
                {catMenuOpen && (
                  <>
                    <div className="fixed inset-0 z-10" onClick={() => setCatMenuOpen(false)} />
                    <div className="absolute top-full left-0 mt-1 bg-white border border-gray-200 rounded-lg shadow-lg z-20 py-1 min-w-[160px]">
                      {CATEGORIES.map(({ value, label }) => (
                        <button
                          key={value}
                          onClick={(e) => { e.stopPropagation(); setCategory(value); setCatMenuOpen(false); }}
                          className={`w-full text-left px-3 py-1.5 text-sm hover:bg-gray-50 ${
                            category === value ? "text-linkedin font-semibold" : "text-gray-700"
                          }`}
                        >
                          {label}
                        </button>
                      ))}
                    </div>
                  </>
                )}
              </th>

              {/* Date — sortable */}
              <th className="px-3 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wide whitespace-nowrap">
                <SortableHeader col="date" {...sharedColProps}>Date</SortableHeader>
              </th>

              {/* Engagement — all sortable */}
              <th className="px-2 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wide text-right whitespace-nowrap">
                <SortableHeader col="reactions" align="right" {...sharedColProps}>👍</SortableHeader>
              </th>
              <th className="px-2 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wide text-right whitespace-nowrap">
                <SortableHeader col="comments" align="right" {...sharedColProps}>💬</SortableHeader>
              </th>
              <th className="px-2 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wide text-right whitespace-nowrap">
                <SortableHeader col="impressions" align="right" {...sharedColProps}>👁</SortableHeader>
              </th>
              <th className="px-2 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wide text-right whitespace-nowrap">
                <SortableHeader col="reposts" align="right" {...sharedColProps}>🔁</SortableHeader>
              </th>
            </tr>
          </thead>

          <tbody className="divide-y divide-gray-50">
            {sortedPosts.map((p) => (
              <tr
                key={p.id}
                onClick={() => onOpenInEditor?.(p.id)}
                className={`cursor-pointer hover:bg-blue-50 transition-colors ${
                  selected.has(p.id) ? "bg-blue-50" : ""
                }`}
              >
                <td className="w-10 px-3 py-2.5" onClick={(e) => toggleRow(e, p.id)}>
                  <input
                    type="checkbox"
                    checked={selected.has(p.id)}
                    onChange={() => {}}
                    className="accent-linkedin cursor-pointer"
                  />
                </td>

                <td className="px-3 py-2.5 max-w-sm">
                  <div className="flex items-start gap-2">
                    <span className="text-[10px] uppercase tracking-wide text-linkedin font-semibold shrink-0 mt-0.5 leading-tight">
                      {FORMAT_LABELS[p.format_type] ?? p.format_type}
                    </span>
                    <div className="min-w-0">
                      <p className="text-gray-800 text-sm leading-snug line-clamp-2">
                        {p.is_pivotal && "⚡ "}
                        {p.headline}
                      </p>
                      {p.is_update && (
                        <span className="text-[9px] font-bold uppercase tracking-wider px-1 py-0.5 rounded bg-amber-100 text-amber-700 mt-0.5 inline-block">
                          Update
                        </span>
                      )}
                    </div>
                  </div>
                </td>

                <td className="px-3 py-2.5 whitespace-nowrap">
                  <StatusBadge status={p.status} />
                </td>

                <td className="px-3 py-2.5 text-xs text-gray-500 whitespace-nowrap capitalize">
                  {p.category || "—"}
                </td>

                <td className="px-3 py-2.5 text-xs text-gray-400 whitespace-nowrap">
                  {new Date(p.created_at).toLocaleDateString()}
                </td>

                <td className="px-2 py-2.5 text-xs text-gray-500 text-right tabular-nums">
                  {fmt(p.metrics?.reactions)}
                </td>
                <td className="px-2 py-2.5 text-xs text-gray-500 text-right tabular-nums">
                  {fmt(p.metrics?.comments)}
                </td>
                <td className="px-2 py-2.5 text-xs text-gray-500 text-right tabular-nums">
                  {fmt(p.metrics?.impressions)}
                </td>
                <td className="px-2 py-2.5 text-xs text-gray-500 text-right tabular-nums">
                  {fmt(p.metrics?.reposts)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>

        {loading && (
          <div className="text-gray-400 text-sm p-6 text-center">Loading…</div>
        )}
        {!loading && !posts.length && (
          <div className="text-gray-400 text-sm p-6 text-center">
            No posts match these filters.
          </div>
        )}
        {hasMore && !loading && (
          <div className="p-3 border-t border-gray-100">
            <button
              onClick={loadMore}
              className="w-full text-sm py-2 rounded-lg border border-gray-200 text-gray-600 hover:bg-gray-50"
            >
              Load more
            </button>
          </div>
        )}
      </div>

      <p className="text-xs text-gray-400 mt-3">
        Posts are retained for ~2 weeks. Topics posted in the last week are auto-skipped by the
        generator (unless flagged pivotal).
      </p>

      {/* Bulk action bar — sticky bottom */}
      {selected.size > 0 && (
        <div className="fixed bottom-6 left-1/2 -translate-x-1/2 bg-gray-900 text-white rounded-xl shadow-2xl px-5 py-3 flex items-center gap-3 z-30">
          <span className="text-sm font-medium tabular-nums">{selected.size} selected</span>
          <div className="w-px h-4 bg-gray-600" />
          <button
            onClick={() => bulkSetStatus("approved")}
            disabled={bulkLoading}
            className="text-sm px-3 py-1.5 rounded-lg bg-linkedin hover:bg-blue-700 font-semibold disabled:opacity-50 transition-colors"
          >
            Approve
          </button>
          <button
            onClick={() => bulkSetStatus("draft")}
            disabled={bulkLoading}
            className="text-sm px-3 py-1.5 rounded-lg bg-gray-700 hover:bg-gray-600 font-semibold disabled:opacity-50 transition-colors"
          >
            Reset to draft
          </button>
          <button
            onClick={() => setSelected(new Set())}
            className="text-sm text-gray-400 hover:text-white transition-colors ml-1"
          >
            ✕
          </button>
        </div>
      )}
    </div>
  );
}
