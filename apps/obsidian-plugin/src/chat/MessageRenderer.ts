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

    // Periodically do a full markdown render for code blocks etc.
    // Every ~150ms use a debounced re-render.
    if (this.accumulatedText.endsWith("\n")) {
      this.debouncedMarkdownRender();
    }
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
  }

  /** Render an error message in the container. */
  renderError(msgEl: HTMLElement, error: string): void {
    const contentEl = msgEl.createDiv({ cls: "ai-chat-content ai-chat-error" });
    contentEl.setText(`Error: ${error}`);
  }
}
