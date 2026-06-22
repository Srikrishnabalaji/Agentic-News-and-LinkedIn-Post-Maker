import { useEffect, useState } from "react";
import { api } from "../api";
import { FORMAT_LABELS, type Post } from "../types";
import HashtagEditor from "./HashtagEditor";
import ImagePicker from "./ImagePicker";
import LinkedInPreview from "./LinkedInPreview";
import StatusBadge from "./StatusBadge";

interface Props {
  post: Post;
  onChange: (p: Post) => void;
  readOnly?: boolean;
}

export default function PostEditor({ post, onChange, readOnly }: Props) {
  const [body, setBody] = useState(post.body);
  const [headline, setHeadline] = useState(post.headline);
  const [hashtags, setHashtags] = useState<string[]>(post.hashtags);
  const [dirty, setDirty] = useState(false);
  const [busy, setBusy] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  // Reset local state when the selected post changes.
  useEffect(() => {
    setBody(post.body);
    setHeadline(post.headline);
    setHashtags(post.hashtags);
    setDirty(false);
  }, [post.id]);

  const save = async () => {
    setBusy("save");
    try {
      const updated = await api.updatePost(post.id, { body, headline, hashtags });
      onChange(updated);
      setDirty(false);
    } finally {
      setBusy(null);
    }
  };

  const doAction = async (label: string, fn: () => Promise<Post>) => {
    setBusy(label);
    try {
      const updated = await fn();
      onChange(updated);
      setBody(updated.body);
      setHeadline(updated.headline);
      setHashtags(updated.hashtags);
      setDirty(false);
    } finally {
      setBusy(null);
    }
  };

  const copy = async () => {
    const tagLine = hashtags.map((h) => `#${h}`).join(" ");
    await navigator.clipboard.writeText(tagLine ? `${body}\n\n${tagLine}` : body);
    setCopied(true);
    setTimeout(() => setCopied(false), 1800);
  };

  const setField = <T,>(setter: (v: T) => void) => (v: T) => {
    setter(v);
    setDirty(true);
  };

  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
      {/* LEFT: editor */}
      <div className="space-y-4">
        <div className="flex items-center justify-between gap-2">
          <span className="text-xs font-semibold uppercase tracking-wide text-linkedin">
            {FORMAT_LABELS[post.format_type] ?? post.format_type}
            {post.is_pivotal && " · ⚡ Pivotal"}
          </span>
          <StatusBadge status={post.status} />
        </div>

        <input
          value={headline}
          onChange={(e) => setField(setHeadline)(e.target.value)}
          disabled={readOnly}
          className="w-full font-semibold text-gray-900 border-b border-gray-200 focus:border-linkedin outline-none pb-1"
        />

        {post.source_url && (
          <a
            href={post.source_url}
            target="_blank"
            rel="noreferrer"
            className="text-xs text-linkedin hover:underline inline-block"
          >
            📰 Read source: {post.source_name} ↗
          </a>
        )}

        <div>
          <div className="flex items-center justify-between mb-1">
            <label className="text-xs font-semibold text-gray-500">
              POST TEXT
            </label>
            <div className="flex gap-1">
              {(["punchy", "formal", "shorter"] as const).map((tone) => (
                <button
                  key={tone}
                  onClick={() => doAction(`tone-${tone}`, () => api.rephrase(post.id, tone))}
                  disabled={!!busy || readOnly}
                  className="text-xs px-2 py-0.5 rounded bg-gray-100 hover:bg-gray-200 capitalize disabled:opacity-50"
                  title={`AI: make it ${tone}`}
                >
                  {busy === `tone-${tone}` ? "…" : `✦ ${tone}`}
                </button>
              ))}
            </div>
          </div>
          <textarea
            value={body}
            onChange={(e) => setField(setBody)(e.target.value)}
            disabled={readOnly}
            rows={12}
            className="w-full text-sm border border-gray-200 rounded-lg p-3 outline-none focus:border-linkedin resize-y leading-relaxed"
          />
        </div>

        <ImagePicker
          key={`${post.id}-${post.image_options?.[0]?.url ?? ''}`}
          recommended={post.image_recommended}
          reason={post.image_reason}
          currentUrl={post.image_url}
          options={post.image_options}
          sourceName={post.source_name}
          onPick={(url, attribution) =>
            doAction("image", () =>
              api.updatePost(post.id, {
                image_url: url,
                image_attribution: attribution,
              })
            )
          }
        />

        <HashtagEditor tags={hashtags} onChange={setField(setHashtags)} />

        {!readOnly && (
          <div className="flex flex-wrap gap-2 pt-2 border-t border-gray-100">
            <button
              onClick={save}
              disabled={!dirty || !!busy}
              className="text-sm px-4 py-1.5 rounded-full bg-linkedin text-white font-semibold disabled:opacity-40"
            >
              {busy === "save" ? "Saving…" : dirty ? "Save edits" : "Saved"}
            </button>
            <button
              onClick={() => doAction("regen", () => api.regenerate(post.id))}
              disabled={!!busy}
              className="text-sm px-4 py-1.5 rounded-full bg-gray-100 hover:bg-gray-200 disabled:opacity-50"
            >
              {busy === "regen" ? "Regenerating…" : "↻ Regenerate"}
            </button>
            <button
              onClick={copy}
              className="text-sm px-4 py-1.5 rounded-full bg-gray-100 hover:bg-gray-200"
            >
              {copied ? "✓ Copied!" : "⧉ Copy text"}
            </button>
            {post.image_url && (
              <a
                href={post.image_url}
                target="_blank"
                rel="noreferrer"
                className="text-sm px-4 py-1.5 rounded-full bg-gray-100 hover:bg-gray-200"
              >
                ⬇ Open image
              </a>
            )}
          </div>
        )}

        {!readOnly && (
          <div className="flex flex-wrap gap-2">
            {post.status === "draft" && (
              <button
                onClick={() => doAction("approve", () => api.setStatus(post.id, "approved"))}
                disabled={!!busy}
                className="text-sm px-4 py-1.5 rounded-full border border-linkedin text-linkedin font-semibold disabled:opacity-50"
              >
                Mark approved
              </button>
            )}
            {post.status !== "posted" && (
              <button
                onClick={() => doAction("posted", () => api.setStatus(post.id, "posted"))}
                disabled={!!busy}
                className="text-sm px-4 py-1.5 rounded-full border border-green-600 text-green-700 font-semibold disabled:opacity-50"
              >
                Mark as posted
              </button>
            )}
            {post.status !== "draft" && (
              <button
                onClick={() => doAction("revert", () => api.setStatus(post.id, "draft"))}
                disabled={!!busy}
                className="text-sm px-4 py-1.5 rounded-full border border-gray-400 text-gray-600 font-semibold disabled:opacity-50"
              >
                ↩ Revert to draft
              </button>
            )}
          </div>
        )}
      </div>

      {/* RIGHT: live preview */}
      <div className="lg:sticky lg:top-6 self-start w-full">
        <div className="text-xs font-semibold text-gray-400 mb-2 uppercase">
          LinkedIn preview
        </div>
        <LinkedInPreview
          body={body}
          hashtags={hashtags}
          imageUrl={post.image_url}
          imageAttribution={post.image_attribution}
        />
      </div>
    </div>
  );
}
