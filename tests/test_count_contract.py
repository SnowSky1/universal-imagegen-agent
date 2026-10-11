import json
from pathlib import Path

import pytest

from universal_imagegen.cli import main

CASES = json.loads(
    (Path(__file__).resolve().parents[1] / "test-fixtures" / "image-counts.json").read_text(
        encoding="utf-8"
    )
)


@pytest.mark.parametrize("operation", ["generate", "edit"])
@pytest.mark.parametrize("scenario", CASES, ids=lambda case: case["name"])
def test_cli_image_count_contract(operation, scenario, tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("IMAGEGEN_CONFIG", raising=False)
    monkeypatch.setenv("IMAGEGEN_API_KEY", "")
    monkeypatch.setenv("IMAGEGEN_BASE_URL", "https://example.invalid/v1")
    monkeypatch.setenv("IMAGEGEN_MODEL", "count-contract-fixture")
    source = tmp_path / "source.png"
    source.write_bytes(b"input fixture for dry-run validation")
    args = (
        ["generate", "A ceramic mug"]
        if operation == "generate"
        else ["edit", "--image", str(source), "--prompt", "Change the background"]
    )
    if "n" in scenario:
        args.extend(["--n", str(scenario["n"])])
    exit_code = main([*args, "--dry-run", "--json"])
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == scenario["exitCode"]
    if exit_code == 0:
        assert payload["request"]["n"] == scenario["expectedCount"]
        assert len(payload["outputs"]) == scenario["expectedCount"]
    else:
        assert payload["error_type"] == "RequestError"
        assert payload["exit_code"] == 2
