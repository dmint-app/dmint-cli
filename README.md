# dmint-cli

`dmint-cli` provides command-line tools for Dmint policy creation (`dmint create-policy`) and compilation (`dmint compile-policy`).

## Installation

```bash
pip install dmint-cli
```

## Usage

```bash
# Interactive wizard to discover tools and create policy
dmint create-policy --tools sqlite_server.py -f access.md -o policy.json

# Compile natural language requirements into policy JSON
dmint compile-policy -f access.md -o policy.json
```
