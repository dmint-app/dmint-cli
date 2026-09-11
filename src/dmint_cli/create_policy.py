"""Interactive wizard to inspect tool files via AST, ask guided security questions, and create access.md + policy.json."""

from __future__ import annotations

import argparse
import ast
import json
import os
import sys
from pathlib import Path
from typing import Any

from dmint.policy import Policy
from dmint_cli.compile_policy import CLIError, compile_policy_file


def parse_tool_declarations_ast(file_path: Path) -> list[dict[str, str]]:
    """Safe AST-based inspection of Python source file to discover tool names and descriptions.

    NO code execution (eval, exec, import) is performed.
    """
    if not file_path.exists():
        raise FileNotFoundError(f"tool source file not found: {file_path}")

    try:
        content = file_path.read_text(encoding="utf-8", errors="ignore")
        tree = ast.parse(content, filename=str(file_path))
    except Exception as exc:
        raise ValueError(f"failed to parse AST for {file_path}: {exc}") from exc

    discovered: list[dict[str, str]] = []
    seen: set[str] = set()

    for node in ast.walk(tree):
        # Look for Call(func=Name(id='Tool') or Attribute(attr='Tool')) or MCPToolBinding
        if isinstance(node, ast.Call):
            func_name = ""
            if isinstance(node.func, ast.Name):
                func_name = node.func.id
            elif isinstance(node.func, ast.Attribute):
                func_name = node.func.attr

            if func_name in {"Tool", "MCPToolBinding"}:
                tool_name = ""
                description = ""
                # Keyword args
                for kw in node.keywords:
                    if kw.arg in {"name", "tool_name"} and isinstance(kw.value, ast.Constant) and isinstance(kw.value.value, str):
                        tool_name = kw.value.value
                    elif kw.arg == "description" and isinstance(kw.value, ast.Constant) and isinstance(kw.value.value, str):
                        description = kw.value.value

                # Positional args if keywords were not used
                if not tool_name and node.args:
                    first_arg = node.args[0]
                    if isinstance(first_arg, ast.Constant) and isinstance(first_arg.value, str):
                        tool_name = first_arg.value

                if tool_name and tool_name not in seen:
                    seen.add(tool_name)
                    discovered.append({
                        "name": tool_name,
                        "description": description or f"Discovered tool from {file_path.name}",
                        "source": file_path.name,
                    })

    return discovered


