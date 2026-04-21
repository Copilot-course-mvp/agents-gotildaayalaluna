#!/usr/bin/env python3
"""Validate YAML front-matter of Copilot prompt files and chat modes.

Run locally:
    python .github/scripts/validate_copilot_customisations.py

The script is intentionally dependency-light (PyYAML only) so it can run in CI
without a heavier toolchain. It checks that every `.prompt.md` and `.chatmode.md`
file in this repository has a well-formed YAML front-matter block with the
required keys, and that the values are of the expected types.

Exits with a non-zero status if any file is malformed, printing all problems.
"""

from __future__ import annotations

import pathlib
import sys
from typing import Iterable

import yaml

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]

PROMPT_ALLOWED_MODES = {"agent", "ask", "edit"}
PROMPT_REQUIRED_KEYS = {"mode", "description"}
CHATMODE_REQUIRED_KEYS = {"description"}


def _read_front_matter(path: pathlib.Path) -> tuple[dict, str] | None:
    """Extract the YAML front-matter dict and the body of a Markdown file.

    Returns None if there is no front-matter at all (we only check files that
    declare themselves as Copilot customisations via their extension, so a
    missing block is an error handled by the caller).
    """
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        return None
    try:
        _, fm, body = text.split("---\n", 2)
    except ValueError:
        return None
    try:
        data = yaml.safe_load(fm) or {}
    except yaml.YAMLError as exc:
        raise ValueError(f"invalid YAML front-matter: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError("front-matter must be a mapping")
    return data, body


def _validate_common(data: dict, errors: list[str]) -> None:
    description = data.get("description")
    if not isinstance(description, str) or not description.strip():
        errors.append("`description` must be a non-empty string")
    tools = data.get("tools")
    if tools is not None and not (
        isinstance(tools, list) and all(isinstance(t, str) for t in tools)
    ):
        errors.append("`tools` must be a list of strings if provided")


def _validate_prompt(path: pathlib.Path) -> list[str]:
    errors: list[str] = []
    try:
        result = _read_front_matter(path)
    except ValueError as exc:
        return [str(exc)]
    if result is None:
        return ["missing YAML front-matter block"]
    data, body = result

    missing = PROMPT_REQUIRED_KEYS - data.keys()
    if missing:
        errors.append(f"missing required keys: {sorted(missing)}")

    mode = data.get("mode")
    if mode is not None and mode not in PROMPT_ALLOWED_MODES:
        errors.append(
            f"`mode` must be one of {sorted(PROMPT_ALLOWED_MODES)}, got {mode!r}"
        )

    _validate_common(data, errors)

    if not body.strip():
        errors.append("prompt body is empty — Copilot has no instructions to apply")

    return errors


def _validate_chatmode(path: pathlib.Path) -> list[str]:
    errors: list[str] = []
    try:
        result = _read_front_matter(path)
    except ValueError as exc:
        return [str(exc)]
    if result is None:
        return ["missing YAML front-matter block"]
    data, body = result

    missing = CHATMODE_REQUIRED_KEYS - data.keys()
    if missing:
        errors.append(f"missing required keys: {sorted(missing)}")

    _validate_common(data, errors)

    if not body.strip():
        errors.append("chat mode body is empty — persona has no description")

    return errors


def _collect(base: pathlib.Path, pattern: str) -> Iterable[pathlib.Path]:
    if not base.exists():
        return []
    return sorted(base.glob(pattern))


def main() -> int:
    prompt_files = _collect(REPO_ROOT / ".github/prompts", "*.prompt.md")
    chatmode_files = _collect(REPO_ROOT / ".github/chatmodes", "*.chatmode.md")

    if not prompt_files and not chatmode_files:
        print("No Copilot customisation files found — nothing to validate.")
        return 0

    failures: dict[pathlib.Path, list[str]] = {}

    for path in prompt_files:
        problems = _validate_prompt(path)
        if problems:
            failures[path] = problems

    for path in chatmode_files:
        problems = _validate_chatmode(path)
        if problems:
            failures[path] = problems

    checked = len(prompt_files) + len(chatmode_files)
    print(
        f"Checked {checked} file(s): "
        f"{len(prompt_files)} prompt(s), {len(chatmode_files)} chat mode(s)."
    )

    if failures:
        print("\n❌ Validation failed:")
        for path, problems in failures.items():
            rel = path.relative_to(REPO_ROOT)
            print(f"\n  {rel}")
            for problem in problems:
                print(f"    - {problem}")
        return 1

    print("✅ All Copilot customisation files are valid.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
