# Dmint CLI — AGENTS.md

## 1. Mission

This repository owns the public `dmint` command-line interface.

The CLI has three primary responsibilities:

```text
dmint
│
├── create-policy
│     ├── external MCP mode
│     └── local tool/source mode
│
├── create-mcp-policy
│     └── existing MCP server
│           ↓
│       discover tools
│           ↓
│       generate/validate policy
│           ↓
│       generate MCP proxy configuration/code
│
└── verify-policy
      └── deterministic policy validation
```

This is the authoritative CLI architecture.

Do not collapse these responsibilities into one command.

The CLI is a developer-facing authoring/configuration layer.

The trusted runtime authorization engine remains the `dmint` core package.

---

# 2. Dmint Protects Two Classes of Tools

Dmint exists to protect both:

## A. External MCP tools

The developer already has an MCP server.

```text
AI Agent / MCP Client
        ↓
Dmint MCP Proxy
        ↓
Dmint deterministic enforcement
        ↓
Existing MCP Server
        ↓
Tool
```

The MCP server is the source of truth for available tools.

Tool discovery happens through MCP protocol discovery.

Do not require local Python source files for this mode.

## B. Developer-owned local tools

The developer owns the tool implementation.

```text
Developer source
      ↓
Static AST discovery
      ↓
Tool/action metadata
      ↓
Dmint policy
      ↓
Dmint enforcement
      ↓
Actual tool execution
```

Source inspection is allowed only because the developer explicitly provides the
source.

Never execute user source code merely to discover tools.

---

# 3. CORE DESIGN PRINCIPLE

Never assume every Dmint-protected capability is a Python source file.

There are two first-class discovery models:

```text
External MCP
    source of truth = actual MCP server tools/list

Local tools
    source of truth = static inspection of developer-provided source
```

Both must converge into the same deterministic authorization model:

```text
ToolRequest
    ↓
Dmint Policy
    ↓
ALLOW / DENY / APPROVAL_REQUIRED
```

Do not create two different policy engines.

Do not create two different authorization semantics.

---

# 4. COMMAND SURFACE

The public CLI should expose:

```text
dmint create-policy
dmint create-mcp-policy
dmint verify-policy
```

These commands have different responsibilities.

## create-policy

Creates a policy from either:

```text
external MCP
local tools/source
```

depending on the selected mode.

## create-mcp-policy

Creates the policy/configuration/proxy setup needed to protect an existing
external MCP server.

The command name intentionally describes what it does:

```text
create MCP protection policy/configuration
```

It does not mean the command itself is the long-running authorization proxy.

## verify-policy

Pure deterministic policy validation.

No LLM.

No network.

No MCP.

---

# 5. COMMAND 1 — `dmint create-policy`

Purpose:

```text
Create a validated Dmint policy from developer requirements.
```

Normal interactive entry:

```bash
dmint create-policy
```

The wizard should ask:

```text
What are you protecting?

1. External MCP server
2. Local tools/source
```

The interactive workflow is the primary UX.

Do not force users to understand internal implementation details just to create
a policy.

---

# 6. `create-policy` — EXTERNAL MCP MODE

When the user selects:

```text
1. External MCP server
```

the workflow is:

```text
MCP connection/configuration
        ↓
connect
        ↓
initialize
        ↓
tools/list
        ↓
display discovered tools
        ↓
read developer requirements
        ↓
policy authoring
        ↓
clarification loop
        ↓
Policy.from_mapping()
        ↓
human confirmation
        ↓
atomic write
        ↓
verify
```

The CLI must use the actual MCP integration/API available in the current
repository/ecosystem.

Do not implement a second MCP protocol stack.

---

# 7. `create-policy` — LOCAL TOOL MODE

When the user selects:

```text
2. Local tools/source
```

ask for source paths.

Accept:

```text
single Python file
directory
multiple files/directories
```

Examples:

```text
tools/
```

```text
tools/github.py, tools/database.py
```

The current `--tools` option may remain as an advanced/backward-compatible
interface if already supported, but the interactive wizard must not depend on
the user knowing it.

---

# 8. LOCAL TOOL DISCOVERY

Local tool discovery must be static.

Allowed:

```python
ast.parse(...)
```

Never use these merely for discovery:

```python
exec(...)
eval(...)
importlib.import_module(...)
subprocess(...)
```

Do not import the developer's tool module just to discover declarations.