def run_create_policy_wizard(
    *,
    tools_file: str | Path | None,
    access_md_file: str | Path,
    output_json_file: str | Path,
    base_url: str | None = None,
    api_key: str | None = None,
    model: str | None = None,
    provider: str | None = None,
    non_interactive: bool = False,
    auto_confirm: bool = False,
    timeout: float = 60.0,
) -> Policy:
    """Guided wizard to inspect tools, prompt for access rules, draft access.md, and compile verified policy.json."""
    md_path = Path(access_md_file).resolve()
    json_path = Path(output_json_file).resolve()

    discovered_tools: list[dict[str, str]] = []
    if tools_file:
        t_path = Path(tools_file).resolve()
        discovered_tools = parse_tool_declarations_ast(t_path)

    print("==================================================")
    print("      Dmint Interactive Policy Creation Wizard     ")
    print("==================================================")

    if discovered_tools:
        print(f"[✓] Discovered {len(discovered_tools)} tool(s) via AST inspection:")
        for t in discovered_tools:
            print(f"    - {t['name']}: {t['description']}")
    else:
        print("[!] No explicit tool declarations discovered via AST. Using default tool actions.")
        discovered_tools = [
            {"name": "read_data", "description": "Read database records"},
            {"name": "write_data", "description": "Insert new records"},
            {"name": "update_data", "description": "Update existing records"},
            {"name": "delete_data", "description": "Delete records from database"},
        ]

    print("\n--- Security Requirements Gathering ---")
    intents: list[str] = []

    if non_interactive or not sys.stdin.isatty():
        print("Non-interactive mode detected. Generating default security intent...")
        for t in discovered_tools:
            name = t["name"]
            if any(k in name.lower() for k in ("delete", "remove", "drop", "terminate")):
                intents.append(f"Agents are DENIED from executing {name}.")
            else:
                intents.append(f"Agents are ALLOWED to execute {name}.")
    else:
        for t in discovered_tools:
            name = t["name"]
            desc = t["description"]
            print(f"Tool: '{name}' ({desc})")
            print("  1. ALLOW (Agents can execute freely)")
            print("  2. DENY (Agents can NEVER execute)")
            print("  3. APPROVAL_REQUIRED (Requires human approval before execution)")
            choice = input("Select effect [1/2/3, default 1]: ").strip()

            if choice == "2":
                intents.append(f"Agents are DENIED from executing {name}.")
            elif choice == "3":
                intents.append(f"Agents require human APPROVAL before executing {name}.")
            else:
                intents.append(f"Agents are ALLOWED to execute {name}.")
            print()

        additional = input("Enter any additional security requirements or context rules (or press Enter): ").strip()
        if additional:
            intents.append(additional)

    # 1. Draft access.md
    md_content = "# Dmint Access Policy Requirements (Human Intent)\n\n" + "\n".join(f"- {intent}" for intent in intents) + "\n"
    md_path.parent.mkdir(parents=True, exist_ok=True)
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(md_content)

    print(f"\n[✓] Developer intent saved to: {md_path}")
    print("Compiling candidate policy JSON with LLM & Dmint Policy Skill...\n")

    # 2. Compile candidate policy.json to temporary destination
    temp_json_path = json_path.with_name(f".tmp_candidate_{json_path.name}")
    verified_policy = compile_policy_file(
        input_file=md_path,
        output_file=temp_json_path,
        base_url=base_url,
        api_key=api_key,
        model=model,
        provider=provider,
        timeout=timeout,
    )

    # 3. Explicit User Confirmation before final write
    print("--- Candidate Policy Review ---")
    print(f"Verified {len(verified_policy.rules)} rules:")
    for r in verified_policy.rules:
        res_str = r.resource if isinstance(r.resource, str) else type(r.resource).__name__
        print(f"  [{r.effect.value.upper()}] tool='{r.tool}', action='{r.action}', resource='{res_str}'")

    if not auto_confirm and not non_interactive and sys.stdin.isatty():
        confirm = input("\nAccept candidate policy and write policy.json? [y/N]: ").strip().lower()
        if confirm not in ("y", "yes"):
            if temp_json_path.exists():
                temp_json_path.unlink()
            raise CLIError("policy creation aborted by user", exit_code=1)

    # Move temp candidate to final policy.json
    if temp_json_path.exists():
        temp_json_path.replace(json_path)
    print(f"\n✓ Created access.md ({md_path})")
    print(f"✓ Created verified policy.json ({json_path})\n")

    return verified_policy


def main_create(args: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="dmint create-policy",
        description="Interactive wizard to discover tools, ask security questions, and create verified Dmint policy files.",
    )
    parser.add_argument("--tools", help="Path to Python MCP tool source file for AST tool discovery (e.g. sqlite_server.py)")
    parser.add_argument("-f", "--file", required=True, help="Output developer intent markdown file (e.g. access.md)")
    parser.add_argument("-o", "--output", required=True, help="Output verified policy JSON file (e.g. policy.json)")
    parser.add_argument("-provider", "--provider", help="LLM provider (e.g. openai, gemini, groq, openrouter, ollama)")
    parser.add_argument("-base_url", "--base-url", help="OpenAI-compatible base URL (default: https://api.openai.com/v1)")
    parser.add_argument("-api_key", "--api-key", help="API key (or via OPENAI_API_KEY / GEMINI_API_KEY env vars)")
    parser.add_argument("-model", "--model", help="Model name (e.g. gpt-4o-mini, gemini-1.5-flash)")
    parser.add_argument("--non-interactive", action="store_true", help="Run without terminal input prompts")
    parser.add_argument("-y", "--yes", action="store_true", help="Auto-confirm candidate policy without prompting")
    parser.add_argument("--timeout", type=float, default=60.0, help="API request timeout in seconds (default: 60.0)")

    try:
        parsed = parser.parse_args(args)
    except SystemExit:
        return 2

    try:
        policy = run_create_policy_wizard(
            tools_file=parsed.tools,
            access_md_file=parsed.file,
            output_json_file=parsed.output,
            base_url=parsed.base_url,
            api_key=parsed.api_key,
            model=parsed.model,
            provider=parsed.provider,
            non_interactive=parsed.non_interactive,
            auto_confirm=parsed.yes,
            timeout=parsed.timeout,
        )
        return 0
    except CLIError as exc:
        print(f"✗ Policy creation failed: {exc}", file=sys.stderr)
        return exc.exit_code
    except Exception as exc:
        print(f"✗ Unexpected error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main_create())
