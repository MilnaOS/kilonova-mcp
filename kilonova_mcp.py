"""
kilonova_mcp.py — Kilonova MCP Server
Persistent knowledge base tools for Claude Code sessions.

Powered by Kilonova — https://aimstudio.app

Tools:
  kb_search(topic, query)                    — search entity records
  kb_load(topic, entity_type, name)          — load a specific record
  kb_write(topic, entity_type, name, data)   — write/update a record
  kb_topics()                                — list available KB topics
  kb_schema(topic, entity_type?)             — show field schema
  dot_load(topic)                            — load full DOT document
  corpus_status(topic)                       — scrape progress stats
  kb_backup(kb_only?, dry?)                  — mirror KB to OneDrive

Setup (Claude Code):
  Add to ~/.claude/settings.json:
  {
    "mcpServers": {
      "kilonova": {
        "command": "python",
        "args": ["path/to/kilonova_mcp.py"],
        "env": {"KILONOVA_KB_ROOT": "path/to/your/kb"}
      }
    }
  }

Then add to ~/.claude/CLAUDE.md:
  At session start, load your context DOT:
    mcp__kilonova__dot_load(topic="claude_context")
"""
import json
import os
import sys
from pathlib import Path

_HERE = Path(__file__).parent
sys.path.insert(0, str(_HERE))

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

from kilonova.tools.kb_search import search_kb

KB_ROOT = Path(os.environ.get('KILONOVA_KB_ROOT', _HERE / 'kb'))

server = Server('kilonova')


