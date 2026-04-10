# BISHOP Use Cases

This document explains where BISHOP is strongest today and how a team can use it in real workflows.

## What BISHOP Is Best At

BISHOP is strongest when you want:

- real local execution instead of black-box hosted agent runs
- Slack-native task intake
- visible terminal sessions
- a human-in-the-loop workflow
- a lightweight control plane over existing AI CLIs
- durable local memory without heavy infrastructure

It is not trying to be a giant all-in-one agent platform. It is an operator layer for practical work.

## Primary Team Use Cases

### Engineering Triage

Use BISHOP to:

- inspect bugs from Slack
- trace failing listeners, workers, or queue jobs
- analyze repo structure
- run targeted code fixes
- summarize what changed back to the team

Example:

```text
/cli inspect the failing Slack reply path and patch the routing bug
```

Why BISHOP fits:

- the work happens in a real terminal
- output streams back into Slack
- a teammate can reply in-thread to steer the run

### Repo Operations

Use BISHOP to:

- inspect Git state
- check recent commits
- summarize changes
- prepare code modifications
- validate local files before merge or release

Example:

```text
/codex inspect the latest changes in the dashboard shell and summarize the risks
```

### Local Ops Automation

Use BISHOP to:

- check service state
- inspect logs
- verify environment config
- troubleshoot local launch problems
- run agent-assisted operational tasks against the machine where the stack lives

Example:

```text
/cli figure out why the local worker is not consuming jobs
```

### Slack-Based Human-in-the-Loop Sessions

BISHOP is especially good when the operator needs to guide the run as it unfolds.

Flow:

1. Start a session from Slack.
2. Watch output in the thread.
3. Reply if the agent needs direction or additional context.
4. Keep the entire session narrative in one place.

This is much more usable for teams than a one-shot fire-and-forget workflow.

### Dashboard-Guided Operator Control

The dashboard is useful when the operator wants:

- a session list
- output tails
- logs
- memory visibility
- queue visibility
- a local UI for triggering the same flows Slack uses

This is useful for:

- demos
- operator oversight
- debugging long-running sessions
- fast follow-up control without leaving the workstation

### Durable Memory and Context

Use BISHOP when the work benefits from keeping local operational memory around:

- known paths
- session history
- durable notes
- persistent instructions in `vibes.md`
- project route maps in `vibes-full.md`

This works well for teams that revisit the same systems repeatedly.

### Multi-System Local Awareness

BISHOP can help when work spans:

- the current repo
- Gemini skills
- shared agent skills
- Hermes files
- OpenClaw files
- session logs and memory stores

This is useful when a prompt needs to reason across several local systems instead of only one repo.

## Good Fit Scenarios

BISHOP is a good fit when:

- the team already works heavily in Slack
- engineers are comfortable with terminals
- local files and credentials matter
- visibility is more important than abstraction
- cost control matters
- you want to extend behavior incrementally

## Less Ideal Scenarios

BISHOP is less ideal when:

- you need a fully managed hosted SaaS product
- you need centralized enterprise orchestration across many remote workers immediately
- you want zero local-machine dependency
- your workflow depends on hiding all terminal details from operators

That does not mean BISHOP cannot grow in those directions. It means that is not the current design center.

## High-Value Internal Use Cases

For your team specifically, the strongest internal use cases are likely:

- engineering debugging from Slack
- local service operations
- repo inspection and patching
- dashboard-driven live session control
- MCP-assisted project workflows
- AI-assisted work that needs real local context

## Why Teams Understand It Quickly

BISHOP is easy to explain because the workflow is familiar:

- Slack receives the request
- the worker launches the job
- Terminal runs the work
- the dashboard shows the state
- SQLite and context files keep the memory

That makes it easier to adopt than a more abstract agent stack.

## Suggested Positioning

If you are describing BISHOP to the team, a strong framing is:

> BISHOP is our lightweight local-first operator system. It turns Slack and a dashboard into a control plane for real terminal-based AI work, with thread continuation, durable context, and lower cost than heavy hosted agent platforms.
