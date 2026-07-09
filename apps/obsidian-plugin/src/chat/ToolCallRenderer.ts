/** ToolCallRenderer — renders tool call cards in chat with smaller font and gray background.
 *
 *  Displays tool name, icon, elapsed time, arguments (collapsed), and result.
 *  Auto-collapses after the result is shown.
 */

import { MarkdownRenderer, Component } from "obsidian";
import type { App } from "obsidian";

interface ToolCallData {
  id: string;
  name: string;
  args: Record<string, unknown>;
}

interface ToolResultData {
  id: string;
  name: string;
  content: string;
  elapsed_ms: number;
}

const TOOL_ICONS: Record<string, string> = {
  search_notes: "🔍",
  read_note: "📖",
  list_folder: "📁",
  suggest_tags: "🏷️",
  recommend_links: "🔗",
  create_note: "✏️",
  update_note: "📝",
  delete_note: "🗑️",
  create_folder: "📂",
  move_note: "📦",
  ocr_document: "🔬",
  classify_note: "📊",
  generate_summary: "📋",
  get_vault_status: "ℹ️",
};

export class ToolCallRenderer {
  private container: HTMLElement;
  private pendingCards = new Map<string, HTMLElement>();

  constructor(container: HTMLElement) {
    this.container = container;
  }

  /** Create a pending tool call card. Returns the card element for later updates. */
  renderToolCall(data: ToolCallData): HTMLElement {
    const icon = TOOL_ICONS[data.name] || "🔧";
    const card = this.container.createDiv({ cls: "ai-tool-call-card" });
    card.setAttribute("data-tool-id", data.id);

    const header = card.createDiv({ cls: "ai-tool-call-header" });
    header.createSpan({ cls: "ai-tool-call-icon", text: icon });
    header.createSpan({ cls: "ai-tool-call-name", text: ` ${data.name}` });
    const timeEl = header.createSpan({ cls: "ai-tool-call-time", text: " ..." });

    const argsEl = card.createDiv({ cls: "ai-tool-call-args" });
    argsEl.setText(JSON.stringify(data.args, null, 0).slice(0, 100));

    // Expand on click
    header.addEventListener("click", () => {
      const body = card.querySelector(".ai-tool-call-body") as HTMLElement | null;
      if (body) {
        body.style.display = body.style.display === "none" ? "block" : "none";
      }
    });

    this.pendingCards.set(data.id, card);
    return card;
  }

  /** Update a pending tool call card with the result. */
  async renderToolResult(data: ToolResultData, app: App, component: Component): Promise<void> {
    const card = this.pendingCards.get(data.id);
    if (!card) return;

    // Update time
    const timeEl = card.querySelector(".ai-tool-call-time");
    if (timeEl) {
      const secs = (data.elapsed_ms / 1000).toFixed(1);
      timeEl.setText(` ${secs}s`);
    }

    // Render result
    const body = card.createDiv({ cls: "ai-tool-call-body" });
    try {
      const parsed = JSON.parse(data.content);
      if (parsed.error) {
        body.createSpan({ cls: "ai-tool-call-error", text: `Error: ${parsed.error}` });
      } else {
        const contentEl = body.createDiv({ cls: "ai-tool-call-content" });
        const summary = this.summarizeResult(data.name, parsed, data.content);
        await MarkdownRenderer.render(app, summary, contentEl, "", component);
      }
    } catch {
      const contentEl = body.createDiv({ cls: "ai-tool-call-content" });
      contentEl.setText(data.content.slice(0, 500));
    }

    // Mark as done
    card.addClass("ai-tool-call-done");
    this.pendingCards.delete(data.id);
  }

  private summarizeResult(name: string, parsed: Record<string, unknown>, raw: string): string {
    switch (name) {
      case "search_notes": {
        const results = parsed.results as Array<Record<string, unknown>> | undefined;
        if (!results?.length) return "No results found.";
        return results.map((r, i) => `${i + 1}. **${r.path}** (*${r.score}*)`).join("\n");
      }
      case "read_note":
        return `Read \`${parsed.path}\` (${(raw.length || 0)} chars).`;
      case "list_folder": {
        const items = parsed.items as Array<Record<string, unknown>> | undefined;
        if (!items?.length) return "Empty folder.";
        return items.map((i) => `${i.type === "folder" ? "📁" : "📄"} ${i.name}`).join("\n");
      }
      case "create_note":
        return `Created \`${parsed.created}\`.`;
      case "ocr_document":
        return `OCR complete: \`${parsed.ocr_result}\` (${parsed.characters} chars).`;
      default:
        return raw.slice(0, 300);
    }
  }

  /** Render the LLM's JSON plan as a collapsible block. */
  renderToolPlan(planJson: string): void {
    const card = this.container.createDiv({ cls: "ai-tool-card ai-tool-plan" });
    const header = card.createDiv({ cls: "ai-tool-header" });
    header.createSpan({ cls: "ai-tool-icon", text: "📋" });
    header.createSpan({ cls: "ai-tool-name", text: "Plan" });

    const body = card.createDiv({ cls: "ai-tool-body" });
    try {
      const plan = JSON.parse(planJson);
      const list = body.createEl("ul", { cls: "ai-tool-plan-list" });
      for (const action of plan) {
        const tool = action.tool || "unknown";
        const args = action.args ? JSON.stringify(action.args) : "";
        list.createEl("li", {
          text: `${tool}(${args.slice(0, 80)}${args.length > 80 ? "..." : ""})`,
        });
      }
    } catch {
      body.createEl("pre", { text: planJson.slice(0, 300) });
    }
    // Auto-collapse after 2s
    setTimeout(() => body.style.display = "none", 3000);
    header.addEventListener("click", () => {
      body.style.display = body.style.display === "none" ? "block" : "none";
    });
  }

  /** Render a sub-agent status marker in the message stream. */
  renderAgentMarker(agent: string, phase: "start" | "end", task?: string): void {
    const el = this.container.createDiv({ cls: "ai-tool-card ai-agent-marker" });
    const icons: Record<string, string> = {
      orchestrator: "🧩",
      searcher: "🔍",
      operator: "⚙️",
      verifier: "✅",
    };
    const icon = icons[agent] || "🤖";
    const label = phase === "start"
      ? `${icon} ${agent} started` + (task ? `: ${task.slice(0, 60)}` : "")
      : `${icon} ${agent} done`;
    el.createSpan({ cls: "ai-tool-name", text: label });
  }
}
