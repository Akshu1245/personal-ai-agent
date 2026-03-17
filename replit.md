# JARVIS v2.0 — Personal AI Desktop Agent

## Overview

JARVIS (Just A Rather Very Intelligent System) is a personal AI assistant built for Akshay. It uses Groq's LLM API (Llama 3.3-70B) and provides a dark-themed web chat interface with real system monitoring, long-term memory, task/notes management, voice I/O, and project context switching.

## Architecture

- **Backend**: Python 3.12 + Flask + Flask-SocketIO (WebSocket support)
- **LLM**: Groq API (`llama-3.3-70b-versatile`)
- **Memory**: SQLite (structured) + ChromaDB (vector search)
- **Port**: 5000
- **Frontend**: Vanilla JS + Socket.IO + marked.js for markdown rendering

## Project Structure

```
main.py              - Entry point, Flask app v2.0 with all routes + SocketIO
config.py            - Root-level config (used by main.py)
core/
  brain.py           - LLM integration (Groq), tool parsing, reasoning
  config.py          - Core config class (loaded from environment)
  memory.py          - SQLite + ChromaDB memory system (tasks, notes, memories)
  context.py         - Project context manager
  router.py          - Tool dispatch router (30+ tools)
tools/
  pc_control.py      - Mouse/keyboard/screenshot automation (pyautogui)
  voice_in.py        - Speech-to-text (SpeechRecognition)
  voice_out.py       - Text-to-speech (pyttsx3)
  scheduler.py       - APScheduler for reminders/briefings
  browser.py         - Web browser automation
  file_ops.py        - File system operations
  web_search.py      - DuckDuckGo web search + page scraping
  notes.py           - Notes management (JSON file, legacy)
  system_info.py     - psutil system info
  crypto_watch.py    - Cardano price watcher
  focus_mode.py      - Focus/Pomodoro timer
  clipboard.py       - Clipboard operations
  code_runner.py     - Python code execution
  github_ops.py      - Git/GitHub operations
ui/
  templates/
    index.html       - Full UI with sidebar tabs, suggestions, markdown support
  static/
    style.css        - Dark cyan theme v2.0
    jarvis.js        - Frontend logic v2.0
data/
  projects.json      - Project definitions (5 projects)
memory/              - Auto-created: SQLite DB + ChromaDB data
```

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/status` | GET | Health + API key check |
| `/api/chat` | POST | Send message, get AI response |
| `/api/chat/clear` | POST | Clear conversation history |
| `/api/system/stats` | GET | Real psutil CPU/RAM/disk stats |
| `/api/memory/stats` | GET | Count of conversations/memories/tasks/notes |
| `/api/memory/search` | POST | Vector+SQL memory search |
| `/api/tasks` | GET | List pending tasks |
| `/api/tasks` | POST | Add a task |
| `/api/tasks/<id>/complete` | POST | Mark task complete |
| `/api/notes` | GET | List notes |
| `/api/notes` | POST | Add a note |
| `/api/notes/<id>` | DELETE | Delete a note |
| `/api/projects` | GET | List projects |
| `/api/projects/<name>` | POST | Switch active project |
| `/api/search` | POST | Web search |

## Frontend Features (v2.0)

- Real-time system stats (CPU/RAM/Disk bars using psutil)
- Typing/thinking indicator with animated dots
- Markdown rendering for bot messages (headers, code, lists, links)
- Sidebar tabs: System / Tasks / Notes
- Task management: add, view, complete tasks (stored in SQLite)
- Notes management: add, view, delete notes (stored in SQLite)  
- Quick action buttons (screenshot, focus mode, Cardano price, etc.)
- Project switcher with priority colors
- Memory stats dashboard
- Copy button on all bot messages
- Toast notifications for feedback
- Suggestion chips for quick starts
- API key missing warning banner
- Animated JARVIS icon with pulsing arcs
- Auto-resize textarea input

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `GROQ_API_KEY` | **Yes** | - | Groq API key from console.groq.com |
| `GROQ_MODEL` | No | `llama-3.3-70b-versatile` | Groq model to use |
| `SECRET_KEY` | No | `jarvis-secret-key-change-me` | Flask session secret |
| `VOICE_ENABLED` | No | `true` | Enable voice I/O |
| `DEBUG` | No | `false` | Flask debug mode |

## Running the App

```bash
python main.py
```

App runs on `0.0.0.0:5000`.

## Key Notes

- **pyautogui** and **pynput** require a display/X server — gracefully degrade in server environments
- **pyttsx3** voice output works if TTS engine is available; falls back to print
- **ChromaDB** is used for vector memory search if available
- **GROQ_API_KEY** must be set as a Replit Secret for AI chat to work
- Notes and tasks stored in SQLite (not the legacy JSON files)
- System stats auto-refresh every 8 seconds
- Memory stats refresh every 30 seconds

## Replit Configuration

- Workflow: `python main.py` on port 5000 (webview)
- Deployment target: `vm` (uses WebSockets + persistent state)
