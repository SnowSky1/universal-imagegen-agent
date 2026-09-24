from __future__ import annotations

import argparse
import json
import re
import sys
from collections.abc import Sequence
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

from . import __version__
from .client import ImageGenClient
from .config import Settings, load_settings
from .errors import ConfigError, ImageGenError, ProviderError, RequestError
from .models import EditRequest, GenerateRequest, OperationResult, PromptSpec
from .prompting import build_prompt, read_prompt


def _config_parent() -> argparse.ArgumentParser:
    parent = argparse.ArgumentParser(add_help=False)
    parent.add_argument("--config", help="Path to a TOML configuration file.")
    parent.add_argument("--base-url", help="Override the compatible API base URL.")
    parent.add_argument("--model", help="Override the configured image model.")
    parent.add_argument("--output-dir", help="Override the default output directory.")
    parent.add_argument(
        "--json",
        action="store_true",
        dest="json_output",
        help="Write machine-readable JSON to stdout.",
    )
    return parent


def _add_prompt_args(parser: argparse.ArgumentParser, *, positional: bool = True) -> None:
    if positional:
        parser.add_argument("prompt", nargs="?", help="Primary image request.")
    else:
        parser.add_argument("--prompt", help="Primary image request.")
    parser.add_argument("--prompt-file", help="Read the primary request from a UTF-8 file.")
    parser.add_argument("--no-augment", action="store_true")
    parser.add_argument("--use-case")
    parser.add_argument("--asset-type")
    parser.add_argument(
        "--input-role",
        action="append",
        default=[],
        help='Input role such as "Image 1: edit target"; repeat as needed.',
    )
    parser.add_argument("--scene")
    parser.add_argument("--subject")
    parser.add_argument("--style")
    parser.add_argument("--composition")
    parser.add_argument("--lighting")
    parser.add_argument("--palette")
    parser.add_argument("--materials")
    parser.add_argument("--text")
    parser.add_argument("--constraints")
    parser.add_argument("--avoid")


def _add_request_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--out", help="Output file path.")
    parser.add_argument("--n", type=int, default=1, help="Variants of this prompt (1-10).")
    parser.add_argument("--size", help="Provider-supported size, for example 1024x1024.")
    parser.add_argument("--quality", help="Provider-supported quality value.")
    parser.add_argument(
        "--background",
        choices=["transparent", "opaque", "auto"],
    )
    parser.add_argument(
        "--output-format",
        "--format",
        dest="output_format",
        choices=["png", "jpeg", "jpg", "webp"],
    )
    parser.add_argument("--output-compression", type=int)
    parser.add_argument("--moderation")
    parser.add_argument(
        "--extra-json",
        help="Provider-specific extra_body as a JSON object.",
    )
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--dry-run", action="store_true")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="imagegen-agent",
        description="Provider-configurable image generation for general-purpose AI agents.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    subparsers = parser.add_subparsers(dest="command", required=True)
    config_parent = _config_parent()

    config_parser = subparsers.add_parser(
        "config",
        parents=[config_parent],
        help="Show the resolved configuration with credentials redacted.",
    )
    config_parser.set_defaults(handler=_handle_config)

    prompt_parser = subparsers.add_parser(
        "prompt",
        parents=[config_parent],
        help="Build a structured prompt without calling an API.",
    )
    _add_prompt_args(prompt_parser)
    prompt_parser.set_defaults(handler=_handle_prompt)

    generate_parser = subparsers.add_parser(
        "generate",
        parents=[config_parent],
        help="Generate one prompt or variants of one prompt.",
    )
    _add_prompt_args(generate_parser)
    _add_request_args(generate_parser)
    generate_parser.set_defaults(handler=_handle_generate)

    edit_parser = subparsers.add_parser(
        "edit",
        parents=[config_parent],
        help="Edit one or more existing images.",
    )
    _add_prompt_args(edit_parser, positional=False)
    _add_request_args(edit_parser)
    edit_parser.add_argument("--image", action="append", required=True)
    edit_parser.add_argument("--mask")
    edit_parser.add_argument("--input-fidelity", choices=["low", "high"])
    edit_parser.set_defaults(handler=_handle_edit)

    batch_parser = subparsers.add_parser(
        "batch",
        parents=[config_parent],
        help="Generate distinct jobs from a JSONL file.",
    )
    batch_parser.add_argument("input", help="JSONL file with one generation job per line.")
    batch_parser.add_argument("--out-dir", required=True)
    batch_parser.add_argument("--concurrency", type=int)
    batch_parser.add_argument("--force", action="store_true")
    batch_parser.add_argument("--dry-run", action="store_true")
    batch_parser.add_argument("--fail-fast", action="store_true")
    batch_parser.set_defaults(handler=_handle_batch)
    return parser


def _settings_from_args(args: argparse.Namespace) -> Settings:
    overrides = {
        "base_url": getattr(args, "base_url", None),
        "model": getattr(args, "model", None),
        "output_dir": getattr(args, "output_dir", None),
    }
    return load_settings(getattr(args, "config", None), overrides=overrides)