Inspect and reuse the current AST discovery implementation, including:

```text
parse_tool_declarations_ast()
```

or its actual current equivalent.

Do not invent new declaration semantics unless explicitly requested.

---

# 9. LOCAL TOOL DISCOVERY UX

Show what was discovered:

```text
Scanning tool source...

✓ tools/github.py
  github.get_repository
  github.create_issue
  github.delete_repository

✓ tools/database.py
  database.query
  database.delete

Discovered 5 tool/action declarations.
```

If none are found:

```text
No supported tool declarations were discovered.
```

Do not invent tool names.

Invalid paths should produce clear errors and allow correction in interactive
mode.

One bad path must not unnecessarily crash the whole wizard.

---

# 10. REQUIREMENTS FILE

Both modes require developer intent.

Example:

```text
Access requirements file:
> access.md
```

Reuse the existing input-file validation, size limits, and
`InputFileError` behavior where applicable.

Never execute requirements files.

Treat requirements as untrusted authoring input.

---

# 11. AUTHORING CONTEXT

Policy authoring should receive:

```text
developer requirements
+
discovered tools/capabilities
```

For MCP mode:

```text
tool name
description
input schema
metadata
```

For local mode:

```text
discovered tool/action declarations
```

Discovered tool information is context/evidence.

It is not authorization.

The deterministic policy engine remains authoritative.

---

# 12. PROVIDER + MODEL

Preserve the current provider architecture.

Supported providers may include:

```text
openai
gemini
groq
openrouter
ollama
custom
```

Inspect the current `api.py` before changing provider behavior.

Preserve environment-variable API-key resolution.

Examples:

```text
OPENAI_API_KEY
GEMINI_API_KEY
GROQ_API_KEY
```

Never print API keys.

Mask secrets in interactive terminal output.

---

# 13. MODEL DISCOVERY

Use the current `list_models()` implementation if present.

Expected endpoint:

```text
GET {base_url}/models
```

with the same authorization mechanism as chat completion.

Expected response:

```json
{
  "data": [{ "id": "model-a" }, { "id": "model-b" }]
}
```

Show a numbered list.

Allow:

```text
select by number
OR
enter model ID manually
```

If model discovery fails:

```text
Model discovery is unavailable for this provider.
Enter the model ID manually.
```

Do not crash.

Do not silently select an arbitrary model.

---

# 14. POLICY AUTHORING PROMPT

The authoring system prompt should be bundled inside `dmint-cli`.

Preferred resource:

```text
src/dmint_cli/prompts/policy_skill.md
```

Runtime policy authoring must not depend on a separately installed
`dmint-skills` package solely to obtain the prompt.

The prompt must ship in:

```text
wheel
sdist
```

Verify this with a clean package installation.

The prompt is authoring guidance.

It is not trusted authorization logic.

---

# 15. MODEL OUTPUT CONTRACT

The authoring model must return exactly one JSON object.

Allowed form:

```json
{
  "type": "clarification_needed",
  "questions": ["..."]
}
```

or:

```json
{
  "type": "policy_ready",
  "rules": [
    {
      "effect": "allow",
      "tool": "...",
      "action": "..."
    }
  ]
}
```

No markdown fences.

No prose around the object.

No arbitrary metadata.

Malformed output enters a bounded retry path.

Never execute model output as code.

---

# 16. MULTI-TURN CLARIFICATION

When the model returns:

```text
clarification_needed
```

the CLI must:

1. display the questions
2. collect the user's answers
3. append answers as a new user turn
4. preserve conversation history
5. send the conversation again

Example:

```text
Dmint needs clarification:

1. Which environment may this action target?

> production only

2. Should database deletion ever be permitted?

> never
```

Do not restart the conversation after clarification.

---

# 17. DETERMINISTIC POLICY VALIDATION

When the model returns:

```text
policy_ready
```

construct:

```json
{
  "rules": [...]
}
```

Then validate using the authoritative core API:

```python
Policy.from_mapping(...)
```

Do not duplicate policy validation in this repository.

Do not silently modify generated policy rules.

---

# 18. SELF-CORRECTING VALIDATION

If `Policy.from_mapping()` raises `PolicyError`:

send the exact error into the same authoring conversation.

Example:

```text
Dmint validation failed:

<exact error>

Fix only the issue identified by the validator and resend the complete
policy_ready JSON.
```

Use a bounded correction count.

For example:

