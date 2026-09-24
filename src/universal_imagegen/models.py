from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class PromptSpec:
    use_case: str | None = None
    asset_type: str | None = None
    input_images: tuple[str, ...] = ()
    scene: str | None = None
    subject: str | None = None
    style: str | None = None
    composition: str | None = None
    lighting: str | None = None
    palette: str | None = None
    materials: str | None = None
    text: str | None = None
    constraints: str | None = None
    avoid: str | None = None


@dataclass(frozen=True)
class GenerateRequest:
    prompt: str
    out: str | Path | None = None
    prompt_spec: PromptSpec = field(default_factory=PromptSpec)
    augment_prompt: bool = True
    model: str | None = None
    n: int = 1
    size: str | None = None
    quality: str | None = None
    background: str | None = None
    output_format: str | None = None
    output_compression: int | None = None
    moderation: str | None = None
    force: bool = False
    extra_body: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class EditRequest:
    prompt: str
    images: tuple[str | Path, ...]
    out: str | Path | None = None
    mask: str | Path | None = None
    prompt_spec: PromptSpec = field(default_factory=PromptSpec)
    augment_prompt: bool = True
    model: str | None = None
    n: int = 1
    size: str | None = None
    quality: str | None = None
    background: str | None = None
    output_format: str | None = None
    output_compression: int | None = None
    input_fidelity: str | None = None
    moderation: str | None = None
    force: bool = False
    extra_body: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class OperationResult:
    status: str
    operation: str
    provider: str
    model: str
    prompt: str
    outputs: tuple[str, ...]
    request: dict[str, Any]
    revised_prompts: tuple[str, ...] = ()
    elapsed_seconds: float | None = None

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["outputs"] = list(self.outputs)
        data["revised_prompts"] = list(self.revised_prompts)
        return data
