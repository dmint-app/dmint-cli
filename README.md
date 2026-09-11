# dmint-cli

> **Developer tooling for creating, compiling, and validating Dmint security policies.**

`dmint-cli` provides command-line utilities for discovering tools via AST analysis, gathering security requirements, and compiling natural language security rules into schema-compliant Dmint policy files (`policy.json`).

```text
access.md (Human Security Intent)
       ↓
dmint compile-policy / create-policy
       ↓
LLM Compiler & Dmint Skill
       ↓
Dmint Core Validation (Policy.from_mapping)
       ↓
policy.json (Authoritative Policy)
```

> **Note:** The CLI helps developers *author* and *validate* policies during development. `dmint` core remains the sole trusted runtime authorization engine.

## Installation

```bash
pip install dmint-cli
```

## CLI Commands

### 1. Interactive Policy Wizard (`dmint create-policy`)

Inspect Python source code for tool declarations using AST analysis (zero execution), prompt the developer for security rules, and generate `access.md` + verified `policy.json`.

```bash
dmint create-policy --tools my_tools.py -f access.md -o policy.json
```

### 2. Policy Compiler (`dmint compile-policy`)

Compile natural language security requirements into a strictly validated `policy.json` file using an OpenAI-compatible API or local fallback parser.

```bash
dmint compile-policy -f access.md -o policy.json
```

## Environment Configuration

Set API credentials via environment variables for LLM policy compilation:

```bash
export OPENAI_API_KEY="sk-..."
# Optional custom provider / base URL
export DMINT_BASE_URL="https://api.openai.com/v1"
export DMINT_MODEL="gpt-4o-mini"
```

## Testing

Run the CLI test suite:

```bash
pytest -v
```

## License

Apache-2.0
