/** AI Chat panel — ItemView with streaming SSE chat, conversation history,
 *  smart auto-scroll, and Markdown file persistence.
 */

import type { IChatMessage } from "@ai-tutor/shared-types";
import { type App, ItemView, Notice, type WorkspaceLeaf } from "obsidian";
import type AILearningAgentPlugin from "../main";
import { MessageRenderer } from "./MessageRenderer";
import { streamChat } from "./sse-client";

export const CHAT_VIEW_TYPE = "ai-learning-chat";

interface ChatMessage {
  id: string;
  role: "user" | "assistant" | "system";
  content: string;
  timestamp: number;
}

export class ChatView extends ItemView {
  plugin: AILearningAgentPlugin;
  renderer: MessageRenderer;

  private messages: ChatMessage[] = [];
  private messagesEl!: HTMLElement;
  private inputEl!: HTMLTextAreaElement;
  private sendBtn!: HTMLElement;
  private stopBtn!: HTMLElement;
  private abortController: AbortController | null = null;
  private isStreaming = false;
  private userScrolledUp = false;
  private readonly SCROLL_THRESHOLD = 50;

  private currentChatFile: string | null = null;

  constructor(leaf: WorkspaceLeaf, plugin: AILearningAgentPlugin) {
    super(leaf);
    this.plugin = plugin;
    this.renderer = new MessageRenderer(this.app, this);
    this.navigation = false;
  }

  getViewType(): string {
    return CHAT_VIEW_TYPE;
  }

  getDisplayText(): string {
    return "AI Tutor";
  }

  getIcon(): string {
    return "message-square";
  }

  async onOpen(): Promise<void> {
    const container = this.containerEl.children[1] as HTMLElement;
    container.empty();
    container.addClass("ai-chat-container");

    this.buildMessageArea(container);
    this.buildInputBar(container);

    await this.loadLastSession();
  }

  async onClose(): Promise<void> {
    this.abortStreaming();
    if (this.messages.length > 0) {
      await this.saveSession();
    }
  }

  // ─── DOM Construction ────────────────────────────────────────

  private buildMessageArea(container: HTMLElement): void {
    this.messagesEl = container.createDiv({ cls: "ai-chat-messages" });

    this.messagesEl.addEventListener("scroll", () => {
      const { scrollTop, scrollHeight, clientHeight } = this.messagesEl;
      const distanceFromBottom = scrollHeight - scrollTop - clientHeight;
      this.userScrolledUp = distanceFromBottom > this.SCROLL_THRESHOLD;
    });
  }

  private buildInputBar(container: HTMLElement): void {
    const inputBar = container.createDiv({ cls: "ai-chat-input-bar" });

    this.inputEl = inputBar.createEl("textarea", {
      attr: {
        placeholder: "Ask your AI tutor anything... (Enter to send, Shift+Enter for newline)",
        rows: "1",
      },
      cls: "ai-chat-input",
    });

    this.inputEl.addEventListener("input", () => {
      this.inputEl.style.height = "auto";
      this.inputEl.style.height = `${Math.min(this.inputEl.scrollHeight, 200)}px`;
    });

    this.inputEl.addEventListener("keydown", (evt: KeyboardEvent) => {
      if (evt.key === "Enter" && !evt.shiftKey) {
        evt.preventDefault();
        this.sendMessage();
      }
      if (evt.key === "Escape" && this.isStreaming) {
        evt.preventDefault();
        this.abortStreaming();
      }
    });

    const btnRow = inputBar.createDiv({ cls: "ai-chat-btn-row" });

    this.stopBtn = btnRow.createEl("button", { cls: "ai-chat-stop-btn", text: "Stop" });
    this.stopBtn.addEventListener("click", () => this.abortStreaming());
    this.stopBtn.style.display = "none";

    this.sendBtn = btnRow.createEl("button", { cls: "ai-chat-send-btn mod-cta", text: "Send" });
    this.sendBtn.addEventListener("click", () => this.sendMessage());
  }

  // ─── Streaming UI State ──────────────────────────────────────

  private setStreamingMode(active: boolean): void {
    this.isStreaming = active;
    this.sendBtn.style.display = active ? "none" : "";
    this.stopBtn.style.display = active ? "" : "none";
    if (active) {
      this.inputEl.setAttribute("disabled", "true");
    } else {
      this.inputEl.removeAttribute("disabled");
      this.inputEl.focus();
    }
  }

  // ─── Message Sending & Streaming ─────────────────────────────

