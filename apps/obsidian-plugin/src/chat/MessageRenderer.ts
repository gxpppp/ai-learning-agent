/** Streaming Markdown message renderer for Obsidian.
 *
 * During active streaming: appends plain text for performance.
 * On completion: does a full MarkdownRenderer.render() pass for
 * syntax highlighting, code blocks, LaTeX, and [[wikilinks]].
 */

import { type Component, MarkdownRenderer } from "obsidian";
import type { App } from "obsidian";

export class MessageRenderer {
  private app: App;
  private component: Component;
  private streamingContentEl: HTMLElement | null = null;
  private thinkingEl: HTMLElement | null = null;
  private thinkingText = "";
  private accumulatedText = "";

  constructor(app: App, component: Component) {
    this.app = app;
    this.component = component;
  }

  /** Create a new message wrapper and return it. */
  createMessageContainer(role: "user" | "assistant" | "system"): HTMLElement {
    const msgEl = createDiv({ cls: `ai-chat-message ai-chat-role-${role}` });
    const roleLabel = msgEl.createSpan({ cls: "ai-chat-role-label" });
    roleLabel.setText(role === "user" ? "You" : "AI Tutor");
    return msgEl;
  }

  /** Render a complete message (non-streaming). */
  async renderMessage(msgEl: HTMLElement, content: string): Promise<void> {
    const contentEl = msgEl.createDiv({ cls: "ai-chat-content" });
    await MarkdownRenderer.render(this.app, content, contentEl, "", this.component);
  }

  /** Begin streaming: create a message bubble with a content container. */
  beginStreaming(msgEl: HTMLElement): void {
    this.accumulatedText = "";
    this.streamingContentEl = msgEl.createDiv({ cls: "ai-chat-content" });
  }

  /** Append a token chunk during streaming. */
  appendToken(token: string): void {
    if (!this.streamingContentEl) return;
    this.accumulatedText += token;
    this.streamingContentEl.setText(this.accumulatedText);

    if (this.accumulatedText.endsWith("\n")) {
      this.debouncedMarkdownRender();
    }
  }

  /** Append thinking content — rendered as collapsible gray block. */
  appendThinking(content: string): void {
    if (!this.streamingContentEl) return;
    if (!this.thinkingEl) {
      const detail = createEl("details", { cls: "ai-thinking-block" });
      detail.setAttribute("open", "true");
      const summary = detail.createEl("summary", { cls: "ai-thinking-summary" });
      summary.setText("💭 Thinking");
      this.thinkingEl = detail.createDiv({ cls: "ai-thinking-content" });
      const parent = this.streamingContentEl.parentElement;
      if (parent) parent.insertBefore(detail, this.streamingContentEl);
    }
    this.thinkingText += content;
    this.thinkingEl.setText(this.thinkingText);
  }

  private renderScheduled = false;
  private debouncedMarkdownRender(): void {
    if (this.renderScheduled || !this.streamingContentEl) return;
    this.renderScheduled = true;
    requestAnimationFrame(async () => {
      if (!this.streamingContentEl) return;
      const text = this.accumulatedText;
      this.streamingContentEl.empty();
      await MarkdownRenderer.render(this.app, text, this.streamingContentEl, "", this.component);
      this.renderScheduled = false;
    });
  }

  /** Finalize streaming: do a clean full Markdown render. */
  async finishStreaming(): Promise<void> {
    if (!this.streamingContentEl) return;
    const text = this.accumulatedText;
    this.streamingContentEl.empty();
    await MarkdownRenderer.render(this.app, text, this.streamingContentEl, "", this.component);
    this.streamingContentEl = null;
    this.accumulatedText = "";
    this.thinkingEl = null;
    this.thinkingText = "";
  }

  /** Render an error message in the container. */
  renderError(msgEl: HTMLElement, error: string): void {
    const contentEl = msgEl.createDiv({ cls: "ai-chat-content ai-chat-error" });
    contentEl.setText(`Error: ${error}`);
  }
}
