"""
JARVIS Memory Module
Long-term memory using ChromaDB + SQLite

Stores: conversations, memories, tasks, notes, projects, user profile, import history
"""

import os
import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional

try:
    import chromadb
    CHROMADB_AVAILABLE = True
except ImportError:
    CHROMADB_AVAILABLE = False


class Memory:
    """JARVIS Memory System"""

    def __init__(self):
        self.project_root = Path(__file__).parent.parent
        self.memory_dir   = self.project_root / 'memory'
        self.chroma_dir   = self.memory_dir / 'chroma_db'
        self.data_dir     = self.memory_dir / 'data'
        self.db_path      = self.data_dir / 'conversations.db'
        self.chroma_client = None
        self.collection    = None
        self._init_storage()

    # ═══════════════════════════════════════
    #  INITIALISATION
    # ═══════════════════════════════════════

    def _init_storage(self):
        self.memory_dir.mkdir(exist_ok=True)
        self.chroma_dir.mkdir(exist_ok=True)
        self.data_dir.mkdir(exist_ok=True)
        self._init_sqlite()
        if CHROMADB_AVAILABLE:
            self._init_chroma()

    def _init_sqlite(self):
        conn = sqlite3.connect(str(self.db_path))
        c = conn.cursor()

        c.executescript('''
            CREATE TABLE IF NOT EXISTS conversations (
                id        INTEGER PRIMARY KEY AUTOINCREMENT,
                role      TEXT NOT NULL,
                content   TEXT NOT NULL,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS memories (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                content    TEXT NOT NULL,
                category   TEXT DEFAULT 'general',
                importance INTEGER DEFAULT 1,
                source     TEXT DEFAULT 'manual',
                timestamp  DATETIME DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS tasks (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                title       TEXT NOT NULL,
                description TEXT DEFAULT '',
                project     TEXT,
                due_date    TEXT,
                completed   INTEGER DEFAULT 0,
                created_at  DATETIME DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS notes (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                title      TEXT NOT NULL,
                content    TEXT DEFAULT '',
                tags       TEXT DEFAULT '',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS projects (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                name        TEXT NOT NULL UNIQUE,
                description TEXT DEFAULT '',
                stack       TEXT DEFAULT '',
                tech        TEXT DEFAULT '[]',
                goals       TEXT DEFAULT '',
                url         TEXT DEFAULT '',
                path        TEXT DEFAULT '',
                status      TEXT DEFAULT 'active',
                priority    TEXT DEFAULT 'medium',
                color       TEXT DEFAULT '#00d4ff',
                created_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at  DATETIME DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS user_profile (
                id            INTEGER PRIMARY KEY DEFAULT 1,
                name          TEXT DEFAULT 'User',
                avatar_initial TEXT DEFAULT 'U',
                groq_model    TEXT DEFAULT 'llama-3.3-70b-versatile',
                theme         TEXT DEFAULT 'dark',
                timezone      TEXT DEFAULT 'UTC',
                created_at    DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at    DATETIME DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS memory_imports (
                id             INTEGER PRIMARY KEY AUTOINCREMENT,
                source         TEXT NOT NULL,
                filename       TEXT DEFAULT '',
                items_imported INTEGER DEFAULT 0,
                imported_at    DATETIME DEFAULT CURRENT_TIMESTAMP
            );
        ''')

        # Add source column to memories if upgrading from older DB
        try:
            c.execute("ALTER TABLE memories ADD COLUMN source TEXT DEFAULT 'manual'")
        except Exception:
            pass

        # Ensure default profile row exists
        c.execute("INSERT OR IGNORE INTO user_profile (id, name) VALUES (1, 'User')")

        conn.commit()
        conn.close()

    def _init_chroma(self):
        try:
            self.chroma_client = chromadb.PersistentClient(str(self.chroma_dir))
            self.collection = self.chroma_client.get_or_create_collection(
                name="jarvis_memory",
                metadata={"description": "JARVIS long-term memory"}
            )
        except Exception as e:
            print(f"ChromaDB init failed: {e}")
            self.chroma_client = None
            self.collection = None

    def initialize(self):
        self._init_storage()

    def _conn(self):
        return sqlite3.connect(str(self.db_path))

    # ═══════════════════════════════════════
    #  USER PROFILE
    # ═══════════════════════════════════════

    def get_profile(self) -> Dict:
        conn = self._conn()
        c = conn.cursor()
        c.execute("SELECT name, avatar_initial, groq_model, theme, timezone FROM user_profile WHERE id=1")
        row = c.fetchone()
        conn.close()
        if row:
            return {
                'name': row[0], 'avatar_initial': row[1],
                'groq_model': row[2], 'theme': row[3], 'timezone': row[4]
            }
        return {'name': 'User', 'avatar_initial': 'U', 'groq_model': 'llama-3.3-70b-versatile', 'theme': 'dark', 'timezone': 'UTC'}

    def update_profile(self, data: Dict):
        fields = []
        values = []
        allowed = ('name', 'avatar_initial', 'groq_model', 'theme', 'timezone')
        for k in allowed:
            if k in data:
                fields.append(f"{k}=?")
                values.append(data[k])
        if not fields:
            return
        fields.append("updated_at=CURRENT_TIMESTAMP")
        values.append(1)
        conn = self._conn()
        conn.execute(f"UPDATE user_profile SET {', '.join(fields)} WHERE id=?", values)
        conn.commit()
        conn.close()

    # ═══════════════════════════════════════
    #  CONVERSATIONS
    # ═══════════════════════════════════════

    def add_conversation(self, role: str, content: str):
        conn = self._conn()
        conn.execute('INSERT INTO conversations (role, content) VALUES (?, ?)', (role, content))
        conn.commit()
        conn.close()

    def get_conversation_history(self, limit: int = 50) -> List[Dict]:
        conn = self._conn()
        c = conn.cursor()
        c.execute('''
            SELECT role, content, timestamp
            FROM conversations
            ORDER BY timestamp DESC LIMIT ?
        ''', (limit,))
        rows = [{'role': r[0], 'content': r[1], 'timestamp': r[2]} for r in c.fetchall()]
        conn.close()
        return list(reversed(rows))

    # ═══════════════════════════════════════
    #  MEMORIES
    # ═══════════════════════════════════════

    def add(self, content: str, category: str = 'general', importance: int = 1, source: str = 'manual'):
        conn = self._conn()
        conn.execute(
            'INSERT INTO memories (content, category, importance, source) VALUES (?, ?, ?, ?)',
            (content, category, importance, source)
        )
        conn.commit()
        conn.close()

        if self.collection is not None:
            try:
                self.collection.add(
                    documents=[content],
                    ids=[f"mem_{datetime.now().timestamp()}_{id(content)}"]
                )
            except Exception:
                pass

    def bulk_add(self, items: List[str], category: str = 'imported', source: str = 'import'):
        """Bulk-insert memories efficiently"""
        conn = self._conn()
        conn.executemany(
            'INSERT INTO memories (content, category, importance, source) VALUES (?, ?, 1, ?)',
            [(item, category, source) for item in items if item.strip()]
        )
        conn.commit()
        conn.close()

    def delete_memory(self, memory_id: int):
        conn = self._conn()
        conn.execute('DELETE FROM memories WHERE id=?', (memory_id,))
        conn.commit()
        conn.close()

    def search(self, query: str, limit: int = 10) -> List[Dict]:
        conn = self._conn()
        c = conn.cursor()
        c.execute('''
            SELECT id, content, category, importance, source, timestamp
            FROM memories
            WHERE content LIKE ?
            ORDER BY importance DESC, timestamp DESC LIMIT ?
        ''', (f'%{query}%', limit))
        rows = [
            {'id': r[0], 'content': r[1], 'category': r[2],
             'importance': r[3], 'source': r[4], 'timestamp': r[5]}
            for r in c.fetchall()
        ]
        conn.close()

        if self.collection and not rows:
            try:
                res = self.collection.query(query_texts=[query], n_results=limit)
                for doc in res.get('documents', [[]])[0]:
                    rows.append({'content': doc, 'source': 'vector'})
            except Exception:
                pass

        return rows

    def get_all_memories(self, category: str = None, source: str = None,
                         limit: int = 200, offset: int = 0) -> List[Dict]:
        conn = self._conn()
        c = conn.cursor()
        conditions = []
        params = []
        if category:
            conditions.append("category=?")
            params.append(category)
        if source:
            conditions.append("source=?")
            params.append(source)
        where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
        params += [limit, offset]
        c.execute(f'''
            SELECT id, content, category, importance, source, timestamp
            FROM memories {where}
            ORDER BY importance DESC, timestamp DESC
            LIMIT ? OFFSET ?
        ''', params)
        rows = [
            {'id': r[0], 'content': r[1], 'category': r[2],
             'importance': r[3], 'source': r[4], 'timestamp': r[5]}
            for r in c.fetchall()
        ]
        conn.close()
        return rows

    def get_memory_sources(self) -> List[str]:
        conn = self._conn()
        c = conn.cursor()
        c.execute("SELECT DISTINCT source FROM memories ORDER BY source")
        sources = [r[0] for r in c.fetchall()]
        conn.close()
        return sources

    # ═══════════════════════════════════════
    #  TASKS
    # ═══════════════════════════════════════

    def add_task(self, title: str, description: str = '', project: str = None, due_date: str = None):
        conn = self._conn()
        conn.execute(
            'INSERT INTO tasks (title, description, project, due_date) VALUES (?, ?, ?, ?)',
            (title, description, project, due_date)
        )
        conn.commit()
        conn.close()

    def get_tasks(self, project: str = None, completed: bool = None) -> List[Dict]:
        conn = self._conn()
        c = conn.cursor()
        q = 'SELECT id, title, description, project, due_date, completed, created_at FROM tasks WHERE 1=1'
        p = []
        if project:
            q += ' AND project=?'; p.append(project)
        if completed is not None:
            q += ' AND completed=?'; p.append(1 if completed else 0)
        q += ' ORDER BY created_at DESC'
        c.execute(q, p)
        rows = [
            {'id': r[0], 'title': r[1], 'description': r[2],
             'project': r[3], 'due_date': r[4], 'completed': bool(r[5]), 'created_at': r[6]}
            for r in c.fetchall()
        ]
        conn.close()
        return rows

    def complete_task(self, task_id: int):
        conn = self._conn()
        conn.execute('UPDATE tasks SET completed=1 WHERE id=?', (task_id,))
        conn.commit()
        conn.close()

    # ═══════════════════════════════════════
    #  NOTES
    # ═══════════════════════════════════════

    def add_note(self, title: str, content: str, tags: str = ''):
        conn = self._conn()
        conn.execute('INSERT INTO notes (title, content, tags) VALUES (?, ?, ?)', (title, content, tags))
        conn.commit()
        conn.close()

    def get_notes(self, search: str = None) -> List[Dict]:
        conn = self._conn()
        c = conn.cursor()
        if search:
            c.execute('''
                SELECT id, title, content, tags, created_at FROM notes
                WHERE title LIKE ? OR content LIKE ? ORDER BY created_at DESC
            ''', (f'%{search}%', f'%{search}%'))
        else:
            c.execute('SELECT id, title, content, tags, created_at FROM notes ORDER BY created_at DESC')
        rows = [{'id': r[0], 'title': r[1], 'content': r[2], 'tags': r[3], 'created_at': r[4]}
                for r in c.fetchall()]
        conn.close()
        return rows

    def delete_note(self, note_id: int):
        conn = self._conn()
        conn.execute('DELETE FROM notes WHERE id=?', (note_id,))
        conn.commit()
        conn.close()

    # ═══════════════════════════════════════
    #  PROJECTS
    # ═══════════════════════════════════════

    def seed_projects_from_json(self, json_path: str):
        """One-time migration: import projects.json into SQLite"""
        path = Path(json_path)
        if not path.exists():
            return 0
        try:
            with open(path) as f:
                projects = json.load(f)
        except Exception:
            return 0

        count = 0
        for p in projects:
            if not p.get('name'):
                continue
            try:
                self.add_project(
                    name=p['name'],
                    description=p.get('description', ''),
                    stack=p.get('stack', ''),
                    tech=p.get('tech', []),
                    goals='',
                    url='',
                    path=p.get('path', '') or '',
                    status=p.get('status', 'active'),
                    priority=p.get('priority', 'medium'),
                )
                count += 1
            except Exception:
                pass  # already exists
        return count

    def get_projects(self) -> List[Dict]:
        conn = self._conn()
        c = conn.cursor()
        c.execute('''
            SELECT id, name, description, stack, tech, goals, url, path,
                   status, priority, color, created_at, updated_at
            FROM projects ORDER BY
                CASE priority WHEN 'high' THEN 1 WHEN 'medium' THEN 2 ELSE 3 END,
                name
        ''')
        rows = []
        for r in c.fetchall():
            try:
                tech = json.loads(r[4]) if r[4] else []
            except Exception:
                tech = []
            rows.append({
                'id': r[0], 'name': r[1], 'description': r[2], 'stack': r[3],
                'tech': tech, 'goals': r[5], 'url': r[6], 'path': r[7],
                'status': r[8], 'priority': r[9], 'color': r[10],
                'created_at': r[11], 'updated_at': r[12]
            })
        conn.close()
        return rows

    def get_project(self, project_id: int) -> Optional[Dict]:
        conn = self._conn()
        c = conn.cursor()
        c.execute('SELECT id, name, description, stack, tech, goals, url, path, status, priority, color FROM projects WHERE id=?', (project_id,))
        r = c.fetchone()
        conn.close()
        if not r:
            return None
        try:
            tech = json.loads(r[4]) if r[4] else []
        except Exception:
            tech = []
        return {'id': r[0], 'name': r[1], 'description': r[2], 'stack': r[3],
                'tech': tech, 'goals': r[5], 'url': r[6], 'path': r[7],
                'status': r[8], 'priority': r[9], 'color': r[10]}

    def add_project(self, name: str, description: str = '', stack: str = '',
                    tech: list = None, goals: str = '', url: str = '',
                    path: str = '', status: str = 'active',
                    priority: str = 'medium', color: str = '#00d4ff') -> int:
        tech_json = json.dumps(tech or [])
        conn = self._conn()
        c = conn.cursor()
        c.execute('''
            INSERT INTO projects (name, description, stack, tech, goals, url, path, status, priority, color)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (name, description, stack, tech_json, goals, url, path, status, priority, color))
        new_id = c.lastrowid
        conn.commit()
        conn.close()
        return new_id

    def update_project(self, project_id: int, data: Dict):
        allowed = ('name', 'description', 'stack', 'goals', 'url', 'path', 'status', 'priority', 'color')
        fields = []
        values = []
        for k in allowed:
            if k in data:
                fields.append(f"{k}=?")
                values.append(data[k])
        if 'tech' in data:
            fields.append("tech=?")
            values.append(json.dumps(data['tech'] if isinstance(data['tech'], list) else []))
        if not fields:
            return
        fields.append("updated_at=CURRENT_TIMESTAMP")
        values.append(project_id)
        conn = self._conn()
        conn.execute(f"UPDATE projects SET {', '.join(fields)} WHERE id=?", values)
        conn.commit()
        conn.close()

    def delete_project(self, project_id: int):
        conn = self._conn()
        conn.execute('DELETE FROM projects WHERE id=?', (project_id,))
        conn.commit()
        conn.close()

    # ═══════════════════════════════════════
    #  IMPORT TRACKING
    # ═══════════════════════════════════════

    def log_import(self, source: str, filename: str, items: int):
        conn = self._conn()
        conn.execute(
            'INSERT INTO memory_imports (source, filename, items_imported) VALUES (?, ?, ?)',
            (source, filename, items)
        )
        conn.commit()
        conn.close()

    def get_import_history(self) -> List[Dict]:
        conn = self._conn()
        c = conn.cursor()
        c.execute('''
            SELECT id, source, filename, items_imported, imported_at
            FROM memory_imports ORDER BY imported_at DESC LIMIT 50
        ''')
        rows = [{'id': r[0], 'source': r[1], 'filename': r[2],
                 'items': r[3], 'imported_at': r[4]} for r in c.fetchall()]
        conn.close()
        return rows

    # ═══════════════════════════════════════
    #  STATS
    # ═══════════════════════════════════════

    def get_stats(self) -> Dict:
        conn = self._conn()
        c = conn.cursor()
        c.execute('SELECT COUNT(*) FROM conversations')
        conversations = c.fetchone()[0]
        c.execute('SELECT COUNT(*) FROM memories')
        memories = c.fetchone()[0]
        c.execute('SELECT COUNT(*) FROM tasks WHERE completed=0')
        pending_tasks = c.fetchone()[0]
        c.execute('SELECT COUNT(*) FROM notes')
        notes_count = c.fetchone()[0]
        c.execute('SELECT COUNT(*) FROM projects')
        projects_count = c.fetchone()[0]
        conn.close()
        return {
            'conversations': conversations,
            'memories': memories,
            'pending_tasks': pending_tasks,
            'notes': notes_count,
            'projects': projects_count,
            'chroma_available': CHROMADB_AVAILABLE
        }

    def clear_old_conversations(self, keep_last: int = 100):
        conn = self._conn()
        conn.execute('''
            DELETE FROM conversations
            WHERE id NOT IN (
                SELECT id FROM conversations ORDER BY timestamp DESC LIMIT ?
            )
        ''', (keep_last,))
        deleted = conn.execute('SELECT changes()').fetchone()[0]
        conn.commit()
        conn.close()
        return deleted


# ── Singleton ────────────────────────────────────────────────

_memory = None

def get_memory() -> Memory:
    global _memory
    if _memory is None:
        _memory = Memory()
    return _memory
