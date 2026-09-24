from __future__ import annotations

from .errors import RequestError
from .models import PromptSpec


def read_prompt(prompt: str | None, prompt_file: str | None) -> str:
    if prompt and prompt_file:
        raise RequestError("Use a prompt argument or --prompt-file, not both.")
    if prompt_file:
        from pathlib import Path

        path = Path(prompt_file)
        if not path.exists():
            raise RequestError(f"Prompt file not found: {path}")
        prompt = path.read_text(encoding="utf-8")
    value = (prompt or "").strip()
    if not value:
        raise RequestError("A non-empty prompt is required.")
    return value


def build_prompt(
    primary_request: str,
    spec: PromptSpec | None = None,
    *,
    augment: bool = True,
) -> str:
    request = primary_request.strip()
    if not request:
        raise RequestError("A non-empty prompt is required.")
    if not augment:
        return request

    details = spec or PromptSpec()
    sections: list[str] = []
    if details.use_case:
        sections.append(f"Use case: {details.use_case}")
    if details.asset_type:
        sections.append(f"Asset type: {details.asset_type}")
    sections.append(f"Primary request: {request}")
    if details.input_images:
        sections.append(f"Input images: {'; '.join(details.input_images)}")
    if details.scene:
        sections.append(f"Scene/backdrop: {details.scene}")
    if details.subject:
        sections.append(f"Subject: {details.subject}")
    if details.style:
        sections.append(f"Style/medium: {details.style}")
    if details.composition:
        sections.append(f"Composition/framing: {details.composition}")
    if details.lighting:
        sections.append(f"Lighting/mood: {details.lighting}")
    if details.palette:
        sections.append(f"Color palette: {details.palette}")
    if details.materials:
        sections.append(f"Materials/textures: {details.materials}")
    if details.text:
        sections.append(f'Text (verbatim): "{details.text}"')
    if details.constraints:
        sections.append(f"Constraints: {details.constraints}")
    if details.avoid:
        sections.append(f"Avoid: {details.avoid}")
    return "\n".join(sections)
