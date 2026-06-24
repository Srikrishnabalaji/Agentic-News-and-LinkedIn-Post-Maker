import { useEffect, useState } from "react";
import { api } from "../api";
import type { Post, StoryCandidate } from "../types";

interface Props {
  category: string; // "security" | "finance"
  onGenerated: (posts: Post[]) => void;
  onClose: () => void;
}

function CandidateCard({
  c,
  checked,
  onToggle,
  onDismiss,
}: {
  c: StoryCandidate;
  checked: boolean;
  onToggle: () => void;
  onDismiss: () => void;
}) {
  return (
    <div className="flex gap-2 p-2 rounded-md border border-gray-100 hover:border-gray-200 bg-white">
      <input
        type="checkbox"
        checked={checked}
        onChange={onToggle}
        className="mt-1 shrink-0"
      />
      <div className="min-w-0 flex-1">
        <div className="text-sm text-gray-800 leading-snug">{c.title}</div>
        {c.summary && (
          <div className="text-[11px] text-gray-500 line-clamp-2 mt-0.5">
            {c.summary}
          </div>
        )}
        <div className="flex items-center gap-2 mt-1 text-[10px] text-gray-400">
          <span>{c.source_name}</span>
          {c.published_at && (
            <span>· {new Date(c.published_at).toLocaleDateString()}</span>
          )}
        </div>
      </div>
      <button
        onClick={onDismiss}
        title="Dismiss"
        className="shrink-0 self-start text-gray-300 hover:text-red-500 text-sm px-1"
      >
        ✕
      </button>
    </div>
  );
}

export default function CandidateDrawer({ category, onGenerated, onClose }: Props) {
  const [candidates, setCandidates] = useState<StoryCandidate[]>([]);
  const [dismissed, setDismissed] = useState<StoryCandidate[]>([]);
  const [dismissedCount, setDismissedCount] = useState(0);
  const [hasMore, setHasMore] = useState(false);
  const [selected, setSelected] = useState<Set<number>>(new Set());
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [showDismissed, setShowDismissed] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);
    api
      .candidates(category)
      .then((r) => {
        setCandidates(r.candidates);
        setDismissedCount(r.dismissed_count);
        setHasMore(r.has_more);
      })
      .catch((e) => setError((e as Error).message))
      .finally(() => setLoading(false));
  }, [category]);

  const toggle = (id: number) =>
    setSelected((s) => {
      const n = new Set(s);
      n.has(id) ? n.delete(id) : n.add(id);
      return n;
    });

  const showMore = async () => {
    setLoadingMore(true);
    setError(null);
    try {
      const r = await api.moreCandidates(category);
      setCandidates(r.candidates);
      setDismissedCount(r.dismissed_count);
      setHasMore(r.has_more);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoadingMore(false);
    }
  };

  const dismiss = async (id: number) => {
    setCandidates((cs) => cs.filter((c) => c.id !== id));
    setSelected((s) => {
      const n = new Set(s);
      n.delete(id);
      return n;
    });
    setDismissedCount((n) => n + 1);
    try {
      await api.dismissCandidate(id);
      if (showDismissed) {
        setDismissed(await api.dismissedCandidates(category));
      }
    } catch {
      /* best-effort; next fetch reconciles */
    }
  };

  const toggleDismissed = async () => {
    if (!showDismissed) {
      setDismissed(await api.dismissedCandidates(category));
    }
    setShowDismissed((v) => !v);
  };

  const undismiss = async (id: number) => {
    try {
      const restored = await api.undismissCandidate(id);
      setDismissed((ds) => ds.filter((d) => d.id !== id));
      setDismissedCount((n) => Math.max(0, n - 1));
      setCandidates((cs) =>
        cs.some((c) => c.id === id) ? cs : [restored, ...cs]
      );
    } catch {
      /* ignore */
    }
  };

  const generate = async () => {
    if (!selected.size) return;
    setGenerating(true);
    setError(null);
    try {
      const ids = [...selected];
      const posts = await api.generateCandidates(ids);
      onGenerated(posts);
      // Remove the now-generated candidates from the list.
      setCandidates((cs) => cs.filter((c) => !selected.has(c.id)));
      setSelected(new Set());
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setGenerating(false);
    }
  };

  return (
    <div className="mt-2 rounded-lg border border-gray-200 bg-gray-50/70 p-3">
      <div className="flex items-center justify-between mb-2">
        <span className="text-xs font-semibold text-gray-600 uppercase tracking-wide">
          Story candidates
        </span>
        <button
          onClick={onClose}
          className="text-gray-400 hover:text-gray-600 text-xs"
        >
          ✕ close
        </button>
      </div>

      {loading ? (
        <div className="text-xs text-gray-400 py-3 text-center">Loading…</div>
      ) : (
        <>
          <div className="space-y-1.5 max-h-80 overflow-y-auto">
            {candidates.map((c) => (
              <CandidateCard
                key={c.id}
                c={c}
                checked={selected.has(c.id)}
                onToggle={() => toggle(c.id)}
                onDismiss={() => dismiss(c.id)}
              />
            ))}
            {!candidates.length && (
              <div className="text-xs text-gray-400 py-3 text-center">
                No candidates right now. Try “Show more”.
              </div>
            )}
          </div>

          {error && <div className="text-xs text-red-600 mt-2">{error}</div>}

          <div className="flex flex-wrap items-center gap-2 mt-2">
            <button
              onClick={generate}
              disabled={!selected.size || generating}
              className="text-xs px-3 py-1 rounded-full bg-linkedin text-white font-semibold disabled:opacity-40"
            >
              {generating
                ? `Generating ${selected.size}…`
                : `Generate selected (${selected.size})`}
            </button>
            <button
              onClick={showMore}
              disabled={loadingMore}
              className="text-xs px-3 py-1 rounded-full bg-gray-100 hover:bg-gray-200 disabled:opacity-50"
            >
              {loadingMore
                ? "Finding…"
                : hasMore
                ? "Show more candidates"
                : "Scrape more stories"}
            </button>
          </div>

          {/* Dismissed recovery */}
          <div className="mt-3 border-t border-gray-200 pt-2">
            <button
              onClick={toggleDismissed}
              className="text-xs text-gray-500 hover:text-gray-700"
            >
              {showDismissed ? "▼" : "▶"} Dismissed ({dismissedCount})
            </button>
            {showDismissed && (
              <div className="space-y-1.5 mt-2">
                {dismissed.map((c) => (
                  <div
                    key={c.id}
                    className="flex gap-2 items-start p-2 rounded-md border border-gray-100 bg-white"
                  >
                    <div className="min-w-0 flex-1">
                      <div className="text-sm text-gray-700 leading-snug">
                        {c.title}
                      </div>
                      <div className="text-[10px] text-gray-400 mt-0.5">
                        {c.source_name}
                      </div>
                    </div>
                    <button
                      onClick={() => undismiss(c.id)}
                      className="shrink-0 text-[11px] text-linkedin hover:underline"
                    >
                      Undo dismiss
                    </button>
                  </div>
                ))}
                {!dismissed.length && (
                  <div className="text-xs text-gray-400 py-2 text-center">
                    Nothing dismissed.
                  </div>
                )}
              </div>
            )}
          </div>
        </>
      )}
    </div>
  );
}
