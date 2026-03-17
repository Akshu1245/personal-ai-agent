"""
JARVIS Memory Importer
Parses AI conversation exports and raw text into importable memories.

Supported formats:
  - ChatGPT  (conversations.json from data export)
  - Claude   (conversations.json from Claude export)
  - Gemini   (JSON export)
  - Plain text / Markdown
  - Generic JSON array
"""

import json
import re
from typing import List, Tuple


# ── Format detection ─────────────────────────────────────────

def detect_format(content: str, filename: str = '') -> str:
    fn = filename.lower()
    if fn.endswith('.txt') or fn.endswith('.md'):
        return 'text'

    try:
        data = json.loads(content)
        if isinstance(data, list) and len(data) > 0:
            first = data[0]
            if isinstance(first, dict):
                if 'mapping' in first or 'conversation_id' in first:
                    return 'chatgpt'
                if 'chat_messages' in first or ('uuid' in first and 'name' in first):
                    return 'claude'
                if 'clientSideConversationId' in first or 'requestedTime' in first:
                    return 'gemini'
        elif isinstance(data, dict):
            if 'conversations' in data and isinstance(data['conversations'], list):
                return 'chatgpt'
    except Exception:
        pass

    return 'text'


# ── Parsers ──────────────────────────────────────────────────

def _clean(text: str, max_len: int = 600) -> str:
    text = text.strip()
    text = re.sub(r'\s+', ' ', text)
    return text[:max_len]


def parse_chatgpt(content: str) -> List[str]:
    """Parse ChatGPT conversations.json export"""
    memories = []
    try:
        data = json.loads(content)
        convs = data if isinstance(data, list) else data.get('conversations', [])

        for conv in convs:
            title = conv.get('title', '').strip()
            mapping = conv.get('mapping', {})

            pairs = []
            for node in mapping.values():
                msg = node.get('message')
                if not msg:
                    continue
                role = msg.get('author', {}).get('role', '')
                parts = msg.get('content', {}).get('parts', [])
                text = ' '.join(str(p) for p in parts if isinstance(p, str)).strip()

                if role in ('user', 'assistant') and len(text) > 15:
                    pairs.append((role, text))

            if title:
                memories.append(f"[ChatGPT topic] {_clean(title)}")

            for role, text in pairs[:40]:
                prefix = "User asked" if role == 'user' else "ChatGPT answered"
                memories.append(f"[ChatGPT] {prefix}: {_clean(text)}")

    except Exception as e:
        pass

    return memories


def parse_claude(content: str) -> List[str]:
    """Parse Claude conversation export"""
    memories = []
    try:
        data = json.loads(content)
        convs = data if isinstance(data, list) else data.get('conversations', [])

        for conv in convs:
            name = conv.get('name', conv.get('title', '')).strip()
            msgs = conv.get('chat_messages', conv.get('messages', []))

            if name:
                memories.append(f"[Claude topic] {_clean(name)}")

            for msg in msgs[:40]:
                sender = msg.get('sender', msg.get('role', ''))
                text = msg.get('text', msg.get('content', ''))
                if isinstance(text, list):
                    text = ' '.join(str(t.get('text', '') if isinstance(t, dict) else t) for t in text)
                text = text.strip()
                if len(text) > 15:
                    prefix = "User said" if sender in ('human', 'user') else "Claude answered"
                    memories.append(f"[Claude] {prefix}: {_clean(text)}")

    except Exception as e:
        pass

    return memories


def parse_gemini(content: str) -> List[str]:
    """Parse Gemini export"""
    memories = []
    try:
        data = json.loads(content)
        convs = data if isinstance(data, list) else data.get('conversations', [])

        for conv in convs:
            for msg in conv.get('messages', conv.get('turns', []))[:40]:
                role = msg.get('role', msg.get('author', ''))
                text = msg.get('content', msg.get('text', ''))
                if isinstance(text, list):
                    text = ' '.join(str(t) for t in text)
                text = str(text).strip()
                if len(text) > 15:
                    prefix = "User asked" if 'user' in role.lower() else "Gemini answered"
                    memories.append(f"[Gemini] {prefix}: {_clean(text)}")

    except Exception as e:
        pass

    return memories


def parse_text(content: str) -> List[str]:
    """Parse plain text or markdown"""
    memories = []
    lines = content.split('\n')
    for line in lines:
        line = line.strip()
        line = re.sub(r'^#{1,6}\s+', '', line)
        line = re.sub(r'^[-*+>]\s+', '', line)
        line = re.sub(r'\*\*(.*?)\*\*', r'\1', line)
        line = re.sub(r'`{1,3}.*?`{1,3}', '', line)
        line = line.strip()
        if len(line) > 25:
            memories.append(_clean(line))
    return memories


def parse_generic_json(content: str) -> List[str]:
    """Try to extract anything useful from generic JSON"""
    memories = []
    try:
        data = json.loads(content)

        def extract(obj, depth=0):
            if depth > 4:
                return
            if isinstance(obj, str) and len(obj) > 25:
                memories.append(_clean(obj))
            elif isinstance(obj, list):
                for item in obj[:50]:
                    extract(item, depth + 1)
            elif isinstance(obj, dict):
                for k, v in obj.items():
                    if k in ('text', 'content', 'message', 'body', 'value', 'description'):
                        extract(v, depth + 1)
                    else:
                        extract(v, depth + 1)

        extract(data)
    except Exception:
        pass
    return list(dict.fromkeys(memories))


# ── Main entry point ─────────────────────────────────────────

def parse_import(content: str, filename: str = '', source: str = 'auto') -> Tuple[List[str], str]:
    """
    Parse an import file and return (list_of_memory_strings, detected_format).

    Args:
        content:  Raw file content as string
        filename: Original filename (used for format hints)
        source:   Force a format: 'chatgpt'|'claude'|'gemini'|'text'|'auto'

    Returns:
        (memories, format_name)
    """
    if source == 'auto':
        source = detect_format(content, filename)

    parsers = {
        'chatgpt': parse_chatgpt,
        'claude':  parse_claude,
        'gemini':  parse_gemini,
        'text':    parse_text,
    }

    parser = parsers.get(source)
    if parser:
        memories = parser(content)
    else:
        memories = []

    # Fallback chain if primary parser returned nothing
    if not memories:
        for fmt, p in parsers.items():
            if fmt != source:
                memories = p(content)
                if memories:
                    source = fmt
                    break

    # Final fallback: generic JSON
    if not memories:
        memories = parse_generic_json(content)
        if memories:
            source = 'generic_json'

    # Deduplicate and filter blanks
    seen = set()
    result = []
    for m in memories:
        if m and m not in seen:
            seen.add(m)
            result.append(m)

    return result, source
