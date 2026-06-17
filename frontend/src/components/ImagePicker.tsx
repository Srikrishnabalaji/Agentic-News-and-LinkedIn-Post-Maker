import { useRef, useState } from "react";
import { api } from "../api";
import type { ImageOption } from "../types";

interface Props {
  recommended: boolean;
  reason: string | null;
  currentUrl: string | null;
  options: ImageOption[];
  sourceName: string | null;
  onPick: (url: string | null, attribution: string | null) => void;
}

function Thumb({
  opt,
  selected,
  onClick,
}: {
  opt: ImageOption;
  selected: boolean;
  onClick: () => void;
}) {
  return (
    <button
      onClick={onClick}
      title={`${opt.attribution}\n${opt.license}`}
      className={`relative shrink-0 rounded overflow-hidden border-2 transition-all ${
        selected
          ? "border-linkedin shadow-md"
          : "border-transparent hover:border-gray-300"
      }`}
      style={{ width: 80, height: 64 }}
    >
      <img src={opt.thumb} alt="" className="w-full h-full object-cover" />
      {opt.source === "Article" && (
        <span className="absolute bottom-0 inset-x-0 bg-amber-500/90 text-white text-[9px] leading-tight text-center py-0.5">
          verify rights
        </span>
      )}
      {opt.source === "Upload" && (
        <span className="absolute bottom-0 inset-x-0 bg-linkedin/80 text-white text-[9px] leading-tight text-center py-0.5">
          uploaded
        </span>
      )}
    </button>
  );
}

