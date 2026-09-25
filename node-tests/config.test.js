import assert from "node:assert/strict";
import { mkdtemp, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import test from "node:test";

import { loadSettings, publicSettings } from "../node/config.js";

test("configuration preserves precedence and redacts the key", async () => {
  const directory = await mkdtemp(join(tmpdir(), "imagegen-config-"));
  await writeFile(
    join(directory, ".imagegen.toml"),
    [
      "[provider]",
      'base_url = "https://toml.example/v1"',
      'api_key_env = "CUSTOM_KEY"',
      'model = "toml-model"',
      "",
      "[defaults]",
      'quality = "medium"',
    ].join("\n"),
  );
  const settings = await loadSettings({
    cwd: directory,
    environ: {
      CUSTOM_KEY: "secret",
      IMAGEGEN_MODEL: "env-model",
      IMAGEGEN_QUALITY: "high",
    },
    loadProjectDotenv: false,
  });
  const publicValue = publicSettings(settings);

  assert.equal(settings.baseUrl, "https://toml.example/v1");
  assert.equal(settings.model, "env-model");
  assert.equal(settings.quality, "high");
  assert.equal(publicValue.api_key_present, true);
  assert.equal(JSON.stringify(publicValue).includes("secret"), false);
});
