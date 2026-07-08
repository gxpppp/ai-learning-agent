export interface ILLMConfig {
  baseUrl: string;
  apiKey: string;
  model: string;
}

export interface IServerConfig {
  port: number;
  host: string;
}

export interface IAppConfig {
  vaultPath: string;
  llm: ILLMConfig;
  server: IServerConfig;
}

export const DEFAULT_CONFIG: IAppConfig = {
  vaultPath: "",
  llm: {
    baseUrl: "https://api.deepseek.com/v1",
    apiKey: "",
    model: "deepseek-chat",
  },
  server: {
    port: 8765,
    host: "127.0.0.1",
  },
};
