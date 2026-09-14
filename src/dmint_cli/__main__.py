"""Entry point for dmint CLI command."""

from __future__ import annotations

import argparse
import sys

from dmint_cli.compile_policy import main_compile
from dmint_cli.create_policy import main_create
from dmint_cli.verify_policy import main_verify


def main(args: list[str] | None = None) -> int:
    if args is None:
        args = sys.argv[1:]

    # Normalize two-word subcommands: "create policy" -> "create-policy", "verify policy" -> "verify-policy", etc.
    normalized_args: list[str] = []
    i = 0
    while i < len(args):
        arg = args[i]
        if arg == "create" and i + 1 < len(args) and args[i + 1] == "policy":
            normalized_args.append("create-policy")
            i += 2
            continue
        if arg == "verify" and i + 1 < len(args) and args[i + 1] == "policy":
            normalized_args.append("verify-policy")
            i += 2
            continue
        if arg == "compile" and i + 1 < len(args) and args[i + 1] == "policy":
            normalized_args.append("compile-policy")
            i += 2
            continue
        normalized_args.append(arg)
        i += 1

    parser = argparse.ArgumentParser(
        prog="dmint",
        description="Dmint deterministic security enforcement & policy authoring CLI.",
    )
    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    subparsers.add_parser(
        "create-policy",
        help="Interactive wizard to create and validate Dmint policy files",
        add_help=False,
    )
    subparsers.add_parser(
        "verify-policy",
        help="Verify a policy.json file against Dmint schema and semantic invariants",
        add_help=False,
    )
    subparsers.add_parser(
        "compile-policy",
        help="Compile natural language policy requirements into a validated policy.json file",
        add_help=False,
    )

    if not normalized_args or normalized_args[0] in ("-h", "--help"):
        parser.print_help()
        return 0

    cmd = normalized_args[0]
    cmd_args = normalized_args[1:]

    if cmd == "create-policy":
        return main_create(cmd_args)
    elif cmd == "verify-policy":
        return main_verify(cmd_args)
    elif cmd == "compile-policy":
        return main_compile(cmd_args)
    else:
        parser.print_help()
        return 2


if __name__ == "__main__":
    sys.exit(main())
