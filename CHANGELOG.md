# Changelog

## 0.1.2 — 2026-10-11

- Normalize both npm `bin` paths so npm publish does not remove the CLI entries.
- Retain the image-count validation fix, shared regression fixtures, and
  reproducible walkthrough introduced in 0.1.1.

## 0.1.1 — 2026-10-11

- Reject an explicit image count of zero in the Node.js generate and edit
  commands and JavaScript API. Previously `n=0` silently became `n=1`.
- Exercise the same image-count fixtures in the Node.js and Python CLIs:
  omitted values, zero, negative values, values above the limit, and both
  valid endpoints.
- Add a reproducible local generate/edit integration walkthrough, with
  clearly labeled fixture outputs and instructions for a real provider.

The default count remains one. Valid counts from one to ten are unchanged.
The Python CLI already rejected zero; its behavior is retained.

## 0.1.0 — 2026-09-26

- Initial npm release with Node.js and Python clients, configurable
  OpenAI-compatible providers, agent skill installation, and CI.
