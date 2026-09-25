import {
  access,
  copyFile,
  cp,
  mkdir,
  readFile,
  rm,
  writeFile,
} from "node:fs/promises";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

import { RequestError } from "./errors.js";

const packageRoot = resolve(dirname(fileURLToPath(import.meta.url)), "..");

async function exists(path) {
  try {
    await access(path);
    return true;
  } catch {
    return false;
  }
}

function defaultSkillsRoot() {
  const home =
    process.env.CODEX_HOME ||
    process.env.HOME ||
    process.env.USERPROFILE;
  if (!home) {
    throw new RequestError(
      "Cannot determine the skill directory. Pass --target explicitly.",
    );
  }
  return process.env.CODEX_HOME
    ? join(process.env.CODEX_HOME, "skills")
    : join(home, ".codex", "skills");
}

export async function installSkill({
  target,
  force = false,
  name = "universal-imagegen",
} = {}) {
  const root = resolve(target || defaultSkillsRoot());
  const destination = join(root, name);
  if (await exists(destination)) {
    if (!force) {
      throw new RequestError(
        `Skill already exists: ${destination} (use --force to replace it)`,
      );
    }
    await rm(destination, { recursive: true, force: true });
  }

  await mkdir(join(destination, "agents"), { recursive: true });
  await mkdir(join(destination, "references"), { recursive: true });
  await copyFile(
    join(packageRoot, "SKILL.md"),
    join(destination, "SKILL.md"),
  );
  await cp(join(packageRoot, "agents"), join(destination, "agents"), {
    recursive: true,
  });
  await cp(join(packageRoot, "references"), join(destination, "references"), {
    recursive: true,
  });

  const manifest = {
    installed_by: "universal-imagegen-agent",
    package_version: JSON.parse(
      await readFile(join(packageRoot, "package.json"), "utf8"),
    ).version,
    source: "https://github.com/SnowSky1/universal-imagegen-agent",
  };
  await writeFile(
    join(destination, ".installation.json"),
    `${JSON.stringify(manifest, null, 2)}\n`,
    "utf8",
  );
  return destination;
}
