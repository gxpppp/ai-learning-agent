export interface IChatMessage {
  role: "system" | "user" | "assistant";
  content: string;
}

export interface IChatRequest {
  messages: IChatMessage[];
  model?: string;
  temperature?: number;
  max_tokens?: number;
}

export interface ITokenEvent {
  event: "token";
  data: { content: string };
}

export interface IRoleEvent {
  event: "role";
  data: { role: string };
}

export interface IErrorEvent {
  event: "error";
  data: { message: string };
}

export type SSEEvent = ITokenEvent | IRoleEvent | IErrorEvent;

export interface IHealthResponse {
  status: string;
  version: string;
  model: string;
}
