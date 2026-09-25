import { readFile } from "node:fs/promises";
import { basename, resolve } from "node:path";

import { ImageGenClient } from "./client.js";
import { loadSettings, publicSettings } from "./config.js";
import { ImageGenError, RequestError } from "./errors.js";
import { installSkill } from "./install-skill.js";
import { buildPrompt, readPrompt } from "./prompting.js";
import { VERSION } from "./version.js";

const VALUE_OPTIONS = new Set([
  "config",
  "base-url",
  "model",
  "output-dir",
  "prompt",
  "prompt-file",
  "use-case",
  "asset-type",
  "scene",
  "subject",
  "style",
  "composition",
  "lighting",
  "palette",
  "materials",
  "text",
  "constraints",
  "avoid",
  "out",
  "n",
  "size",
  "quality",
  "background",
  "output-format",
  "format",
  "output-compression",
  "moderation",
  "extra-json",
  "mask",
  "input-fidelity",
  "out-dir",
  "concurrency",
  "target",
  "name",
]);
const MULTI_OPTIONS = new Set(["image", "input-role"]);
const FLAG_OPTIONS = new Set([
  "json",
  "dry-run",
  "force",
  "no-augment",
  "fail-fast",
  "help",
]);

function camel(value) {
  return value.replace(/-([a-z])/gu, (_, character) => character.toUpperCase());
}

function parseArguments(tokens) {
  const options = {};
  const positionals = [];
  for (let index = 0; index < tokens.length; index += 1) {
    const token = tokens[index];
    if (!token.startsWith("--")) {
      positionals.push(token);
      continue;
    }
    const equal = token.indexOf("=");
    const rawName = token.slice(2, equal >= 0 ? equal : undefined);
    const name = camel(rawName);
    if (FLAG_OPTIONS.has(rawName)) {
      if (equal >= 0) {
        throw new RequestError(`--${rawName} does not accept a value.`);
      }
      options[name] = true;
      continue;
    }
    if (!VALUE_OPTIONS.has(rawName) && !MULTI_OPTIONS.has(rawName)) {
      throw new RequestError(`Unknown option: --${rawName}`);
    }
    const value =
      equal >= 0
        ? token.slice(equal + 1)
        : tokens[index + 1] && !tokens[index + 1].startsWith("--")
          ? tokens[++index]
          : undefined;
    if (value === undefined) {
      throw new RequestError(`--${rawName} requires a value.`);
    }
    if (MULTI_OPTIONS.has(rawName)) {
      options[name] ||= [];
      options[name].push(value);
    } else {
      options[name] = value;
    }
  }
  return { options, positionals };
}

function promptSpec(options) {
  return {
    useCase: options.useCase,
    assetType: options.assetType,
    inputImages: options.inputRole || [],
    scene: options.scene,
    subject: options.subject,
    style: options.style,
    composition: options.composition,
    lighting: options.lighting,
    palette: options.palette,
    materials: options.materials,
    text: options.text,
    constraints: options.constraints,
    avoid: options.avoid,
  };
}

function parseJsonObject(raw, name) {
  if (!raw) return {};
  try {
    const value = JSON.parse(raw);
    if (!value || Array.isArray(value) || typeof value !== "object") {
      throw new Error("expected an object");
    }
    return value;
  } catch (error) {
    throw new RequestError(`${name} must be a JSON object: ${error.message}`);
  }
}

function integer(raw, fallback, name) {
  if (raw === undefined) return fallback;
  const value = Number(raw);
  if (!Number.isInteger(value)) {
    throw new RequestError(`${name} must be an integer.`);
  }
  return value;
}

async function settingsFrom(options) {
  return loadSettings({
    configPath: options.config,
    overrides: {
      baseUrl: options.baseUrl,
      model: options.model,
      outputDir: options.outputDir,
    },
  });
}

function generateRequest(options, prompt, overrides = {}) {
  return {
    prompt,
    out: overrides.out || options.out,
    promptSpec: overrides.promptSpec || promptSpec(options),
    augmentPrompt: overrides.augment ?? !options.noAugment,
    model: overrides.model || options.model,
    n: integer(overrides.n ?? options.n, 1, "n"),
    size: overrides.size || options.size,
    quality: overrides.quality || options.quality,
    background: overrides.background || options.background,
    outputFormat:
      overrides.outputFormat || options.outputFormat || options.format,
    outputCompression:
      overrides.outputCompression ??
      (options.outputCompression === undefined
        ? undefined
        : integer(options.outputCompression, undefined, "output_compression")),
    moderation: overrides.moderation || options.moderation,
    extraBody:
      overrides.extraBody || parseJsonObject(options.extraJson, "--extra-json"),
    force: overrides.force ?? Boolean(options.force),
  };
}

