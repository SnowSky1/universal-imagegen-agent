# Universal ImageGen Agent

[![GitHub stars](https://img.shields.io/github/stars/SnowSky1/universal-imagegen-agent?style=flat-square)](https://github.com/SnowSky1/universal-imagegen-agent/stargazers)
[![CI](https://img.shields.io/github/actions/workflow/status/SnowSky1/universal-imagegen-agent/ci.yml?branch=main&style=flat-square&label=CI)](https://github.com/SnowSky1/universal-imagegen-agent/actions/workflows/ci.yml)
[![License](https://img.shields.io/github/license/SnowSky1/universal-imagegen-agent?style=flat-square)](LICENSE)

A runtime-neutral image generation and editing skill that brings the workflow,
prompt engineering, use-case taxonomy, edit invariants, and prompt library of
the OpenAI Codex `imagegen` skill to any general-purpose AI agent. Agents can
reuse this mature image-generation methodology through a CLI or Python API
without depending on a Codex-only built-in image tool.

This is especially useful as open image ecosystems such as Qwen-Image and
Qwen-Image-2.1 grow. The project separates the agent-side workflow from the
model backend: it can use OpenAI Images APIs, third-party compatible services,
or Qwen-Image deployments exposed through an OpenAI-compatible gateway. A
different serving protocol can be supported by adding a provider adapter
without rewriting the prompt library or agent workflow.

The currently bundled provider is OpenAI-compatible. Native local Diffusers,
ComfyUI, and SGLang backends for Qwen-Image are not built in yet.

It offers a CLI, a Python API, machine-readable JSON output, configurable
credentials, custom base URLs, custom models, custom headers, and compatible
Images API support.

The original Codex `imagegen` skill is preserved unchanged under
`upstream/imagegen/`. The adapted root `SKILL.md` is suitable for agents with
shell access and does not depend on a Codex-only built-in image tool.

## Quick start

```bash
npm install --global universal-imagegen-agent
imagegen-agent install-skill
imagegen-agent config --json
imagegen-agent generate "A ceramic mug on a stone table" --dry-run --json
```

With pnpm:

```bash
pnpm add --global universal-imagegen-agent
imagegen-agent install-skill
```

Without a global install:

```bash
npx universal-imagegen-agent install-skill
pnpm dlx universal-imagegen-agent generate "A ceramic mug" --dry-run --json
```

Install the latest GitHub version before an npm release:

```bash
npm install --global github:SnowSky1/universal-imagegen-agent
```

For full documentation, see [README.md](README.md).
