import type { ImageOption, Post, PostStatus, Run } from "./types";

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
  history: (status?: PostStatus) =>
    req<Post[]>(`/posts/history${status ? `?status=${status}` : ""}`),
  getPost: (id: number) => req<Post>(`/posts/${id}`),
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
};
