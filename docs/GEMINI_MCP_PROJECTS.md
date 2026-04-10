# Gemini MCP and Project Setup

This document explains how to connect MCP servers to specific projects using Gemini CLI, how that interacts with BISHOP, and how to structure project-level `.gemini` files so the agent can use the right tools from the right repo.

## Why This Matters

Gemini CLI can load MCP servers from:

- a global user config at `~/.gemini/settings.json`
- a project config at `.gemini/settings.json`

That gives you two useful patterns:

- global MCPs for tools you want available everywhere
- project MCPs for tools that only make sense inside a specific repo

For BISHOP, this is important because BISHOP launches Gemini from a project root. If that project contains a `.gemini/settings.json`, Gemini can load the MCPs defined there automatically.

BISHOP now also includes a local MCP integration layer:

- `config/mcp_registry.json` for curated placeholders and enable flags
- `agent-context/mcp_catalog_snapshot.json` for a synced search snapshot of the external BishopTech MCP catalog
- `./scripts/bishop_mcp.py` for init, sync, search, and `.gemini/settings.json` generation

## The Practical Rule

Use:

- `~/.gemini/settings.json` for universal tools you want across all work
- `.gemini/settings.json` for repo-specific tools, secrets, and integrations
- `GEMINI.md` for project instructions and behavioral guidance

That gives you a clean separation between global capability and project-local context.

## Official Gemini CLI Behavior

The current Gemini CLI docs state that:

- project settings live at `.gemini/settings.json`
- project settings override user settings
- `gemini mcp add` defaults to project scope
- untrusted folders ignore workspace settings, including project MCP config

Official references:

