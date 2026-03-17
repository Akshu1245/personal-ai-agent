# JARVIS v2.0 — Market-Ready Personal AI Agent

## Overview

JARVIS (Just A Rather Very Intelligent System) is a market-ready, installable personal AI assistant. Anyone can deploy it, personalise it, and import their entire AI conversation history from ChatGPT, Claude, Gemini, or plain text. Runs on **Gunicorn + Eventlet**, uses **Groq's Llama 3.3-70B API**, maintains long-term memory in **SQLite + ChromaDB**, and is installable as a **PWA desktop app** or via **Windows one-click installer**.

## Architecture

- **Production Server**: Gunicorn + Eventlet (async WebSocket)
- **Framework**: Flask + Flask-SocketIO
- **LLM**: Groq API (`llama-3.3-70b-versatile` — configurable per user)
- **Memory**: SQLite (structured) + ChromaDB (vector search)
- **Frontend**: Vanilla JS + Socket.IO + marked.js (markdown)
- **Install**: PWA (any OS) + JARVIS-Setup.bat (Windows)

## Running

```bash
# Production (Replit workflow)
gunicorn -c gunicorn.conf.py wsgi:application

# Development
python main.py

# Windows one-click install
JARVIS-Setup.bat
```

## Key URLs

| URL | Description |
|-----|-------------|
| `/` | Main JARVIS chat UI |
| `/setup` | First-run setup wizard |
| `/health` | Health check endpoint (JSON) |
| `/manifest.json` | PWA manifest |
| `/sw.js` | Service worker (root scope) |
| `/api/...` | REST API |

## Project Structure

```
main.py              - Flask app (all routes, singletons init at module level)
wsgi.py              - Production WSGI entry (eventlet monkey-patch)
gunicorn.conf.py     - Gunicorn config
install.sh           - Linux/Mac installer
JARVIS-Setup.bat     - Windows one-click installer
Launch-JARVIS.bat    - Windows launcher (desktop shortcut target)
core/
  brain.py           - Groq LLM + tool parsing
  memory.py          - SQLite+ChromaDB: conversations, memories, tasks, notes, projects, profile, imports
  importer.py        - AI export parser (ChatGPT, Claude, Gemini, text)
  context.py         - Project context manager
  router.py          - Tool dispatch
tools/               - 15+ automation tools
ui/
  templates/
    index.html       - Main UI (5 sidebar tabs, 4 modals)
    setup.html       - First-run wizard
    404.html / 500.html
  static/
    style.css        - Dark cyan theme
    jarvis.js        - Frontend (profile, projects, memory browser, import, teach)
    manifest.json    - PWA manifest
    sw.js            - Service worker
    icons/           - PWA icons (10 sizes, maskable, apple-touch)
memory/              - SQLite DB + ChromaDB data (auto-created)
logs/                - access.log, error.log, jarvis.log (auto-created)
data/projects.json   - Seed data (migrated to SQLite on first run)
```

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Liveness check |
| `/api/status` | GET | API key + model status |
| `/api/chat` | POST | AI chat |
| `/api/chat/clear` | POST | Clear conversation |
| `/api/profile` | GET/POST | User profile (name, model) |
| `/api/system/stats` | GET | Live CPU/RAM/disk |
| `/api/memory/stats` | GET | Memory DB counts |
| `/api/memory/browse` | GET | Browse/search memories (paginated) |
| `/api/memory/teach` | POST | Manually add a memory |
| `/api/memory/<id>` | DELETE | Delete a memory |
| `/api/memory/import` | POST | Import from file or paste (ChatGPT/Claude/Gemini/text) |
| `/api/memory/import/history` | GET | Import log |
| `/api/tasks` | GET/POST | Tasks |
| `/api/tasks/<id>/complete` | POST | Complete task |
| `/api/notes` | GET/POST | Notes |
| `/api/notes/<id>` | DELETE | Delete note |
| `/api/projects` | GET/POST | List/create projects |
| `/api/projects/<id>` | GET/PUT/DELETE | Project CRUD |
| `/api/projects/<name>/switch` | POST | Switch active context |
| `/api/search` | POST | Web search |

## SQLite Tables

| Table | Contents |
|-------|----------|
| `conversations` | Chat history |
| `memories` | Long-term memories (source, category, importance) |
| `tasks` | Tasks with project links |
| `notes` | Notes with tags |
| `projects` | Full project info (name, stack, goals, URL, path, status, priority) |
| `user_profile` | Name, model preference, theme |
| `memory_imports` | Import log (source, filename, count, timestamp) |

## UI Features

- **5 sidebar tabs**: System / Projects / Memory / Tasks / Notes
- **Profile modal**: Name + AI model selection, avatar with initial
- **Projects tab**: Full CRUD — add/edit/delete projects with goals, stack, URL, path
- **Memory tab**: Browse/search all memories, filter by source, delete, + Teach + Import buttons
- **Import modal**: Drag & drop or paste — ChatGPT, Claude, Gemini, text auto-detected
- **Teach modal**: Manually add any fact/preference/context JARVIS should remember
- **PWA install banner**: Appears at bottom on first visit, installs as native app

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `GROQ_API_KEY` | **Yes** | — | Groq API key (console.groq.com) |
| `GROQ_MODEL` | No | `llama-3.3-70b-versatile` | LLM model |
| `SECRET_KEY` | No | auto | Flask session secret |
| `DEBUG` | No | `false` | Debug mode |

## Deployment

- **Target**: VM (persistent state + WebSockets)
- **Run**: `gunicorn -c gunicorn.conf.py wsgi:application`
- Click **Publish** in Replit → live `.replit.app` domain → users can install as PWA
