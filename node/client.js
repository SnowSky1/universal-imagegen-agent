import {
  access,
  mkdir,
  readFile,
  rename,
  rm,
  stat,
  writeFile,
} from "node:fs/promises";
import { basename, dirname, extname, resolve } from "node:path";
import { randomUUID } from "node:crypto";

import {
  ConfigError,
  OutputError,
  ProviderError,
  RequestError,
} from "./errors.js";
import { buildPrompt } from "./prompting.js";

const MAX_INPUT_BYTES = 50 * 1024 * 1024;
const MAX_DOWNLOAD_BYTES = 100 * 1024 * 1024;
const FORMATS = new Set(["png", "jpeg", "jpg", "webp"]);

async function exists(path) {
  try {
    await access(path);
    return true;
  } catch {
    return false;
  }
}

function normalizeFormat(value) {
  const format = String(value).toLowerCase();
  if (!FORMATS.has(format)) {
    throw new RequestError("output format must be png, jpeg, jpg, or webp.");
  }
  return format === "jpg" ? "jpeg" : format;
}

function validateCommon({
  n,
  background,
  outputFormat,
  outputCompression,
}) {
  if (!Number.isInteger(n) || n < 1 || n > 10) {
    throw new RequestError("n must be between 1 and 10.");
  }
  if (
    background !== undefined &&
    !["transparent", "opaque", "auto"].includes(background)
  ) {
    throw new RequestError("background must be transparent, opaque, or auto.");
  }
  if (
    background === "transparent" &&
    !["png", "webp"].includes(outputFormat)
  ) {
    throw new RequestError("Transparent output requires PNG or WebP.");
  }
  if (
    outputCompression !== undefined &&
    (!Number.isInteger(outputCompression) ||
      outputCompression < 0 ||
      outputCompression > 100)
  ) {
    throw new RequestError("output_compression must be between 0 and 100.");
  }
}

async function planOutputPaths({
  out,
  outputDir,
  outputFormat,
  count,
  force,
}) {
  const extension = `.${outputFormat}`;
  let base = resolve(out || `${outputDir}/output${extension}`);
  if (!extname(base)) base += extension;
  const suffix = extname(base).toLowerCase();
  const accepted = new Set([extension]);
  if (outputFormat === "jpeg") accepted.add(".jpg");
  if (!accepted.has(suffix)) {
    throw new RequestError(
      `Output extension ${suffix || "(none)"} does not match format ${outputFormat}.`,
    );
  }

  const stem = base.slice(0, -suffix.length);
  const paths =
    count === 1
      ? [base]
      : Array.from({ length: count }, (_, index) => `${stem}-${index + 1}${suffix}`);
  if (!force) {
    const existing = [];
    for (const path of paths) {
      if (await exists(path)) existing.push(path);
    }
    if (existing.length) {
      throw new RequestError(
        `Output already exists: ${existing.join(", ")} (use --force to overwrite)`,
      );
    }
  }
  return paths;
}

function cleanPayload(value) {
  return Object.fromEntries(
    Object.entries(value).filter(([, item]) => item !== undefined),
  );
}

async function validateInput(raw, label) {
  const path = resolve(String(raw));
  let info;
  try {
    info = await stat(path);
  } catch {
    throw new RequestError(`${label} file not found: ${path}`);
  }
  if (!info.isFile()) throw new RequestError(`${label} is not a file: ${path}`);
  if (info.size > MAX_INPUT_BYTES) {
    throw new RequestError(`${label} exceeds the 50MB input limit: ${path}`);
  }
  return path;
}

async function decodeResponse(response) {
  if (!response?.data || !Array.isArray(response.data)) {
    throw new OutputError("Provider response did not contain a data list.");
  }
  const images = [];
  const revisedPrompts = [];
  for (const [index, item] of response.data.entries()) {
    if (item.revised_prompt) revisedPrompts.push(String(item.revised_prompt));
    if (item.b64_json) {
      images.push(Buffer.from(item.b64_json, "base64"));
      continue;
    }
    if (item.url) {
      images.push(await downloadImage(String(item.url)));
      continue;
    }
    throw new OutputError(
      `Provider response image ${index + 1} contained neither b64_json nor url.`,
    );
  }
  if (!images.length) throw new OutputError("Provider returned no images.");
  return { images, revisedPrompts };
}

