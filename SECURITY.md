# Security

## Credentials

- Never commit API keys.
- Prefer `IMAGEGEN_API_KEY` or a custom environment variable named by
  `provider.api_key_env`.
- `.env` and `.imagegen.toml` are ignored by Git. The example files contain no
  real credentials.
- The CLI never accepts an API key as a command-line flag, so keys do not leak
  into shell history or process listings.
- `imagegen-agent config --json` reports only whether a key is present; it
  never prints the key.

## Custom endpoints

A custom `base_url` receives prompts, input images, request headers, and any
other data sent for generation or editing. Only configure endpoints you trust.
Provider-specific headers can contain secrets, so prefer
`IMAGEGEN_HEADERS_JSON` over committing headers to TOML.

## Output and downloads

The CLI refuses to overwrite output files unless `--force` is supplied. If an
API returns image URLs instead of base64 data, the CLI downloads those URLs
with a bounded timeout. Treat generated files as untrusted input when feeding
them to other tools.

## Reporting

Report security concerns privately to the repository owner rather than opening
a public issue that could expose users before a fix is available.

## npm publishing

Prefer npm Trusted Publishing through the repository's
`publish-npm.yml` workflow. If an `NPM_TOKEN` is used for the initial publish,
store it only as a GitHub Actions secret or in the local npm credential store.
Never commit `.npmrc` files containing authentication tokens.
