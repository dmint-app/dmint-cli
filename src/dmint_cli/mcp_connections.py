"""Generic MCP connection modeling and tool discovery for dmint-cli."""

from __future__ import annotations

import asyncio
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from dmint_cli.compile_policy import CLIError

SUPPORTED_TRANSPORTS = {"stdio"}


@dataclass
class MCPIntegration:
    """Generic representation of an MCP integration for CLI policy authoring."""

    integration_id: str
    transport: str = "stdio"
    connection: dict[str, Any] = field(default_factory=dict)
    authentication: dict[str, Any] = field(default_factory=dict)
    discovered_tools: list[dict[str, Any]] = field(default_factory=list)

    def validate_transport(self) -> None:
        """Validate that the requested transport is supported by the dmint-mcp runtime."""
        trans = (self.transport or "").lower().strip()
        if trans not in SUPPORTED_TRANSPORTS:
            raise CLIError(
                f"Unsupported MCP transport type '{self.transport}'. "
                f"The current dmint-mcp runtime only supports 'stdio'. "
                f"Remote HTTP/SSE transport support requires dmint-mcp runtime updates."
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "integration_id": self.integration_id,
            "transport": self.transport,
            "connection": self.connection,
            "tool_bindings": {
                t["name"]: {
                    "tool_name": t["name"],
                    "capability": f"mcp.{self.integration_id}.{t['name']}",
                    "discovery": "exposed",
                }
                for t in self.discovered_tools
            },
        }


async def discover_mcp_tools_generic(integration: MCPIntegration) -> list[dict[str, Any]]:
    """Discover tools from an MCP integration according to its transport settings."""
    integration.validate_transport()

    command = integration.connection.get("command")
    args = integration.connection.get("args", [])
    env = integration.connection.get("env")

    if not command:
        raise CLIError(f"Missing executable command for integration '{integration.integration_id}'.")

    try:
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client
    except ImportError as exc:
        raise CLIError("mcp package is required for MCP tool discovery. Install via `pip install mcp`.") from exc

    params = StdioServerParameters(
        command=command,
        args=args if isinstance(args, list) else list(args),
        env=env or dict(os.environ),
    )

    try:
        async with stdio_client(params) as (read_stream, write_stream):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()
                tools_res = await session.list_tools()
                tools: list[dict[str, Any]] = []
                for t in tools_res.tools:
                    schema = getattr(t, "inputSchema", getattr(t, "input_schema", {}))
                    tools.append({
                        "name": t.name,
                        "description": t.description or f"MCP tool {t.name}",
                        "input_schema": schema if isinstance(schema, dict) else {},
                        "integration_id": integration.integration_id,
                    })
                integration.discovered_tools = tools
                return tools
    except CLIError:
        raise
    except Exception as exc:
        raise CLIError(f"Failed to connect to MCP server for integration '{integration.integration_id}': {exc}") from exc
