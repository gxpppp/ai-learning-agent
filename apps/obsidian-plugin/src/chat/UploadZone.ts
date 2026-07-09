/** UploadZone — drag-drop file upload area above the chat input. */

import { Notice } from "obsidian";

interface UploadResult {
  filename: string;
  name: string;
  size: number;
  chunks: number;
  status: string;
  type: string;
}

export class UploadZone {
  private container: HTMLElement;
  private files: Array<{ name: string; size: number; result?: UploadResult }> = [];
  private port: number;

  constructor(container: HTMLElement, port: number) {
    this.port = port;
    this.container = container.createDiv({ cls: "ai-upload-zone" });
    this.render();
    this.setupDragDrop();
  }

  private render(): void {
    this.container.empty();
    if (this.files.length === 0) {
      const hint = this.container.createDiv({ cls: "ai-upload-hint" });
      hint.setText("Drop PDF/images here to scan (OCR \u2192 notes)");
    } else {
      for (let i = 0; i < this.files.length; i++) {
        const f = this.files[i];
        if (!f) continue;
        const row = this.container.createDiv({ cls: "ai-upload-file" });
        const icon = row.createSpan({ cls: "ai-upload-file-icon" });
        const done = f.result?.status === "done";
        icon.setText(done ? "\u2705" : this.fileIcon(f.name));

        const info = row.createSpan({ cls: "ai-upload-file-name" });
        if (done && f.result) {
          info.setText(`${f.name} \u2192 ${f.result.name} (${f.result.chunks} chunks)`);
        } else {
          info.setText(f.name);
        }

        row.createSpan({
          cls: "ai-upload-file-size",
          text: this.formatSize(f.size),
        });

        const rm = row.createSpan({ cls: "ai-upload-file-rm" });
        rm.setText("\u00d7");
        rm.addEventListener("click", () => {
          this.files.splice(i, 1);
          this.render();
        });
      }
    }
  }

  private fileIcon(name: string): string {
    const ext = name.split(".").pop()?.toLowerCase() || "";
    if (ext === "pdf") return "\ud83d\udcc4";
    if (ext === "md") return "\ud83d\udcdd";
    return "\ud83d\uddbc\ufe0f";
  }

  private formatSize(bytes: number): string {
    if (bytes < 1024) return `${bytes}B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)}KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)}MB`;
  }

  private setupDragDrop(): void {
    this.container.addEventListener("dragover", (e) => {
      e.preventDefault();
      this.container.addClass("ai-upload-dragover");
    });
    this.container.addEventListener("dragleave", () => {
      this.container.removeClass("ai-upload-dragover");
    });
    this.container.addEventListener("drop", async (e) => {
      e.preventDefault();
      this.container.removeClass("ai-upload-dragover");
      const dt = e.dataTransfer;
      if (!dt?.files.length) return;

      for (let i = 0; i < dt.files.length; i++) {
        const file = dt.files[i];
        if (!file) continue;
        this.files.push({ name: file.name, size: file.size });
        this.render();
        try {
          const result = await this.uploadFile(file);
          const entry = this.files.find((f) => f.name === file.name);
          if (entry) entry.result = result;
        } catch {
          new Notice(`Upload failed: ${file.name}`);
        }
        this.render();
      }
    });

    this.container.addEventListener("click", () => {
      const input = document.createElement("input");
      input.type = "file";
      input.multiple = true;
      input.accept = ".pdf,.png,.jpg,.jpeg,.bmp,.tiff,.tif,.webp,.md";
      input.addEventListener("change", async () => {
        if (!input.files) return;
        for (let i = 0; i < input.files.length; i++) {
          const file = input.files[i];
          if (!file) continue;
          this.files.push({ name: file.name, size: file.size });
          this.render();
          try {
            const result = await this.uploadFile(file);
            const entry = this.files.find((f) => f.name === file.name);
            if (entry) entry.result = result;
          } catch {
            new Notice(`Upload failed: ${file.name}`);
          }
          this.render();
        }
        input.remove();
      });
      document.body.appendChild(input);
      input.click();
    });
  }

  private async uploadFile(file: File): Promise<UploadResult> {
    const formData = new FormData();
    formData.append("file", file);
    const resp = await fetch(`http://127.0.0.1:${this.port}/api/upload/`, {
      method: "POST",
      body: formData,
    });
    if (!resp.ok) throw new Error(`Upload failed (${resp.status})`);
    return resp.json();
  }

  getProcessedFiles(): UploadResult[] {
    return this.files.filter((f) => f.result?.status === "done").map((f) => f.result!);
  }

  getUploadedPaths(): string[] {
    return this.files.filter((f) => f.result).map((f) => `Inbox/${f.result!.name}`);
  }

  clear(): void {
    this.files = [];
    this.render();
  }
}