async function downloadImage(url) {
  if (!/^https?:\/\//u.test(url)) {
    throw new OutputError("Provider returned an unsupported image URL.");
  }
  let response;
  try {
    response = await fetch(url, { signal: AbortSignal.timeout(60_000) });
  } catch (error) {
    throw new OutputError(`Could not download provider image: ${error.message}`);
  }
  if (!response.ok) {
    throw new OutputError(
      `Could not download provider image: HTTP ${response.status}`,
    );
  }
  const length = Number(response.headers.get("content-length") || 0);
  if (length > MAX_DOWNLOAD_BYTES) {
    throw new OutputError("Provider image download exceeds 100MB.");
  }
  const bytes = Buffer.from(await response.arrayBuffer());
  if (bytes.length > MAX_DOWNLOAD_BYTES) {
    throw new OutputError("Provider image download exceeds 100MB.");
  }
  return bytes;
}

async function writeOutputs(images, paths, force) {
  if (images.length !== paths.length) {
    throw new OutputError(
      `Provider returned ${images.length} image(s), expected ${paths.length}.`,
    );
  }
  const written = [];
  for (let index = 0; index < paths.length; index += 1) {
    const path = paths[index];
    await mkdir(dirname(path), { recursive: true });
    if (!force && (await exists(path))) {
      throw new OutputError(`Output already exists: ${path}`);
    }
    const temporary = resolve(
      dirname(path),
      `.${basename(path)}.${randomUUID()}.tmp`,
    );
    try {
      await writeFile(temporary, images[index], { flag: "wx" });
      if (force && (await exists(path))) await rm(path);
      await rename(temporary, path);
      written.push(path);
    } catch (error) {
      await rm(temporary, { force: true }).catch(() => {});
      throw new OutputError(`Could not write output ${path}: ${error.message}`);
    }
  }
  return written;
}

async function requestJson(url, options, settings) {
  if (!settings.apiKey) {
    throw new ConfigError(
      `API key is missing. Set ${settings.apiKeyEnv} locally.`,
    );
  }
  let lastError;
  for (let attempt = 0; attempt <= settings.maxRetries; attempt += 1) {
    try {
      const response = await fetch(url, {
        ...options,
        headers: {
          Authorization: `Bearer ${settings.apiKey}`,
          ...settings.headers,
          ...options.headers,
        },
        signal: AbortSignal.timeout(settings.timeoutSeconds * 1000),
      });
      const text = await response.text();
      let payload;
      try {
        payload = text ? JSON.parse(text) : {};
      } catch {
        throw new ProviderError(
          `Image API returned non-JSON content (HTTP ${response.status}).`,
        );
      }
      if (!response.ok) {
        const message =
          payload?.error?.message ||
          payload?.message ||
          `Image API returned HTTP ${response.status}.`;
        const retryable = response.status === 429 || response.status >= 500;
        if (retryable && attempt < settings.maxRetries) {
          await new Promise((resolvePromise) =>
            setTimeout(resolvePromise, Math.min(1000 * 2 ** attempt, 10_000)),
          );
          continue;
        }
        throw new ProviderError(message);
      }
      return payload;
    } catch (error) {
      if (error instanceof ProviderError || error instanceof ConfigError) {
        throw error;
      }
      lastError = error;
      if (attempt < settings.maxRetries) continue;
    }
  }
  throw new ProviderError(`Image API request failed: ${lastError?.message}`);
}

export class ImageGenClient {
  constructor(settings) {
    this.settings = settings;
  }

