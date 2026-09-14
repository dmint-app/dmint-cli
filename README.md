# dmint-cli (v0.2.0)

> **Developer tooling for interactive creation, compilation, and validation of Dmint security policies.**

`dmint-cli` provides command-line utilities for discovering tools via static AST analysis, interactive multi-turn policy authoring via LLM model selection and clarification loops, and deterministic schema/semantic policy verification (`policy.json`).

```text
access.md (Human Security Intent)
       ↓
dmint create-policy (Multi-turn Wizard & Model Discovery)
       ↓
Self-Correcting LLM Loop (clarification_needed / policy_ready)
       ↓
Dmint Core Validation (Policy.from_mapping)
       ↓
dmint verify-policy (Pure Deterministic Verification)
       ↓
policy.json (Authoritative Policy)
```

> **Note:** The CLI helps developers *author* and *validate* policies during development. `dmint` core remains the sole trusted runtime authorization engine.

---

## Installation

```bash
pip install dmint-cli
```

---

## CLI Commands

### 1. Interactive Policy Wizard (`dmint create-policy`)

Interactive, multi-turn wizard to create and validate a Dmint policy:
- Interactive provider and model discovery (`list_models`).
- AST-based static tool discovery via `--tools` parameter.
- Multi-turn envelope output contract (`clarification_needed` & `policy_ready`).
- Self-correcting validation retry loop on `PolicyError`.
- Atomic file write and immediate verification.

```bash
dmint create-policy -f access.md -o policy.json --tools my_tools.py
```

### 2. Standalone Policy Verification (`dmint verify-policy`)

Pure, deterministic schema and semantic validation of `policy.json` without LLM involvement. Returns exit code `0` on success or non-zero on validation failure:

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

## Testing

Run the CLI test suite:

```bash
python3 -m unittest discover -s tests -p "test_*.py"
```

---

## License

Licensed under the [Apache License, Version 2.0](LICENSE).
See the [`LICENSE`](LICENSE) file for the complete license text.
