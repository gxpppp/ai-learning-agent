// FeedbackBar — thumbs up/down buttons appended to assistant messages.

import { Notice } from "obsidian";

export class FeedbackBar {
  private container: HTMLElement;
  private port: number;
  private sessionId: string;

  constructor(parentEl: HTMLElement, port: number, sessionId: string) {
    this.port = port;
    this.sessionId = sessionId;
    this.container = parentEl.createDiv({ cls: "ai-feedback-bar" });
    this.render();
  }

  private render(): void {
    const thumbUp = this.container.createSpan({ cls: "ai-feedback-btn", text: "👍" });
    thumbUp.addEventListener("click", () => this.sendFeedback("thumbs_up", ""));

    const thumbDown = this.container.createSpan({ cls: "ai-feedback-btn", text: "👎" });
    thumbDown.addEventListener("click", () => this.showReasonPrompt());
  }

  private async sendFeedback(rating: string, reason: string): Promise<void> {
    try {
      await fetch(`http://127.0.0.1:${this.port}/api/feedback`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ rating, reason, session_id: this.sessionId }),
      });
    } catch {
      // silently fail — feedback is best-effort
    }
    this.container.empty();
    const done = this.container.createSpan({ cls: "ai-feedback-done", text: "Thanks!" });
    done.style.color = "var(--text-faint)";
    done.style.fontSize = "11px";
  }

  private showReasonPrompt(): void {
    const overlay = document.createElement("div");
    overlay.className = "ai-feedback-overlay";
    overlay.innerHTML = `
      <div class="ai-feedback-prompt">
        <strong>What was wrong?</strong>
        <label><input type="radio" name="reason" value="inaccurate"> Inaccurate</label>
        <label><input type="radio" name="reason" value="wrong_tool"> Wrong tool</label>
        <label><input type="radio" name="reason" value="too_long"> Too verbose</label>
        <label><input type="radio" name="reason" value="not_helpful"> Not helpful</label>
        <label><input type="radio" name="reason" value="other"> Other</label>
        <textarea placeholder="(optional details)" rows="2"></textarea>
        <div class="ai-feedback-actions">
          <button class="ai-feedback-submit">Submit</button>
          <button class="ai-feedback-cancel">Cancel</button>
        </div>
      </div>
    `;
    document.body.appendChild(overlay);

    const close = () => overlay.remove();
    overlay.querySelector<HTMLElement>(".ai-feedback-cancel")!.onclick = close;
    overlay.addEventListener("click", (e) => { if (e.target === overlay) close(); });

    overlay.querySelector<HTMLElement>(".ai-feedback-submit")!.onclick = async () => {
      const checked = overlay.querySelector<HTMLInputElement>("input[name='reason']:checked");
      const reason = checked?.value || "other";
      const detail = overlay.querySelector<HTMLTextAreaElement>("textarea")?.value || "";
      await this.sendFeedback("thumbs_down", detail ? `${reason}: ${detail}` : reason);
      close();
      new Notice("Feedback recorded. Thanks!");
    };
  }
}
