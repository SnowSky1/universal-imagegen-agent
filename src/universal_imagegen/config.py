from __future__ import annotations

import json
import os
import tomllib
from collections.abc import Mapping
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

from .errors import ConfigError

DEFAULT_BASE_URL = "https://api.openai.com/v1"
DEFAULT_MODEL = "gpt-image-2.5-sunburst"
DEFAULT_OUTPUT_DIR = "output/imagegen"


@dataclass(frozen=True)
class Settings:
    provider_name: str = "openai-compatible"
    base_url: str = DEFAULT_BASE_URL
    api_key_env: str = "IMAGEGEN_API_KEY"
    api_key: str | None = field(default=None, repr=False)
    model: str = DEFAULT_MODEL
    timeout_seconds: float = 180.0
    max_retries: int = 2
    default_headers: dict[str, str] = field(default_factory=dict)
    size: str = "auto"
    quality: str = "auto"
    output_format: str = "png"
    output_dir: Path = Path(DEFAULT_OUTPUT_DIR)
    concurrency: int = 4
    config_path: Path | None = None

    @property
    def is_official_openai(self) -> bool:
        normalized = self.base_url.lower().rstrip("/")
        return normalized in {
            "https://api.openai.com/v1",
            "https://api.openai.com",
        }

    def with_overrides(self, **overrides: Any) -> Settings:
        filtered = {key: value for key, value in overrides.items() if value is not None}
        if "output_dir" in filtered:
            filtered["output_dir"] = Path(filtered["output_dir"])
        if "base_url" in filtered:
            filtered["base_url"] = str(filtered["base_url"]).rstrip("/")
        updated = replace(self, **filtered)
        _validate_settings(updated)
        return updated

    def public_dict(self) -> dict[str, Any]:
        return {
            "provider": self.provider_name,
            "base_url": self.base_url,
            "api_key_env": self.api_key_env,
            "api_key_present": bool(self.api_key),
            "model": self.model,
            "timeout_seconds": self.timeout_seconds,
            "max_retries": self.max_retries,
            "default_headers": sorted(self.default_headers),
            "size": self.size,
            "quality": self.quality,
            "output_format": self.output_format,
            "output_dir": str(self.output_dir),
            "concurrency": self.concurrency,
            "config_path": str(self.config_path) if self.config_path else None,
        }


def _as_int(value: Any, name: str) -> int:
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise ConfigError(f"{name} must be an integer.") from exc


def _as_float(value: Any, name: str) -> float:
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise ConfigError(f"{name} must be a number.") from exc


def _json_object(value: str, name: str) -> dict[str, Any]:
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError as exc:
        raise ConfigError(f"{name} must be a valid JSON object: {exc}") from exc
    if not isinstance(parsed, dict):
        raise ConfigError(f"{name} must be a JSON object.")
    return parsed


