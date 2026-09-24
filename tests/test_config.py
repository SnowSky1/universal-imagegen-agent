from pathlib import Path

import pytest

from universal_imagegen.config import DEFAULT_MODEL, ConfigError, load_settings


def test_defaults_are_safe_and_key_is_redacted(tmp_path: Path) -> None:
    settings = load_settings(
        cwd=tmp_path,
        environ={},
        load_project_dotenv=False,
    )

    assert settings.model == DEFAULT_MODEL
    assert settings.api_key is None
    public = settings.public_dict()
    assert public["api_key_present"] is False
    assert "api_key" not in public


def test_toml_then_environment_precedence(tmp_path: Path) -> None:
    config = tmp_path / "config.toml"
    config.write_text(
        """
[provider]
base_url = "https://toml.example/v1"
api_key_env = "CUSTOM_KEY"
model = "toml-model"

[defaults]
quality = "medium"
concurrency = 3
""".strip(),
        encoding="utf-8",
    )
    settings = load_settings(
        config,
        cwd=tmp_path,
        environ={
            "CUSTOM_KEY": "secret",
            "IMAGEGEN_MODEL": "env-model",
            "IMAGEGEN_QUALITY": "high",
        },
        load_project_dotenv=False,
    )

    assert settings.base_url == "https://toml.example/v1"
    assert settings.api_key == "secret"
    assert settings.model == "env-model"
    assert settings.quality == "high"
    assert settings.concurrency == 3


def test_custom_headers_merge_with_environment(tmp_path: Path) -> None:
    config = tmp_path / "config.toml"
    config.write_text(
        """
[provider]
headers = { X-Static = "one" }
""".strip(),
        encoding="utf-8",
    )
    settings = load_settings(
        config,
        cwd=tmp_path,
        environ={"IMAGEGEN_HEADERS_JSON": '{"X-Dynamic":"two"}'},
        load_project_dotenv=False,
    )

    assert settings.default_headers == {
        "X-Static": "one",
        "X-Dynamic": "two",
    }


def test_invalid_base_url_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(ConfigError):
        load_settings(
            cwd=tmp_path,
            environ={"IMAGEGEN_BASE_URL": "file:///tmp/api"},
            load_project_dotenv=False,
        )
