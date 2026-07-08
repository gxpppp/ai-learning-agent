/** RAG query service — communicates with backend /api/rag/query SSE stream. */

import type { IRagQueryRequest } from "@ai-tutor/shared-types";

export interface RagStreamCallbacks {
  onToken: (content: string) => void;
  onSource: (sources: Array<{ note_path: string; content: string; score: number }>) => void;
  onError?: (message: string) => void;
  onDone?: () => void;
}

export async function ragQuery(
  query: string,
  baseUrl: string,
  callbacks: RagStreamCallbacks,
  signal?: AbortSignal,
): Promise<string> {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), 120_000);
  if (signal) {
    signal.addEventListener("abort", () => controller.abort());
  }

  let fullText = "";

  try {
    const resp = await fetch(`${baseUrl}/api/rag/query`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ query, top_k: 5 } satisfies IRagQueryRequest),
      signal: controller.signal,
    });

    if (!resp.ok) {
      const err = await resp.text().catch(() => "");
      throw new Error(`RAG query failed (${resp.status}): ${err}`);
    }

    const reader = resp.body?.getReader();
    if (!reader) throw new Error("No response body");

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
          if (line.startsWith("event:")) eventType = line.slice(6).trim();
          else if (line.startsWith("data:")) dataPayload = line.slice(5).trim();
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
          } else if (eventType === "source") {
            callbacks.onSource(parsed);
          } else if (eventType === "error") {
            callbacks.onError?.(parsed.message ?? "Unknown error");
          }
        } catch {
          // skip unparseable
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
  }
}
