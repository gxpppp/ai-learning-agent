/** UploadZone — drag-drop file upload area above the chat input. */

import { Notice } from "obsidian";

export class UploadZone {
  private container: HTMLElement;
  private files: Array<{ name: string; size: number; path?: string }> = [];
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
      hint.setText("Drop PDF/images here to scan (OCR → notes)");
    } else {
      for (let i = 0; i < this.files.length; i++) {
        const f = this.files[i];
        if (!f) continue;
        const row = this.container.createDiv({ cls: "ai-upload-file" });
        const icon = row.createSpan({ cls: "ai-upload-file-icon" });
        icon.setText(this.fileIcon(f.name));
        row.createSpan({ cls: "ai-upload-file-name", text: f.name });
        row.createSpan({ cls: "ai-upload-file-size", text: this.formatSize(f.size) });
        const rm = row.createSpan({ cls: "ai-upload-file-rm" });
        rm.setText("×");
        rm.addEventListener("click", () => {
          this.files.splice(i, 1);
          this.render();
        });
      }
    }
  }

  private fileIcon(name: string): string {
    const ext = name.split(".").pop()?.toLowerCase() || "";
    if (ext === "pdf") return "📄";
    return "🖼️";
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
          const path = await this.uploadFile(file);
          const entry = this.files.find((f) => f.name === file.name);
          if (entry) entry.path = path;
        } catch (err) {
          new Notice(`Upload failed: ${file.name}`);
        }
        this.render();
      }
    });

    this.container.addEventListener("click", () => {
      const input = document.createElement("input");
      input.type = "file";
      input.multiple = true;
      input.accept = ".pdf,.png,.jpg,.jpeg,.bmp,.tiff,.tif,.webp";
      input.addEventListener("change", async () => {
        if (!input.files) return;
        for (let i = 0; i < input.files.length; i++) {
          const file = input.files[i];
          if (!file) continue;
          this.files.push({ name: file.name, size: file.size });
          this.render();
          try {
            const path = await this.uploadFile(file);
            const entry = this.files.find((f) => f.name === file.name);
            if (entry) entry.path = path;
          } catch (err) {
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

  private async uploadFile(file: File): Promise<string> {
    const formData = new FormData();
    formData.append("file", file);
    const resp = await fetch(`http://127.0.0.1:${this.port}/api/upload/`, {
      method: "POST",
      body: formData,
    });
    if (!resp.ok) throw new Error(`Upload failed (${resp.status})`);
    const data = await resp.json();
    return data.file_path;
  }

  getUploadedPaths(): string[] {
    return this.files.filter((f) => f.path).map((f) => f.path!);
  }

  clear(): void {
    this.files = [];
    this.render();
  }
}
