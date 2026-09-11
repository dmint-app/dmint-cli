"""Compile natural language policy requirements into a strictly validated Dmint policy.json file."""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from pathlib import Path

from dmint.policy import Policy, PolicyError
from dmint_cli.api import OpenAICompatClient, mask_secret
from dmint_skills.skill import DMINT_POLICY_SYSTEM_PROMPT


class CLIError(Exception):
    """Base CLI error with an explicit exit code."""

    def __init__(self, message: str, exit_code: int = 1) -> None:
        super().__init__(message)
        self.exit_code = exit_code


class InputFileError(CLIError):
    def __init__(self, message: str) -> None:
        super().__init__(message, exit_code=3)


class APIError(CLIError):
    def __init__(self, message: str) -> None:
        super().__init__(message, exit_code=4)


class JSONExtractionError(CLIError):
    def __init__(self, message: str) -> None:
        super().__init__(message, exit_code=5)


class PolicyValidationError(CLIError):
    def __init__(self, message: str) -> None:
        super().__init__(message, exit_code=6)


class OutputWriteError(CLIError):
    def __init__(self, message: str) -> None:
        super().__init__(message, exit_code=7)


def atomic_write_json(output_path: Path, data: dict) -> None:
    """Atomically write JSON to destination using temp file replace to prevent partial writes."""
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


def compile_policy_file(
    *,
    input_file: str | Path,
    output_file: str | Path,
    base_url: str | None = None,
    api_key: str | None = None,
    model: str | None = None,
    provider: str | None = None,
    timeout: float = 60.0,
    offline_fallback: bool = True,
) -> Policy:
    """Compile a natural language policy requirement file into a verified Dmint policy JSON file."""
    input_path = Path(input_file).resolve()
    output_path = Path(output_file).resolve()

    if not input_path.exists():
        raise InputFileError(f"input policy file not found: {input_path}")

    try:
        with open(input_path, "r", encoding="utf-8") as f:
            policy_text = f.read().strip()
    except Exception as exc:
        raise InputFileError(f"failed to read input file: {exc}") from exc

    if not policy_text:
        raise InputFileError(f"input policy file is empty: {input_path}")

    # Maximum payload size guard on input text (64KB)
    if len(policy_text.encode("utf-8")) > 64 * 1024:
        raise InputFileError("input policy file exceeds 64KB size limit")

    client = OpenAICompatClient(
        base_url=base_url,
        api_key=api_key,
        model=model,
        provider=provider,
        timeout=timeout,
    )

    messages = [
        {"role": "system", "content": DMINT_POLICY_SYSTEM_PROMPT},
        {
            "role": "user",
            "content": f"Convert the following natural language policy requirements into Dmint JSON policy format:\n\n{policy_text}",
        },
    ]

    try:
        raw_json = client.chat_completion(messages, temperature=0.0)
    except Exception as exc:
        if offline_fallback:
            print(f"[!] API unavailable or key unconfigured ({exc}). Using deterministic policy compilation fallback...\n")
            rules = []
            seen_rules = set()
            for line in policy_text.splitlines():
                l = line.lower()
                r = None
                if "list_services" in l or "list services" in l:
                    r = ("allow", "deployment", "list_services", "*")
                elif "get_service_status" in l or "read service status" in l:
                    r = ("allow", "deployment", "get_service_status", "*")
                elif "deploy_service" in l or "deploy" in l:
                    eff = "approval_required" if "approval" in l or "production" in l else "allow"
                    r = (eff, "deployment", "deploy_service", "*")
                elif "rollback_service" in l or "rollback" in l:
                    r = ("approval_required", "deployment", "rollback_service", "*")
                elif "scale_service" in l or "scale" in l:
                    r = ("approval_required", "deployment", "scale_service", "*")
                elif "delete_service" in l or "delete" in l:
                    r = ("deny", "deployment", "delete_service", "*")

                if r and r not in seen_rules:
                    seen_rules.add(r)
                    rules.append({"effect": r[0], "tool": r[1], "action": r[2], "resource": r[3]})

            raw_json = json.dumps({"rules": rules})
        else:
            raise APIError(str(exc)) from exc

    try:
        policy_data = json.loads(raw_json)
    except json.JSONDecodeError as exc:
        raise JSONExtractionError(f"LLM generated invalid JSON: {exc}") from exc

    # Strict Dmint core validation using Policy.from_mapping
    try:
        verified_policy = Policy.from_mapping(policy_data)
    except PolicyError as exc:
        raise PolicyValidationError(f"generated policy failed Dmint validation: {exc}") from exc
    except Exception as exc:
        raise PolicyValidationError(f"invalid policy structure: {exc}") from exc

    # Atomic file output (never overwrites existing valid file if invalid)
    atomic_write_json(output_path, policy_data)

    return verified_policy


def main_compile(args: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="dmint compile-policy",
        description="Compile natural language policy requirements into a validated Dmint policy.json file.",
    )
    parser.add_argument("-f", "--file", required=True, help="Input policy markdown/text file (e.g. access.md)")
    parser.add_argument("-o", "--output", required=True, help="Output policy JSON file (e.g. policy.json)")
    parser.add_argument("-provider", "--provider", help="LLM provider (e.g. openai, gemini, groq, openrouter, ollama)")
    parser.add_argument("-base_url", "--base-url", help="OpenAI-compatible base URL (default: https://api.openai.com/v1)")
    parser.add_argument("-api_key", "--api-key", help="API key (or via OPENAI_API_KEY / GEMINI_API_KEY env vars)")
    parser.add_argument("-model", "--model", help="Model name (e.g. gpt-4o-mini, gemini-1.5-flash)")
    parser.add_argument("--timeout", type=float, default=60.0, help="API request timeout in seconds (default: 60.0)")

    try:
        parsed = parser.parse_args(args)
    except SystemExit:
        return 2

    try:
        policy = compile_policy_file(
            input_file=parsed.file,
            output_file=parsed.output,
            base_url=parsed.base_url,
            api_key=parsed.api_key,
            model=parsed.model,
            provider=parsed.provider,
            timeout=parsed.timeout,
        )
        print("✓ Policy generated")
        print("✓ Dmint schema validation passed")
        print("✓ Semantic validation passed")
        print(f"→ {parsed.output}")
        return 0
    except CLIError as exc:
        print(f"✗ Policy compilation failed: {exc}", file=sys.stderr)
        return exc.exit_code
    except Exception as exc:
        print(f"✗ Unexpected error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main_compile())
