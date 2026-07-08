import { type ChildProcess, execSync, spawn } from "node:child_process";
import * as path from "node:path";
import type { IAppConfig } from "@ai-tutor/shared-types";

export class SidecarManager {
  private process: ChildProcess | null = null;
  private config: IAppConfig;

  constructor(config: IAppConfig) {
    this.config = config;
  }

  async start(): Promise<void> {
    const { port, host } = this.config.server;
    const env = {
      ...process.env,
      LLM_BASE_URL: this.config.llm.baseUrl,
      LLM_API_KEY: this.config.llm.apiKey,
      LLM_MODEL: this.config.llm.model,
      SERVER_PORT: String(port),
      SERVER_HOST: host,
      OBSIDIAN_VAULT_PATH: this.config.vaultPath,
    };

    const projectRoot = this.getProjectRoot();
    const pythonExe =
      process.platform === "win32"
        ? path.join(projectRoot, ".venv", "Scripts", "python.exe")
        : path.join(projectRoot, ".venv", "bin", "python");

    const proc = spawn(
      pythonExe,
      ["-m", "uvicorn", "app.main:app", "--host", host, "--port", String(port)],
      {
        env,
        cwd: this.getSourceDir(),
        stdio: ["ignore", "pipe", "pipe"],
      },
    );
    this.process = proc;

    proc.stdout?.on("data", (data: Buffer) => {
      console.log(`[backend] ${data.toString().trim()}`);
    });

    proc.stderr?.on("data", (data: Buffer) => {
      console.log(`[backend] ${data.toString().trim()}`);
    });

    proc.on("error", (err: Error) => {
      console.error("[sidecar] process error:", err.message);
      this.process = null;
    });

    proc.on("close", (code: number | null) => {
      console.log(`[sidecar] process exited with code ${code}`);
      this.process = null;
    });

    await this.waitForHealth(10000);
  }

  async stop(): Promise<void> {
    const proc = this.process;
    if (!proc || !proc.pid) return;

    return new Promise((resolve) => {
      proc.on("close", () => {
        this.process = null;
        resolve();
      });

      if (process.platform === "win32") {
        try {
          execSync(`taskkill /pid ${proc.pid} /T /F`);
        } catch {
          proc.kill?.("SIGTERM");
        }
      } else {
        try {
          execSync(`pkill -P ${proc.pid}`);
        } catch {
          // children may already be dead
        }
        proc.kill?.("SIGTERM");
      }
    });
  }

  private async waitForHealth(timeoutMs: number): Promise<void> {
    const start = Date.now();
    const port = this.config.server.port;

    while (Date.now() - start < timeoutMs) {
      try {
        const resp = await fetch(`http://127.0.0.1:${port}/api/health`);
        if (resp.ok) return;
      } catch {
        // server not ready yet
      }
      await new Promise((r) => setTimeout(r, 500));
    }

    throw new Error(`Backend did not become healthy within ${timeoutMs}ms`);
  }

  private getProjectRoot(): string {
    try {
      const base = typeof __dirname !== "undefined" && __dirname ? __dirname : ".";
      return path.resolve(base, "..", "..", "..", "python", "backend");
    } catch {
      return path.resolve("python", "backend");
    }
  }

  private getSourceDir(): string {
    return path.join(this.getProjectRoot(), "src");
  }
}
