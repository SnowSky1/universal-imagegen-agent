# Integration guide

This project is deliberately host-neutral. Any agent that can execute a command
and parse JSON can use it.

## Install through npm or pnpm

```bash
npm install --global universal-imagegen-agent
# or
pnpm add --global universal-imagegen-agent
```

Install the accompanying skill:

```bash
imagegen-agent install-skill
```

For an ephemeral invocation, use `npx universal-imagegen-agent` or
`pnpm dlx universal-imagegen-agent`.

## Stable command contract

Use:

```bash
imagegen-agent <command> ... --json
```

Commands:

- `config`: resolved non-secret configuration.
- `prompt`: structured prompt only; no API request.
- `generate`: one request or variants of one request.
- `edit`: one or more image inputs, optionally with a mask.
- `batch`: distinct generation jobs from JSONL.

Exit codes:

- `0`: success.
- `1`: provider, network, download, or output failure.
- `2`: invalid configuration or invalid user request.
- `130`: interrupted.

Standard output is a single JSON object when `--json` is used. Human progress
or error text is kept out of successful JSON output.

## Configuration order

Highest to lowest priority:

1. CLI overrides for non-secret values.
2. `IMAGEGEN_*` environment variables and project `.env`.
3. TOML selected by `--config`, `IMAGEGEN_CONFIG`, or `.imagegen.toml`.
4. package defaults.

Credentials are intentionally not accepted as a CLI flag. Configure
`provider.api_key_env` in TOML and set that environment variable locally.
`IMAGEGEN_API_KEY` is the universal direct override; `OPENAI_API_KEY` remains a
compatibility fallback.

## Generic agent policy

An integrating agent should:

1. run `config --json`;
2. ask the user to configure the named environment variable if
   `api_key_present` is false and a live call is needed;
3. run the intended request with `--dry-run --json`;
4. verify output paths and model;
5. perform the live request;
6. inspect output files;
7. report the final paths and prompt.

Never print the contents of `.env`, credential environment variables, or
authorization headers.

## Provider compatibility

The current provider adapter uses the official OpenAI Python SDK with a
configurable `base_url`. A compatible service should implement image
generation and edit operations and return either base64 image data or image
URLs in the standard response data list.

Provider-specific request fields can be supplied through `extra_body` in the
Python API, `--extra-json` in a one-off CLI request, or `extra_body` in a batch
job.
