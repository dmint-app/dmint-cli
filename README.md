# dmint-cli (v0.3.0)

> **Developer tooling for interactive creation, compilation, and validation of Dmint security policies.**

`dmint-cli` provides command-line utilities for discovering capabilities via static AST analysis (local source) or stdio protocol (external MCP servers), multi-turn policy authoring via LLMs, and deterministic policy verification (`policy.json`).

```text
                             Dmint CLI
                                │
              ┌─────────────────┼─────────────────┐
              │                 │                 │
       create-policy     create-mcp-policy   verify-policy
              │                 │                 │
         ┌────┴────┐       MCP integrations   pure validation
         │         │             │
       Local      MCP            │
       tools      tools          │
         │         │             │
         │      ┌──┴─────────────┴───────┐
         │      │                        │
       AST     stdio/local           remote MCP
                │                        │
                └──────────┬─────────────┘
                           │
                      tools/list
                           │
                  discovered capabilities
                           │
                      policy authoring
                           │
                     Policy.from_mapping()
                           │
                       policy.json
                           │
                  Dmint MCP protection
```

> **Note:** The CLI helps developers *author* and *validate* policies during development. `dmint` core remains the sole trusted runtime authorization engine.

---

## Installation

```bash
pip install dmint-cli
```

---

## CLI Commands

### 1. General Policy Authoring Wizard (`dmint create-policy`)

Interactive wizard to create and validate a Dmint policy for local source code or external MCP tools:
- **Mode 1 (External MCP server)**: Connects to external MCP servers and discovers tools.
- **Mode 2 (Local tools/source)**: Safely inspects single/multiple Python files or directories via static AST analysis (`ast.parse()`, zero code execution).
- Multi-turn envelope output contract (`clarification_needed` & `policy_ready`).
- Self-correcting validation retry loop on `PolicyError`.

```bash
dmint create-policy -f access.md -o policy.json --tools tools/
```

### 2. Specialized MCP Policy & Protection Wizard (`dmint create-mcp-policy`)

Specialized wizard for existing external MCP servers:
- Supports single or multiple MCP servers (`stdio` transport).
- Discovers MCP tools over stdio protocol using the official MCP SDK.
- Preserves integration namespace (`mcp.{integration_id}.{tool_name}`) so `postgres.query != analytics.query`.
- Fails closed on unsupported remote transports (`remote-http` / `https://...`) as `dmint-mcp` runtime currently implements `stdio`.
- Generates `policy.json` and multi-integration protection configuration `mcp_protection.json`.

```bash
dmint create-mcp-policy --command mcp-server-postgres --args postgresql://localhost/opshub_db
```

*Note:* `protect-mcp` is supported as an explicit compatibility alias to `create-mcp-policy`.

### 3. Standalone Policy Verification (`dmint verify-policy`)

Pure, deterministic schema and semantic validation of `policy.json` without LLM, network, or MCP involvement. Returns exit code `0` on success or non-zero on validation failure:

```bash
dmint verify-policy policy.json
# or
dmint verify-policy -f policy.json
```

---

## Environment Configuration

Set API credentials via environment variables for LLM policy compilation:

```bash
export OPENAI_API_KEY="sk-..."
# Optional custom providers (openai, gemini, groq, openrouter, ollama)
export GEMINI_API_KEY="..."
export GROQ_API_KEY="..."
```

---

## Testing & Verification

Run the CLI test suite:

```bash
python3 -m unittest discover -s tests -p "test_*.py"
```

Build sdist and wheel:

```bash
python3 -m build
```

---

## License

Licensed under the [Apache License, Version 2.0](LICENSE).
See the [`LICENSE`](LICENSE) file for the complete license text.
