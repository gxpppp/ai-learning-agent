export interface IRagQueryRequest {
  query: string;
  top_k?: number;
}

export interface IRagChunk {
  note_path: string;
  content: string;
  score: number;
}

export interface IRagSource {
  note_path: string;
  content: string;
  score: number;
}

export interface IRagQueryResponse {
  answer: string;
  sources: IRagChunk[];
}
