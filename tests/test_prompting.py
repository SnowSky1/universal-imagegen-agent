from pathlib import Path

import pytest

from universal_imagegen.errors import RequestError
from universal_imagegen.models import PromptSpec
from universal_imagegen.prompting import build_prompt, read_prompt


def test_structured_prompt_order_and_verbatim_text() -> None:
    prompt = build_prompt(
        "Create a campaign poster",
        PromptSpec(
            use_case="ads-marketing",
            asset_type="vertical poster",
            style="editorial photography",
            text="Yours to Create.",
            constraints="render the tagline exactly once",
            avoid="watermarks",
        ),
    )

    assert prompt.splitlines() == [
        "Use case: ads-marketing",
        "Asset type: vertical poster",
        "Primary request: Create a campaign poster",
        "Style/medium: editorial photography",
        'Text (verbatim): "Yours to Create."',
        "Constraints: render the tagline exactly once",
        "Avoid: watermarks",
    ]


def test_no_augment_returns_original_prompt() -> None:
    assert build_prompt("  Keep me concise  ", augment=False) == "Keep me concise"


def test_read_prompt_file(tmp_path: Path) -> None:
    path = tmp_path / "prompt.txt"
    path.write_text("hello", encoding="utf-8")
    assert read_prompt(None, str(path)) == "hello"


def test_prompt_and_prompt_file_are_mutually_exclusive(tmp_path: Path) -> None:
    path = tmp_path / "prompt.txt"
    path.write_text("hello", encoding="utf-8")
    with pytest.raises(RequestError):
        read_prompt("world", str(path))
