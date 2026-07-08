/** SSE stream parser using fetch() + ReadableStream.
 *
 * The backend streams SSE events over a POST HTTP connection.
 * This client parses the stream token-by-token and invokes callbacks.
 * Supports AbortController for cancellation.
 */

import type { IChatMessage } from "@ai-tutor/shared-types";

export interface StreamCallbacks {
  onToken: (content: string) => void;
  onError?: (message: string) => void;
  onDone?: () => void;
}

export interface StreamOptions {
  baseUrl: string;
  model?: string;
  temperature?: number;
  maxTokens?: number;
  signal?: AbortSignal;
  timeoutMs?: number;
}

export async function streamChat(
  messages: IChatMessage[],
  callbacks: StreamCallbacks,
  options: StreamOptions,
): Promise<string> {
  const baseUrl = options.baseUrl;
  const timeoutMs = options.timeoutMs ?? 120_000;

  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), timeoutMs);

  if (options.signal) {
    options.signal.addEventListener("abort", () => controller.abort());
  }

  let fullText = "";

  try {
    const response = await fetch(`${baseUrl}/api/chat/stream`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        messages,
        model: options.model,
        temperature: options.temperature ?? 0.7,
        max_tokens: options.maxTokens ?? 4096,
      }),
      signal: controller.signal,
    });

    if (!response.ok) {
      const errorText = await response.text().catch(() => "");
      throw new Error(
        `HTTP ${response.status}: ${response.statusText}${errorText ? ` - ${errorText}` : ""}`,
      );
    }

    const reader = response.body?.getReader();
    if (!reader) {
      throw new Error("Response body is not readable");
    }

    const decoder = new TextDecoder("utf-8");
    let buffer = "";

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const parts = buffer.split("\n\n");
      buffer = parts.pop() ?? "";

      for (const part of parts) {
        if (!part.trim()) continue;

        const lines = part.split("\n");
        let eventType = "message";
        let dataPayload = "";

        for (const line of lines) {
          if (line.startsWith("event:")) {
            eventType = line.slice(6).trim();
          } else if (line.startsWith("data:")) {
            dataPayload = line.slice(5).trim();
          }
        }

        if (dataPayload === "[DONE]") {
          callbacks.onDone?.();
          return fullText;
        }

        try {
          const parsed = JSON.parse(dataPayload);
          if (eventType === "token" && parsed.content) {
            fullText += parsed.content;
            callbacks.onToken(parsed.content);
          } else if (eventType === "error") {
            callbacks.onError?.(parsed.message ?? "Unknown error");
            return fullText;
          }
        } catch {
          // ignore unparseable lines (keepalives, comments)
        }
      }
    }

    callbacks.onDone?.();
    return fullText;
  } catch (err: unknown) {
    if (err instanceof DOMException && err.name === "AbortError") {
      callbacks.onDone?.();
      return fullText;
    }
    const msg = err instanceof Error ? err.message : String(err);
    callbacks.onError?.(msg);
    throw err;
  } finally {
    clearTimeout(timeoutId);
    if (options.signal) {
      options.signal.removeEventListener("abort", () => controller.abort());
    }
  }
}
