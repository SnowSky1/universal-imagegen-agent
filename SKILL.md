---
name: "universal-imagegen"
description: "Bring the Codex imagegen workflow, prompt engineering, use-case taxonomy, edit invariants, and prompt library to any general-purpose agent, then generate or edit raster images through a configurable Images API. Supports OpenAI-compatible services and Qwen-Image deployments exposed through compatible gateways."
---

# Universal Image Generation Skill

> Adapted on 2026-09-24 from the OpenAI Codex `imagegen` skill. The unmodified
> source snapshot is preserved under `upstream/imagegen/`.

## Runtime contract

This skill does not assume a host-specific built-in image tool.

- Preferred execution: the npm/pnpm-installed `imagegen-agent` CLI.
- If the global command is unavailable and package execution is allowed, use
  `npx -y universal-imagegen-agent` or
  `pnpm dlx universal-imagegen-agent` as the command prefix.
- Reuse the bundled Codex-derived prompt library and workflow regardless of
  which compatible image model serves the request.
- Machine-readable execution: always add `--json`.
- Safe validation: run with `--dry-run` before a costly or destructive retry.
- Credentials: read from environment variables only. Never ask a user to paste
  a complete API key into chat and never pass a key on the command line.
- API portability: model, base URL, headers, and API-key environment variable
  are configurable. Do not assume one provider's model catalog.
- Open models: Qwen-Image and similar deployments can be used when exposed
  through the bundled OpenAI-compatible interface. For native Diffusers,
  ComfyUI, SGLang, or another protocol, add a provider adapter rather than
  changing the agent-facing workflow.
- Output safety: do not overwrite existing files unless the user explicitly
  authorizes replacement and `--force` is supplied.

## Installation

Install the CLI and this skill together:

```bash
npm install --global universal-imagegen-agent
imagegen-agent install-skill
```

Or install only the skill without keeping a global package:

```bash
npx universal-imagegen-agent install-skill
```

Restart or reload the host agent after installation. The installer defaults to
`$CODEX_HOME/skills/universal-imagegen`, or
`~/.codex/skills/universal-imagegen` when `CODEX_HOME` is unset. Use
`--target` for another compatible agent's skill directory.

## Intent decision

Classify the request independently along two axes:

1. Intent:
   - `generate`: create a new image; reference images guide style,
     composition, mood, or subject.
   - `edit`: preserve an existing image while changing specified parts.
2. Execution:
   - one asset;
   - multiple variants of one prompt (`--n`);
   - many distinct jobs (`batch` with one JSONL record per asset).

Assume `generate` unless the user explicitly asks to modify an existing image.
For edits, label each input image by index and role in the prompt.

## Workflow

1. Determine whether the output is a preview or a project deliverable.
2. Collect the primary request, exact in-image text, constraints, avoid list,
   input images, and required output path.
3. Check configuration with `imagegen-agent config --json`.
4. Structure the prompt using the schema below without inventing unrelated
   objects, brands, slogans, characters, palettes, or narrative details.
5. For an edit, state invariants as `change only X; keep Y unchanged`.
6. Run the intended request with `--dry-run --json`.
7. Execute the real request only when configuration and paths are correct.
8. Inspect every output for subject, composition, exact text, edit invariants,
   unwanted artifacts, and alpha-channel requirements.
9. Iterate with one targeted change at a time.
10. Report output paths, effective model/provider, and final prompt.

## Prompt schema

Use only the useful lines:

```text
Use case: <taxonomy slug>
Asset type: <where the asset will be used>
Primary request: <user's request>
Input images: <Image 1: role; Image 2: role>
Scene/backdrop: <environment>
Subject: <main subject>
Style/medium: <photo, illustration, 3D, etc.>
Composition/framing: <viewpoint, crop, placement>
Lighting/mood: <lighting and mood>
Color palette: <palette notes>
Materials/textures: <surface details>
Text (verbatim): "<exact text>"
Constraints: <must keep and must avoid>
Avoid: <negative constraints>
```

If the user prompt is already specific, normalize it without adding creative
requirements. If it is generic, add only details that materially improve
composition, intended use, or production quality.

## Taxonomy

Generate:

- `photorealistic-natural`
- `product-mockup`
- `ui-mockup`
- `infographic-diagram`
- `scientific-educational`
- `ads-marketing`
- `productivity-visual`
- `logo-brand`
- `illustration-story`
- `stylized-concept`
- `historical-scene`

Edit:

- `text-localization`
- `identity-preserve`
- `precise-object-edit`
- `lighting-weather`
- `background-extraction`
- `style-transfer`
- `compositing`
- `sketch-to-render`

## CLI recipes

Configuration:

```bash
imagegen-agent config --json
```

Generate:

```bash
imagegen-agent generate "A minimal ceramic mug product photo" \
  --use-case product-mockup \
  --composition "wide composition with usable negative space" \
  --constraints "no logos; no text; no watermark" \
  --out output/imagegen/mug.png \
  --json
```

Edit:

```bash
imagegen-agent edit \
  --image input.png \
  --prompt "Replace only the background with a warm sunset" \
  --constraints "keep the product, its edges, framing, and labels unchanged" \
  --out output/imagegen/sunset.png \
  --json
```

Batch:

```bash
imagegen-agent batch jobs.jsonl \
  --out-dir output/imagegen/batch \
  --concurrency 4 \
  --json
```

## Transparent output

Request an actually transparent background and use PNG or WebP. API capability
varies by provider and model. If native transparency is unsupported, explain
the limitation and ask before switching models or using chroma-key extraction.
Never silently change the selected model.

## Text and edits

- Put exact text in quotes and request verbatim rendering with no extra text.
- Spell difficult words character by character when accuracy is critical.
- Preserve edit invariants on every iteration.
- A mask guides generation but does not guarantee pixel-perfect boundaries.
- For multi-image edits, image order is meaningful.

## Boundaries

Use direct SVG, HTML/CSS, canvas, or repository-native editing instead when the
task is deterministic vector work, a small change to an editable source asset,
or an extension of an established icon/logo system.

## References

- `references/prompting.md`: runtime-neutral prompting guidance.
- `references/integration.md`: configuration and agent integration.
- `references/sample-jobs.jsonl`: batch examples.
- `upstream/imagegen/`: complete original skill snapshot.
