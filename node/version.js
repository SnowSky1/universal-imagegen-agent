import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const packageRoot = resolve(dirname(fileURLToPath(import.meta.url)), "..");

export const VERSION = JSON.parse(
  readFileSync(resolve(packageRoot, "package.json"), "utf8"),
).version;