- [Gemini CLI configuration](https://geminicli.com/docs/reference/configuration/)
- [MCP servers with the Gemini CLI](https://geminicli.com/docs/tools/mcp-server/)
- [Trusted folders](https://geminicli.com/docs/cli/trusted-folders/)

## How BISHOP Uses This

BISHOP currently launches Gemini from the configured project root in [config.py](/Users/matthewbishop/BishopBot/config.py):

- `PROJECT_ROOT_DIR`

That means:

- if BISHOP starts Gemini inside a repo with `.gemini/settings.json`, Gemini can load those project MCP servers
- if that repo also has a `GEMINI.md`, Gemini can use those repo-specific instructions
- if you want BISHOP to operate in a different repo, point BISHOP at that repo or launch BISHOP from that repo context

In other words, BISHOP does not need to hardcode every MCP server itself. Gemini can load project-scoped MCPs natively.

For the BISHOP repo itself:

```bash
./scripts/bishop_mcp.py init
./scripts/bishop_mcp.py search github
./scripts/bishop_mcp.py build-gemini
```

Recommended flow:

1. sync the external MCP catalog repo into the local snapshot
2. curate the MCPs you actually want inside `config/mcp_registry.json`
3. only enable the entries that have a real command or URL
4. regenerate `.gemini/settings.json`

## Recommended Folder Pattern Per Project

For any repo where you want project-specific MCP behavior, use this layout:

```text
your-project/
├── .gemini/
│   └── settings.json
├── GEMINI.md
└── ...
```

Recommended meanings:

- `.gemini/settings.json`
  Project-specific MCP servers and Gemini settings
- `GEMINI.md`
  Project instructions, routes, conventions, and guardrails

## Best Practice Model

### Global User Scope

Put universal tools in `~/.gemini/settings.json`.

Examples:

- GitHub MCP you want everywhere
- Slack MCP you want everywhere
- a general filesystem or docs server

### Project Scope

Put repo-local tools in `.gemini/settings.json`.

Examples:

- a project-specific Postgres MCP
- an internal API MCP with project-specific base URL
- a local custom tool server shipped with that repo
- tools that rely on repo-local `.env` values or local scripts

### Project Guidance

Put project behavior and system instructions in `GEMINI.md`.

Examples:

- architecture guidance
- approved workflows
- directory map
- project conventions
- what not to touch

## Recommended Setup Flow

### Option A: Add MCP using the Gemini CLI

For a project-specific MCP:

```bash
cd /path/to/your-project
gemini mcp add --scope project github docker run -i --rm -e GITHUB_PERSONAL_ACCESS_TOKEN ghcr.io/github/github-mcp-server:latest
```

For a global MCP:

```bash
gemini mcp add --scope user github docker run -i --rm -e GITHUB_PERSONAL_ACCESS_TOKEN ghcr.io/github/github-mcp-server:latest
```

The official Gemini CLI docs say `gemini mcp add` writes to:

- `~/.gemini/settings.json` for user scope
- `.gemini/settings.json` for project scope

### Option B: Edit `.gemini/settings.json` manually

Example project-level file:

```json
{
  "mcpServers": {
    "github": {
      "command": "docker",
      "args": [
        "run",
        "-i",
        "--rm",
        "-e",
        "GITHUB_PERSONAL_ACCESS_TOKEN",
        "ghcr.io/github/github-mcp-server:latest"
      ],
      "env": {
        "GITHUB_PERSONAL_ACCESS_TOKEN": "${GITHUB_PERSONAL_ACCESS_TOKEN}"
      }
    }
  }
}
```

This is the same pattern shown in the Gemini CLI MCP docs: define the server under `mcpServers`, keep secrets in environment variables, and avoid hardcoding tokens in JSON.

## How To Verify It

Inside the project:

```bash
cd /path/to/your-project
gemini mcp list
```

If needed:

```bash
/mcp list
/mcp reload
```

What you want to see:

- the server is listed
- the server shows as connected
- Gemini can discover the tool naturally from a normal prompt

## Trusted Folder Requirement

This part matters.

Gemini CLI treats project MCP config as workspace settings. The official docs say untrusted folders ignore workspace settings. In practice, that means your project `.gemini/settings.json` may not load until the folder is trusted.

If a project MCP is not connecting:

1. confirm you are inside the correct repo
2. run `gemini mcp list`
3. trust the folder if needed using Gemini’s trust flow
4. reload the MCP config

## Recommended `GEMINI.md` Pattern

Use `GEMINI.md` for instructions, not secret config.

A good `GEMINI.md` usually contains:

- what the project is
- key directories
- how to run it
- key constraints
- what systems are safe to modify
- expected style or architecture

Example:

```md
# Project Context

## Purpose
- This project powers our internal dashboard and Slack operator workflows.

## Key Paths
- `app/`: Next.js app routes
- `services/`: backend orchestration logic
- `.gemini/settings.json`: project MCP config

## Rules
- Do not edit deployment config unless the task requires it.
- Prefer existing service abstractions over new ad hoc files.
- Run tests before summarizing code changes.
```

## Strong Pattern for Teams

The cleanest team model is:

### Global

- put company-wide MCPs in `~/.gemini/settings.json`
- keep those minimal

### Per Project

- put project-specific MCPs in `.gemini/settings.json`
- put project instructions in `GEMINI.md`
- keep secrets in environment variables, not in Git

### For BISHOP

- run BISHOP against the project root you want Gemini to operate inside
- let Gemini load the repo’s own `.gemini/settings.json`
- let `GEMINI.md` carry the project behavior

This is the easiest way to make MCP tools feel available “from anywhere” while still keeping the right tools attached to the right repo.

## Use Cases

This pattern is especially useful when:

- one repo needs GitHub + Postgres tools
- another repo needs Slack + internal API tools
- another repo needs a local MCP server shipped with the project itself

Instead of trying to put every tool into one giant global config, you keep each repo self-describing.

## Example Scenarios

### Scenario 1: GitHub Everywhere

Put GitHub MCP in `~/.gemini/settings.json`.

Result:

- any project can use GitHub tools

### Scenario 2: Project-Specific Internal API

Put your internal API MCP in `.gemini/settings.json` for that repo only.

Result:

- only that repo loads the internal API tools
- you avoid polluting every other project

### Scenario 3: Repo-Shipped MCP Server

If a repo includes its own local MCP server, point `.gemini/settings.json` at the repo-local command.

Result:

- the project becomes self-contained
- Gemini can use the tool whenever it is launched from that repo

## Suggested BISHOP Workflow

If you want BISHOP plus project MCPs to work cleanly:

1. configure `.gemini/settings.json` inside the target repo
2. create a `GEMINI.md` in that repo
3. make sure required environment variables exist
4. trust the folder in Gemini CLI
5. run BISHOP with that repo as the working project context

Then prompts like these work naturally:

```text
Use the project MCP tools to inspect the open PRs and summarize the deployment risk.
Use the internal API MCP to fetch the latest records and compare them to the local schema.
Use the Slack MCP in this repo to draft the rollout summary after you finish the patch.
```

## Bottom Line

The best way to think about this is:

- BISHOP provides the control plane
- Gemini provides the runtime
- `.gemini/settings.json` provides project-scoped tools
- `GEMINI.md` provides project-scoped instructions

That combination is what makes project-specific MCP usage practical and portable.
