"""Unit and security tests for interactive policy wizard (src/dmint/cli/create_policy.py)."""

import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from dmint_cli.create_policy import (
    main_create,
    parse_tool_declarations_ast,
    run_create_policy_wizard,
)
from dmint.policy import Policy


class PolicyCreateWizardTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.base_path = Path(self.temp_dir.name)
        self.md_file = self.base_path / "access.md"
        self.json_file = self.base_path / "policy.json"
        self.tool_file = self.base_path / "sqlite_server.py"
        self.tool_file.write_text(
            'types.Tool(name="read_data", description="Read records")\n'
            'types.Tool(name="delete_data", description="Delete records")\n',
            encoding="utf-8",
        )

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_ast_tool_discovery_is_static_and_safe(self):
        # Source file containing malicious executable code outside tool AST nodes
        malicious_tool = self.base_path / "malicious.py"
        malicious_tool.write_text(
            'types.Tool(name="read_data", description="Safe tool")\n'
            'raise RuntimeError("Code execution during import!")\n',
            encoding="utf-8",
        )

        # AST discovery MUST parse without triggering code execution (no RuntimeError raised)
        tools = parse_tool_declarations_ast(malicious_tool)
        self.assertEqual(len(tools), 1)
        self.assertEqual(tools[0]["name"], "read_data")

    @patch("dmint_cli.create_policy.compile_policy_file")
    def test_run_wizard_non_interactive_creates_files(self, mock_compile):
        mock_compile.return_value = Policy()

        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            policy = run_create_policy_wizard(
                tools_file=self.tool_file,
                access_md_file=self.md_file,
                output_json_file=self.json_file,
                api_key="sk-test",
                non_interactive=True,
                auto_confirm=True,
            )

        self.assertIsInstance(policy, Policy)
        self.assertTrue(self.md_file.exists())
        content = self.md_file.read_text()
        self.assertIn("read_data", content)
        self.assertIn("delete_data", content)

    @patch("dmint_cli.create_policy.compile_policy_file")
    def test_wizard_user_aborts_confirmation_does_not_write_final_json(self, mock_compile):
        mock_compile.return_value = Policy()

        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            with patch("sys.stdin.isatty", return_value=True), patch("builtins.input", return_value="n"):
                with self.assertRaises(Exception):
                    run_create_policy_wizard(
                        tools_file=self.tool_file,
                        access_md_file=self.md_file,
                        output_json_file=self.json_file,
                        api_key="sk-test",
                        non_interactive=False,
                        auto_confirm=False,
                    )

        # Final policy.json MUST NOT exist when user denies confirmation
        self.assertFalse(self.json_file.exists())

    def test_cli_main_create_usage_error(self):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            code = main_create([])
        self.assertEqual(code, 2)

