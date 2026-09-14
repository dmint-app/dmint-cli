"""Wizard for dmint create-mcp-policy (specialized for external MCP servers)."""

from __future__ import annotations

import argparse
import asyncio
import getpass
import json
import os
import sys
from pathlib import Path
from typing import Any

from dmint.policy import Policy, PolicyError
from dmint_cli.api import OpenAICompatClient, resolve_api_key
from dmint_cli.errors import (
    APIError,
    CLIError,
    InputFileError,
    JSONExtractionError,
    OutputWriteError,
    PolicyValidationError,
)
from dmint_cli.io_utils import atomic_write_json, load_system_prompt
from dmint_cli.mcp_connections import MCPIntegration, discover_mcp_tools_generic
from dmint_cli.verify_policy import verify_policy_file


def run_create_mcp_policy_wizard(
    *,
    command: str | None = None,
    args: list[str] | None = None,
    integration_id: str | None = None,
    transport: str = "stdio",
    url: str | None = None,
    access_md_file: str | Path = "access.md",
    output_json_file: str | Path = "policy.json",
    config_output_file: str | Path = "mcp_protection.json",
    base_url: str | None = None,
    api_key: str | None = None,
    model: str | None = None,
    provider: str | None = None,
    non_interactive: bool = False,
    auto_confirm: bool = False,
    timeout: float = 60.0,
) -> tuple[Policy, dict[str, Any]]:
    """Wizard to discover tools from one or more existing MCP servers, create policy, and output MCP protection config."""
    md_path = Path(access_md_file).resolve()
    json_path = Path(output_json_file).resolve()
    config_path = Path(config_output_file).resolve()

    is_tty = sys.stdin.isatty() and not non_interactive

    print("==================================================")
    print("      Dmint External MCP Policy Creation Wizard   ")
    print("==================================================")

    integrations: list[MCPIntegration] = []

    # 1. Initial MCP Integration setup (from parameters or interactive prompt)
    if url or (transport and transport.lower() not in ("stdio", "")):
        # Remote URL transport requested
        integ = MCPIntegration(
            integration_id=integration_id or "remote-mcp",
            transport=transport if transport else "remote-http",
            connection={"url": url or "https://example.com/mcp"},
        )
        integ.validate_transport()  # Fails closed with explicit unsupported error
        integrations.append(integ)
    else:
        mcp_cmd = command
        mcp_args = args or []

        if is_tty and not mcp_cmd:
            print("\nAdd MCP Server\n")
            print("Connection type:")
            print("  1. Local process / stdio")
            print("  2. Remote MCP server (URL)\n")
            conn_type = input("Select [1/2, default 1]: ").strip()

            if conn_type == "2":
                r_url = input("Enter Remote MCP URL (e.g. https://example.com/mcp): ").strip()
                r_id = input("Enter Integration ID [default: remote-mcp]: ").strip() or "remote-mcp"
                integ = MCPIntegration(
                    integration_id=r_id,
                    transport="remote-http",
                    connection={"url": r_url},
                )
                integ.validate_transport()  # Fails closed explicitly
                integrations.append(integ)
            else:
                mcp_cmd = input("Command (e.g. npx, mcp-server-postgres): ").strip() or "npx"
                args_str = input("Arguments (e.g. -y @modelcontextprotocol/server-postgres ...): ").strip()
                if args_str:
                    mcp_args = args_str.split()
                r_id = input(f"Integration ID [default: {mcp_cmd.replace('/', '-')[:20]}]: ").strip() or mcp_cmd.replace('/', '-')[:20]
                integrations.append(MCPIntegration(
                    integration_id=r_id,
                    transport="stdio",
                    connection={"command": mcp_cmd, "args": mcp_args},
                ))
        else:
            mcp_cmd = mcp_cmd or "npx"
            r_id = integration_id or f"mcp-{mcp_cmd.replace('/', '-').replace(':', '-')}"
            integrations.append(MCPIntegration(
                integration_id=r_id,
                transport="stdio",
                connection={"command": mcp_cmd, "args": mcp_args},
            ))

    # Support adding additional MCP servers interactively
    if is_tty:
        while True:
            add_more = input("\nAdd another MCP server? [y/N]: ").strip().lower()
            if add_more not in ("y", "yes"):
                break
            print("\nAdd Additional MCP Server")
            print("Connection type:")
            print("  1. Local process / stdio")
            print("  2. Remote MCP server (URL)\n")
            conn_type = input("Select [1/2, default 1]: ").strip()
            if conn_type == "2":
                r_url = input("Enter Remote MCP URL: ").strip()
                r_id = input("Enter Integration ID: ").strip() or f"remote-mcp-{len(integrations)+1}"
                integ = MCPIntegration(
                    integration_id=r_id,
                    transport="remote-http",
                    connection={"url": r_url},
                )
                integ.validate_transport()
                integrations.append(integ)
            else:
                next_cmd = input("Command: ").strip() or "npx"
                next_args = input("Arguments: ").strip().split()
                default_id = f"{next_cmd.replace('/', '-')[:15]}-{len(integrations)+1}"
                next_id = input(f"Integration ID [default: {default_id}]: ").strip() or default_id
                integrations.append(MCPIntegration(
                    integration_id=next_id,
                    transport="stdio",
                    connection={"command": next_cmd, "args": next_args},
                ))

    # Validate unique integration IDs across all requested MCP servers
    seen_ids: set[str] = set()
    for integ in integrations:
        if integ.integration_id in seen_ids:
            raise CLIError(f"Duplicate integration ID '{integ.integration_id}'. Integration IDs must be unique across all MCP servers.")
        seen_ids.add(integ.integration_id)

    # 2. Perform tool discovery for each MCP server
    all_discovered_tools: list[dict[str, Any]] = []
    for integ in integrations:
        print(f"\nConnecting to MCP server for integration '{integ.integration_id}'...")
        try:
            tools = asyncio.run(discover_mcp_tools_generic(integ))
            integ.discovered_tools = tools
            print(f"[✓] Discovered {len(tools)} tool(s) for '{integ.integration_id}':")
            for t in tools:
                print(f"    - {t['name']}: {t['description']}")
            all_discovered_tools.extend(tools)
        except CLIError:
            raise
        except Exception as exc:
            raise CLIError(f"Failed tool discovery for integration '{integ.integration_id}': {exc}") from exc

    if not all_discovered_tools:
        print("\n[!] No tools discovered across requested MCP servers.")

    # Display grouped capability inventory
    print("\n--- Discovered MCP Capabilities ---")
    for integ in integrations:
        print(f"\nIntegration '{integ.integration_id}' ({integ.transport}):")
        if integ.discovered_tools:
            for t in integ.discovered_tools:
                print(f"  - {t['name']}: {t['description']}")
        else:
            print("  (no tools exposed)")

    # 3. Requirements file handling
    if not md_path.exists():
        if is_tty:
            print(f"\nRequirements file '{md_path.name}' not found. Please enter security rules for discovered tools:")
            req_lines = []
            for t in all_discovered_tools:
                ans = input(f"Effect for '{t['integration_id']}.{t['name']}' (ALLOW / DENY / APPROVAL_REQUIRED) [default ALLOW]: ").strip().upper()
                eff = ans if ans in ("ALLOW", "DENY", "APPROVAL_REQUIRED") else "ALLOW"
                req_lines.append(f"- Tool '{t['name']}' under integration '{t['integration_id']}': {eff}")
            md_path.parent.mkdir(parents=True, exist_ok=True)
            md_path.write_text("# MCP Security Requirements\n" + "\n".join(req_lines) + "\n", encoding="utf-8")
        else:
            raise InputFileError(f"requirements file not found: {md_path}")

    try:
        policy_text = md_path.read_text(encoding="utf-8").strip()
    except Exception as exc:
        raise InputFileError(f"failed to read requirements file: {exc}") from exc

    if not policy_text:
        raise InputFileError(f"input requirements file is empty: {md_path}")

    # Build prompt context preserving integration identity & tool metadata
    if all_discovered_tools:
        mcp_summary_lines = []
        for integ in integrations:
            mcp_summary_lines.append(f"\nIntegration '{integ.integration_id}' ({integ.transport}):")
            for t in integ.discovered_tools:
                schema_str = json.dumps(t["input_schema"])
                mcp_summary_lines.append(f"  - tool_name: '{t['name']}', capability: 'mcp.{integ.integration_id}.{t['name']}', description: '{t['description']}', schema: {schema_str}")
        mcp_summary = "\n".join(mcp_summary_lines)
        policy_text = f"[DISCOVERED EXTERNAL MCP CAPABILITIES]\n{mcp_summary}\n\n[HUMAN SECURITY REQUIREMENTS]\n{policy_text}"

    # 4. Provider & Model Selection
    selected_provider = (provider or "").lower().strip()
    if is_tty and not selected_provider:
        prov_in = input("\nSelect provider (openai/gemini/groq/openrouter/ollama/custom) [default: openai]: ").strip()
        selected_provider = prov_in.lower() if prov_in else "openai"
    elif not selected_provider:
        selected_provider = "openai"

    resolved_key = resolve_api_key(api_key, selected_provider)
    if is_tty and not resolved_key and selected_provider != "ollama":
        key_in = getpass.getpass(f"Enter API Key for {selected_provider} (leave blank if using env var): ").strip()
        if key_in:
            resolved_key = key_in

    client = OpenAICompatClient(
        base_url=base_url,
        api_key=resolved_key,
        model=model,
        provider=selected_provider,
        timeout=timeout,
    )

    selected_model = model
    if is_tty and not selected_model:
        try:
            available_models = client.list_models()
            print("\n[✓] Discovered available models:")
            for idx, m_id in enumerate(available_models[:15], start=1):
                print(f"  {idx}) {m_id}")
            default_m = available_models[0]
            choice = input(f"\nSelect model number (1-{min(len(available_models), 15)}) or type model ID [default: {default_m}]: ").strip()
            if choice.isdigit():
                c_idx = int(choice) - 1
                selected_model = available_models[c_idx] if 0 <= c_idx < len(available_models) else default_m
            else:
                selected_model = choice or default_m
        except Exception as exc:
            print(f"\n[!] Could not list models: {exc}. Please enter model ID manually.")
            manual_m = input("Enter model ID [default: gpt-4o-mini]: ").strip()
            selected_model = manual_m or "gpt-4o-mini"
    elif not selected_model:
        selected_model = "gpt-4o-mini"

    client = OpenAICompatClient(
        base_url=base_url,
        api_key=resolved_key,
        model=selected_model,
        provider=selected_provider,
        timeout=timeout,
    )

    # 5. Multi-turn conversation & validation
    system_prompt = load_system_prompt()
    messages: list[dict[str, Any]] = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": policy_text},
    ]

    shape_retry_attempts = 0
    policy_error_attempts = 0

    while True:
        try:
            raw_response = client.chat_completion(messages, temperature=0.0)
        except Exception as exc:
            raise APIError(str(exc)) from exc

        try:
            response_data = json.loads(raw_response)
        except json.JSONDecodeError:
            response_data = None

        if not isinstance(response_data, dict) or "type" not in response_data:
            shape_retry_attempts += 1
            if shape_retry_attempts >= 3:
                raise JSONExtractionError(f"Model failed to match output contract. Raw:\n{raw_response}")
            messages.append({"role": "assistant", "content": raw_response})
            messages.append({"role": "user", "content": "Your last response did not match the required output contract, resend as one of the two exact JSON shapes"})
            continue

        msg_type = response_data.get("type")

        if msg_type == "clarification_needed":
            questions = response_data.get("questions") or ["Clarify tool scope?"]
            print("\n--- Clarification Needed from Assistant ---")
            answers = []
            for idx, q in enumerate(questions, start=1):
                print(f"Q{idx}: {q}")
                ans = input("A: ").strip() if is_tty else "Apply least-privilege defaults."
                answers.append(f"Q{idx}: {q}\nA{idx}: {ans}")
            messages.append({"role": "assistant", "content": json.dumps(response_data)})
            messages.append({"role": "user", "content": "\n".join(answers)})
            continue

        elif msg_type == "policy_ready":
            rules = response_data.get("rules")
            if not isinstance(rules, list):
                shape_retry_attempts += 1
                if shape_retry_attempts >= 3:
                    raise JSONExtractionError("policy_ready missing rules list.")
                messages.append({"role": "assistant", "content": raw_response})
                messages.append({"role": "user", "content": "Your last response did not match the required output contract, resend as one of the two exact JSON shapes"})
                continue

            policy_mapping = {"rules": rules}

            try:
                verified_policy = Policy.from_mapping(policy_mapping)
            except Exception as exc:
                policy_error_attempts += 1
                if policy_error_attempts >= 4:
                    raise PolicyValidationError(f"Dmint validation failed: {exc}") from exc
                messages.append({"role": "assistant", "content": json.dumps(response_data)})
                messages.append({"role": "user", "content": f"Dmint validation failed: {exc}. Fix it and resend."})
                continue

            print("\n--- Candidate Policy Review ---")
            print(f"Verified {len(verified_policy.rules)} rules:")
            for r in verified_policy.rules:
                res_str = r.resource if isinstance(r.resource, str) else type(r.resource).__name__
                print(f"  [{r.effect.value.upper()}] tool='{r.tool}', action='{r.action}', resource='{res_str}'")

            if not auto_confirm and is_tty:
                confirm = input("\nAccept candidate policy and write policy.json + mcp_protection.json? [y/N]: ").strip().lower()
                if confirm not in ("y", "yes"):
                    raise CLIError("policy creation aborted by user", exit_code=1)

            atomic_write_json(json_path, policy_mapping)
            verify_policy_file(json_path)

            # Generate multi-integration MCP protection configuration artifact
            protection_config = {
                "policy_file": json_path.name,
                "integrations": [integ.to_dict() for integ in integrations],
            }

            atomic_write_json(config_path, protection_config)

            print(f"\n✓ Verified & saved policy: {json_path}")
            print(f"✓ Created MCP protection config: {config_path}\n")
            return verified_policy, protection_config

        else:
            shape_retry_attempts += 1
            if shape_retry_attempts >= 3:
                raise JSONExtractionError(f"Unrecognized response type '{msg_type}'.")
            messages.append({"role": "assistant", "content": raw_response})
            messages.append({"role": "user", "content": "Your last response did not match the required output contract, resend as one of the two exact JSON shapes"})
            continue