function humanResult(result) {
  const lines = [
    `Status: ${result.status}`,
    `Operation: ${result.operation}`,
    `Provider: ${result.provider}`,
    `Model: ${result.model}`,
  ];
  for (const output of result.outputs || []) lines.push(`Output: ${output}`);
  if (result.elapsed_seconds !== null && result.elapsed_seconds !== undefined) {
    lines.push(`Elapsed: ${result.elapsed_seconds.toFixed(3)}s`);
  }
  return lines.join("\n");
}

function emit(payload, jsonOutput = false) {
  if (jsonOutput) {
    console.log(JSON.stringify(payload, null, 2));
    return;
  }
  if (payload.operation) {
    console.log(humanResult(payload));
    return;
  }
  console.log(JSON.stringify(payload, null, 2));
}

function help() {
  return `Universal ImageGen Agent ${VERSION}

Usage:
  imagegen-agent config [options]
  imagegen-agent prompt <request> [options]
  imagegen-agent generate <request> [options]
  imagegen-agent edit --image <path> --prompt <request> [options]
  imagegen-agent batch <jobs.jsonl> --out-dir <directory> [options]
  imagegen-agent install-skill [--target <skills-directory>] [--force]

Examples:
  imagegen-agent config --json
  imagegen-agent generate "A ceramic mug" --dry-run --json
  imagegen-agent edit --image input.png --prompt "Change only the background"
  imagegen-agent install-skill

Run through npm/pnpm without installing:
  npx universal-imagegen-agent generate "A ceramic mug" --dry-run --json
  pnpm dlx universal-imagegen-agent install-skill
`;
}

async function readBatch(path) {
  const jobs = [];
  const lines = (await readFile(resolve(path), "utf8")).split(/\r?\n/u);
  for (let index = 0; index < lines.length; index += 1) {
    const line = lines[index].trim();
    if (!line || line.startsWith("#")) continue;
    let job;
    try {
      job = JSON.parse(line);
    } catch (error) {
      throw new RequestError(
        `Invalid JSON on line ${index + 1}: ${error.message}`,
      );
    }
    if (typeof job === "string") job = { prompt: job };
    if (!job || typeof job !== "object" || !String(job.prompt || "").trim()) {
      throw new RequestError(`Batch line ${index + 1} must contain a prompt.`);
    }
    jobs.push({ ...job, line: index + 1 });
  }
  if (!jobs.length) throw new RequestError("Batch input contains no jobs.");
  if (jobs.length > 500) {
    throw new RequestError("Batch input exceeds the 500-job limit.");
  }
  return jobs;
}

function slugify(value) {
  return (
    value
      .toLowerCase()
      .replace(/[^a-z0-9]+/gu, "-")
      .replace(/^-+|-+$/gu, "")
      .slice(0, 48) || "job"
  );
}

function jobPromptSpec(job) {
  const fields = job.fields || {};
  const value = (name) => job[name] ?? fields[name];
  let roles = value("input_images") ?? value("input_roles") ?? [];
  if (typeof roles === "string") roles = [roles];
  if (!Array.isArray(roles)) {
    throw new RequestError(
      `Batch line ${job.line}: input_images must be a string or list.`,
    );
  }
  return {
    useCase: value("use_case"),
    assetType: value("asset_type"),
    inputImages: roles.map(String),
    scene: value("scene"),
    subject: value("subject"),
    style: value("style"),
    composition: value("composition"),
    lighting: value("lighting"),
    palette: value("palette"),
    materials: value("materials"),
    text: value("text"),
    constraints: value("constraints"),
    avoid: value("avoid") ?? value("negative"),
  };
}