```text
maximum corrections = 4
```

If exhausted:

- print the final error
- print the relevant final model output
- exit non-zero
- do not write invalid policy

Never generate a fallback permission set.

---

# 19. NO OFFLINE POLICY FALLBACK

Do not use hardcoded string matching or heuristic policy generation when the
LLM/API fails.

If:

```text
API unavailable
API key invalid
provider unavailable
model unavailable
```

then:

```text
fail clearly
```

Do not generate a plausible-looking fake policy.

Security configuration must not silently degrade.

---

# 20. HUMAN CONFIRMATION

After deterministic validation:

show a concise rule summary.

Example:

```text
Policy validated.

1. ALLOW                github.get_repository       resource=*
2. ALLOW                github.create_issue         resource=*
3. DENY                 github.delete_repository    resource=*
4. APPROVAL_REQUIRED   deployment.deploy           resource=production
```

Then require explicit confirmation:

```text
Write policy to policy.json? [y/N]
```

Do not overwrite a valid policy without confirmation unless an explicit
non-interactive/yes option already exists.

---

# 21. ATOMIC WRITE

Reuse the current atomic write implementation.

Security invariant:

```text
invalid policy
    ↓
MUST NOT replace existing valid policy
```

Only write after:

```text
model output
    ↓
deterministic validation
    ↓
human confirmation
```

---

# 22. POST-WRITE VERIFICATION

After writing `policy.json`, perform the same deterministic validation used by:

```text
dmint verify-policy
```

Final sequence:

```text
generate
    ↓
validate
    ↓
confirm
    ↓
atomic write
    ↓
read file
    ↓
Policy.from_mapping()
    ↓
success
```

Do not report success if post-write verification fails.

---

# 23. COMMAND 2 — `dmint create-mcp-policy`

## Purpose

This command is specifically for protecting an existing external MCP server.

It creates the artifacts needed to put Dmint in front of that server.

Expected conceptual workflow:

```text
Existing MCP Server
        ↓
create-mcp-policy
        ↓
discover tools
        ↓
collect security requirements
        ↓
generate policy
        ↓
validate policy
        ↓
confirm
        ↓
generate MCP protection configuration/proxy artifact
```

The key output should be clear and useful.

For example:

```text
✓ policy.json
✓ dmint MCP proxy configuration
✓ discovered tool bindings
```

The exact output format must follow the current `dmint-mcp` package architecture.

Do not invent a new proxy runtime inside `dmint-cli`.

---

# 24. IMPORTANT: PROXY GENERATION

`create-mcp-policy` is allowed to CREATE/CONFIGURE the protection setup.

It must NOT duplicate the MCP proxy implementation.

The proxy runtime belongs to:

```text
dmint-mcp
```

The CLI is responsible for:

```text
configuration
authoring
validation
orchestration
artifact generation
```

The MCP package is responsible for:

```text
MCP protocol
downstream connection
tools/list
tools/call
enforcement gate
approval workflow
retry
```

---

# 25. CREATE-MCP-POLICY UX

Preferred interactive flow:

```text
$ dmint create-mcp-policy

Dmint MCP Policy Wizard

MCP server connection:
> ...

Connecting...

Discovering tools...

✓ github.get_repository
✓ github.create_issue
✓ github.delete_repository
✓ database.query
✓ database.delete

Requirements file:
> access.md

Provider:
> openai

Model:
> [model selection]

Generating policy...

Dmint validation passed.

Write policy? [y/N]

✓ policy.json created
✓ MCP protection configuration created
```

The exact UX may evolve, but it must remain understandable to a developer who
already has an MCP server.

---

# 26. CREATE-MCP-POLICY MUST NOT MEAN "RUN THE PROXY"

Creating protection configuration and running protection are different
responsibilities.

The command should create the required policy/configuration/proxy artifact.

The actual long-running MCP proxy execution belongs to the `dmint-mcp`
runtime/package.

Do not turn `create-mcp-policy` into a permanent daemon by default.

If the current CLI later gains an explicit run/start command, it must be a
separate deliberate command.

---

# 27. MCP DISCOVERY IS NOT AUTHORIZATION

`tools/list` tells the CLI/proxy:

```text
what tools exist
```

It does NOT decide:

```text
what the agent may execute
```

Every actual `tools/call` must pass Dmint enforcement.

Hiding a tool from discovery is not sufficient security.

---

# 28. MCP EXECUTION MODEL

