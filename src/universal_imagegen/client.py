from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from .config import Settings
from .errors import RequestError
from .models import EditRequest, GenerateRequest, OperationResult
from .output import (
    extract_response_data,
    normalize_format,
    plan_output_paths,
    write_outputs,
)
from .prompting import build_prompt
from .provider import OpenAICompatibleProvider

MAX_INPUT_BYTES = 50 * 1024 * 1024


def _without_none(payload: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in payload.items() if value is not None}


def _validate_common(
    *,
    n: int,
    background: str | None,
    output_format: str,
    output_compression: int | None,
) -> None:
    if n < 1 or n > 10:
        raise RequestError("n must be between 1 and 10.")
    fmt = normalize_format(output_format)
    if background == "transparent" and fmt not in {"png", "webp"}:
        raise RequestError("Transparent output requires PNG or WebP.")
    if background not in {None, "transparent", "opaque", "auto"}:
        raise RequestError("background must be transparent, opaque, or auto.")
    if output_compression is not None and not 0 <= output_compression <= 100:
        raise RequestError("output_compression must be between 0 and 100.")


def _extra_body(value: dict[str, Any]) -> dict[str, Any] | None:
    return dict(value) if value else None


class ImageGenClient:
    def __init__(
        self,
        settings: Settings,
        *,
        provider: OpenAICompatibleProvider | None = None,
    ) -> None:
        self.settings = settings
        self.provider = provider or OpenAICompatibleProvider(settings)

    def generate(
        self,
        request: GenerateRequest,
        *,
        dry_run: bool = False,
    ) -> OperationResult:
        prompt = build_prompt(
            request.prompt,
            request.prompt_spec,
            augment=request.augment_prompt,
        )
        model = request.model or self.settings.model
        size = request.size or self.settings.size
        quality = request.quality or self.settings.quality
        output_format = normalize_format(request.output_format or self.settings.output_format)
        _validate_common(
            n=request.n,
            background=request.background,
            output_format=output_format,
            output_compression=request.output_compression,
        )
        outputs = plan_output_paths(
            out=request.out,
            output_dir=self.settings.output_dir,
            output_format=output_format,
            count=request.n,
            force=request.force,
        )
        payload = _without_none(
            {
                "model": model,
                "prompt": prompt,
                "n": request.n,
                "size": size,
                "quality": quality,
                "background": request.background,
                "output_format": output_format,
                "output_compression": request.output_compression,
                "moderation": request.moderation,
                "extra_body": _extra_body(request.extra_body),
            }
        )
        preview = _request_preview(payload, outputs)
        if dry_run:
            return OperationResult(
                status="dry-run",
                operation="generate",
                provider=self.settings.provider_name,
                model=model,
                prompt=prompt,
                outputs=tuple(str(path) for path in outputs),
                request=preview,
            )

        started = time.monotonic()
        response = self.provider.generate(payload)
        images, revised = extract_response_data(response)
        written = write_outputs(images, outputs, force=request.force)
        return OperationResult(
            status="ok",
            operation="generate",
            provider=self.settings.provider_name,
            model=model,
            prompt=prompt,
            outputs=written,
            request=preview,
            revised_prompts=revised,
            elapsed_seconds=round(time.monotonic() - started, 3),
        )

    def edit(
        self,
        request: EditRequest,
        *,
        dry_run: bool = False,
    ) -> OperationResult:
        images = tuple(_validate_input(path, "Image") for path in request.images)
        if not images:
            raise RequestError("At least one edit image is required.")
        mask = _validate_input(request.mask, "Mask") if request.mask else None
        prompt = build_prompt(
            request.prompt,
            request.prompt_spec,
            augment=request.augment_prompt,
        )
        model = request.model or self.settings.model
        size = request.size or self.settings.size
        quality = request.quality or self.settings.quality
        output_format = normalize_format(request.output_format or self.settings.output_format)
        _validate_common(
            n=request.n,
            background=request.background,
            output_format=output_format,
            output_compression=request.output_compression,
        )
        if request.input_fidelity not in {None, "low", "high"}:
            raise RequestError("input_fidelity must be low or high.")
        outputs = plan_output_paths(
            out=request.out,
            output_dir=self.settings.output_dir,
            output_format=output_format,
            count=request.n,
            force=request.force,
        )
        payload = _without_none(
            {
                "model": model,
                "prompt": prompt,
                "n": request.n,
                "size": size,
                "quality": quality,
                "background": request.background,
                "output_format": output_format,
                "output_compression": request.output_compression,
                "input_fidelity": request.input_fidelity,
                "moderation": request.moderation,
                "extra_body": _extra_body(request.extra_body),
            }
        )
        preview = _request_preview(payload, outputs)
        preview["images"] = [str(path) for path in images]
        preview["mask"] = str(mask) if mask else None
        if dry_run:
            return OperationResult(
                status="dry-run",
                operation="edit",
                provider=self.settings.provider_name,
                model=model,
                prompt=prompt,
                outputs=tuple(str(path) for path in outputs),
                request=preview,
            )

        started = time.monotonic()
        response = self.provider.edit(payload, images=images, mask=mask)
        image_bytes, revised = extract_response_data(response)
        written = write_outputs(image_bytes, outputs, force=request.force)
        return OperationResult(
            status="ok",
            operation="edit",
            provider=self.settings.provider_name,
            model=model,
            prompt=prompt,
            outputs=written,
            request=preview,
            revised_prompts=revised,
            elapsed_seconds=round(time.monotonic() - started, 3),
        )


def _validate_input(raw: str | Path, label: str) -> Path:
    path = Path(raw).expanduser()
    if not path.exists() or not path.is_file():
        raise RequestError(f"{label} file not found: {path}")
    if path.stat().st_size > MAX_INPUT_BYTES:
        raise RequestError(f"{label} exceeds the 50MB input limit: {path}")
    return path.resolve()


def _request_preview(
    payload: dict[str, Any],
    outputs: tuple[Path, ...],
) -> dict[str, Any]:
    preview = dict(payload)
    preview["outputs"] = [str(path) for path in outputs]
    return preview
