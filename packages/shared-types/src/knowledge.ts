export interface ITagSuggestRequest {
  note_path: string;
  max_tags?: number;
}

export interface ITagSuggestResponse {
  tags: string[];
  confidence: number;
}

export interface ILinkRecommendRequest {
  note_path: string;
  max_links?: number;
}

export interface ILinkRecommendItem {
  target: string;
  context: string;
  score: number;
}

export interface ILinkRecommendResponse {
  links: ILinkRecommendItem[];
}

export interface IWordCloudRequest {
  folder?: string;
  top_n?: number;
}

export interface IWordCloudWord {
  word: string;
  weight: number;
  tfidf: number;
  link_count: number;
}

export interface IWordCloudResponse {
  words: IWordCloudWord[];
  total_notes: number;
  generated_at?: string;
}

export interface IVaultIndexRequest {
  vault_path: string;
  force_reindex?: boolean;
}

export interface IVaultIndexResponse {
  status: string;
  total_files: number;
  indexed_files: number;
  skipped_files: number;
  total_chunks: number;
}

export interface IVaultStatusResponse {
  total_files: number;
  indexed_files: number;
  last_indexed?: string;
  status: string;
}