  async generate(request, { dryRun = false } = {}) {
    const prompt = buildPrompt(
      request.prompt,
      request.promptSpec,
      request.augmentPrompt !== false,
    );
    const model = request.model || this.settings.model;
    const outputFormat = normalizeFormat(
      request.outputFormat || this.settings.outputFormat,
    );
    const n = Number(request.n || 1);
    validateCommon({
      n,
      background: request.background,
      outputFormat,
      outputCompression: request.outputCompression,
    });
    const outputs = await planOutputPaths({
      out: request.out,
      outputDir: this.settings.outputDir,
      outputFormat,
      count: n,
      force: Boolean(request.force),
    });
    const payload = cleanPayload({
      model,
      prompt,
      n,
      size: request.size || this.settings.size,
      quality: request.quality || this.settings.quality,
      background: request.background,
      output_format: outputFormat,
      output_compression: request.outputCompression,
      moderation: request.moderation,
      ...(request.extraBody || {}),
    });
    const preview = { ...payload, outputs };
    if (dryRun) {
      return {
        status: "dry-run",
        operation: "generate",
        provider: this.settings.provider,
        model,
        prompt,
        outputs,
        request: preview,
        revised_prompts: [],
        elapsed_seconds: null,
      };
    }

    const started = performance.now();
    const response = await requestJson(
      `${this.settings.baseUrl}/images/generations`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      },
      this.settings,
    );
    const { images, revisedPrompts } = await decodeResponse(response);
    const written = await writeOutputs(images, outputs, Boolean(request.force));
    return {
      status: "ok",
      operation: "generate",
      provider: this.settings.provider,
      model,
      prompt,
      outputs: written,
      request: preview,
      revised_prompts: revisedPrompts,
      elapsed_seconds: Number(((performance.now() - started) / 1000).toFixed(3)),
    };
  }

  async edit(request, { dryRun = false } = {}) {
    const imagePaths = [];
    for (const image of request.images || []) {
      imagePaths.push(await validateInput(image, "Image"));
    }
    if (!imagePaths.length) {
      throw new RequestError("At least one edit image is required.");
    }
    const maskPath = request.mask
      ? await validateInput(request.mask, "Mask")
      : undefined;
    const prompt = buildPrompt(
      request.prompt,
      request.promptSpec,
      request.augmentPrompt !== false,
    );
    const model = request.model || this.settings.model;
    const outputFormat = normalizeFormat(
      request.outputFormat || this.settings.outputFormat,
    );
    const n = Number(request.n || 1);
    validateCommon({
      n,
      background: request.background,
      outputFormat,
      outputCompression: request.outputCompression,
    });
    if (
      request.inputFidelity !== undefined &&
      !["low", "high"].includes(request.inputFidelity)
    ) {
      throw new RequestError("input_fidelity must be low or high.");
    }
    const outputs = await planOutputPaths({
      out: request.out,
      outputDir: this.settings.outputDir,
      outputFormat,
      count: n,
      force: Boolean(request.force),
    });
    const fields = cleanPayload({
      model,
      prompt,
      n,
      size: request.size || this.settings.size,
      quality: request.quality || this.settings.quality,
      background: request.background,
      output_format: outputFormat,
      output_compression: request.outputCompression,
      input_fidelity: request.inputFidelity,
      moderation: request.moderation,
      ...(request.extraBody || {}),
    });
    const preview = {
      ...fields,
      images: imagePaths,
      mask: maskPath || null,
      outputs,
    };
    if (dryRun) {
      return {
        status: "dry-run",
        operation: "edit",
        provider: this.settings.provider,
        model,
        prompt,
        outputs,
        request: preview,
        revised_prompts: [],
        elapsed_seconds: null,
      };
    }

    const form = new FormData();
    for (const [key, value] of Object.entries(fields)) {
      if (value !== undefined) form.append(key, String(value));
    }
    for (const path of imagePaths) {
      const bytes = await readFile(path);
      form.append("image", new Blob([bytes]), basename(path));
    }
    if (maskPath) {
      form.append(
        "mask",
        new Blob([await readFile(maskPath)]),
        basename(maskPath),
      );
    }
    const started = performance.now();
    const response = await requestJson(
      `${this.settings.baseUrl}/images/edits`,
      { method: "POST", body: form },
      this.settings,
    );
    const { images, revisedPrompts } = await decodeResponse(response);
    const written = await writeOutputs(images, outputs, Boolean(request.force));
    return {
      status: "ok",
      operation: "edit",
      provider: this.settings.provider,
      model,
      prompt,
      outputs: written,
      request: preview,
      revised_prompts: revisedPrompts,
      elapsed_seconds: Number(((performance.now() - started) / 1000).toFixed(3)),
    };
  }
}
