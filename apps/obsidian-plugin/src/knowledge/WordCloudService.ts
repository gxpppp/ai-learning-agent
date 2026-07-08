/** Word cloud API client — calls /api/wordcloud/generate. */

import type { IWordCloudRequest, IWordCloudResponse } from "@ai-tutor/shared-types";

export class WordCloudService {
  private baseUrl: string;

  constructor(port: number) {
    this.baseUrl = `http://127.0.0.1:${port}`;
  }

  async generate(folder?: string, topN = 50): Promise<IWordCloudResponse> {
    const resp = await fetch(`${this.baseUrl}/api/wordcloud/generate`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ folder, top_n: topN } satisfies IWordCloudRequest),
    });

    if (!resp.ok) {
      const text = await resp.text().catch(() => "");
      throw new Error(`Word cloud failed (${resp.status}): ${text}`);
    }

    return (await resp.json()) as IWordCloudResponse;
  }
}
