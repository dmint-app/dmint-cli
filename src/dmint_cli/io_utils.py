"""Shared I/O helpers for atomic writing and prompt loading."""

from __future__ import annotations

import importlib.resources
import json
import os
import tempfile
from pathlib import Path

from dmint_cli.errors import OutputWriteError


def load_system_prompt() -> str:
    """Load system prompt from bundled resource file policy_skill.md."""
    try:
        return importlib.resources.files("dmint_cli.prompts").joinpath("policy_skill.md").read_text(encoding="utf-8")
    except Exception:
        prompt_path = Path(__file__).parent / "prompts" / "policy_skill.md"
        return prompt_path.read_text(encoding="utf-8")


def atomic_write_json(output_path: Path, data: dict) -> None:
    """Atomically write JSON to destination using temp file replace to prevent partial writes."""
    output_path = Path(output_path).resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temp_fd, temp_path = tempfile.mkstemp(dir=output_path.parent, prefix=".policy_tmp_")
    try:
        with open(temp_fd, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(temp_path, output_path)
    except Exception as exc:
        if os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except OSError:
                pass
        raise OutputWriteError(f"failed to write output policy file: {exc}") from exc
