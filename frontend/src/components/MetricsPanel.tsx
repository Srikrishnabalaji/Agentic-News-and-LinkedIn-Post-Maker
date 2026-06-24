import { useEffect, useState } from "react";
import { api } from "../api";
import type { Post, PostMetrics } from "../types";

interface Props {
  post: Post;
  onSaved?: (m: PostMetrics) => void;
}

type MetricKey = "impressions" | "reactions" | "comments" | "reposts";

const FIELDS: { key: MetricKey; label: string }[] = [
  { key: "impressions", label: "Impressions" },
  { key: "reactions", label: "Reactions" },
  { key: "comments", label: "Comments" },
  { key: "reposts", label: "Reposts" },
];

const blank = { impressions: 0, reactions: 0, comments: 0, reposts: 0 };

// Manual performance entry for a posted draft. Designed so the future
// LinkedIn API can replace manual input without UI changes.
export default function MetricsPanel({ post, onSaved }: Props) {
  const [vals, setVals] = useState<Record<MetricKey, number>>({ ...blank });
  const [busy, setBusy] = useState(false);
  const [saved, setSaved] = useState(false);
  const [dirty, setDirty] = useState(false);

  useEffect(() => {
    const m = post.metrics;
    setVals({
      impressions: m?.impressions ?? 0,
      reactions: m?.reactions ?? 0,
      comments: m?.comments ?? 0,
      reposts: m?.reposts ?? 0,
    });
    setDirty(false);
  }, [post.id, post.metrics]);

  const set = (k: MetricKey, raw: string) => {
    const n = Math.max(0, Math.floor(Number(raw) || 0));
    setVals((s) => ({ ...s, [k]: n }));
    setDirty(true);
    setSaved(false);
  };

  const save = async () => {
    setBusy(true);
    try {
      const m = await api.saveMetrics(post.id, vals);
      onSaved?.(m);
      setDirty(false);
      setSaved(true);
      setTimeout(() => setSaved(false), 1800);
    } finally {
      setBusy(false);
    }
  };

  const engagement = vals.reactions + vals.comments * 2 + vals.reposts * 3;

  return (
    <div className="rounded-lg border border-gray-200 bg-gray-50/60 p-3">
      <div className="flex items-center justify-between mb-2">
        <span className="text-xs font-semibold text-gray-500 uppercase tracking-wide">
          Performance
        </span>
        <span className="text-[11px] text-gray-400">
          Engagement score {engagement.toLocaleString()}
        </span>
      </div>
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
        {FIELDS.map((f) => (
          <label key={f.key} className="block">
            <span className="text-[11px] text-gray-500">{f.label}</span>
            <input
              type="number"
              min={0}
              value={vals[f.key]}
              onChange={(e) => set(f.key, e.target.value)}
              className="mt-0.5 w-full text-sm border border-gray-200 rounded-md px-2 py-1 outline-none focus:border-linkedin"
            />
          </label>
        ))}
      </div>
      <div className="flex items-center gap-2 mt-2">
        <button
          onClick={save}
          disabled={busy || !dirty}
          className="text-xs px-3 py-1 rounded-full bg-linkedin text-white font-semibold disabled:opacity-40"
        >
          {busy ? "Saving…" : saved ? "✓ Saved" : dirty ? "Save metrics" : "Saved"}
        </button>
        {post.metrics?.updated_at && (
          <span className="text-[11px] text-gray-400">
            Updated {new Date(post.metrics.updated_at).toLocaleString()}
          </span>
        )}
      </div>
    </div>
  );
}