@server.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name='kb_search',
            description=(
                'Search a Kilonova knowledge base for records matching a query. '
                'Pass topic="claude_context" to search your session notes, decisions, and project state. '
                'Pass any other topic name for domain-specific KBs (game systems, research, codebases, etc.).'
            ),
            inputSchema={
                'type': 'object',
                'properties': {
                    'topic': {
                        'type': 'string',
                        'description': 'KB topic to search (e.g. "claude_context", "my_project")',
                    },
                    'query': {
                        'type': 'string',
                        'description': 'Natural language search query',
                    },
                    'entity_types': {
                        'type': 'array',
                        'items': {'type': 'string'},
                        'description': 'Optional: filter to specific entity types',
                    },
                },
                'required': ['topic', 'query'],
            },
        ),
        Tool(
            name='kb_load',
            description='Load a specific entity record from a KB by name.',
            inputSchema={
                'type': 'object',
                'properties': {
                    'topic': {'type': 'string', 'description': 'KB topic'},
                    'entity_type': {'type': 'string', 'description': 'Entity type folder name'},
                    'name': {'type': 'string', 'description': 'Entity name'},
                },
                'required': ['topic', 'entity_type', 'name'],
            },
        ),
        Tool(
            name='kb_write',
            description=(
                'Write or update an entity record in a KB. '
                'Use this mid-session to persist decisions, task state, patterns, or any structured note. '
                'Merges with existing record — only non-empty fields overwrite.'
            ),
            inputSchema={
                'type': 'object',
                'properties': {
                    'topic': {'type': 'string', 'description': 'KB topic (e.g. "claude_context")'},
                    'entity_type': {'type': 'string', 'description': 'Entity type (e.g. "decision", "active_task")'},
                    'name': {'type': 'string', 'description': 'Record name — used as filename'},
                    'data': {'type': 'object', 'description': 'Record fields as a JSON object'},
                },
                'required': ['topic', 'entity_type', 'name', 'data'],
            },
        ),
        Tool(
            name='kb_topics',
            description='List all available KB topics and their entity type counts.',
            inputSchema={'type': 'object', 'properties': {}, 'required': []},
        ),
        Tool(
            name='kb_schema',
            description=(
                'Show field schema for an entity type in a KB topic. '
                'Call with no entity_type to list all schema types for the topic.'
            ),
            inputSchema={
                'type': 'object',
                'properties': {
                    'topic': {'type': 'string', 'description': 'KB topic'},
                    'entity_type': {'type': 'string', 'description': 'Optional: specific entity type'},
                },
                'required': ['topic'],
            },
        ),
        Tool(
            name='dot_load',
            description=(
                'Load the full DOT (Document of Truth) for a KB topic. '
                'A DOT is a compressed, structured reference document with symbols, TOC, and cards. '
                'Use dot_load("claude_context") at session start to load your persistent working memory.'
            ),
            inputSchema={
                'type': 'object',
                'properties': {
                    'topic': {'type': 'string', 'description': 'KB topic (e.g. "claude_context")'},
                },
                'required': ['topic'],
            },
        ),
        Tool(
            name='corpus_status',
            description='Show ingestion progress for a topic — record counts, file size, last modified.',
            inputSchema={
                'type': 'object',
                'properties': {
                    'topic': {'type': 'string', 'description': 'KB topic'},
                },
                'required': ['topic'],
            },
        ),
        Tool(
            name='kb_backup',
            description=(
                'Mirror the KB folder to OneDrive. '
                'Use dry=true to preview without copying.'
            ),
            inputSchema={
                'type': 'object',
                'properties': {
                    'kb_only': {'type': 'boolean', 'description': 'KB folder only (default true)'},
                    'dry': {'type': 'boolean', 'description': 'Preview only — no copying'},
                },
                'required': [],
            },
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:

    if name == 'kb_search':
        result = search_kb(
            topic=arguments['topic'],
            query=arguments['query'],
            entity_types=arguments.get('entity_types'),
            kb_root=KB_ROOT,
        )
        text = result if result else f'No records found for "{arguments["query"]}" in {arguments["topic"]} KB.'
        return [TextContent(type='text', text=text)]

    if name == 'kb_load':
        topic       = arguments['topic']
        entity_type = arguments['entity_type']
        name_arg    = arguments['name']
        safe = name_arg.lower().replace(' ', '_')
        candidates = [
            KB_ROOT / topic / 'entries' / entity_type / f'{safe}.json',
            KB_ROOT / topic / 'entries' / entity_type / f'{name_arg}.json',
        ]
        for path in candidates:
            if path.exists():
                record = json.loads(path.read_text(encoding='utf-8'))
                return [TextContent(type='text', text=json.dumps(record, indent=2))]
        entity_dir = KB_ROOT / topic / 'entries' / entity_type
        if entity_dir.exists():
            matches = [f for f in entity_dir.glob('*.json')
                       if safe[:5] in f.stem or f.stem[:5] in safe]
            if matches:
                record = json.loads(matches[0].read_text(encoding='utf-8'))
                return [TextContent(type='text', text=json.dumps(record, indent=2))]
        return [TextContent(type='text', text=f'Record not found: {topic}/{entity_type}/{name_arg}')]

    if name == 'kb_write':
        topic       = arguments['topic']
        entity_type = arguments['entity_type']
        raw_name    = arguments['name']
        data        = arguments['data']
        safe        = raw_name.lower().replace(' ', '_')
        entity_dir  = KB_ROOT / topic / 'entries' / entity_type
        entity_dir.mkdir(parents=True, exist_ok=True)
        record_path = entity_dir / f'{safe}.json'
        if record_path.exists():
            try:
                existing = json.loads(record_path.read_text(encoding='utf-8'))
                for k, v in data.items():
                    if v is not None and v != '' and v != []:
                        existing[k] = v
                data = existing
            except Exception:
                pass
        record_path.write_text(json.dumps(data, indent=2), encoding='utf-8')
        index_path = entity_dir / '_index.json'
        try:
            index = json.loads(index_path.read_text(encoding='utf-8')) if index_path.exists() else []
            name_key = data.get('name') or data.get('id') or raw_name
            for i, entry in enumerate(index):
                if (entry.get('name') or entry.get('id')) == name_key:
                    index[i] = data
                    break
            else:
                index.append(data)
            index_path.write_text(json.dumps(index, indent=2), encoding='utf-8')
        except Exception:
            pass
        return [TextContent(type='text', text=f'Written: {topic}/{entity_type}/{safe}.json ({len(json.dumps(data))} bytes)')]

    if name == 'kb_topics':
        entries_roots = [d for d in KB_ROOT.iterdir() if d.is_dir()] if KB_ROOT.exists() else []
        lines = ['Available KB topics:\n']
        for topic_dir in sorted(entries_roots):
            topic = topic_dir.name
            entries_dir = topic_dir / 'entries'
            entity_types = [d.name for d in entries_dir.iterdir() if d.is_dir()] if entries_dir.exists() else []
            dot_file = topic_dir / f'{topic}_dot.txt'
            dot_note = ' [DOT]' if dot_file.exists() else ''
            lines.append(f'  {topic}{dot_note}: {len(entity_types)} entity types')
            for et in sorted(entity_types):
                index = entries_dir / et / '_index.json'
                if index.exists():
                    count = len(json.loads(index.read_text(encoding='utf-8')))
                    lines.append(f'    - {et}: {count} records')
        return [TextContent(type='text', text='\n'.join(lines))]

    if name == 'kb_schema':
        topic       = arguments['topic']
        entity_type = arguments.get('entity_type')
        schemas_dir = KB_ROOT / topic / 'schemas'
        if not schemas_dir.exists():
            return [TextContent(type='text', text=f'No schemas found for topic "{topic}".')]
        if entity_type:
            schema_path = schemas_dir / f'{entity_type}.json'
            if not schema_path.exists():
                available = [f.stem for f in schemas_dir.glob('*.json')]
                return [TextContent(type='text', text=f'Schema "{entity_type}" not found. Available: {", ".join(sorted(available))}')]
            schema = json.loads(schema_path.read_text(encoding='utf-8'))
            lines = [f'Schema: {topic}/{entity_type}\n']
            for field, defn in schema.items():
                ftype = defn.get('type', 'string') if isinstance(defn, dict) else str(defn)
                desc  = defn.get('description', '') if isinstance(defn, dict) else ''
                lines.append(f'  {field} ({ftype}): {desc}')
            return [TextContent(type='text', text='\n'.join(lines))]
        else:
            lines = [f'Schemas for "{topic}":\n']
            for sf in sorted(schemas_dir.glob('*.json')):
                try:
                    schema = json.loads(sf.read_text(encoding='utf-8'))
                    fields = list(schema.keys())
                    lines.append(f'  {sf.stem}: {", ".join(fields[:6])}{"..." if len(fields) > 6 else ""}')
                except Exception:
                    lines.append(f'  {sf.stem}: (unreadable)')
            return [TextContent(type='text', text='\n'.join(lines))]

    if name == 'dot_load':
        topic = arguments['topic']
        topic_dir = KB_ROOT / topic
        candidates = [
            topic_dir / f'{topic}_dot.txt',
            topic_dir / 'overview.md',
            topic_dir / f'{topic}.dot',
        ]
        for path in candidates:
            if path.exists():
                text = path.read_text(encoding='utf-8', errors='ignore')
                return [TextContent(type='text', text=text)]
        return [TextContent(type='text', text=f'No DOT found for topic "{topic}". Expected: {topic_dir}/{topic}_dot.txt')]

    if name == 'corpus_status':
        topic = arguments['topic']
        topic_dir = KB_ROOT / topic
        lines = [f'KB status: {topic}\n']
        entries_dir = topic_dir / 'entries'
        if entries_dir.exists():
            for et_dir in sorted(entries_dir.iterdir()):
                if et_dir.is_dir():
                    index = et_dir / '_index.json'
                    if index.exists():
                        count = len(json.loads(index.read_text(encoding='utf-8')))
                        lines.append(f'  {et_dir.name}: {count} records')
        corpus = topic_dir / 'corpus.txt'
        if corpus.exists():
            from datetime import datetime
            size_kb = corpus.stat().st_size // 1024
            mod_str = datetime.fromtimestamp(corpus.stat().st_mtime).strftime('%Y-%m-%d %H:%M')
            lines.append(f'\n  corpus.txt: {size_kb} KB  (modified {mod_str})')
        dot = topic_dir / f'{topic}_dot.txt'
        if dot.exists():
            lines.append(f'  DOT: {dot.stat().st_size // 1024} KB')
        return [TextContent(type='text', text='\n'.join(lines))]

    if name == 'kb_backup':
        onedrive = Path.home() / 'OneDrive' / 'kilonova_kb_backup'
        dry = arguments.get('dry', False)
        import shutil
        copied = 0
        try:
            if not dry:
                onedrive.mkdir(parents=True, exist_ok=True)
            for item in KB_ROOT.rglob('*'):
                if item.is_file():
                    dest = onedrive / item.relative_to(KB_ROOT)
                    if not dry:
                        dest.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(item, dest)
                    copied += 1
            label = 'Would copy' if dry else 'Backed up'
            return [TextContent(type='text', text=f'{label}: {copied} files → {onedrive}')]
        except Exception as e:
            return [TextContent(type='text', text=f'Backup failed: {e}')]

    return [TextContent(type='text', text=f'Unknown tool: {name}')]


async def main():
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == '__main__':
    import asyncio
    asyncio.run(main())
