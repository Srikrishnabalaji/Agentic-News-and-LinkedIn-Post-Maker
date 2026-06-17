import { useEffect, useState } from "react";
import { api } from "../api";
import StatusBadge from "../components/StatusBadge";
import { FORMAT_LABELS, type Post, type PostStatus } from "../types";

const FILTERS: (PostStatus | "all")[] = ["all", "draft", "approved", "posted"];

export default function History() {
  const [posts, setPosts] = useState<Post[]>([]);
  const [filter, setFilter] = useState<PostStatus | "all">("all");
  const [open, setOpen] = useState<number | null>(null);

  useEffect(() => {
    api.history(filter === "all" ? undefined : filter).then(setPosts);
  }, [filter]);

  return (
    <div className="max-w-4xl mx-auto p-6">
      <div className="flex items-center gap-2 mb-4">
        <h2 className="text-lg font-semibold text-gray-800 mr-2">
          Post history
        </h2>
        {FILTERS.map((f) => (
          <button
            key={f}
            onClick={() => setFilter(f)}
            className={`text-sm px-3 py-1 rounded-full capitalize ${
              filter === f
                ? "bg-linkedin text-white"
                : "bg-white text-gray-600 hover:bg-gray-100"
            }`}
          >
            {f}
          </button>
        ))}
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
              </span>
              <span className="text-xs text-gray-400">
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
                {p.source_url && (
                  <a
                    href={p.source_url}
                    target="_blank"
                    rel="noreferrer"
                    className="text-xs text-gray-400 hover:underline mt-2 inline-block"
                  >
                    Source: {p.source_name} ↗
                  </a>
                )}
              </div>
            )}
          </div>
        ))}
        {!posts.length && (
          <div className="text-gray-400 text-sm p-6 text-center">
            No posts in this view yet.
          </div>
        )}
      </div>
    </div>
  );
}
