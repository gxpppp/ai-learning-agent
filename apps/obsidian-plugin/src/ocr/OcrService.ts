/** OCR service client — communicates with the Python backend OCR endpoints.
 *
 *  Supports:
 *    - parse(filePath, task) → raw markdown text
 *    - parseAndSave(filePath, vaultPath, folder) → markdown + written to vault
 *    - health() → paddeocr service status
 */

import type {
  IOcrHealthResponse,
  IOcrParseAndSaveRequest,
  IOcrParseAndSaveResponse,
  IOcrParseRequest,
  IOcrParseResponse,
} from "@ai-tutor/shared-types";

export class OcrService {
  private baseUrl: string;

  constructor(port: number) {
    this.baseUrl = `http://127.0.0.1:${port}`;
  }

  async parse(filePath: string, task: IOcrParseRequest["task"] = "ocr"): Promise<string> {
    const resp = await fetch(`${this.baseUrl}/api/ocr/parse`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ file_path: filePath, task } satisfies IOcrParseRequest),
    });

    if (!resp.ok) {
      const text = await resp.text().catch(() => "");
      throw new Error(`OCR parse failed (${resp.status}): ${text}`);
    }

    const data: IOcrParseResponse = await resp.json();
    if (!data.success || !data.markdown) {
      throw new Error(data.error ?? "OCR returned empty result");
    }

    return data.markdown;
  }

  async parseAndSave(
    filePath: string,
    vaultPath: string,
    targetFolder?: string,
    filename?: string,
    task: IOcrParseAndSaveRequest["task"] = "ocr",
  ): Promise<IOcrParseAndSaveResponse> {
    const resp = await fetch(`${this.baseUrl}/api/ocr/parse-and-save`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        file_path: filePath,
        vault_path: vaultPath,
        target_folder: targetFolder,
        filename,
        task,
      } satisfies IOcrParseAndSaveRequest),
    });

    if (!resp.ok) {
      const text = await resp.text().catch(() => "");
      throw new Error(`OCR parse-and-save failed (${resp.status}): ${text}`);
    }

    return (await resp.json()) as IOcrParseAndSaveResponse;
  }

  async health(): Promise<IOcrHealthResponse> {
    const resp = await fetch(`${this.baseUrl}/api/ocr/health`);
    if (!resp.ok) {
      const text = await resp.text().catch(() => "");
      throw new Error(`OCR health check failed (${resp.status}): ${text}`);
    }
    return (await resp.json()) as IOcrHealthResponse;
  }
}
