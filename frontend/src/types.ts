export type PostStatus = "draft" | "approved" | "posted";

export interface ImageOption {
  url: string;
  thumb: string;
  attribution: string;
  source: string;
  license: string;
  source_url: string;
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

export const FORMAT_LABELS: Record<string, string> = {
  punchy_take: "Punchy Take",
  explainer: "Explainer",
  psa_alert: "Public Safety Alert",
  thought_leadership: "Thought Leadership",
  myth_bust: "Myth-Bust",
};

export const LINKEDIN_LIMIT = 3000;
