import assert from "node:assert/strict";
import { Buffer } from "node:buffer";
import { createServer } from "node:http";
import { mkdtemp, readFile, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import test from "node:test";

import { ImageGenClient } from "../node/client.js";

async function fakeApi() {
  const records = [];
  const server = createServer(async (request, response) => {
    const chunks = [];
    for await (const chunk of request) chunks.push(chunk);
    const body = Buffer.concat(chunks);
    records.push({ method: request.method, url: request.url, headers: request.headers, body });

    if (request.url === "/v1/images/generations") {
      const payload = JSON.stringify({
        data: [{ b64_json: Buffer.from("generated").toString("base64") }],
      });
      response.writeHead(200, { "content-type": "application/json" });
      response.end(payload);
      return;
    }
    if (request.url === "/v1/images/edits") {
      const address = server.address();
      const payload = JSON.stringify({
        data: [{ url: `http://127.0.0.1:${address.port}/image.png` }],
      });
      response.writeHead(200, { "content-type": "application/json" });
      response.end(payload);
      return;
    }
    if (request.url === "/image.png") {
      response.writeHead(200, { "content-type": "image/png" });
      response.end("edited");
      return;
    }
    response.writeHead(404).end();
  });
  await new Promise((resolvePromise) =>
    server.listen(0, "127.0.0.1", resolvePromise),
  );
  return {
    records,
    baseUrl: `http://127.0.0.1:${server.address().port}/v1`,
    close: () =>
      new Promise((resolvePromise) => server.close(resolvePromise)),
  };
}

function settings(baseUrl, outputDir) {
  return {
    provider: "openai-compatible",
    baseUrl,
    apiKeyEnv: "IMAGEGEN_API_KEY",
    apiKey: "test-key",
    model: "test-model",
    timeoutSeconds: 30,
    maxRetries: 0,
    headers: { "x-agent-test": "enabled" },
    size: "auto",
    quality: "auto",
    outputFormat: "png",
    outputDir,
    concurrency: 2,
  };
}

test("generate calls a custom compatible endpoint and writes base64 output", async () => {
  const api = await fakeApi();
  const directory = await mkdtemp(join(tmpdir(), "imagegen-node-"));
  try {
    const out = join(directory, "generated.png");
    const result = await new ImageGenClient(
      settings(api.baseUrl, directory),
    ).generate({ prompt: "A mug", out });

    assert.equal(result.status, "ok");
    assert.equal((await readFile(out, "utf8")), "generated");
    assert.equal(api.records[0].url, "/v1/images/generations");
    assert.equal(api.records[0].headers.authorization, "Bearer test-key");
    assert.equal(api.records[0].headers["x-agent-test"], "enabled");
  } finally {
    await api.close();
  }
});

test("edit sends multipart data and downloads URL output", async () => {
  const api = await fakeApi();
  const directory = await mkdtemp(join(tmpdir(), "imagegen-node-edit-"));
  try {
    const source = join(directory, "source.png");
    const out = join(directory, "edited.png");
    await writeFile(source, "source-image");
    const result = await new ImageGenClient(
      settings(api.baseUrl, directory),
    ).edit({ prompt: "Change only the background", images: [source], out });

    assert.equal(result.status, "ok");
    assert.equal((await readFile(out, "utf8")), "edited");
    assert.equal(api.records[0].url, "/v1/images/edits");
    assert.match(api.records[0].headers["content-type"], /^multipart\/form-data/u);
    assert.equal(api.records[0].body.includes(Buffer.from("source-image")), true);
  } finally {
    await api.close();
  }
});
