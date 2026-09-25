import assert from "node:assert/strict";
import test from "node:test";

import { buildPrompt } from "../node/prompting.js";

test("buildPrompt creates the shared structured prompt", () => {
  const result = buildPrompt("Create a campaign poster", {
    useCase: "ads-marketing",
    assetType: "vertical poster",
    style: "editorial photography",
    text: "Yours to Create.",
    constraints: "render the tagline exactly once",
    avoid: "watermarks",
  });

  assert.equal(
    result,
    [
      "Use case: ads-marketing",
      "Asset type: vertical poster",
      "Primary request: Create a campaign poster",
      "Style/medium: editorial photography",
      'Text (verbatim): "Yours to Create."',
      "Constraints: render the tagline exactly once",
      "Avoid: watermarks",
    ].join("\n"),
  );
});
