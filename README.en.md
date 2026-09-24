# Universal ImageGen Agent

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

```powershell
uv sync --extra dev
Copy-Item .env.example .env
# Set IMAGEGEN_API_KEY in .env
uv run imagegen-agent config
uv run imagegen-agent generate "A ceramic mug on a stone table" --dry-run --json
```

For full documentation, see [README.md](README.md).
