import assert from "node:assert/strict";
import { access, mkdtemp, readFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import test from "node:test";

import { installSkill } from "../node/install-skill.js";

test("installSkill creates a self-contained Codex skill", async () => {
  const root = await mkdtemp(join(tmpdir(), "imagegen-skill-"));
  const destination = await installSkill({ target: root });

  await access(join(destination, "SKILL.md"));
  await access(join(destination, "agents", "openai.yaml"));
  await access(join(destination, "references", "prompting.md"));
  const skill = await readFile(join(destination, "SKILL.md"), "utf8");
  assert.match(skill, /^---\nname: "universal-imagegen"/u);
});
