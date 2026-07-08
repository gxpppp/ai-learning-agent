/** Tag suggestion and link recommendation UI service. */

import type {
  ILinkRecommendRequest,
  ILinkRecommendResponse,
  ITagSuggestRequest,
  ITagSuggestResponse,
} from "@ai-tutor/shared-types";

export class TagSuggestService {
  private baseUrl: string;

  constructor(port: number) {
    this.baseUrl = `http://127.0.0.1:${port}`;
  }

  async suggestTags(notePath: string, maxTags = 5): Promise<ITagSuggestResponse> {
    const resp = await fetch(`${this.baseUrl}/api/tags/suggest`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ note_path: notePath, max_tags: maxTags } satisfies ITagSuggestRequest),
    });
    if (!resp.ok) {
      throw new Error(`Tag suggest failed (${resp.status})`);
    }
    return (await resp.json()) as ITagSuggestResponse;
  }

  async recommendLinks(notePath: string, maxLinks = 5): Promise<ILinkRecommendResponse> {
    const resp = await fetch(`${this.baseUrl}/api/links/recommend`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        note_path: notePath,
        max_links: maxLinks,
      } satisfies ILinkRecommendRequest),
    });
    if (!resp.ok) {
      throw new Error(`Link recommend failed (${resp.status})`);
    }
    return (await resp.json()) as ILinkRecommendResponse;
  }
}
