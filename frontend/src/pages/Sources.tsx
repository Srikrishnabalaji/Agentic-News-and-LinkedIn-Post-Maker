import { useEffect, useState } from "react";
import { api } from "../api";
import type { RSSSource, SourceSuggestion } from "../types";

function authorityColor(a: number): string {
  if (a >= 0.7) return "bg-green-100 text-green-700";
  if (a >= 0.4) return "bg-amber-100 text-amber-700";
  return "bg-red-100 text-red-700";
}

export default function Sources() {
  const [sources, setSources] = useState<RSSSource[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Add form
  const [name, setName] = useState("");
  const [url, setUrl] = useState("");
  const [category, setCategory] = useState("security");
  const [authority, setAuthority] = useState(0.8);
  const [adding, setAdding] = useState(false);
  const [addError, setAddError] = useState<string | null>(null);

  // Suggestions
  const [suggestTab, setSuggestTab] = useState<"curated" | "ai">("curated");
  const [curated, setCurated] = useState<SourceSuggestion[]>([]);
  const [aiResults, setAiResults] = useState<SourceSuggestion[]>([]);
  const [aiBusy, setAiBusy] = useState(false);
  const [aiError, setAiError] = useState<string | null>(null);

  const load = async () => {
    setLoading(true);
    try {
      setSources(await api.listSources());
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  };

  const loadCurated = async () => {
    try {
      setCurated(await api.curatedSuggestions());
    } catch {
      /* ignore */
    }
  };

  useEffect(() => {
    load();
    loadCurated();
  }, []);

  const toggle = async (s: RSSSource) => {
    const updated = await api.updateSource(s.id, { enabled: !s.enabled });
    setSources((ss) => ss.map((x) => (x.id === s.id ? updated : x)));
  };

  const setAuthorityFor = async (s: RSSSource, value: number) => {
    const updated = await api.updateSource(s.id, { authority: value });
    setSources((ss) => ss.map((x) => (x.id === s.id ? updated : x)));
  };

  const remove = async (s: RSSSource) => {
    try {
      await api.deleteSource(s.id);
      setSources((ss) => ss.filter((x) => x.id !== s.id));
      loadCurated();
    } catch (e) {
      setError((e as Error).message);
    }
  };

  const add = async () => {
    if (!url.trim()) return;
    setAdding(true);
    setAddError(null);
    try {
      const created = await api.addSource({
        name: name.trim() || url.trim(),
        url: url.trim(),
        category,
        authority,
      });
      setSources((ss) => [...ss, created]);
      setName("");
      setUrl("");
      loadCurated();
    } catch (e) {
      // Surface the backend's clear validation message.
      const msg = (e as Error).message;
      setAddError(msg.includes(":") ? msg.split(":").slice(1).join(":").trim() : msg);
    } finally {
      setAdding(false);
    }
  };

  const addFromSuggestion = async (s: SourceSuggestion) => {
    try {
      const created = await api.addSource({
        name: s.name,
        url: s.url,
        category: s.category,
        authority: s.authority,
      });
      setSources((ss) => [...ss, created]);
      setCurated((cs) => cs.filter((c) => c.url !== s.url));
      setAiResults((rs) => rs.filter((c) => c.url !== s.url));
    } catch (e) {
      setError((e as Error).message);
    }
  };

  const runAi = async (cat: string) => {
    setAiBusy(true);
    setAiError(null);
    try {
      setAiResults(await api.aiSuggestions(cat));
    } catch (e) {
      const msg = (e as Error).message;
      setAiError(msg.includes(":") ? msg.split(":").slice(1).join(":").trim() : msg);
    } finally {
      setAiBusy(false);
    }
  };

  const groups = [
    { key: "security", label: "Security" },
    { key: "finance", label: "Finance" },
  ];

  return (
    <div className="max-w-[1100px] mx-auto p-6 grid grid-cols-1 lg:grid-cols-3 gap-6">
      {/* LEFT: current sources */}
      <div className="lg:col-span-2 space-y-5">
        <h2 className="text-lg font-semibold text-gray-800">RSS sources</h2>
        {error && <div className="text-sm text-red-600">{error}</div>}
        {loading ? (
          <div className="text-gray-400 text-sm">Loading…</div>
        ) : (
          groups.map((g) => {
            const list = sources.filter((s) => s.category === g.key);
            return (
              <div key={g.key}>
                <h3 className="text-xs font-semibold text-gray-400 uppercase mb-2">
                  {g.label} · {list.length}
                </h3>
                <div className="space-y-1.5">
                  {list.map((s) => (
                    <div
                      key={s.id}
                      className="flex items-center gap-3 bg-white rounded-lg border border-gray-200 p-2.5"
                    >
                      <label className="flex items-center gap-2 cursor-pointer shrink-0">
                        <input
                          type="checkbox"
                          checked={s.enabled}
                          onChange={() => toggle(s)}
                        />
                      </label>
                      <div className="min-w-0 flex-1">
                        <div className={`text-sm font-medium truncate ${s.enabled ? "text-gray-800" : "text-gray-400 line-through"}`}>
                          {s.name}
                          {!s.is_custom && (
                            <span className="ml-1.5 text-[9px] uppercase tracking-wide text-gray-400">
                              built-in
                            </span>
                          )}
                        </div>
                        <div className="text-[11px] text-gray-400 truncate">{s.url}</div>
                      </div>
                      <span
                        className={`text-[10px] font-semibold px-1.5 py-0.5 rounded ${authorityColor(
                          s.authority
                        )}`}
                      >
                        {s.authority.toFixed(2)}
                      </span>
                      <input
                        type="number"
                        min={0}
                        max={1}
                        step={0.05}
                        defaultValue={s.authority}
                        onBlur={(e) => {
                          const v = Math.max(0, Math.min(1, Number(e.target.value)));
                          if (v !== s.authority) setAuthorityFor(s, v);
                        }}
                        className="w-16 text-xs border border-gray-200 rounded px-1.5 py-0.5"
                        title="Edit authority weight"
                      />
                      {s.is_custom ? (
                        <button
                          onClick={() => remove(s)}
                          className="text-gray-300 hover:text-red-500 text-sm shrink-0"
                          title="Delete source"
                        >
                          🗑
                        </button>
                      ) : (
                        <span
                          className="text-gray-200 text-sm shrink-0 cursor-not-allowed"
                          title="Built-in sources can be disabled but not deleted"
                        >
                          🗑
                        </span>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            );
          })
        )}

        {/* Add form */}
        <div className="bg-white rounded-lg border border-gray-200 p-3">
          <div className="text-xs font-semibold text-gray-500 uppercase mb-2">
            Add a feed
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
            <input
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              placeholder="Feed URL (https://…/feed)"
              className="text-sm border border-gray-200 rounded-md px-2 py-1.5 outline-none focus:border-linkedin sm:col-span-2"
            />
            <input
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Display name (optional)"
              className="text-sm border border-gray-200 rounded-md px-2 py-1.5 outline-none focus:border-linkedin"
            />
            <select
              value={category}
              onChange={(e) => setCategory(e.target.value)}
              className="text-sm border border-gray-200 rounded-md px-2 py-1.5 outline-none focus:border-linkedin"
            >
              <option value="security">Security</option>
              <option value="finance">Finance</option>
            </select>
            <label className="text-xs text-gray-500 flex items-center gap-2 sm:col-span-2">
              Authority {authority.toFixed(2)}
              <input
                type="range"
                min={0}
                max={1}
                step={0.05}
                value={authority}
                onChange={(e) => setAuthority(Number(e.target.value))}
                className="flex-1"
              />
            </label>
          </div>
          {addError && <div className="text-xs text-red-600 mt-1.5">{addError}</div>}
          <button
            onClick={add}
            disabled={adding || !url.trim()}
            className="mt-2 text-sm px-4 py-1.5 rounded-full bg-linkedin text-white font-semibold disabled:opacity-40"
          >
            {adding ? "Validating feed…" : "Add source"}
          </button>
        </div>
      </div>

      {/* RIGHT: suggestions */}
      <div className="space-y-3">
        <h2 className="text-lg font-semibold text-gray-800">Suggestions</h2>
        <div className="flex gap-1">
          {(["curated", "ai"] as const).map((t) => (
            <button
              key={t}
              onClick={() => setSuggestTab(t)}
              className={`text-sm px-3 py-1 rounded-full capitalize ${
                suggestTab === t
                  ? "bg-linkedin text-white"
                  : "bg-white text-gray-600 hover:bg-gray-100"
              }`}
            >
              {t === "ai" ? "AI" : "Curated"}
            </button>
          ))}
        </div>

        {suggestTab === "curated" ? (
          <div className="space-y-1.5">
            {curated.map((s) => (
              <div
                key={s.url}
                className="bg-white rounded-lg border border-gray-200 p-2.5 flex items-start gap-2"
              >
                <div className="min-w-0 flex-1">
                  <div className="text-sm text-gray-800 truncate">{s.name}</div>
                  <div className="text-[11px] text-gray-400 truncate">{s.url}</div>
                  <span className="text-[10px] text-gray-400 capitalize">
                    {s.category} · {s.authority.toFixed(2)}
                  </span>
                </div>
                <button
                  onClick={() => addFromSuggestion(s)}
                  className="text-xs text-linkedin font-semibold hover:underline shrink-0"
                >
                  + Add
                </button>
              </div>
            ))}
            {!curated.length && (
              <div className="text-xs text-gray-400 py-3 text-center">
                All curated feeds already added.
              </div>
            )}
          </div>
        ) : (
          <div className="space-y-2">
            <div className="flex gap-2">
              <button
                onClick={() => runAi("security")}
                disabled={aiBusy}
                className="text-xs px-3 py-1 rounded-full bg-gray-100 hover:bg-gray-200 disabled:opacity-50"
              >
                Suggest Security
              </button>
              <button
                onClick={() => runAi("finance")}
                disabled={aiBusy}
                className="text-xs px-3 py-1 rounded-full bg-gray-100 hover:bg-gray-200 disabled:opacity-50"
              >
                Suggest Finance
              </button>
            </div>
            {aiBusy && <div className="text-xs text-gray-400">Asking Gemini…</div>}
            {aiError && <div className="text-xs text-red-600">{aiError}</div>}
            <div className="space-y-1.5">
              {aiResults.map((s) => (
                <div
                  key={s.url}
                  className="bg-white rounded-lg border border-gray-200 p-2.5 flex items-start gap-2"
                >
                  <div className="min-w-0 flex-1">
                    <div className="text-sm text-gray-800 truncate">{s.name}</div>
                    <div className="text-[11px] text-gray-400 truncate">{s.url}</div>
                    <span className="text-[10px] text-gray-400 capitalize">
                      {s.category} · {s.authority.toFixed(2)}
                    </span>
                  </div>
                  <button
                    onClick={() => addFromSuggestion(s)}
                    className="text-xs text-linkedin font-semibold hover:underline shrink-0"
                  >
                    + Add
                  </button>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