def _prompt_spec(args: argparse.Namespace) -> PromptSpec:
    return PromptSpec(
        use_case=getattr(args, "use_case", None),
        asset_type=getattr(args, "asset_type", None),
        input_images=tuple(getattr(args, "input_role", []) or []),
        scene=getattr(args, "scene", None),
        subject=getattr(args, "subject", None),
        style=getattr(args, "style", None),
        composition=getattr(args, "composition", None),
        lighting=getattr(args, "lighting", None),
        palette=getattr(args, "palette", None),
        materials=getattr(args, "materials", None),
        text=getattr(args, "text", None),
        constraints=getattr(args, "constraints", None),
        avoid=getattr(args, "avoid", None),
    )


def _parse_extra_json(raw: str | None) -> dict[str, Any]:
    if not raw:
        return {}
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RequestError(f"--extra-json must be valid JSON: {exc}") from exc
    if not isinstance(value, dict):
        raise RequestError("--extra-json must contain a JSON object.")
    return value


def _handle_config(args: argparse.Namespace) -> int:
    settings = _settings_from_args(args)
    payload = {"status": "ok", "configuration": settings.public_dict()}
    _emit(payload, json_output=args.json_output)
    return 0


def _handle_prompt(args: argparse.Namespace) -> int:
    primary = read_prompt(args.prompt, args.prompt_file)
    prompt = build_prompt(
        primary,
        _prompt_spec(args),
        augment=not args.no_augment,
    )
    payload = {"status": "ok", "prompt": prompt}
    if args.json_output:
        _emit(payload, json_output=True)
    else:
        print(prompt)
    return 0


def _generate_request(args: argparse.Namespace) -> GenerateRequest:
    return GenerateRequest(
        prompt=read_prompt(args.prompt, args.prompt_file),
        out=args.out,
        prompt_spec=_prompt_spec(args),
        augment_prompt=not args.no_augment,
        model=args.model,
        n=args.n,
        size=args.size,
        quality=args.quality,
        background=args.background,
        output_format=args.output_format,
        output_compression=args.output_compression,
        moderation=args.moderation,
        force=args.force,
        extra_body=_parse_extra_json(args.extra_json),
    )


def _handle_generate(args: argparse.Namespace) -> int:
    settings = _settings_from_args(args)
    result = ImageGenClient(settings).generate(
        _generate_request(args),
        dry_run=args.dry_run,
    )
    _emit_result(result, json_output=args.json_output)
    return 0


def _handle_edit(args: argparse.Namespace) -> int:
    settings = _settings_from_args(args)
    request = EditRequest(
        prompt=read_prompt(args.prompt, args.prompt_file),
        images=tuple(args.image),
        out=args.out,
        mask=args.mask,
        prompt_spec=_prompt_spec(args),
        augment_prompt=not args.no_augment,
        model=args.model,
        n=args.n,
        size=args.size,
        quality=args.quality,
        background=args.background,
        output_format=args.output_format,
        output_compression=args.output_compression,
        input_fidelity=args.input_fidelity,
        moderation=args.moderation,
        force=args.force,
        extra_body=_parse_extra_json(args.extra_json),
    )
    result = ImageGenClient(settings).edit(request, dry_run=args.dry_run)
    _emit_result(result, json_output=args.json_output)
    return 0


def _read_batch_jobs(path: str | Path) -> list[dict[str, Any]]:
    input_path = Path(path)
    if not input_path.exists():
        raise RequestError(f"Batch input not found: {input_path}")
    jobs: list[dict[str, Any]] = []
    for line_number, raw in enumerate(
        input_path.read_text(encoding="utf-8").splitlines(),
        start=1,
    ):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        try:
            job = json.loads(line)
        except json.JSONDecodeError as exc:
            raise RequestError(f"Invalid JSON on line {line_number}: {exc}") from exc
        if isinstance(job, str):
            job = {"prompt": job}
        if not isinstance(job, dict) or not str(job.get("prompt", "")).strip():
            raise RequestError(f"Batch line {line_number} must contain a prompt.")
        job["_line"] = line_number
        jobs.append(job)
    if not jobs:
        raise RequestError("Batch input contains no jobs.")
    if len(jobs) > 500:
        raise RequestError("Batch input exceeds the 500-job limit.")
    return jobs


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", value).strip("-").lower()
    return slug[:48] or "job"


def _batch_out(
    job: dict[str, Any],
    *,
    index: int,
    out_dir: Path,
    output_format: str,
) -> Path:
    raw = job.get("out")
    if raw:
        filename = Path(str(raw)).name
    else:
        filename = f"{index:03d}-{_slugify(str(job['prompt']))}.{output_format}"
    return out_dir / filename


def _job_prompt_spec(job: dict[str, Any]) -> PromptSpec:
    fields = job.get("fields", {})
    if fields is None:
        fields = {}
    if not isinstance(fields, dict):
        raise RequestError(f"Batch line {job['_line']}: fields must be an object.")

    def value(name: str) -> Any:
        return job.get(name, fields.get(name))

    roles = value("input_images") or value("input_roles") or []
    if isinstance(roles, str):
        roles = [roles]
    if not isinstance(roles, list):
        raise RequestError(f"Batch line {job['_line']}: input_images must be a string or list.")
    return PromptSpec(
        use_case=value("use_case"),
        asset_type=value("asset_type"),
        input_images=tuple(str(role) for role in roles),
        scene=value("scene"),
        subject=value("subject"),
        style=value("style"),
        composition=value("composition"),
        lighting=value("lighting"),
        palette=value("palette"),
        materials=value("materials"),
        text=value("text"),
        constraints=value("constraints"),
        avoid=value("avoid") or value("negative"),
    )


