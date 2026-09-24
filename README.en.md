# Universal ImageGen Agent

A runtime-neutral image generation and editing skill for AI agents. It offers
a CLI, a Python API, machine-readable JSON output, configurable credentials,
custom base URLs, custom models, custom headers, and OpenAI-compatible Images
API support.

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