async function runBatch(options, positional) {
  const input = positional[0];
  if (!input) throw new RequestError("batch requires a JSONL input file.");
  if (!options.outDir) throw new RequestError("batch requires --out-dir.");
  const settings = await settingsFrom(options);
  const jobs = await readBatch(input);
  const concurrency = integer(
    options.concurrency,
    settings.concurrency,
    "concurrency",
  );
  if (concurrency < 1 || concurrency > 25) {
    throw new RequestError("concurrency must be between 1 and 25.");
  }
  const results = Array(jobs.length);
  const failures = [];
  let cursor = 0;
  let stopped = false;

  async function worker() {
    while (!stopped) {
      const index = cursor++;
      if (index >= jobs.length) return;
      const job = jobs[index];
      try {
        const format = String(
          job.output_format || job.format || settings.outputFormat,
        );
        const out = resolve(
          options.outDir,
          basename(
            job.out ||
              `${String(index + 1).padStart(3, "0")}-${slugify(job.prompt)}.${format}`,
          ),
        );
        const request = generateRequest(options, String(job.prompt), {
          out,
          promptSpec: jobPromptSpec(job),
          augment: job.augment !== false,
          model: job.model,
          n: integer(job.n, 1, "n"),
          size: job.size,
          quality: job.quality,
          background: job.background,
          outputFormat: format,
          outputCompression: job.output_compression,
          moderation: job.moderation,
          extraBody: job.extra_body || {},
          force: Boolean(options.force || job.force),
        });
        results[index] = await new ImageGenClient(settings).generate(request, {
          dryRun: Boolean(options.dryRun),
        });
      } catch (error) {
        failures.push({
          job: index + 1,
          line: job.line,
          error: error.message,
          error_type: error.name,
        });
        if (options.failFast) stopped = true;
      }
    }
  }

  await Promise.all(
    Array.from({ length: Math.min(concurrency, jobs.length) }, () => worker()),
  );
  return {
    status: failures.length
      ? "partial"
      : options.dryRun
        ? "dry-run"
        : "ok",
    operation: "batch",
    jobs: jobs.length,
    results: results.filter(Boolean),
    failures,
    exitCode: failures.length ? 1 : 0,
  };
}

async function dispatch(command, options, positional) {
  if (options.help || command === "help") {
    console.log(help());
    return 0;
  }
  if (command === "config") {
    emit(
      {
        status: "ok",
        configuration: publicSettings(await settingsFrom(options)),
      },
      options.json,
    );
    return 0;
  }
  if (command === "prompt") {
    const prompt = await readPrompt(positional[0], options.promptFile);
    const result = buildPrompt(prompt, promptSpec(options), !options.noAugment);
    emit({ status: "ok", prompt: result }, options.json);
    return 0;
  }
  if (command === "generate") {
    const prompt = await readPrompt(positional[0], options.promptFile);
    const result = await new ImageGenClient(
      await settingsFrom(options),
    ).generate(generateRequest(options, prompt), {
      dryRun: Boolean(options.dryRun),
    });
    emit(result, options.json);
    return 0;
  }
  if (command === "edit") {
    const prompt = await readPrompt(options.prompt, options.promptFile);
    const settings = await settingsFrom(options);
    const result = await new ImageGenClient(settings).edit(
      {
        ...generateRequest(options, prompt),
        images: options.image || [],
        mask: options.mask,
        inputFidelity: options.inputFidelity,
      },
      { dryRun: Boolean(options.dryRun) },
    );
    emit(result, options.json);
    return 0;
  }
  if (command === "batch") {
    const result = await runBatch(options, positional);
    const exitCode = result.exitCode;
    delete result.exitCode;
    emit(result, options.json);
    return exitCode;
  }
  if (command === "install-skill") {
    const destination = await installSkill({
      target: options.target,
      force: Boolean(options.force),
      name: options.name,
    });
    emit(
      {
        status: "ok",
        operation: "install-skill",
        destination,
        restart_required: true,
      },
      options.json,
    );
    return 0;
  }
  throw new RequestError(`Unknown command: ${command}`);
}

export async function main(argv = process.argv.slice(2)) {
  if (argv.includes("--version") || argv.includes("-v")) {
    console.log(`imagegen-agent ${VERSION}`);
    return 0;
  }
  if (!argv.length || argv.includes("--help") && argv.length === 1) {
    console.log(help());
    return 0;
  }
  const jsonOutput = argv.includes("--json");
  try {
    const command = argv[0];
    const { options, positionals } = parseArguments(argv.slice(1));
    return await dispatch(command, options, positionals);
  } catch (error) {
    const expected = error instanceof ImageGenError;
    const exitCode = expected ? error.exitCode : 1;
    if (jsonOutput) {
      console.log(
        JSON.stringify(
          {
            status: "error",
            error: error.message,
            error_type: error.name,
            exit_code: exitCode,
          },
          null,
          2,
        ),
      );
    } else {
      console.error(`Error: ${error.message}`);
    }
    return exitCode;
  }
}
