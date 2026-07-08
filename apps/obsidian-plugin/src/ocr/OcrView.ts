/** OCR panel — ItemView skeleton for document scanning.
 *
 *  Phase 1.5: Provides command-based OCR triggers via the plugin.
 *  Full UI panel with drag-drop and preview will follow.
 */

import { ItemView, Notice, type WorkspaceLeaf } from "obsidian";
import type AILearningAgentPlugin from "../main";
import { OcrService } from "./OcrService";

export const OCR_VIEW_TYPE = "ai-ocr-panel";

export class OcrView extends ItemView {
  plugin: AILearningAgentPlugin;
  private ocrService: OcrService;

  constructor(leaf: WorkspaceLeaf, plugin: AILearningAgentPlugin) {
    super(leaf);
    this.plugin = plugin;
    this.ocrService = new OcrService(plugin.settings.server.port);
    this.navigation = false;
  }

  getViewType(): string {
    return OCR_VIEW_TYPE;
  }

  getDisplayText(): string {
    return "AI OCR";
  }

  getIcon(): string {
    return "scan";
  }

  async onOpen(): Promise<void> {
    const container = this.containerEl.children[1] as HTMLElement;
    container.empty();
    container.addClass("ai-ocr-container");

    container.createEl("h3", { text: "Document Scanner" });
    container.createEl("p", {
      text: "Use commands (Ctrl+P → OCR) to scan documents. This panel will show recent results.",
      cls: "ai-ocr-placeholder",
    });
  }

  async onClose(): Promise<void> {
    // cleanup
  }

  /** OCR the currently active file (if it is an image or PDF). */
  async ocrCurrentFile(): Promise<void> {
    const activeFile = this.app.workspace.getActiveFile();
    if (!activeFile) {
      new Notice("No file is currently open");
      return;
    }

    const ext = activeFile.extension.toLowerCase();
    const supported = ["png", "jpg", "jpeg", "bmp", "tiff", "tif", "webp", "pdf"];
    if (!supported.includes(ext)) {
      new Notice(`File type .${ext} is not supported for OCR. Supported: ${supported.join(", ")}`);
      return;
    }

    const vaultPath = (this.app.vault.adapter as { basePath?: string }).basePath;
    if (!vaultPath) {
      new Notice("Cannot determine vault path. Please set it in plugin settings.");
      return;
    }

    const filePath = `${vaultPath}/${activeFile.path}`;
    new Notice(`Scanning: ${activeFile.name}...`);

    try {
      const result = await this.ocrService.parseAndSave(filePath, vaultPath, "OCR");
      new Notice(`OCR complete! Saved to ${result.saved_path}`);
      this.renderResult(result.markdown ?? "");
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e);
      new Notice(`OCR failed: ${msg}`);
    }
  }

  private renderResult(markdown: string): void {
    const container = this.containerEl.children[1] as HTMLElement;
    const existing = container.querySelector(".ai-ocr-result");
    if (existing) existing.remove();

    const resultEl = container.createDiv({ cls: "ai-ocr-result" });
    resultEl.createEl("h4", { text: "Latest OCR Result" });
    const pre = resultEl.createEl("pre", { cls: "ai-ocr-content" });
    pre.setText(markdown.slice(0, 2000) + (markdown.length > 2000 ? "\n... (truncated)" : ""));
  }
}
