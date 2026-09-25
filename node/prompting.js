import { readFile } from "node:fs/promises";

import { RequestError } from "./errors.js";

export async function readPrompt(prompt, promptFile) {
  if (prompt && promptFile) {
    throw new RequestError("Use a prompt argument or --prompt-file, not both.");
  }
  const value = promptFile ? await readFile(promptFile, "utf8") : prompt;
  if (!value?.trim()) throw new RequestError("A non-empty prompt is required.");
  return value.trim();
}

export function buildPrompt(primaryRequest, spec = {}, augment = true) {
  const request = primaryRequest?.trim();
  if (!request) throw new RequestError("A non-empty prompt is required.");
  if (!augment) return request;

  const sections = [];
  if (spec.useCase) sections.push(`Use case: ${spec.useCase}`);
  if (spec.assetType) sections.push(`Asset type: ${spec.assetType}`);
  sections.push(`Primary request: ${request}`);
  if (spec.inputImages?.length) {
    sections.push(`Input images: ${spec.inputImages.join("; ")}`);
  }
  if (spec.scene) sections.push(`Scene/backdrop: ${spec.scene}`);
  if (spec.subject) sections.push(`Subject: ${spec.subject}`);
  if (spec.style) sections.push(`Style/medium: ${spec.style}`);
  if (spec.composition) {
    sections.push(`Composition/framing: ${spec.composition}`);
  }
  if (spec.lighting) sections.push(`Lighting/mood: ${spec.lighting}`);
  if (spec.palette) sections.push(`Color palette: ${spec.palette}`);
  if (spec.materials) sections.push(`Materials/textures: ${spec.materials}`);
  if (spec.text) sections.push(`Text (verbatim): "${spec.text}"`);
  if (spec.constraints) sections.push(`Constraints: ${spec.constraints}`);
  if (spec.avoid) sections.push(`Avoid: ${spec.avoid}`);
  return sections.join("\n");
}
