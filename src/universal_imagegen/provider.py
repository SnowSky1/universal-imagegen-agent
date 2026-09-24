from __future__ import annotations

from contextlib import ExitStack
from pathlib import Path
from typing import Any

from .config import Settings
from .errors import ConfigError, ProviderError, RequestError


class OpenAICompatibleProvider:
    def __init__(self, settings: Settings, *, client: Any | None = None) -> None:
        self.settings = settings
        self._client = client

    def _get_client(self) -> Any:
        if self._client is not None:
            return self._client
        if not self.settings.api_key:
            raise ConfigError(f"API key is missing. Set {self.settings.api_key_env} locally.")
        try:
            from openai import OpenAI
        except ImportError as exc:
            raise ConfigError(
                "The openai package is not installed. Run `uv sync` or install the project."
            ) from exc

        self._client = OpenAI(
            api_key=self.settings.api_key,
            base_url=self.settings.base_url,
            timeout=self.settings.timeout_seconds,
            max_retries=self.settings.max_retries,
            default_headers=self.settings.default_headers or None,
        )
        return self._client

    def generate(self, payload: dict[str, Any]) -> Any:
        try:
            return self._get_client().images.generate(**payload)
        except (ConfigError, RequestError):
            raise
        except Exception as exc:
            raise ProviderError(f"Image generation API call failed: {exc}") from exc

    def edit(
        self,
        payload: dict[str, Any],
        *,
        images: tuple[Path, ...],
        mask: Path | None,
    ) -> Any:
        try:
            client = self._get_client()
            with ExitStack() as stack:
                handles = [stack.enter_context(path.open("rb")) for path in images]
                request = dict(payload)
                request["image"] = handles if len(handles) > 1 else handles[0]
                if mask is not None:
                    request["mask"] = stack.enter_context(mask.open("rb"))
                return client.images.edit(**request)
        except (ConfigError, RequestError):
            raise
        except OSError as exc:
            raise RequestError(f"Could not open edit input: {exc}") from exc
        except Exception as exc:
            raise ProviderError(f"Image edit API call failed: {exc}") from exc