def main_create_mcp(args: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="dmint create-mcp-policy",
        description="Specialized wizard to discover tools from existing MCP servers, create Dmint policy, and generate protection artifacts.",
    )
    parser.add_argument("--command", help="MCP server executable command (e.g. npx, mcp-server-postgres)")
    parser.add_argument("--args", nargs="*", help="Arguments for MCP server executable")
    parser.add_argument("--integration-id", help="Unique integration ID for this MCP server")
    parser.add_argument("--transport", default="stdio", help="MCP transport type (default: stdio)")
    parser.add_argument("--url", help="Remote MCP server URL (if transport is remote)")
    parser.add_argument("-f", "--file", default="access.md", help="Input requirements markdown file (default: access.md)")
    parser.add_argument("-o", "--output", default="policy.json", help="Output verified policy JSON file (default: policy.json)")
    parser.add_argument("--config-output", default="mcp_protection.json", help="Output MCP protection configuration JSON file (default: mcp_protection.json)")
    parser.add_argument("-provider", "--provider", help="LLM provider (e.g. openai, gemini, groq, openrouter, ollama)")
    parser.add_argument("-base_url", "--base-url", help="OpenAI-compatible base URL")
    parser.add_argument("-api_key", "--api-key", help="API key")
    parser.add_argument("-model", "--model", help="Model name")
    parser.add_argument("--non-interactive", action="store_true", help="Run without terminal input prompts")
    parser.add_argument("-y", "--yes", action="store_true", help="Auto-confirm candidate policy without prompting")
    parser.add_argument("--timeout", type=float, default=60.0, help="API request timeout in seconds (default: 60.0)")

    try:
        parsed = parser.parse_args(args)
    except SystemExit as exc:
        return exc.code if isinstance(exc.code, int) else 0

    try:
        run_create_mcp_policy_wizard(
            command=parsed.command,
            args=parsed.args,
            integration_id=parsed.integration_id,
            transport=parsed.transport,
            url=parsed.url,
            access_md_file=parsed.file,
            output_json_file=parsed.output,
            config_output_file=parsed.config_output,
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
        print(f"✗ MCP Policy creation failed: {exc}", file=sys.stderr)
        return exc.exit_code
    except Exception as exc:
        print(f"✗ Unexpected error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main_create_mcp())
