from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

from .actions import ActionContext, action_from_recipe
from .prompting import build_prompt, parse_model_response
from .system_intents import DEFAULT_ACTIONS_INTENTDEFINITION, system_intent_catalog
from .validation import ValidationError, validate_recipe
from .workflow import Shortcut


def main() -> int:
    try:
        return run()
    except ValidationError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    except (json.JSONDecodeError, ValueError, subprocess.CalledProcessError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1


def run() -> int:
    parser = argparse.ArgumentParser(prog="shortcutgen")
    subparsers = parser.add_subparsers(dest="command", required=True)

    compile_parser = subparsers.add_parser("compile", help="Compile a recipe JSON file")
    compile_parser.add_argument("recipe", type=Path)
    compile_parser.add_argument("--output", "-o", type=Path, required=True)
    compile_parser.add_argument("--sign", action="store_true")
    compile_parser.add_argument(
        "--sign-mode",
        choices=["anyone", "people-who-know-me"],
        default="anyone",
    )

    compile_response_parser = subparsers.add_parser(
        "compile-response",
        help="Compile a raw model response JSON file",
    )
    compile_response_parser.add_argument("response", type=Path)
    compile_response_parser.add_argument("--output", "-o", type=Path, required=True)
    compile_response_parser.add_argument("--sign", action="store_true")
    compile_response_parser.add_argument(
        "--sign-mode",
        choices=["anyone", "people-who-know-me"],
        default="anyone",
    )

    prompt_parser = subparsers.add_parser(
        "prompt",
        help="Build a prompt for recipe generation",
    )
    prompt_parser.add_argument("request")
    prompt_parser.add_argument("--example", action="append", type=Path, default=[])
    prompt_parser.add_argument("--output", "-o", type=Path)

    validate_parser = subparsers.add_parser("validate", help="Validate a compilable recipe")
    validate_parser.add_argument("recipe", type=Path)

    validate_response_parser = subparsers.add_parser(
        "validate-response",
        help="Validate a raw model response",
    )
    validate_response_parser.add_argument("response", type=Path)

    system_intents_parser = subparsers.add_parser(
        "system-intents",
        help="Extract Apple WorkflowKit Shortcuts intent metadata",
    )
    system_intents_parser.add_argument(
        "--source",
        type=Path,
        default=DEFAULT_ACTIONS_INTENTDEFINITION,
    )
    system_intents_parser.add_argument("--output", "-o", type=Path)

    args = parser.parse_args()

    if args.command == "compile":
        return compile_recipe(args.recipe, args.output, args.sign, args.sign_mode)

    if args.command == "compile-response":
        return compile_response(args.response, args.output, args.sign, args.sign_mode)

    if args.command == "prompt":
        return write_prompt(args.request, args.example, args.output)

    if args.command == "validate":
        validate_recipe(load_recipe(args.recipe))
        print(f"Valid recipe: {args.recipe}")
        return 0

    if args.command == "validate-response":
        response = parse_model_response(args.response.read_text(encoding="utf-8"))
        if response.unsupported:
            print(f"Unsupported response: {response.reason}")
        else:
            print(f"Valid response: {args.response}")
        return 0

    if args.command == "system-intents":
        return write_system_intents(args.source, args.output)

    parser.error(f"Unknown command: {args.command}")
    return 2


def compile_recipe(
    recipe_path: Path,
    output_path: Path,
    should_sign: bool,
    sign_mode: str,
) -> int:
    recipe = load_recipe(recipe_path)
    validate_recipe(recipe)
    shortcut = shortcut_from_recipe(recipe)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    shortcut.write(output_path)
    print(f"Wrote {output_path}")

    if should_sign:
        signed_path = output_path.with_name(f"{output_path.stem}.signed{output_path.suffix}")
        sign_shortcut(output_path, signed_path, sign_mode)
        print(f"Signed {signed_path}")

    return 0


def compile_response(
    response_path: Path,
    output_path: Path,
    should_sign: bool,
    sign_mode: str,
) -> int:
    response = parse_model_response(response_path.read_text(encoding="utf-8"))
    if response.unsupported:
        raise ValueError(f"Model response is unsupported: {response.reason}")

    shortcut = shortcut_from_recipe(response.recipe)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    shortcut.write(output_path)
    print(f"Wrote {output_path}")

    if should_sign:
        signed_path = output_path.with_name(f"{output_path.stem}.signed{output_path.suffix}")
        sign_shortcut(output_path, signed_path, sign_mode)
        print(f"Signed {signed_path}")

    return 0


def write_prompt(request: str, example_paths: list[Path], output_path: Path | None) -> int:
    examples = [load_recipe(path) for path in example_paths]
    prompt = build_prompt(request, examples)
    if output_path is None:
        print(prompt)
        return 0

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(prompt, encoding="utf-8")
    print(f"Wrote {output_path}")
    return 0


def write_system_intents(source_path: Path, output_path: Path | None) -> int:
    catalog = system_intent_catalog(source_path)
    content = json.dumps(catalog, indent=2, sort_keys=True)
    if output_path is None:
        print(content)
        return 0

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(f"{content}\n", encoding="utf-8")
    print(f"Wrote {output_path}")
    return 0


def load_recipe(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)

    if not isinstance(data, dict):
        raise ValueError("Recipe root must be a JSON object")

    return data


def shortcut_from_recipe(recipe: dict[str, Any]) -> Shortcut:
    name = recipe.get("name")
    if not isinstance(name, str) or not name:
        raise ValueError("Recipe is missing non-empty string field 'name'")

    action_specs = recipe.get("actions")
    if not isinstance(action_specs, list) or not action_specs:
        raise ValueError("Recipe is missing non-empty array field 'actions'")

    actions = []
    context = ActionContext()
    for index, spec in enumerate(action_specs):
        if not isinstance(spec, dict):
            raise ValueError(f"Action at index {index} must be an object")
        actions.append(action_from_recipe(spec, context))

    return Shortcut(name=name, actions=actions)


def sign_shortcut(input_path: Path, output_path: Path, mode: str) -> None:
    input_path = input_path.resolve()
    output_path = output_path.resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    temporary_output = Path(tempfile.mkdtemp(prefix="shortcutgen-sign-")) / output_path.name
    subprocess.run(
        [
            "shortcuts",
            "sign",
            "--mode",
            mode,
            "--input",
            str(input_path),
            "--output",
            str(temporary_output),
        ],
        check=True,
    )
    shutil.move(str(temporary_output), output_path)
