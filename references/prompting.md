# Runtime-neutral prompting guidance

> This document was adapted on 2026-09-24 from the upstream `imagegen` skill.
> The original unmodified guidance is in `upstream/imagegen/references/`.

## Structure

Use this order when relevant:

1. scene or backdrop;
2. subject;
3. key visual details;
4. exact text;
5. constraints and invariants;
6. intended use.

For complex requests, short labeled lines are easier for both agents and image
models to inspect than one long paragraph.

## Specificity

- Preserve a detailed user prompt and normalize it without adding creative
  requirements.
- For a generic prompt, add only composition, intended-use, layout, or
  production details that materially improve the result.
- Do not invent extra characters, props, brands, slogans, color palettes, or
  narrative beats.

## Edits

- State `change only X; keep Y unchanged`.
- Repeat identity, geometry, framing, layout, text, and background invariants
  on every iteration.
- Label each input by index and role.
- Treat a style reference as generation unless the user asks to modify it.

## Exact text

- Put required text in quotes.
- Request verbatim rendering and no extra words.
- Specify typography and placement when they matter.
- Spell difficult names character by character when accuracy is critical.

## Iteration

Start with a clean prompt. Inspect the result, then request one targeted change
at a time while restating all critical invariants.