Runtime protection must remain:

```text
MCP Client
    ↓
Dmint MCP Proxy
    ↓
Dmint policy evaluation
    ├── ALLOW → downstream call
    ├── DENY → zero downstream call
    └── APPROVAL_REQUIRED
             ↓
         persist exact request
             ↓
         return immediately
             ↓
         trusted approval
             ↓
         exact retry
             ↓
         verify current policy
             ↓
         atomically consume
             ↓
         downstream call
```

Never execute first and inspect afterward.

---

# 29. APPROVAL MODEL

Approval applies to a specific AI-agent action.

An approval is not generic permission to use a tool.

Exact request binding includes relevant:

```text
request ID
principal
integration
capability
tool
action
resource
canonical arguments
trusted context
fingerprint
policy provenance
expiry
approval credential
```

Example:

```text
Approved:
    deploy payments v2 production

Attempt:
    deploy payments v3 production

Result:
    REQUEST_MISMATCH
```

Consumed approvals must not be replayable.

---

# 30. LOCAL TOOLS VS MCP — KEEP THEM DISTINCT

Never combine these discovery mechanisms into one ambiguous implementation.

External MCP:

```text
connection
    ↓
MCP initialize
    ↓
tools/list
```

Local tools:

```text
source path
    ↓
read source
    ↓
AST parse
```

Both produce tool metadata.

Both eventually use the same Dmint policy engine.

---

# 31. SECURITY BOUNDARY

Dmint only protects capability paths that actually pass through Dmint.

Local tools:

```text
tool
 ↓
Dmint runtime
 ↓
execution
```

External MCP:

```text
AI client
 ↓
Dmint proxy
 ↓
MCP server
```

If the agent has another path such as:

```text
raw credentials
direct MCP endpoint
shell
Docker socket
raw database access
original callable
```

that path may bypass Dmint.

Never claim otherwise in CLI output, README, examples, or documentation.

---

# 32. POLICY SCHEMA

The CLI must consume the authoritative policy schema from the `dmint` package.

Do not create a parallel schema.

Core concepts:

```text
effect:
    allow
    deny
    approval_required

tool
action
resource
agent_id
conditions
```

Condition operators:

```text
equals
notEquals
in
contains
startsWith
endsWith
```

Precedence:

```text
DENY
  >
APPROVAL_REQUIRED
  >
ALLOW
```

Unmatched requests are denied.

Resource semantics distinguish:

```text
NO_RESOURCE
ANY_RESOURCE
EXACT_RESOURCE
```

---

# 33. PROMPT INJECTION / UNTRUSTED INPUT

Treat as untrusted:

```text
access.md
policy.md
MCP tool descriptions
MCP schemas
local source comments/docstrings
model output
interactive free text
```

Never execute them.

Never allow an LLM to modify trusted runtime authorization semantics.

The LLM is an authoring assistant.

Dmint core is the runtime authority.

---

# 34. TEST REQUIREMENTS

Inspect the current test suite before editing.

Preserve valuable existing security tests.

Required coverage:

## create-policy

- external MCP mode selected
- local tools mode selected
- requirements file
- provider selection
- model discovery
- model discovery fallback
- manual model selection
- clarification loop
- policy validation
- correction retry
- correction retry exhaustion
- explicit confirmation
- atomic write
- final verification

## MCP policy mode

- MCP connection
- MCP initialization
- tool discovery
- discovered tool context
- MCP failure path
- no invented tools
- policy generation
- validation
- output artifact/configuration generation

## Local tools

- single file
- multiple files
- directory
- invalid path
- no declarations
- multiple declarations
- supported declaration patterns
- AST-only discovery
- malicious source never executed

## verify-policy

- valid policy
- invalid policy
- malformed JSON
- missing file
- correct exit codes
- no LLM
- no network

## Security

- no offline policy fallback
- invalid model output never becomes executable code
- invalid policy never replaces valid policy
- API keys never leak
- source inspection never executes source
- MCP discovery never becomes authorization
- hidden tools are not treated as authorization

---

# 35. STATIC DISCOVERY SECURITY TEST

Create/retain a test proving that local tool source containing executable side
effects is never run.

For example:

```python
raise RuntimeError("THIS MUST NEVER EXECUTE")
```

AST inspection must remain safe.

Do not weaken this test.

---

# 36. PACKAGE VERIFICATION

Build:

```bash
python -m build
```

