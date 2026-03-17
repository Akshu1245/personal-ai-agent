# JARVIS v2.0 — Personal AI Agent (Production-Ready)

## Overview

JARVIS (Just A Rather Very Intelligent System) is a production-grade personal AI assistant built for Akshay. It runs on **Gunicorn + Eventlet** (production WSGI server), uses **Groq's Llama 3.3-70B API** for AI, maintains **long-term memory** in SQLite + ChromaDB, and provides a polished dark-themed web UI with real-time Socket.IO communication.

## Architecture

- **Production Server**: Gunicorn + Eventlet (async WebSocket support)
- **Framework**: Flask + Flask-SocketIO
- **LLM**: Groq API (`llama-3.3-70b-versatile`)
- **Memory**: SQLite (structured) + ChromaDB (vector search)
- **Port**: 5000 (mapped to external port 80)
- **Frontend**: Vanilla JS + Socket.IO + marked.js (markdown)

## Running

```bash
# Development
python main.py

# Production (used by Replit workflow)
gunicorn -c gunicorn.conf.py wsgi:application

# Install from scratch
bash install.sh
```

## Key URLs

| URL | Description |
|-----|-------------|
| `/` | Main JARVIS chat UI |
| `/setup` | First-run setup wizard (4 steps) |
| `/health` | Health check endpoint (JSON) |
| `/api/...` | REST API |

## Project Structure

```
main.py              - Flask app (production): routes, SocketIO, logging
wsgi.py              - Production WSGI entry point (eventlet monkey-patch)
gunicorn.conf.py     - Gunicorn production config (workers, logging, hooks)
install.sh           - One-command installer (creates venv, installs deps, .env)
requirements.txt     - Clean, versioned Python dependencies
.env.example         - Environment variable template
config.py            - Root config loader
core/
  brain.py           - Groq LLM integration + tool parsing
  memory.py          - SQLite + ChromaDB memory (tasks, notes, memories, conv)
  context.py         - Project context manager
  router.py          - Tool dispatch router (30+ tools)
tools/
  pc_control.py      - Desktop automation (graceful degradation)
  voice_in/out.py    - Voice I/O (pyttsx3 + SpeechRecognition)
  web_search.py      - DuckDuckGo search + page scraper
  system_info.py     - psutil system info
  scheduler.py       - APScheduler for reminders
  ... (15+ more tools)
ui/
  templates/
    index.html       - Main chat UI (tabs, suggestions, markdown)
    setup.html       - First-run wizard (4-step: key → settings → check → launch)
    404.html         - Custom 404 page
    500.html         - Custom 500 page
  static/
    style.css        - Dark cyan theme v2.0
    jarvis.js        - Frontend logic (Socket.IO, markdown, tasks, notes)
logs/                - Auto-created: access.log, error.log, jarvis.log
memory/              - Auto-created: SQLite DB + ChromaDB data
data/
  projects.json      - Project definitions
```

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Liveness check (used by load balancers) |
| `/api/status` | GET | API key + model status |
| `/api/chat` | POST | Send message → AI response |
| `/api/chat/clear` | POST | Clear conversation history |
| `/api/system/stats` | GET | Live psutil CPU/RAM/disk/net stats |
| `/api/memory/stats` | GET | Memory DB counts |
| `/api/memory/search` | POST | Full-text + vector memory search |
| `/api/tasks` | GET/POST | List/add tasks |
| `/api/tasks/<id>/complete` | POST | Mark task complete |
| `/api/notes` | GET/POST | List/add notes |
| `/api/notes/<id>` | DELETE | Delete note |
| `/api/projects` | GET | List projects |
| `/api/projects/<name>` | POST | Switch active project |
| `/api/search` | POST | DuckDuckGo web search |

## Production Features

- **Gunicorn + Eventlet**: Single-worker eventlet server for WebSocket support
- **Rate limiting**: 30 requests/min per IP (in-memory)
- **Security headers**: X-Content-Type-Options, X-Frame-Options, X-XSS-Protection
- **Request size cap**: 16MB max upload
- **Rotating logs**: `logs/access.log`, `logs/error.log`, `logs/jarvis.log`
- **Health endpoint**: `/health` returns JSON status for monitoring
- **Custom error pages**: Branded 404 and 500 pages
- **Conversation persistence**: All chats saved to SQLite
- **Setup wizard**: 4-step first-run wizard at `/setup`
- **Auto-detect async**: Uses eventlet if available, falls back to threading

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `GROQ_API_KEY` | **Yes** | — | Groq API key from console.groq.com |
| `GROQ_MODEL` | No | `llama-3.3-70b-versatile` | Groq model |
| `SECRET_KEY` | No | `jarvis-change-this...` | Flask session secret |
| `VOICE_ENABLED` | No | `false` | TTS voice (local only) |
| `DEBUG` | No | `false` | Flask debug mode |
| `USER_NAME` | No | `Akshay` | Agent's owner name |

## Deployment

- **Target**: VM (always-on, persistent state + WebSockets)
- **Run**: `gunicorn -c gunicorn.conf.py wsgi:application`
- **Port**: 5000 → external 80

Click the **Publish** button in Replit to deploy to a `.replit.app` domain.
