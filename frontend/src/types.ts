export type PostStatus = "draft" | "approved" | "posted";

export interface ImageOption {
  url: string;
  thumb: string;
  attribution: string;
  source: string;
  license: string;
  source_url: string;
}

export interface PostMetrics {
  post_id: number;
  impressions: number;
  reactions: number;
  comments: number;
  reposts: number;
  updated_at: string | null;
}

export interface Post {
  id: number;
  run_id: number | null;
  headline: string;
  body: string;
  format_type: string;
  hashtags: string[];
  char_count: number;
  image_recommended: boolean;
  image_reason: string | null;
  image_url: string | null;
  image_attribution: string | null;
  image_options: ImageOption[];
  source_url: string | null;
  source_name: string | null;
  topic_key: string | null;
  is_pivotal: boolean;
  is_update: boolean;
  category: string;
  status: PostStatus;
  created_at: string;
  updated_at: string;
  posted_at: string | null;
  linkedin_post_id: string | null;
  metrics: PostMetrics | null;
}

export interface Run {
  id: number;
  status: "running" | "completed" | "failed";
  num_candidates: number;
  num_posts: number;
  error: string | null;
  created_at: string;
  finished_at: string | null;
}

export interface RSSSource {
  id: number;
  name: string;
  url: string;
  category: string;
  authority: number;
  audience: string;
  enabled: boolean;
  is_custom: boolean;
}

export interface SourceSuggestion {
  name: string;
  url: string;
  authority: number;
  category: string;
}

export type CandidateStatus = "pending" | "shown" | "generated" | "dismissed";

export interface StoryCandidate {
  id: number;
  url: string;
  title: string;
  source_name: string;
  summary: string | null;
  lead_image_url: string | null;
  published_at: string | null;
  category: string;
  score: number;
  status: CandidateStatus;
}

export interface CandidateList {
  candidates: StoryCandidate[];
  dismissed_count: number;
  has_more: boolean;
}

export interface LiveSearchResult {
  title: string;
  url: string;
  content: string;
  published_date: string | null;
  source: string;
}

export const FORMAT_LABELS: Record<string, string> = {
  punchy_take: "Punchy Take",
  explainer: "Explainer",
  psa_alert: "Public Safety Alert",
  thought_leadership: "Thought Leadership",
  myth_bust: "Myth-Bust",
};

export const LINKEDIN_LIMIT = 3000;
