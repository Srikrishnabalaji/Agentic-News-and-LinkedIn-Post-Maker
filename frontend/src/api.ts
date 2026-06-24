import type {
  CandidateList,
  ImageOption,
  LiveSearchResult,
  Post,
  PostMetrics,
  PostStatus,
  RSSSource,
  Run,
  SourceSuggestion,
  StoryCandidate,
} from "./types";

export interface HistoryParams {
  status?: PostStatus;
  category?: string;
  date_from?: string;
  date_to?: string;
  q?: string;
  sort_by?: "date" | "date_asc" | "engagement";
  limit?: number;
  offset?: number;
}

function qs(params: Record<string, string | number | undefined>): string {
  const parts = Object.entries(params)
    .filter(([, v]) => v !== undefined && v !== "" && v !== null)
    .map(([k, v]) => `${k}=${encodeURIComponent(String(v))}`);
  return parts.length ? `?${parts.join("&")}` : "";
}

const BASE = (import.meta.env.VITE_API_BASE as string | undefined) ?? "/api";

async function req<T>(path: string, opts: RequestInit = {}): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...opts,
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`${res.status}: ${text}`);
  }
  return res.status === 204 ? (undefined as T) : res.json();
}

export const api = {
  health: () => req<{ status: string; anthropic: boolean; email: boolean }>("/health"),
  today: () => req<Post[]>("/posts/today"),
  history: (params: HistoryParams = {}) =>
    req<Post[]>(`/posts/history${qs(params as Record<string, string | number | undefined>)}`),
  getPost: (id: number) => req<Post>(`/posts/${id}`),
  getMetrics: (id: number) => req<PostMetrics>(`/posts/${id}/metrics`),
  saveMetrics: (id: number, m: Partial<Omit<PostMetrics, "post_id" | "updated_at">>) =>
    req<PostMetrics>(`/posts/${id}/metrics`, {
      method: "PUT",
      body: JSON.stringify(m),
    }),
  updatePost: (id: number, body: Partial<Post>) =>
    req<Post>(`/posts/${id}`, { method: "PUT", body: JSON.stringify(body) }),
  setStatus: (id: number, status: PostStatus) =>
    req<Post>(`/posts/${id}/status`, {
      method: "POST",
      body: JSON.stringify({ status }),
    }),
  regenerate: (id: number) =>
    req<Post>(`/posts/${id}/regenerate`, { method: "POST" }),
  rephrase: (id: number, tone: "punchy" | "formal" | "shorter") =>
    req<Post>(`/posts/${id}/rephrase?tone=${tone}`, { method: "POST" }),
  searchImages: (query: string, source_name = "", page = 1) =>
    req<ImageOption[]>("/images/search", {
      method: "POST",
      body: JSON.stringify({ query, source_name, page }),
    }),
  uploadImage: async (file: File): Promise<ImageOption> => {
    const form = new FormData();
    form.append("file", file);
    const res = await fetch(`${BASE}/images/upload`, { method: "POST", body: form });
    if (!res.ok) throw new Error(`${res.status}: ${await res.text()}`);
    return res.json();
  },
  latestRun: () => req<Run | null>("/runs/latest"),
  triggerRun: () => req<{ status: string }>("/runs/trigger", { method: "POST" }),

  // --- Sources ---
  listSources: () => req<RSSSource[]>("/sources"),
  addSource: (body: {
    name: string;
    url: string;
    category: string;
    authority: number;
    audience?: string;
  }) => req<RSSSource>("/sources", { method: "POST", body: JSON.stringify(body) }),
  updateSource: (
    id: number,
    body: Partial<Pick<RSSSource, "name" | "authority" | "enabled">>
  ) => req<RSSSource>(`/sources/${id}`, { method: "PATCH", body: JSON.stringify(body) }),
  deleteSource: (id: number) =>
    req<void>(`/sources/${id}`, { method: "DELETE" }),
  curatedSuggestions: (category?: string) =>
    req<SourceSuggestion[]>(`/sources/suggestions/curated${qs({ category })}`),
  aiSuggestions: (category: string) =>
    req<SourceSuggestion[]>("/sources/suggestions/ai", {
      method: "POST",
      body: JSON.stringify({ category }),
    }),

  // --- Story candidates ---
  candidates: (category: string, limit = 5) =>
    req<CandidateList>(`/candidates${qs({ category, limit })}`),
  moreCandidates: (category: string, limit = 5) =>
    req<CandidateList>(`/candidates/more${qs({ category, limit })}`, {
      method: "POST",
    }),
  dismissedCandidates: (category: string) =>
    req<StoryCandidate[]>(`/candidates/dismissed${qs({ category })}`),
  generateCandidates: (ids: number[]) =>
    req<Post[]>("/candidates/generate", {
      method: "POST",
      body: JSON.stringify({ candidate_ids: ids }),
    }),
  dismissCandidate: (id: number) =>
    req<StoryCandidate>(`/candidates/${id}/dismiss`, { method: "PATCH" }),
  undismissCandidate: (id: number) =>
    req<StoryCandidate>(`/candidates/${id}/undismiss`, { method: "PATCH" }),

  // --- Search ---
  searchStored: (q: string, category?: string) =>
    req<Post[]>(`/search/stored${qs({ q, category })}`),
  searchLive: (q: string) => req<LiveSearchResult[]>(`/search/live${qs({ q })}`),
  generateFromSearch: (body: {
    url: string;
    title: string;
    summary: string;
    category: string;
  }) =>
    req<Post>("/search/generate", { method: "POST", body: JSON.stringify(body) }),
};