Install the generated wheel into a clean virtual environment.

Verify:

```text
dmint command starts
create-policy works
create-mcp-policy is registered
verify-policy works
bundled prompt exists
dmint-skills is not required merely to load the prompt
```

Do not rely solely on editable installs.

---

# 37. GENERATED FILES

Do not commit:

```text
build/
dist/
*.egg-info/
__pycache__/
*.pyc
.pytest_cache/
.venv/
venv/
.env
```

Use `.gitignore`.

---

# 38. README

README must clearly document:

```text
dmint create-policy
dmint create-mcp-policy
dmint verify-policy
```

Explain:

```text
create-policy
    Create a policy for either external MCP tools or local tools.

create-mcp-policy
    Discover an existing MCP server, create its Dmint policy, and generate
    the protection configuration/proxy artifact.

verify-policy
    Pure deterministic policy validation.
```

Provide quickstart examples for both tool types.

Do not document old `protect-mcp` as the primary command once the rename is
implemented.

If backwards compatibility is intentionally retained, clearly label it.

---

# 39. COMMAND RENAMING

The old command:

```text
protect-mcp
```

is renamed to:

```text
create-mcp-policy
```

Update:

```text
CLI command registration
README
help text
tests
examples
documentation strings
error messages
completion/help metadata
```

Search the entire repository for stale references:

```bash
grep -R "protect-mcp" -n src tests README.md . 2>/dev/null || true
```

Do not leave accidental stale public references.

If compatibility aliasing is desired, it must be explicit and tested.

Do not silently retain two competing conceptual meanings.

---

# 40. CURRENT CODE IS AUTHORITATIVE

Before changing anything:

1. inspect current source
2. inspect current tests
3. inspect current Git history
4. inspect current `origin/main`
5. understand what is already implemented
6. preserve correct code
7. change only what is required
8. add regression tests

Do not blindly apply an old Claude/Copilot specification.

Specifications describe intent.

Current implementation + current tests + Dmint core API are authoritative.

---

# 41. GIT SAFETY

Before making changes:

```bash
git status
git log --oneline -10
git branch -vv
git remote -v
git fetch origin
git status
git log --oneline HEAD..origin/main
```

Do not:

```text
force reset
force push
discard user work
rewrite history
push automatically
```

Inspect differences before integrating remote changes.

---

# 42. VERIFICATION

Before finishing:

```bash
python3 -m unittest discover -s tests -p "test_*.py"
python -m build
```

Also run a clean wheel-install test.

Report the actual test count.

Do not claim historical test counts as current.

---

# 43. FINAL ARCHITECTURE

The intended architecture is:

```text
                         Dmint CLI
                            │
             ┌──────────────┼──────────────┐
             │              │              │
     create-policy   create-mcp-policy  verify-policy
             │              │              │
       ┌─────┴─────┐        │        deterministic
       │           │        │          validation
      MCP      Local tools  │
       │           │        │
   MCP discovery  AST       │
       │           │        │
       └─────┬─────┘        │
             │              │
             └──────┬───────┘
                    │
               policy.json
                    │
             deterministic Dmint
                authorization
                    │
         ┌──────────┼──────────┐
         │          │          │
       ALLOW      DENY    APPROVAL_REQUIRED
         │          │          │
      execute     stop     persist/approve
```

For external MCP:

```text
AI Agent
   ↓
Dmint MCP Proxy
   ↓
Dmint Core
   ↓
External MCP Server
   ↓
Tool
```

For local tools:

```text
AI Agent / Application
   ↓
Dmint enforcement
   ↓
Developer-owned Tool
```

For authoring:

```text
Requirements
   +
Tool discovery
   ↓
LLM authoring
   ↓
Policy.from_mapping()
   ↓
Human confirmation
   ↓
policy.json
```

---

# 44. FINAL PRODUCT PRINCIPLE

Dmint is not merely:

```text
an MCP security tool
```

and not merely:

```text
a Python decorator
```

Dmint is a deterministic authorization/enforcement layer that can protect:

```text
1. external MCP capabilities
2. developer-owned local capabilities
```

The CLI must make both paths first-class.

`create-policy` is for policy authoring.

`create-mcp-policy` is for turning an existing MCP server into a Dmint-protected
integration/configuration.

`verify-policy` is for deterministic policy validation.

The execution/security semantics remain owned by Dmint Core and Dmint MCP.
