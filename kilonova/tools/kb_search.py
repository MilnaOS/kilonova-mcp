"""
KB Search — searches entity indexes in a Kilonova knowledge base.
Returns matching records as a formatted context block for injection into Claude.
"""
import json
import re
from pathlib import Path


_DEFAULT_KB_ROOT = Path('kb')
_MAX_RECORDS = 12
_MAX_CHARS   = 6000


def _load_index(topic: str, entity: str, kb_root: Path) -> list[dict]:
    path = kb_root / topic / 'entries' / entity / '_index.json'
    if path.exists():
        try:
            return json.loads(path.read_text(encoding='utf-8'))
        except Exception:
            pass
    entity_dir = kb_root / topic / 'entries' / entity
    if not entity_dir.exists():
        return []
    records = []
    for f in entity_dir.glob('*.json'):
        if f.name == '_index.json':
            continue
        try:
            records.append(json.loads(f.read_text(encoding='utf-8')))
        except Exception:
            pass
    return records


def _collection_schema_names(kb_root: Path, topic: str) -> set[str]:
    schemas_dir = kb_root / topic / 'schemas'
    names: set[str] = set()
    if schemas_dir.exists():
        for sf in schemas_dir.glob('*.json'):
            try:
                if json.loads(sf.read_text(encoding='utf-8')).get('_collection'):
                    names.add(sf.stem)
            except Exception:
                pass
    return names


def _count_entities(kb_root: Path, topic: str) -> dict[str, int]:
    entries_root = kb_root / topic / 'entries'
    if not entries_root.exists():
        return {}
    skip = _collection_schema_names(kb_root, topic)
    counts = {}
    for entity_dir in entries_root.iterdir():
        if not entity_dir.is_dir() or entity_dir.name in skip:
            continue
        index = entity_dir / '_index.json'
        if index.exists():
            try:
                counts[entity_dir.name] = len(json.loads(index.read_text(encoding='utf-8')))
                continue
            except Exception:
                pass
        counts[entity_dir.name] = sum(1 for f in entity_dir.glob('*.json') if f.name != '_index.json')
    return counts


def _fuzzy_match(term: str, target: str) -> bool:
    if term in target:
        return True
    min_len = min(len(term), len(target))
    if min_len >= 5 and target[:min_len - 1] == term[:min_len - 1]:
        return True
    return False


def _score_record(record: dict, terms: list[str]) -> int:
    text = json.dumps(record, default=str).lower()
    score = 0
    for term in terms:
        if _fuzzy_match(term, text):
            name = (record.get('name') or record.get('id') or '').lower()
            if _fuzzy_match(term, name):
                score += 10
            else:
                score += 1
    return score


def _tokenize(query: str) -> list[str]:
    stopwords = {
        'a', 'an', 'the', 'is', 'are', 'was', 'what', 'who', 'how', 'many',
        'tell', 'me', 'about', 'and', 'or', 'of', 'to', 'in', 'on', 'for',
        'with', 'can', 'do', 'does', 'did', 'list', 'give', 'show', 'find',
        'which', 'where', 'when', 'i', 'my', 'its', 'it', 'from', 'that',
        'this', 'there', 'any', 'all', 'some', 'their', 'they', 'have',
        'has', 'had', 'not', 'but', 'by', 'at', 'be', 'as', 'up', 'get',
    }
    words = re.findall(r"[a-z0-9][a-z0-9'\-]*", query.lower())
    return [w for w in words if w not in stopwords and len(w) > 2]


def _format_record(record: dict) -> str:
    """Format a record as compact readable text. Works with any schema."""
    lines = []
    name = record.get('name') or record.get('id') or 'Unknown'
    lines.append(f"**{name}**")
    skip = {'name', 'id', 'setting'}
    for key, val in record.items():
        if key in skip or val is None or val == '' or val == [] or val == {}:
            continue
        label = key.replace('_', ' ').title()
        if isinstance(val, list):
            if all(isinstance(v, str) for v in val):
                lines.append(f"  {label}: {', '.join(val)}")
            else:
                lines.append(f"  {label}: {json.dumps(val)}")
        elif isinstance(val, dict):
            lines.append(f"  {label}: {json.dumps(val)}")
        else:
            lines.append(f"  {label}: {val}")
    return '\n'.join(lines)


_COUNT_TERMS = {'how', 'many', 'count', 'total', 'number', 'list', 'all'}


def search_kb(
    topic: str,
    query: str,
    entity_types: list[str] | None = None,
    kb_root: Path | None = None,
) -> str:
    root = kb_root or _DEFAULT_KB_ROOT

    q_lower = query.lower()
    if any(t in q_lower for t in _COUNT_TERMS):
        counts = _count_entities(root, topic)
        if counts:
            lines = [f'## {topic.upper()} KB — Record Counts\n']
            for entity, n in sorted(counts.items()):
                lines.append(f'  {entity}: {n} records')
            return '\n'.join(lines)

    terms = _tokenize(query)
    if not terms:
        return ''

    entries_root = root / topic / 'entries'
    if not entries_root.exists():
        return ''

    _collection_types: set[str] = _collection_schema_names(root, topic)

    if entity_types:
        types_to_search = [e for e in entity_types if e not in _collection_types]
    else:
        types_to_search = [
            p.name for p in entries_root.iterdir()
            if p.is_dir() and p.name not in _collection_types
        ]

    scored: list[tuple[int, str, dict]] = []
    for entity in types_to_search:
        records = _load_index(topic, entity, root)
        for record in records:
            score = _score_record(record, terms)
            if score > 0:
                scored.append((score, entity, record))

    if not scored:
        return ''

    scored.sort(key=lambda x: x[0], reverse=True)
    top = scored[:_MAX_RECORDS]

    blocks = []
    total_chars = 0
    for score, entity, record in top:
        formatted = _format_record(record)
        if total_chars + len(formatted) > _MAX_CHARS:
            break
        blocks.append(f"[{entity}]\n{formatted}")
        total_chars += len(formatted)

    if not blocks:
        return ''

    header = f"## KB: {topic.upper()} — {len(blocks)} record(s) matching \"{query[:60]}\"\n\n"
    return header + '\n\n---\n\n'.join(blocks)