  async sendMessage(): Promise<void> {
    const content = this.inputEl.value.trim();
    if (!content || this.isStreaming) return;

    this.inputEl.value = "";
    this.inputEl.style.height = "auto";

    const userMsg = this.addMessage("user", content);
    this.renderMessageToDOM(userMsg);
    this.forceScrollToBottom();

    this.setStreamingMode(true);
    this.abortController = new AbortController();

    const assistantMsgEl = this.renderer.createMessageContainer("assistant");
    this.messagesEl.appendChild(assistantMsgEl);
    this.renderer.beginStreaming(assistantMsgEl);
    this.forceScrollToBottom();

    const port = this.plugin.settings.server.port;
    const fullContent: IChatMessage[] = [
      {
        role: "system",
        content: "You are an AI tutor. Use Socratic questioning. Be concise and helpful.",
      },
      ...this.messages.map((m) => ({
        role: m.role as "system" | "user" | "assistant",
        content: m.content,
      })),
    ];

    try {
      const responseText = await streamChat(
        fullContent,
        {
          onToken: (token: string) => {
            this.renderer.appendToken(token);
            this.scrollToBottomIfDesired();
          },
          onError: (msg: string) => {
            new Notice(`Chat error: ${msg}`);
          },
          onDone: () => {},
        },
        {
          baseUrl: `http://127.0.0.1:${port}`,
          model: this.plugin.settings.llm.model,
          signal: this.abortController.signal,
        },
      );

      await this.renderer.finishStreaming();
      this.addMessage("assistant", responseText);
      await this.saveSession();
    } catch (err: unknown) {
      if (this.abortController?.signal.aborted) {
        await this.renderer.finishStreaming();
        const partial = this.messagesEl.querySelector(".ai-chat-content")?.textContent ?? "";
        this.addMessage("assistant", `${partial}\n\n*[Stopped]*`);
        await this.saveSession();
      } else {
        const msg = err instanceof Error ? err.message : String(err);
        this.renderer.renderError(assistantMsgEl, msg);
      }
    } finally {
      this.setStreamingMode(false);
      this.abortController = null;
    }
  }

  abortStreaming(): void {
    this.abortController?.abort();
  }

  // ─── Message Storage ─────────────────────────────────────────

  private addMessage(role: "user" | "assistant" | "system", content: string): ChatMessage {
    const msg: ChatMessage = {
      id: crypto.randomUUID(),
      role,
      content,
      timestamp: Date.now(),
    };
    this.messages.push(msg);
    return msg;
  }

  private renderMessageToDOM(msg: ChatMessage): void {
    const msgEl = this.renderer.createMessageContainer(msg.role);
    this.messagesEl.appendChild(msgEl);
    this.renderer.renderMessage(msgEl, msg.content);
  }

  renderAllMessages(): void {
    this.messagesEl.empty();
    for (const msg of this.messages) {
      this.renderMessageToDOM(msg);
    }
    this.forceScrollToBottom();
  }

  // ─── Conversation Persistence (Markdown files) ───────────────

  private readonly CHAT_FOLDER = "AI Chat Logs";

  private async saveSession(): Promise<void> {
    if (this.messages.length === 0) return;

    try {
      await this.ensureFolder(this.CHAT_FOLDER);

      if (!this.currentChatFile) {
        const date = new Date().toISOString().slice(0, 10);
        this.currentChatFile = `${this.CHAT_FOLDER}/Chat - ${date}.md`;
      }

      let md = "---\n";
      md += `session_date: ${new Date().toISOString()}\n`;
      md += `message_count: ${this.messages.length}\n`;
      md += `model: ${this.plugin.settings.llm.model}\n`;
      md += "---\n\n";

      for (const msg of this.messages) {
        const roleIcon = msg.role === "user" ? "You" : "AI Tutor";
        md += `### ${roleIcon}\n\n${msg.content}\n\n---\n\n`;
      }

      await this.app.vault.adapter.write(this.currentChatFile, md);
    } catch (err) {
      console.error("[ai-tutor] Failed to save chat session:", err);
    }
  }

  private async loadLastSession(): Promise<void> {
    try {
      await this.ensureFolder(this.CHAT_FOLDER);

      const files = await this.app.vault.adapter.list(this.CHAT_FOLDER);
      if (files.files.length === 0) return;

      const mdFiles = files.files
        .filter((f) => f.endsWith(".md"))
        .sort()
        .reverse();

      const latest = mdFiles[0];
      if (!latest) return;

      const content = await this.app.vault.adapter.read(latest);
      this.currentChatFile = latest;
      this.messages = this.parseMarkdownToMessages(content);
      this.renderAllMessages();
    } catch (err) {
      console.error("[ai-tutor] Failed to load chat session:", err);
    }
  }

  private parseMarkdownToMessages(md: string): ChatMessage[] {
    const messages: ChatMessage[] = [];
    const sections = md.split(/\n### (You|AI Tutor)\n\n/);

    for (let i = 1; i < sections.length; i += 2) {
      const roleStr = sections[i];
      let content = (sections[i + 1] ?? "").trim();
      content = content.replace(/\n---\n\n$/, "").replace(/\n---$/, "");

      const role = roleStr === "You" ? "user" : "assistant";
      messages.push({
        id: crypto.randomUUID(),
        role,
        content,
        timestamp: Date.now(),
      });
    }
    return messages;
  }

  private async ensureFolder(folderPath: string): Promise<void> {
    const exists = await this.app.vault.adapter.exists(folderPath);
    if (!exists) {
      await this.app.vault.createFolder(folderPath);
    }
  }

  /** Clear current conversation and start fresh. */
  async newSession(): Promise<void> {
    await this.saveSession();
    this.messages = [];
    this.currentChatFile = null;
    this.messagesEl.empty();
  }

  // ─── Scroll Helpers ──────────────────────────────────────────

  private forceScrollToBottom(): void {
    this.userScrolledUp = false;
    requestAnimationFrame(() => {
      this.messagesEl.scrollTop = this.messagesEl.scrollHeight;
    });
  }

  private scrollToBottomIfDesired(): void {
    if (this.userScrolledUp) return;
    requestAnimationFrame(() => {
      this.messagesEl.scrollTop = this.messagesEl.scrollHeight;
    });
  }
}