export default function ImagePicker({
  recommended,
  reason,
  currentUrl,
  options,
  sourceName,
  onPick,
}: Props) {
  // originalOptions is frozen at mount — always available to reset to.
  const [originalOptions] = useState<ImageOption[]>(options);
  const [displayedOptions, setDisplayedOptions] = useState<ImageOption[]>(options);
  const [hasSearched, setHasSearched] = useState(false);
  const [query, setQuery] = useState("");
  const [searching, setSearching] = useState(false);
  const [loadingMore, setLoadingMore] = useState(false);
  const [searchPage, setSearchPage] = useState(1);
  const [uploading, setUploading] = useState(false);
  const [expanded, setExpanded] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // All known options: original + any new ones from search/upload,
  // de-duped by URL. Used in the expanded modal.
  const [allKnownOptions, setAllKnownOptions] = useState<ImageOption[]>(options);

  const mergeNew = (incoming: ImageOption[]) => {
    setAllKnownOptions((prev) => {
      const urls = new Set(prev.map((o) => o.url));
      return [...prev, ...incoming.filter((o) => !urls.has(o.url))];
    });
  };

  const search = async () => {
    const q = query.trim();
    if (!q) return;
    setSearching(true);
    try {
      const found = await api.searchImages(q, sourceName ?? "", 1);
      setDisplayedOptions(found);
      mergeNew(found);
      setHasSearched(true);
      setSearchPage(1);
    } finally {
      setSearching(false);
    }
  };

  const loadMore = async () => {
    const q = query.trim();
    if (!q) return;
    const nextPage = searchPage + 1;
    setLoadingMore(true);
    try {
      const found = await api.searchImages(q, sourceName ?? "", nextPage);
      if (found.length > 0) {
        setDisplayedOptions((prev) => [...prev, ...found]);
        mergeNew(found);
        setSearchPage(nextPage);
      }
    } finally {
      setLoadingMore(false);
    }
  };

  const resetToOriginal = () => {
    setDisplayedOptions(originalOptions);
    setHasSearched(false);
    setQuery("");
    setSearchPage(1);
  };

  const handleUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploading(true);
    try {
      const opt = await api.uploadImage(file);
      onPick(opt.url, opt.attribution);
      setDisplayedOptions((prev) => [opt, ...prev]);
      mergeNew([opt]);
    } catch (err) {
      alert(`Upload failed: ${(err as Error).message}`);
    } finally {
      setUploading(false);
      // Reset input so the same file can be re-selected if needed.
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  };

  const selectedOpt =
    allKnownOptions.find((o) => o.url === currentUrl) ??
    displayedOptions.find((o) => o.url === currentUrl);

  // Options shown in the compact strip (max 4 + "No image" button).
  const stripOptions = displayedOptions.slice(0, 4);

  return (
    <div>
      {/* Header row */}
      <div className="flex items-center justify-between mb-1">
        <label className="text-xs font-semibold text-gray-500">IMAGE</label>
        <span
          className={`text-xs px-2 py-0.5 rounded-full ${
            recommended ? "bg-green-50 text-green-700" : "bg-gray-100 text-gray-500"
          }`}
          title={reason ?? ""}
        >
          {recommended ? "AI: recommended" : "AI: not needed"}
        </span>
      </div>
      {reason && <p className="text-xs text-gray-400 mb-2">{reason}</p>}

      {/* Compact strip */}
      <div className="flex items-center gap-2 mb-2 flex-wrap">
        {/* No-image option */}
        <button
          onClick={() => onPick(null, null)}
          className={`shrink-0 w-20 h-16 rounded border-2 text-xs flex items-center justify-center ${
            !currentUrl
              ? "border-linkedin text-linkedin font-semibold"
              : "border-gray-200 text-gray-400"
          }`}
        >
          No image
        </button>

        {stripOptions.map((o) => (
          <Thumb
            key={o.url}
            opt={o}
            selected={currentUrl === o.url}
            onClick={() => onPick(o.url, o.attribution)}
          />
        ))}

        {/* "Show all" button — opens expanded modal */}
        <button
          onClick={() => setExpanded(true)}
          className="shrink-0 w-20 h-16 rounded border-2 border-dashed border-gray-300 text-gray-400 text-xs flex flex-col items-center justify-center gap-1 hover:border-linkedin hover:text-linkedin transition-colors"
        >
          <span className="text-lg leading-none">⊞</span>
          <span>Show all</span>
        </button>
      </div>

      {/* Attribution / license for currently selected */}
      {selectedOpt && (
        <p className="text-[11px] text-gray-400 mb-2 leading-tight">
          {selectedOpt.license}
          {selectedOpt.source_url && (
            <>
              {" · "}
              <a
                href={selectedOpt.source_url}
                target="_blank"
                rel="noreferrer"
                className="underline hover:text-gray-600"
              >
                source ↗
              </a>
            </>
          )}
        </p>
      )}

      {/* Search bar + back + upload */}
      <div className="flex gap-2 flex-wrap">
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && search()}
          placeholder="Search free images…"
          className="flex-1 min-w-0 text-sm px-2 py-1 border border-gray-200 rounded outline-none focus:border-linkedin"
        />
        <button
          onClick={search}
          disabled={searching}
          className="text-sm px-3 py-1 rounded bg-gray-100 hover:bg-gray-200 disabled:opacity-50"
        >
          {searching ? "…" : "Search"}
        </button>
        {hasSearched && (
          <button
            onClick={resetToOriginal}
            className="text-sm px-3 py-1 rounded border border-gray-200 text-gray-500 hover:bg-gray-50"
            title="Go back to AI suggestions"
          >
            ← Suggestions
          </button>
        )}
        {/* Upload from computer */}
        <button
          onClick={() => fileInputRef.current?.click()}
          disabled={uploading}
          className="text-sm px-3 py-1 rounded bg-gray-100 hover:bg-gray-200 disabled:opacity-50"
          title="Upload an image from your computer"
        >
          {uploading ? "Uploading…" : "⬆ Upload"}
        </button>
        <input
          ref={fileInputRef}
          type="file"
          accept="image/jpeg,image/png,image/gif,image/webp"
          className="hidden"
          onChange={handleUpload}
        />
      </div>

      {/* ── Expanded modal ── */}
      {expanded && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/50"
          onClick={() => setExpanded(false)}
        >
          <div
            className="bg-white rounded-2xl shadow-2xl w-[90vw] max-w-2xl max-h-[85vh] flex flex-col overflow-hidden"
            onClick={(e) => e.stopPropagation()}
          >
            {/* Modal header */}
            <div className="flex items-center justify-between px-5 py-3 border-b border-gray-100">
              <span className="font-semibold text-gray-800">Choose an image</span>
              <button
                onClick={() => setExpanded(false)}
                className="text-gray-400 hover:text-gray-700 text-xl leading-none"
              >
                ×
              </button>
            </div>

            {/* Search inside modal */}
            <div className="px-5 py-3 border-b border-gray-100 flex gap-2">
              <input
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && search()}
                placeholder="Search free images…"
                className="flex-1 text-sm px-3 py-1.5 border border-gray-200 rounded-lg outline-none focus:border-linkedin"
              />
              <button
                onClick={search}
                disabled={searching}
                className="text-sm px-4 py-1.5 rounded-lg bg-linkedin text-white font-semibold disabled:opacity-50"
              >
                {searching ? "…" : "Search"}
              </button>
              {hasSearched && (
                <button
                  onClick={resetToOriginal}
                  className="text-sm px-3 py-1.5 rounded-lg border border-gray-200 text-gray-500 hover:bg-gray-50"
                >
                  ← Back
                </button>
              )}
              <button
                onClick={() => { setExpanded(false); fileInputRef.current?.click(); }}
                disabled={uploading}
                className="text-sm px-3 py-1.5 rounded-lg bg-gray-100 hover:bg-gray-200 disabled:opacity-50"
              >
                ⬆ Upload
              </button>
            </div>

            {/* Scrollable grid */}
            <div className="overflow-y-auto p-5 flex flex-col gap-3">
              <div className="grid grid-cols-3 gap-3">
                {/* No-image tile */}
                <button
                  onClick={() => { onPick(null, null); setExpanded(false); }}
                  className={`h-36 rounded-xl border-2 text-sm flex items-center justify-center ${
                    !currentUrl
                      ? "border-linkedin text-linkedin font-semibold bg-blue-50"
                      : "border-dashed border-gray-200 text-gray-400 hover:border-gray-400"
                  }`}
                >
                  No image
                </button>

                {allKnownOptions.map((o) => (
                  <button
                    key={o.url}
                    onClick={() => { onPick(o.url, o.attribution); setExpanded(false); }}
                    title={`${o.attribution}\n${o.license}`}
                    className={`relative h-36 rounded-xl overflow-hidden border-2 transition-all ${
                      currentUrl === o.url
                        ? "border-linkedin shadow-lg"
                        : "border-transparent hover:border-gray-300"
                    }`}
                  >
                    <img src={o.thumb} alt="" className="w-full h-full object-cover" />
                    <div className="absolute inset-x-0 bottom-0 bg-gradient-to-t from-black/60 to-transparent px-2 py-1.5">
                      <p className="text-white text-[10px] leading-tight line-clamp-2">
                        {o.attribution}
                      </p>
                      {o.source === "Article" && (
                        <p className="text-amber-300 text-[10px] font-semibold">
                          verify rights
                        </p>
                      )}
                    </div>
                  </button>
                ))}
              </div>

              {/* Load More — only shown after a search */}
              {hasSearched && (
                <button
                  onClick={loadMore}
                  disabled={loadingMore}
                  className="w-full py-2.5 rounded-xl border border-gray-200 text-sm text-gray-500 hover:bg-gray-50 hover:border-gray-400 disabled:opacity-50 transition-colors"
                >
                  {loadingMore ? "Loading…" : "Load more images"}
                </button>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
