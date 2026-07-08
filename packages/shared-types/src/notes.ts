export interface INoteCreateRequest {
  vaultPath: string;
  folder: string;
  filename: string;
  content: string;
}

export interface INoteReadRequest {
  vaultPath: string;
  path: string;
}

export interface INoteUpdateRequest {
  vaultPath: string;
  path: string;
  content: string;
}

export interface INoteDeleteRequest {
  vaultPath: string;
  path: string;
}

export interface INoteOperationResult {
  success: boolean;
  path?: string;
  content?: string;
  error?: string;
}

export interface INoteMetadata {
  path: string;
  folder: string;
  filename: string;
  size: number;
  modified: number;
  tags: string[];
  links: string[];
}