def _read_config(path: Path | None) -> dict[str, Any]:
    if path is None:
        return {}
    if not path.exists():
        raise ConfigError(f"Configuration file not found: {path}")
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError) as exc:
        raise ConfigError(f"Could not read configuration file {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise ConfigError("Configuration root must be a TOML table.")
    return data


def _resolve_config_path(
    explicit: str | Path | None,
    env: Mapping[str, str],
    cwd: Path,
) -> Path | None:
    raw = explicit or env.get("IMAGEGEN_CONFIG")
    if raw:
        path = Path(raw).expanduser()
        return path if path.is_absolute() else cwd / path
    local = cwd / ".imagegen.toml"
    return local if local.exists() else None


def _get_table(config: dict[str, Any], name: str) -> dict[str, Any]:
    value = config.get(name, {})
    if not isinstance(value, dict):
        raise ConfigError(f"[{name}] must be a TOML table.")
    return value


def _merge_headers(
    config_headers: Any,
    env_headers: str | None,
) -> dict[str, str]:
    merged: dict[str, Any] = {}
    if config_headers is not None:
        if not isinstance(config_headers, dict):
            raise ConfigError("provider.headers must be a TOML table/object.")
        merged.update(config_headers)
    if env_headers:
        merged.update(_json_object(env_headers, "IMAGEGEN_HEADERS_JSON"))
    return {str(key): str(value) for key, value in merged.items()}


def _validate_settings(settings: Settings) -> None:
    if settings.provider_name != "openai-compatible":
        raise ConfigError("Only provider.name='openai-compatible' is currently implemented.")
    if not settings.base_url.startswith(("https://", "http://")):
        raise ConfigError("base_url must start with https:// or http://.")
    if not settings.api_key_env.strip():
        raise ConfigError("api_key_env cannot be empty.")
    if not settings.model.strip():
        raise ConfigError("model cannot be empty.")
    if settings.timeout_seconds <= 0:
        raise ConfigError("timeout_seconds must be greater than zero.")
    if settings.max_retries < 0 or settings.max_retries > 20:
        raise ConfigError("max_retries must be between 0 and 20.")
    if settings.concurrency < 1 or settings.concurrency > 25:
        raise ConfigError("concurrency must be between 1 and 25.")
    if settings.output_format.lower() not in {"png", "jpeg", "jpg", "webp"}:
        raise ConfigError("output_format must be png, jpeg, jpg, or webp.")


def load_settings(
    config_path: str | Path | None = None,
    *,
    cwd: str | Path | None = None,
    environ: Mapping[str, str] | None = None,
    load_project_dotenv: bool = True,
    overrides: Mapping[str, Any] | None = None,
) -> Settings:
    working_dir = Path(cwd or Path.cwd()).resolve()

    if environ is None:
        if load_project_dotenv:
            load_dotenv(working_dir / ".env", override=False)
        env: Mapping[str, str] = os.environ
    else:
        env = environ

    resolved_path = _resolve_config_path(config_path, env, working_dir)
    config = _read_config(resolved_path)
    provider = _get_table(config, "provider")
    defaults = _get_table(config, "defaults")

    api_key_env = str(
        env.get("IMAGEGEN_API_KEY_ENV") or provider.get("api_key_env") or "IMAGEGEN_API_KEY"
    )
    api_key = env.get("IMAGEGEN_API_KEY") or env.get(api_key_env) or env.get("OPENAI_API_KEY")

    settings = Settings(
        provider_name=str(provider.get("name", "openai-compatible")),
        base_url=str(
            env.get("IMAGEGEN_BASE_URL")
            or provider.get("base_url")
            or env.get("OPENAI_BASE_URL")
            or DEFAULT_BASE_URL
        ).rstrip("/"),
        api_key_env=api_key_env,
        api_key=api_key,
        model=str(env.get("IMAGEGEN_MODEL") or provider.get("model") or DEFAULT_MODEL),
        timeout_seconds=_as_float(
            env.get("IMAGEGEN_TIMEOUT") or provider.get("timeout_seconds", 180.0),
            "timeout_seconds",
        ),
        max_retries=_as_int(
            env.get("IMAGEGEN_MAX_RETRIES") or provider.get("max_retries", 2),
            "max_retries",
        ),
        default_headers=_merge_headers(
            provider.get("headers"),
            env.get("IMAGEGEN_HEADERS_JSON"),
        ),
        size=str(env.get("IMAGEGEN_SIZE") or defaults.get("size") or "auto"),
        quality=str(env.get("IMAGEGEN_QUALITY") or defaults.get("quality") or "auto"),
        output_format=str(
            env.get("IMAGEGEN_OUTPUT_FORMAT") or defaults.get("output_format") or "png"
        ).lower(),
        output_dir=Path(
            env.get("IMAGEGEN_OUTPUT_DIR") or defaults.get("output_dir") or DEFAULT_OUTPUT_DIR
        ),
        concurrency=_as_int(
            env.get("IMAGEGEN_CONCURRENCY") or defaults.get("concurrency", 4),
            "concurrency",
        ),
        config_path=resolved_path,
    )

    if overrides:
        settings = settings.with_overrides(**dict(overrides))
    _validate_settings(settings)
    return settings
