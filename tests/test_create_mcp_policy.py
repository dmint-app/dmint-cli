"""Unit and security tests for create-mcp-policy command (src/dmint_cli/create_mcp_policy.py)."""

import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from dmint.policy import Policy
from dmint_cli.__main__ import main
from dmint_cli.create_mcp_policy import (
    main_create_mcp,
    run_create_mcp_policy_wizard,
)
from dmint_cli.errors import CLIError
from dmint_cli.mcp_connections import MCPIntegration


class CreateMCPPolicyTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.base_path = Path(self.temp_dir.name)
        self.md_file = self.base_path / "access.md"
        self.json_file = self.base_path / "policy.json"
        self.config_file = self.base_path / "mcp_protection.json"

        self.md_file.write_text("# Requirements\n- Allow postgres query.", encoding="utf-8")

    def tearDown(self):
        self.temp_dir.cleanup()

    @patch("dmint_cli.create_mcp_policy.discover_mcp_tools_generic", new_callable=AsyncMock)
    @patch("dmint_cli.create_mcp_policy.OpenAICompatClient")
    def test_run_create_mcp_policy_wizard_generates_policy_and_config(self, mock_client_cls, mock_discover):
        mock_discover.return_value = [
            {"name": "query", "description": "Run SQL query", "input_schema": {"type": "object"}, "integration_id": "mcp-mcp-server-postgres"}
        ]
        mock_client = MagicMock()
        mock_client.model = "gpt-4o-mini"
        mock_client.base_url = "https://api.openai.com/v1"
        mock_client.chat_completion.return_value = json.dumps({
            "type": "policy_ready",
            "rules": [{"effect": "allow", "tool": "postgres", "action": "query", "resource": "*"}]
        })
        mock_client_cls.return_value = mock_client

        policy, config = run_create_mcp_policy_wizard(
            command="mcp-server-postgres",
            args=["postgresql://localhost/db"],
            access_md_file=self.md_file,
            output_json_file=self.json_file,
            config_output_file=self.config_file,
            api_key="sk-test",
            non_interactive=True,
            auto_confirm=True,
        )

        self.assertIsInstance(policy, Policy)
        self.assertTrue(self.json_file.exists())
        self.assertTrue(self.config_file.exists())
        self.assertIn("integrations", config)
        self.assertEqual(config["integrations"][0]["connection"]["command"], "mcp-server-postgres")
        self.assertIn("query", config["integrations"][0]["tool_bindings"])

    def test_mcp_integration_model_to_dict_preserves_identity(self):
        integ = MCPIntegration(
            integration_id="github",
            transport="stdio",
            connection={"command": "npx", "args": ["-y", "@example/github-mcp"]},
            discovered_tools=[
                {"name": "get_repository", "description": "Get repo details"},
                {"name": "create_issue", "description": "Create issue"},
            ],
        )
        d = integ.to_dict()
        self.assertEqual(d["integration_id"], "github")
        self.assertEqual(d["transport"], "stdio")
        self.assertIn("get_repository", d["tool_bindings"])
        self.assertEqual(d["tool_bindings"]["get_repository"]["capability"], "mcp.github.get_repository")

    def test_distinct_cross_server_tool_identities(self):
        # Two servers exposing the same tool name "query"
        integ1 = MCPIntegration(
            integration_id="postgres",
            transport="stdio",
            connection={"command": "mcp-server-postgres"},
            discovered_tools=[{"name": "query", "description": "Execute DB query"}],
        )
        integ2 = MCPIntegration(
            integration_id="analytics",
            transport="stdio",
            connection={"command": "mcp-server-analytics"},
            discovered_tools=[{"name": "query", "description": "Execute analytics query"}],
        )
        d1 = integ1.to_dict()
        d2 = integ2.to_dict()
        self.assertNotEqual(
            d1["tool_bindings"]["query"]["capability"],
            d2["tool_bindings"]["query"]["capability"],
        )
        self.assertEqual(d1["tool_bindings"]["query"]["capability"], "mcp.postgres.query")
        self.assertEqual(d2["tool_bindings"]["query"]["capability"], "mcp.analytics.query")

    def test_remote_mcp_transport_raises_unsupported_error(self):
        with self.assertRaises(CLIError) as ctx:
            run_create_mcp_policy_wizard(
                url="https://example.com/mcp",
                transport="remote-http",
                access_md_file=self.md_file,
                output_json_file=self.json_file,
                config_output_file=self.config_file,
                non_interactive=True,
            )
        self.assertIn("Unsupported MCP transport type 'remote-http'", str(ctx.exception))

    def test_protect_mcp_alias_normalizes_to_create_mcp_policy(self):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            code = main(["protect-mcp", "--help"])
        self.assertEqual(code, 0)
        self.assertIn("create-mcp-policy", buf.getvalue())

    def test_main_create_mcp_usage_error(self):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            code = main_create_mcp(["--invalid-flag"])
        self.assertEqual(code, 2)
