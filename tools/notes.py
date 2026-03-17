"""
JARVIS Notes Module
Quick notes and journal

Author: Rashi AI
Built for: Akshay
"""

import json
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List

# Project root
PROJECT_ROOT = Path(__file__).parent.parent
NOTES_FILE = PROJECT_ROOT / 'data' / 'notes.json'
JOURNAL_DIR = PROJECT_ROOT / 'journal'


def load_notes() -> List[Dict]:
    """Load notes from file"""
    if NOTES_FILE.exists():
        with open(NOTES_FILE, 'r') as f:
            return json.load(f)
    return []


def save_notes(notes: List[Dict]):
    """Save notes to file"""
    NOTES_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(NOTES_FILE, 'w') as f:
        json.dump(notes, f, indent=2)


def add_note(title: str, content: str = '', tags: str = '') -> Dict[str, Any]:
    """
    Add a note
    
    Args:
        title: Note title
        content: Note content
        tags: Comma-separated tags
        
    Returns:
        Dict with success status
    """
    notes = load_notes()
    
    note = {
        'id': len(notes) + 1,
        'title': title,
        'content': content,
        'tags': [t.strip() for t in tags.split(',') if t.strip()],
        'created_at': datetime.now().isoformat(),
        'updated_at': datetime.now().isoformat()
    }
    
    notes.append(note)
    save_notes(notes)
    
    return {
        'success': True,
        'message': f'Note added: {title}',
        'note': note
    }


def get_notes(search: str = None) -> Dict[str, Any]:
    """Get all notes, optionally filtered by search"""
    notes = load_notes()
    
    if search:
        search_lower = search.lower()
        notes = [n for n in notes if search_lower in n['title'].lower() or search_lower in n['content'].lower()]
    
    return {
        'success': True,
        'count': len(notes),
        'notes': notes
    }


def delete_note(note_id: int) -> Dict[str, Any]:
    """Delete a note"""
    notes = load_notes()
    notes = [n for n in notes if n['id'] != note_id]
    save_notes(notes)
    
    return {
        'success': True,
        'message': f'Deleted note {note_id}'
    }


def add_journal_entry(content: str, mood: str = None) -> Dict[str, Any]:
    """
    Add a journal entry
    
    Args:
        content: Journal content
        mood: Current mood (optional)
        
    Returns:
        Dict with success status
    """
    JOURNAL_DIR.mkdir(parents=True, exist_ok=True)
    
    # Create filename with date
    date_str = datetime.now().strftime('%Y-%m-%d')
    filepath = JOURNAL_DIR / f'{date_str}.md'
    
    # Append to file
    timestamp = datetime.now().strftime('%H:%M')
    entry = f"\n## {timestamp}"
    if mood:
        entry += f" (Mood: {mood})"
    entry += f"\n\n{content}\n"
    
    with open(filepath, 'a', encoding='utf-8') as f:
        f.write(entry)
    
    return {
        'success': True,
        'message': 'Journal entry saved',
        'date': date_str
    }


def get_journal_entries(limit: int = 7) -> Dict[str, Any]:
    """Get recent journal entries"""
    if not JOURNAL_DIR.exists():
        return {
            'success': True,
            'entries': []
        }
    
    entries = []
    for file in sorted(JOURNAL_DIR.glob('*.md'), reverse=True)[:limit]:
        with open(file, 'r', encoding='utf-8') as f:
            entries.append({
                'date': file.stem,
                'content': f.read()
            })
    
    return {
        'success': True,
        'count': len(entries),
        'entries': entries
    }
