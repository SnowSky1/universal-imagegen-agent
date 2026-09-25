import { access, readFile } from "node:fs/promises";
import { resolve } from "node:path";

import { parse as parseToml } from "smol-toml";

import { ConfigError } from "./errors.js";

export const DEFAULT_BASE_URL = "https://api.openai.com/v1";
export const DEFAULT_MODEL = "gpt-image-2.5-sunburst";

async function exists(path) {
  try {
    await access(path);
    return true;
  } catch {
    return false;
  }
}

function parseDotenv(contents) {
  const values = {};
  for (const raw of contents.split(/\r?\n/u)) {
    const line = raw.trim();
    if (!line || line.startsWith("#")) continue;
    const normalized = line.startsWith("export ") ? line.slice(7).trim() : line;
    const separator = normalized.indexOf("=");
    if (separator < 1) continue;
    const key = normalized.slice(0, separator).trim();
    let value = normalized.slice(separator + 1).trim();
    if (
      value.length >= 2 &&
      ((value.startsWith('"') && value.endsWith('"')) ||
        (value.startsWith("'") && value.endsWith("'")))
    ) {
      value = value.slice(1, -1);
    }
    values[key] = value;
  }
  return values;
}

function parseHeaders(value, name) {
  if (!value) return {};
  try {
    const result = typeof value === "string" ? JSON.parse(value) : value;
    if (!result || Array.isArray(result) || typeof result !== "object") {
      throw new Error("expected an object");
    }
    return Object.fromEntries(
      Object.entries(result).map(([key, item]) => [String(key), String(item)]),
    );
  } catch (error) {
    throw new ConfigError(`${name} must be a JSON object: ${error.message}`);
  }
}

function integer(value, fallback, name) {
  const result = value === undefined || value === "" ? fallback : Number(value);
  if (!Number.isInteger(result)) {
    throw new ConfigError(`${name} must be an integer.`);
  }
  return result;
}

function number(value, fallback, name) {
  const result = value === undefined || value === "" ? fallback : Number(value);
  if (!Number.isFinite(result)) {
    throw new ConfigError(`${name} must be a number.`);
  }
  return result;
}

function validate(settings) {
  if (settings.provider !== "openai-compatible") {
    throw new ConfigError(
      "Only provider.name='openai-compatible' is currently implemented.",
    );
  }
  if (!/^https?:\/\//u.test(settings.baseUrl)) {
    throw new ConfigError("base_url must start with https:// or http://.");
  }
  if (!settings.model) throw new ConfigError("model cannot be empty.");
  if (settings.timeoutSeconds <= 0) {
    throw new ConfigError("timeout_seconds must be greater than zero.");
  }
  if (settings.maxRetries < 0 || settings.maxRetries > 20) {
    throw new ConfigError("max_retries must be between 0 and 20.");
  }
  if (settings.concurrency < 1 || settings.concurrency > 25) {
    throw new ConfigError("concurrency must be between 1 and 25.");
  }
  if (!["png", "jpeg", "jpg", "webp"].includes(settings.outputFormat)) {
    throw new ConfigError("output_format must be png, jpeg, jpg, or webp.");
  }
}

export async function loadSettings({
  cwd = process.cwd(),
  configPath,
  overrides = {},
  environ = process.env,
  loadProjectDotenv = true,
} = {}) {
  const environment = { ...environ };
  const dotenvPath = resolve(cwd, ".env");
  if (loadProjectDotenv && (await exists(dotenvPath))) {
    const values = parseDotenv(await readFile(dotenvPath, "utf8"));
    for (const [key, value] of Object.entries(values)) {
      if (environment[key] === undefined) environment[key] = value;
    }
  }

  const rawConfigPath =
    configPath || environment.IMAGEGEN_CONFIG || (await exists(resolve(cwd, ".imagegen.toml"))
      ? ".imagegen.toml"
      : undefined);
  const resolvedConfigPath = rawConfigPath
    ? resolve(cwd, rawConfigPath)
    : undefined;
  let config = {};
  if (resolvedConfigPath) {
    if (!(await exists(resolvedConfigPath))) {
      throw new ConfigError(`Configuration file not found: ${resolvedConfigPath}`);
    }
    try {
      config = parseToml(await readFile(resolvedConfigPath, "utf8"));
    } catch (error) {
      throw new ConfigError(
        `Could not parse configuration file ${resolvedConfigPath}: ${error.message}`,
      );
    }
  }

  const provider = config.provider || {};
  const defaults = config.defaults || {};
  const apiKeyEnv =
    environment.IMAGEGEN_API_KEY_ENV ||
    provider.api_key_env ||
    "IMAGEGEN_API_KEY";

  const settings = {
    provider: provider.name || "openai-compatible",
    baseUrl: String(
      overrides.baseUrl ||
        environment.IMAGEGEN_BASE_URL ||
        provider.base_url ||
        environment.OPENAI_BASE_URL ||
        DEFAULT_BASE_URL,
    ).replace(/\/+$/u, ""),
    apiKeyEnv,
    apiKey:
      environment.IMAGEGEN_API_KEY ||
      environment[apiKeyEnv] ||
      environment.OPENAI_API_KEY,
    model: String(
      overrides.model ||
        environment.IMAGEGEN_MODEL ||
        provider.model ||
        DEFAULT_MODEL,
    ),
    timeoutSeconds: number(
      environment.IMAGEGEN_TIMEOUT ?? provider.timeout_seconds,
      180,
      "timeout_seconds",
    ),
    maxRetries: integer(
      environment.IMAGEGEN_MAX_RETRIES ?? provider.max_retries,
      2,
      "max_retries",
    ),
    headers: {
      ...parseHeaders(provider.headers, "provider.headers"),
      ...parseHeaders(
        environment.IMAGEGEN_HEADERS_JSON,
        "IMAGEGEN_HEADERS_JSON",
      ),
    },
    size: String(environment.IMAGEGEN_SIZE || defaults.size || "auto"),
    quality: String(
      environment.IMAGEGEN_QUALITY || defaults.quality || "auto",
    ),
    outputFormat: String(
      environment.IMAGEGEN_OUTPUT_FORMAT ||
        defaults.output_format ||
        "png",
    ).toLowerCase(),
    outputDir: resolve(
      cwd,
      overrides.outputDir ||
        environment.IMAGEGEN_OUTPUT_DIR ||
        defaults.output_dir ||
        "output/imagegen",
    ),
    concurrency: integer(
      environment.IMAGEGEN_CONCURRENCY ?? defaults.concurrency,
      4,
      "concurrency",
    ),
    configPath: resolvedConfigPath,
  };
  validate(settings);
  return settings;
}

export function publicSettings(settings) {
  return {
    provider: settings.provider,
    base_url: settings.baseUrl,
    api_key_env: settings.apiKeyEnv,
    api_key_present: Boolean(settings.apiKey),
    model: settings.model,
    timeout_seconds: settings.timeoutSeconds,
    max_retries: settings.maxRetries,
    default_headers: Object.keys(settings.headers).sort(),
    size: settings.size,
    quality: settings.quality,
    output_format: settings.outputFormat,
    output_dir: settings.outputDir,
    concurrency: settings.concurrency,
    config_path: settings.configPath || null,
  };
}
