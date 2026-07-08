export interface IOcrParseRequest {
  file_path: string;
  task: "ocr" | "table" | "formula" | "chart";
}

export interface IOcrParseResponse {
  success: boolean;
  markdown: string | null;
  error: string | null;
}

export interface IOcrParseAndSaveRequest {
  file_path: string;
  vault_path: string;
  target_folder?: string;
  filename?: string;
  task?: "ocr" | "table" | "formula" | "chart";
}

export interface IOcrParseAndSaveResponse {
  success: boolean;
  markdown: string | null;
  saved_path: string | null;
  error: string | null;
}

export interface IOcrHealthResponse {
  status: string;
  model: string;
  server: string;
}
