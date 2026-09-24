import json
from pathlib import Path

from universal_imagegen.cli import main


def test_config_json_is_redacted(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("IMAGEGEN_API_KEY", "top-secret")

    exit_code = main(["config", "--json"])
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["configuration"]["api_key_present"] is True
    assert "top-secret" not in json.dumps(payload)


def test_generate_dry_run_json(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.chdir(tmp_path)
    out = tmp_path / "draft.png"

    exit_code = main(
        [
            "generate",
            "A ceramic mug",
            "--use-case",
            "product-mockup",
            "--out",
            str(out),
            "--dry-run",
            "--json",
        ]
    )
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["status"] == "dry-run"
    assert payload["operation"] == "generate"
    assert payload["outputs"] == [str(out.resolve())]


def test_edit_dry_run_json(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.chdir(tmp_path)
    source = tmp_path / "source.png"
    source.write_bytes(b"source")

    exit_code = main(
        [
            "edit",
            "--image",
            str(source),
            "--prompt",
            "Change only the background",
            "--out",
            str(tmp_path / "edited.png"),
            "--dry-run",
            "--json",
        ]
    )
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["operation"] == "edit"
    assert payload["request"]["images"] == [str(source.resolve())]


def test_batch_dry_run_has_stable_outputs(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.chdir(tmp_path)
    jobs = tmp_path / "jobs.jsonl"
    jobs.write_text(
        "\n".join(
            [
                '{"prompt":"A wolf","out":"wolf.png"}',
                '{"prompt":"A mug","out":"mug.png","quality":"high"}',
            ]
        ),
        encoding="utf-8",
    )

    exit_code = main(
        [
            "batch",
            str(jobs),
            "--out-dir",
            str(tmp_path / "batch"),
            "--dry-run",
            "--json",
        ]
    )
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["status"] == "dry-run"
    assert payload["jobs"] == 2
    outputs = [result["outputs"][0] for result in payload["results"]]
    assert outputs == [
        str((tmp_path / "batch" / "wolf.png").resolve()),
        str((tmp_path / "batch" / "mug.png").resolve()),
    ]


def test_invalid_extra_json_returns_request_error(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.chdir(tmp_path)
    exit_code = main(
        [
            "generate",
            "A mug",
            "--extra-json",
            "[]",
            "--dry-run",
            "--json",
        ]
    )
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 2
    assert payload["error_type"] == "RequestError"
