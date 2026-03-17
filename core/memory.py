"""
JARVIS Memory Module
Long-term memory using ChromaDB + SQLite

Author: Rashi AI
Built for: Akshay
"""

import os
import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional

# Try to import chromadb, fallback to simple storage
try:
    import chromadb
    CHROMADB_AVAILABLE = True
except ImportError:
    CHROMADB_AVAILABLE = False


class Memory:
    """JARVIS Memory System"""
    
    def __init__(self):
        self.project_root = Path(__file__).parent.parent
        self.memory_dir = self.project_root / 'memory'
        self.chroma_dir = self.memory_dir / 'chroma_db'
        self.data_dir = self.memory_dir / 'data'
        
        # SQLite for structured data
        self.db_path = self.data_dir / 'conversations.db'
        
        # ChromaDB client
        self.chroma_client = None
        self.collection = None
        
        # Initialize
        self._init_storage()
        
    def _init_storage(self):
        """Initialize storage directories and databases"""
        # Create directories
        self.memory_dir.mkdir(exist_ok=True)
        self.chroma_dir.mkdir(exist_ok=True)
        self.data_dir.mkdir(exist_ok=True)
        
        # Initialize SQLite
        self._init_sqlite()
        
        # Initialize ChromaDB if available
        if CHROMADB_AVAILABLE:
            self._init_chroma()
            
    def _init_sqlite(self):
        """Initialize SQLite database"""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        
        # Create tables
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS conversations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS memories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                content TEXT NOT NULL,
                category TEXT,
                importance INTEGER DEFAULT 1,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                description TEXT,
                project TEXT,
                due_date TEXT,
                completed INTEGER DEFAULT 0,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS notes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                content TEXT,
                tags TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        conn.commit()
        conn.close()
        
    def _init_chroma(self):
        """Initialize ChromaDB for vector storage"""
        try:
            self.chroma_client = chromadb.PersistentClient(str(self.chroma_dir))
            self.collection = self.chroma_client.get_or_create_collection(
                name="jarvis_memory",
                metadata={"description": "JARVIS long-term memory"}
            )
        except Exception as e:
            print(f"ChromaDB initialization failed: {e}")
            self.chroma_client = None
            self.collection = None
            
    def initialize(self):
        """Initialize the memory system"""
        self._init_storage()
        print(f"Memory initialized - SQLite: {self.db_path}, ChromaDB: {CHROMADB_AVAILABLE}")
        
    # ==================== CONVERSATIONS ====================
    
    def add_conversation(self, role: str, content: str):
        """Add a conversation turn"""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        
        cursor.execute(
            'INSERT INTO conversations (role, content) VALUES (?, ?)',
            (role, content)
        )
        
        conn.commit()
        conn.close()
        
    def get_conversation_history(self, limit: int = 50) -> List[Dict]:
        """Get conversation history"""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT role, content, timestamp 
            FROM conversations 
            ORDER BY timestamp DESC 
            LIMIT ?
        ''', (limit,))
        
        results = [
            {'role': row[0], 'content': row[1], 'timestamp': row[2]}
            for row in cursor.fetchall()
        ]
        
        conn.close()
        return list(reversed(results))
    
    # ==================== LONG-TERM MEMORY ====================
    
    def add(self, content: str, category: str = 'general', importance: int = 1):
        """Add a memory"""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        
        cursor.execute(
            'INSERT INTO memories (content, category, importance) VALUES (?, ?, ?)',
            (content, category, importance)
        )
        
        conn.commit()
        conn.close()
        
        # Also add to ChromaDB if available
        if self.collection is not None:
            try:
                self.collection.add(
                    documents=[content],
                    ids=[f"mem_{datetime.now().timestamp()}"]
                )
            except Exception as e:
                print(f"ChromaDB add failed: {e}")
                
    def search(self, query: str, limit: int = 5) -> List[Dict]:
        """Search memories"""
        results = []
        
        # Search in SQLite
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT content, category, importance, timestamp 
            FROM memories 
            WHERE content LIKE ? 
            ORDER BY importance DESC, timestamp DESC 
            LIMIT ?
        ''', (f'%{query}%', limit))
        
        results = [
            {
                'content': row[0],
                'category': row[1],
                'importance': row[2],
                'timestamp': row[3]
            }
            for row in cursor.fetchall()
        ]
        
        conn.close()
        
        # Also search in ChromaDB if available
        if self.collection is not None and not results:
            try:
                chroma_results = self.collection.query(
                    query_texts=[query],
                    n_results=limit
                )
                for i, doc in enumerate(chroma_results.get('documents', [[]])[0]):
                    results.append({
                        'content': doc,
                        'source': 'vector',
                        'distance': chroma_results.get('distances', [[]])[0][i] if chroma_results.get('distances') else None
                    })
            except Exception as e:
                print(f"ChromaDB search failed: {e}")
                
        return results
        
    def get_all_memories(self, category: str = None, limit: int = 100) -> List[Dict]:
        """Get all memories, optionally filtered by category"""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        
        if category:
            cursor.execute('''
                SELECT content, category, importance, timestamp 
                FROM memories 
                WHERE category = ?
                ORDER BY importance DESC, timestamp DESC 
                LIMIT ?
            ''', (category, limit))
        else:
            cursor.execute('''
                SELECT content, category, importance, timestamp 
                FROM memories 
                ORDER BY importance DESC, timestamp DESC 
                LIMIT ?
            ''', (limit,))
            
        results = [
            {'content': row[0], 'category': row[1], 'importance': row[2], 'timestamp': row[3]}
            for row in cursor.fetchall()
        ]
        
        conn.close()
        return results
        
    # ==================== TASKS ====================
    
    def add_task(self, title: str, description: str = '', project: str = None, due_date: str = None):
        """Add a task"""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        
        cursor.execute(
            'INSERT INTO tasks (title, description, project, due_date) VALUES (?, ?, ?, ?)',
            (title, description, project, due_date)
        )
        
        conn.commit()
        conn.close()
        
    def get_tasks(self, project: str = None, completed: bool = None) -> List[Dict]:
        """Get tasks"""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        
        query = 'SELECT id, title, description, project, due_date, completed, created_at FROM tasks WHERE 1=1'
        params = []
        
        if project:
            query += ' AND project = ?'
            params.append(project)
            
        if completed is not None:
            query += ' AND completed = ?'
            params.append(1 if completed else 0)
            
        query += ' ORDER BY created_at DESC'
        
        cursor.execute(query, params)
        
        results = [
            {
                'id': row[0],
                'title': row[1],
                'description': row[2],
                'project': row[3],
                'due_date': row[4],
                'completed': bool(row[5]),
                'created_at': row[6]
            }
            for row in cursor.fetchall()
        ]
        
        conn.close()
        return results
        
    def complete_task(self, task_id: int):
        """Mark task as complete"""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        
        cursor.execute('UPDATE tasks SET completed = 1 WHERE id = ?', (task_id,))
        
        conn.commit()
        conn.close()
        
    # ==================== NOTES ====================
    
    def add_note(self, title: str, content: str, tags: str = ''):
        """Add a note"""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        
        cursor.execute(
            'INSERT INTO notes (title, content, tags) VALUES (?, ?, ?)',
            (title, content, tags)
        )
        
        conn.commit()
        conn.close()
        
    def get_notes(self, search: str = None) -> List[Dict]:
        """Get notes"""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        
        if search:
            cursor.execute('''
                SELECT id, title, content, tags, created_at 
                FROM notes 
                WHERE title LIKE ? OR content LIKE ?
                ORDER BY created_at DESC
            ''', (f'%{search}%', f'%{search}%'))
        else:
            cursor.execute('SELECT id, title, content, tags, created_at FROM notes ORDER BY created_at DESC')
            
        results = [
            {'id': row[0], 'title': row[1], 'content': row[2], 'tags': row[3], 'created_at': row[4]}
            for row in cursor.fetchall()
        ]
        
        conn.close()
        return results
        
    def delete_note(self, note_id: int):
        """Delete a note"""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        
        cursor.execute('DELETE FROM notes WHERE id = ?', (note_id,))
        
        conn.commit()
        conn.close()
        
    # ==================== UTILITY ====================
    
    def get_stats(self) -> Dict:
        """Get memory statistics"""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        
        cursor.execute('SELECT COUNT(*) FROM conversations')
        conversations = cursor.fetchone()[0]
        
        cursor.execute('SELECT COUNT(*) FROM memories')
        memories = cursor.fetchone()[0]
        
        cursor.execute('SELECT COUNT(*) FROM tasks WHERE completed = 0')
        pending_tasks = cursor.fetchone()[0]
        
        cursor.execute('SELECT COUNT(*) FROM notes')
        notes_count = cursor.fetchone()[0]
        
        conn.close()
        
        return {
            'conversations': conversations,
            'memories': memories,
            'pending_tasks': pending_tasks,
            'notes': notes_count,
            'chroma_available': CHROMADB_AVAILABLE
        }
        
    def clear_old_conversations(self, keep_last: int = 100):
        """Clear old conversation history"""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        
        cursor.execute('''
            DELETE FROM conversations 
            WHERE id NOT IN (
                SELECT id FROM conversations 
                ORDER BY timestamp DESC 
                LIMIT ?
            )
        ''', (keep_last,))
        
        conn.commit()
        deleted = cursor.rowcount
        conn.close()
        
        return deleted


# Singleton
_memory = None

def get_memory() -> Memory:
    """Get memory singleton"""
    global _memory
    if _memory is None:
        _memory = Memory()
    return _memory
