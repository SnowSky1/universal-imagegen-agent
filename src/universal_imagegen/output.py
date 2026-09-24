from __future__ import annotations

import base64
import binascii
import os
import tempfile
import urllib.request
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from .errors import OutputError, RequestError

MAX_DOWNLOAD_BYTES = 100 * 1024 * 1024
FORMATS = {"png": ".png", "jpeg": ".jpeg", "jpg": ".jpg", "webp": ".webp"}


def normalize_format(value: str) -> str:
    normalized = value.lower()
    if normalized not in FORMATS:
        raise RequestError("output format must be png, jpeg, jpg, or webp.")
    return "jpeg" if normalized == "jpg" else normalized


def plan_output_paths(
    *,
    out: str | Path | None,
    output_dir: str | Path,
    output_format: str,
    count: int,
    force: bool,
) -> tuple[Path, ...]:
    if count < 1 or count > 10:
        raise RequestError("n must be between 1 and 10.")
    fmt = normalize_format(output_format)
    extension = "." + fmt
    base = Path(out) if out else Path(output_dir) / f"output{extension}"

    if not base.is_absolute():
        base = Path.cwd() / base
    if not base.suffix:
        base = base.with_suffix(extension)
    actual_suffix = base.suffix.lower()
    accepted = {extension}
    if fmt == "jpeg":
        accepted.add(".jpg")
    if actual_suffix not in accepted:
        raise RequestError(f"Output extension {base.suffix!r} does not match format {fmt!r}.")

    paths = (
        (base,)
        if count == 1
        else tuple(
            base.with_name(f"{base.stem}-{index}{base.suffix}") for index in range(1, count + 1)
        )
    )
    duplicates = {path for path in paths if paths.count(path) > 1}
    if duplicates:
        raise RequestError("Output paths must be unique.")
    existing = [path for path in paths if path.exists()]
    if existing and not force:
        joined = ", ".join(str(path) for path in existing)
        raise RequestError(f"Output already exists: {joined} (use --force to overwrite)")
    return tuple(path.resolve() for path in paths)


def _field(item: Any, name: str) -> Any:
    if isinstance(item, dict):
        return item.get(name)
    return getattr(item, name, None)


def extract_response_data(response: Any) -> tuple[list[bytes], tuple[str, ...]]:
    data: Iterable[Any] | None = _field(response, "data")
    if data is None:
        raise OutputError("Provider response did not contain a data list.")

    images: list[bytes] = []
    revised: list[str] = []
    for index, item in enumerate(data, start=1):
        revised_prompt = _field(item, "revised_prompt")
        if revised_prompt:
            revised.append(str(revised_prompt))
        encoded = _field(item, "b64_json")
        if encoded:
            try:
                images.append(base64.b64decode(encoded, validate=True))
            except (binascii.Error, ValueError) as exc:
                raise OutputError(f"Provider returned invalid base64 for image {index}.") from exc
            continue
        url = _field(item, "url")
        if url:
            images.append(_download_image(str(url)))
            continue
        raise OutputError(f"Provider response image {index} contained neither b64_json nor url.")
    if not images:
        raise OutputError("Provider returned no images.")
    return images, tuple(revised)


def _download_image(url: str) -> bytes:
    if not url.startswith(("https://", "http://")):
        raise OutputError("Provider returned an unsupported image URL.")
    request = urllib.request.Request(url, headers={"User-Agent": "universal-imagegen-agent"})
    try:
        with urllib.request.urlopen(request, timeout=60) as response:  # noqa: S310
            content_length = response.headers.get("Content-Length")
            if content_length and int(content_length) > MAX_DOWNLOAD_BYTES:
                raise OutputError("Provider image download exceeds 100MB.")
            payload = response.read(MAX_DOWNLOAD_BYTES + 1)
    except OutputError:
        raise
    except Exception as exc:
        raise OutputError(f"Could not download provider image: {exc}") from exc
    if len(payload) > MAX_DOWNLOAD_BYTES:
        raise OutputError("Provider image download exceeds 100MB.")
    return payload


def write_outputs(
    image_bytes: list[bytes],
    paths: tuple[Path, ...],
    *,
    force: bool,
) -> tuple[str, ...]:
    if len(image_bytes) != len(paths):
        raise OutputError(f"Provider returned {len(image_bytes)} image(s), expected {len(paths)}.")

    for path in paths:
        if path.exists() and not force:
            raise OutputError(f"Output already exists: {path}")
        path.parent.mkdir(parents=True, exist_ok=True)

    written: list[str] = []
    for payload, path in zip(image_bytes, paths, strict=True):
        temp_path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="wb",
                dir=path.parent,
                prefix=f".{path.name}.",
                suffix=".tmp",
                delete=False,
            ) as handle:
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
                temp_path = Path(handle.name)
            os.replace(temp_path, path)
            written.append(str(path))
        except OSError as exc:
            if temp_path and temp_path.exists():
                temp_path.unlink(missing_ok=True)
            raise OutputError(f"Could not write output {path}: {exc}") from exc
    return tuple(written)
