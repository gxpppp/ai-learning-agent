/** Word cloud ItemView panel — renders d3-cloud SVG, click-to-search. */

import * as d3 from "d3";
import cloud from "d3-cloud";
import { ItemView, Notice, type WorkspaceLeaf } from "obsidian";
import type AILearningAgentPlugin from "../main";
import { WordCloudService } from "./WordCloudService";

export const WORDCLOUD_VIEW_TYPE = "ai-wordcloud-panel";

export class WordCloudView extends ItemView {
  plugin: AILearningAgentPlugin;
  private service: WordCloudService;
  private svgEl!: HTMLElement;

  constructor(leaf: WorkspaceLeaf, plugin: AILearningAgentPlugin) {
    super(leaf);
    this.plugin = plugin;
    this.service = new WordCloudService(plugin.settings.server.port);
    this.navigation = false;
  }

  getViewType(): string {
    return WORDCLOUD_VIEW_TYPE;
  }

  getDisplayText(): string {
    return "Word Cloud";
  }

  getIcon(): string {
    return "cloud";
  }

  async onOpen(): Promise<void> {
    const container = this.containerEl.children[1] as HTMLElement;
    container.empty();
    container.addClass("ai-wordcloud-container");
    this.svgEl = container.createDiv({ cls: "ai-wordcloud-svg" });
    container.createEl("small", { text: "Click a word to search notes", cls: "ai-wordcloud-hint" });
  }

  async onClose(): Promise<void> {
    // cleanup
  }

  async refresh(folder?: string): Promise<void> {
    try {
      new Notice("Generating word cloud...");
      const data = await this.service.generate(folder, 50);
      this.renderCloud(data.words);
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e);
      new Notice(`Word cloud failed: ${msg}`);
    }
  }

  private renderCloud(wordData: Array<{ word: string; weight: number }>): void {
    this.svgEl.empty();

    if (wordData.length === 0) {
      this.svgEl.createEl("p", {
        text: "No words found. Index your vault first.",
        cls: "ai-wordcloud-empty",
      });
      return;
    }

    const width = this.svgEl.clientWidth || 400;
    const height = Math.max(width * 0.7, 300);
    const maxWeight = wordData[0]!.weight;
    const fontSizeScale = d3.scaleLinear().domain([0, maxWeight]).range([12, 60]);

    const words = wordData.map((d) => ({
      text: d.word,
      size: Math.max(12, fontSizeScale(d.weight)),
    }));

    // d3-cloud Word type has optional fields; use any for compatibility
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const wordCloudLayout = (cloud() as any)
      .size([width, height])
      .words(words)
      .padding(6)
      .rotate(() => 0)
      .font("var(--font-text)")
      .fontSize((d: { size?: number }) => d.size ?? 12)
      .on(
        "end",
        (
          layoutWords: Array<{ text: string; size: number; x: number; y: number; rotate: number }>,
        ) => {
          const svg = d3
            .select(this.svgEl)
            .append("svg")
            .attr("width", width)
            .attr("height", height)
            .append("g")
            .attr("transform", `translate(${width / 2},${height / 2})`);

          svg
            .selectAll("text")
            .data(layoutWords)
            .enter()
            .append("text")
            .style("font-size", (d) => `${d.size}px`)
            .style("font-family", "var(--font-text)")
            .style("fill", "var(--text-accent)")
            .style("cursor", "pointer")
            .attr("text-anchor", "middle")
            .attr("transform", (d) => `translate(${d.x},${d.y})rotate(${d.rotate})`)
            .text((d) => d.text)
            .on("click", (_event, d) => {
              this.searchWord(d.text);
            });
        },
      );

    wordCloudLayout.start();
  }

  private searchWord(word: string): void {
    const searchLeaf = this.app.workspace.getLeavesOfType("search")[0];
    if (searchLeaf) {
      this.app.workspace.revealLeaf(searchLeaf);
    }
    // Internal Obsidian search API
    try {
      const appExt = this.app as unknown as {
        internalPlugins: {
          getPluginById(id: string): { instance: { openGlobalSearch(q: string): void } } | null;
        };
      };
      const sp = appExt.internalPlugins.getPluginById("global-search");
      sp?.instance?.openGlobalSearch(word);
    } catch {
      // skip if search plugin unavailable
    }
  }
}
