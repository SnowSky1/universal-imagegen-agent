import base64
from pathlib import Path
from types import SimpleNamespace

import pytest

from universal_imagegen.client import ImageGenClient
from universal_imagegen.config import Settings
from universal_imagegen.errors import RequestError
from universal_imagegen.models import EditRequest, GenerateRequest, PromptSpec


class FakeProvider:
    def __init__(self, payloads: list[dict] | None = None) -> None:
        self.payloads = payloads if payloads is not None else []

    def generate(self, payload: dict):
        self.payloads.append(payload)
        encoded = base64.b64encode(b"fake-png").decode("ascii")
        return SimpleNamespace(data=[SimpleNamespace(b64_json=encoded, revised_prompt="revised")])

    def edit(self, payload: dict, *, images, mask):
        self.payloads.append(
            {
                **payload,
                "_images": tuple(images),
                "_mask": mask,
            }
        )
        encoded = base64.b64encode(b"edited-png").decode("ascii")
        return {"data": [{"b64_json": encoded}]}


def settings(tmp_path: Path) -> Settings:
    return Settings(
        api_key="test",
        output_dir=tmp_path / "output",
    )


def test_generate_dry_run_needs_no_provider_call(tmp_path: Path) -> None:
    provider = FakeProvider()
    client = ImageGenClient(settings(tmp_path), provider=provider)
    result = client.generate(
        GenerateRequest(
            prompt="A mug",
            out=tmp_path / "mug.png",
            prompt_spec=PromptSpec(use_case="product-mockup"),
        ),
        dry_run=True,
    )

    assert result.status == "dry-run"
    assert provider.payloads == []
    assert result.prompt.startswith("Use case: product-mockup")
    assert result.outputs == (str((tmp_path / "mug.png").resolve()),)


def test_generate_writes_provider_bytes(tmp_path: Path) -> None:
    provider = FakeProvider()
    client = ImageGenClient(settings(tmp_path), provider=provider)
    out = tmp_path / "mug.png"
    result = client.generate(GenerateRequest(prompt="A mug", out=out))

    assert result.status == "ok"
    assert out.read_bytes() == b"fake-png"
    assert result.revised_prompts == ("revised",)
    assert provider.payloads[0]["model"] == "gpt-image-2.5-sunburst"


def test_generate_refuses_overwrite(tmp_path: Path) -> None:
    out = tmp_path / "existing.png"
    out.write_bytes(b"old")
    client = ImageGenClient(settings(tmp_path), provider=FakeProvider())

    with pytest.raises(RequestError):
        client.generate(GenerateRequest(prompt="A mug", out=out), dry_run=True)


def test_edit_validates_inputs_and_writes_output(tmp_path: Path) -> None:
    source = tmp_path / "source.png"
    source.write_bytes(b"source")
    out = tmp_path / "edited.png"
    provider = FakeProvider()
    client = ImageGenClient(settings(tmp_path), provider=provider)
    result = client.edit(
        EditRequest(
            prompt="Change only the background",
            images=(source,),
            out=out,
            prompt_spec=PromptSpec(constraints="keep the subject and edges unchanged"),
        )
    )

    assert result.status == "ok"
    assert out.read_bytes() == b"edited-png"
    assert provider.payloads[0]["_images"] == (source.resolve(),)


def test_transparency_requires_alpha_capable_format(tmp_path: Path) -> None:
    client = ImageGenClient(settings(tmp_path), provider=FakeProvider())
    with pytest.raises(RequestError):
        client.generate(
            GenerateRequest(
                prompt="A cutout",
                out=tmp_path / "cutout.jpeg",
                background="transparent",
                output_format="jpeg",
            ),
            dry_run=True,
        )
