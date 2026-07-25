# Kilonova MCP

<!-- mcp-name: io.github.MilnaOS/kilonova-mcp -->

**Persistent knowledge base tools for Claude Code.**  
Claude remembers your projects, decisions, and patterns across sessions — stored on your machine, no cloud required.

Built by [AIM Studio](https://aimstudio.app) · Free · MIT License

---

## The Problem

Every Claude Code session starts cold. You re-explain your project structure, re-describe decisions you made last week, re-state what's in flight. Context burns fast.

## The Solution: DOT + KB

Kilonova gives Claude a persistent knowledge base on your local machine. At session start, Claude loads your **DOT** (Document of Truth) — a compressed, structured reference doc with your project state, active tasks, decisions, and patterns. During the session, Claude writes new discoveries back to the KB. Next session, it's all there.

```
Session 1: Claude learns your architecture → kb_write saves the decision
Session 2: dot_load → Claude already knows. No recap needed.
```

---

## Install

```bash
pip install kilonova-mcp
```

Or from source:
```bash
git clone https://github.com/MilnaOS/kilonova-mcp
cd kilonova-mcp
pip install -e .
```

## Wire Up Claude Code

Add to `~/.claude/settings.json`:

```json
{
  "mcpServers": {
    "kilonova": {
      "command": "python",
      "args": ["-m", "kilonova_mcp"],
      "env": {
        "KILONOVA_KB_ROOT": "/path/to/your/kb"
      }
    }
  }
}
```

Copy `CLAUDE.md.template` to `~/.claude/CLAUDE.md` (or append to your existing one).

## Quick Start

**1. Create your first KB topic:**

In Claude Code, just start writing:
```
mcp__kilonova__kb_write(
  topic="claude_context",
  entity_type="project_state",
  name="my-project",
  data={
    "name": "my-project",
    "status": "active",
    "location": "/path/to/project",
    "summary": "What this project is",
    "next_action": "What to do next"
  }
)
```

**2. Load it next session:**
```
mcp__kilonova__dot_load(topic="claude_context")
```

**3. Search it:**
```
mcp__kilonova__kb_search(topic="claude_context", query="authentication decision")
```

---

## The DOT Format

A DOT is a plain text file with three sections:

```
---SYMBOLS---
[PR]=My Project (/path/to/project)
[DB]=Database (PostgreSQL on localhost:5432)

---TOC---
1:Projects|1.1:My_Project
2:Active_Tasks
3:Decisions

---CARDS---

## [1] PROJECTS
### [1.1] My Project
STATUS: active
NEXT: wire up the auth flow
```

Symbols compress repeated references. The TOC lets Claude fetch only the section it needs. Cards hold the actual content.

See `example_dot/` for a starter template.

---

## Starter Schema: `claude_context`

Copy `schemas/claude_context/` into your KB directory under `<kb_root>/claude_context/schemas/`:

| Entity type | Use for |
|---|---|
| `project_state` | Current status, location, next action per project |
| `decision` | Architectural choices with rationale |
| `pattern` | Code conventions, gotchas, file locations |
| `active_task` | In-flight work across sessions |
| `session_note` | End-of-session summaries |

---

## Tools

| Tool | Description |
|---|---|
| `dot_load(topic)` | Load full DOT document into context |
| `kb_search(topic, query)` | Search records by natural language query |
| `kb_write(topic, entity_type, name, data)` | Write/update a record (merges with existing) |
| `kb_load(topic, entity_type, name)` | Load one specific record |
| `kb_topics()` | List all KB topics and record counts |
| `kb_schema(topic, entity_type?)` | Show field schema for an entity type |
| `corpus_status(topic)` | Show KB size and record counts |
| `kb_backup(dry?)` | Mirror KB to OneDrive |

---

## Bring Your Own KB

Kilonova doesn't care what you store. Define your own schemas:

```json
// kb/my_topic/schemas/component.json
{
  "name": {"type": "string", "description": "Component name"},
  "file": {"type": "string", "description": "Path to file"},
  "purpose": {"type": "string", "description": "What it does"},
  "dependencies": {"type": "array", "description": "What it depends on"}
}
```

Then write records to it and search them naturally.

---

## Part of the Kilonova Ecosystem

Kilonova MCP is the free, standalone KB layer extracted from **Milna OS** — a full BYOK multi-model AI terminal. If you want the whole thing (parallel model legs, distillation engine, web ingestion, local+cloud hybrid inference), check out [Milna OS](https://aimstudio.app).

---

MIT License · © AIM Studio