def _batch_request(
    job: dict[str, Any],
    *,
    index: int,
    out_dir: Path,
    settings: Settings,
    force: bool,
) -> GenerateRequest:
    output_format = str(
        job.get("output_format") or job.get("format") or settings.output_format
    ).lower()
    extra = job.get("extra_body") or {}
    if not isinstance(extra, dict):
        raise RequestError(f"Batch line {job['_line']}: extra_body must be an object.")
    return GenerateRequest(
        prompt=str(job["prompt"]),
        out=_batch_out(
            job,
            index=index,
            out_dir=out_dir,
            output_format=output_format,
        ),
        prompt_spec=_job_prompt_spec(job),
        augment_prompt=bool(job.get("augment", True)),
        model=job.get("model"),
        n=int(job.get("n", 1)),
        size=job.get("size"),
        quality=job.get("quality"),
        background=job.get("background"),
        output_format=output_format,
        output_compression=job.get("output_compression"),
        moderation=job.get("moderation"),
        force=force or bool(job.get("force", False)),
        extra_body=extra,
    )


def _handle_batch(args: argparse.Namespace) -> int:
    settings = _settings_from_args(args)
    concurrency = args.concurrency or settings.concurrency
    if concurrency < 1 or concurrency > 25:
        raise RequestError("concurrency must be between 1 and 25.")
    jobs = _read_batch_jobs(args.input)
    out_dir = Path(args.out_dir).resolve()
    requests = [
        _batch_request(
            job,
            index=index,
            out_dir=out_dir,
            settings=settings,
            force=args.force,
        )
        for index, job in enumerate(jobs, start=1)
    ]

    results: list[dict[str, Any] | None] = [None] * len(requests)
    failures: list[dict[str, Any]] = []

    def run(index: int, request: GenerateRequest) -> tuple[int, OperationResult]:
        client = ImageGenClient(settings)
        return index, client.generate(request, dry_run=args.dry_run)

    with ThreadPoolExecutor(max_workers=concurrency) as executor:
        future_map = {
            executor.submit(run, index, request): index for index, request in enumerate(requests)
        }
        for future in as_completed(future_map):
            index = future_map[future]
            try:
                _, result = future.result()
                results[index] = result.to_dict()
            except Exception as exc:
                failure = {
                    "job": index + 1,
                    "line": jobs[index]["_line"],
                    "error": str(exc),
                    "error_type": exc.__class__.__name__,
                }
                failures.append(failure)
                if args.fail_fast:
                    for pending in future_map:
                        pending.cancel()
                    break

    payload = {
        "status": "partial" if failures else ("dry-run" if args.dry_run else "ok"),
        "operation": "batch",
        "jobs": len(jobs),
        "results": [result for result in results if result is not None],
        "failures": failures,
    }
    _emit(payload, json_output=args.json_output)
    return 1 if failures else 0


def _emit_result(result: OperationResult, *, json_output: bool) -> None:
    if json_output:
        _emit(result.to_dict(), json_output=True)
        return
    print(f"Status: {result.status}")
    print(f"Operation: {result.operation}")
    print(f"Provider: {result.provider}")
    print(f"Model: {result.model}")
    for output in result.outputs:
        print(f"Output: {output}")
    if result.elapsed_seconds is not None:
        print(f"Elapsed: {result.elapsed_seconds:.3f}s")


def _emit(payload: dict[str, Any], *, json_output: bool) -> None:
    if json_output:
        print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
        return
    if "configuration" in payload:
        for key, value in payload["configuration"].items():
            print(f"{key}: {value}")
        return
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def _wants_json(argv: Sequence[str]) -> bool:
    return "--json" in argv


def main(argv: Sequence[str] | None = None) -> int:
    arguments = list(argv) if argv is not None else sys.argv[1:]
    json_output = _wants_json(arguments)
    parser = build_parser()
    try:
        args = parser.parse_args(arguments)
        return int(args.handler(args))
    except (ConfigError, RequestError) as exc:
        return _emit_error(exc, json_output=json_output, exit_code=2)
    except (ProviderError, ImageGenError) as exc:
        return _emit_error(exc, json_output=json_output, exit_code=1)
    except KeyboardInterrupt:
        return _emit_error(
            ProviderError("Interrupted by user."),
            json_output=json_output,
            exit_code=130,
        )


def _emit_error(exc: Exception, *, json_output: bool, exit_code: int) -> int:
    if json_output:
        print(
            json.dumps(
                {
                    "status": "error",
                    "error": str(exc),
                    "error_type": exc.__class__.__name__,
                    "exit_code": exit_code,
                },
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
        )
    else:
        print(f"Error: {exc}", file=sys.stderr)
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
