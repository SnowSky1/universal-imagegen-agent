import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { mkdtemp, readFile, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import test from "node:test";

import { ImageGenClient } from "../node/client.js";
import { RequestError } from "../node/errors.js";

const cases = JSON.parse(
  await readFile(new URL("../test-fixtures/image-counts.json", import.meta.url), "utf8"),
);
const cli = fileURLToPath(new URL("../bin/imagegen-agent.js", import.meta.url));

for (const operation of ["generate", "edit"]) {
  for (const scenario of cases) {
    test(`${operation} CLI image-count contract: ${scenario.name}`, async () => {
      const directory = await mkdtemp(join(tmpdir(), "imagegen-count-cli-"));
      try {
        const source = join(directory, "source.png");
        await writeFile(source, "input fixture for dry-run validation");
        const args = operation === "generate"
          ? ["generate", "A ceramic mug"]
          : ["edit", "--image", source, "--prompt", "Change the background"];
        if (scenario.n !== undefined) args.push("--n", String(scenario.n));
        const result = spawnSync(process.execPath, [cli, ...args, "--dry-run", "--json"], {
          cwd: directory,
          encoding: "utf8",
          timeout: 10_000,
          env: {
            ...process.env,
            IMAGEGEN_CONFIG: "",
            IMAGEGEN_API_KEY: "",
            IMAGEGEN_BASE_URL: "https://example.invalid/v1",
            IMAGEGEN_MODEL: "count-contract-fixture",
          },
        });
        assert.equal(result.error, undefined);
        assert.equal(result.status, scenario.exitCode, result.stdout || result.stderr);
        const payload = JSON.parse(result.stdout);
        if (scenario.exitCode === 0) {
          assert.equal(payload.request.n, scenario.expectedCount);
          assert.equal(payload.outputs.length, scenario.expectedCount);
        } else {
          assert.equal(payload.error_type, "RequestError");
          assert.equal(payload.exit_code, 2);
        }
      } finally {
        await rm(directory, { recursive: true, force: true });
      }
    });
  }

  test(`${operation} JavaScript API rejects an explicit numeric zero`, async () => {
    const directory = await mkdtemp(join(tmpdir(), "imagegen-count-api-"));
    try {
      const source = join(directory, "source.png");
      await writeFile(source, "input fixture for dry-run validation");
      const client = new ImageGenClient({
        provider: "openai-compatible",
        model: "count-contract-fixture",
        outputFormat: "png",
        outputDir: directory,
      });
      await assert.rejects(
        client[operation]({ prompt: "A mug", images: [source], n: 0 }, { dryRun: true }),
        RequestError,
      );
    } finally {
      await rm(directory, { recursive: true, force: true });
    }
  });
}
