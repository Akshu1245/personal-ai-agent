# JARVIS - Personal AI Desktop Agent

## Overview

JARVIS (Just A Rather Very Intelligent System) is a personal AI assistant built for Akshay. It uses Groq's LLM API (Llama 3.3-70B) and provides a web-based chat interface with voice I/O support, long-term memory, PC automation, and project management.

## Architecture

- **Backend**: Python 3.12 + Flask + Flask-SocketIO (WebSocket support)
- **LLM**: Groq API (`llama-3.3-70b-versatile`)
- **Memory**: SQLite (structured) + ChromaDB (vector search)
- **Port**: 5000

## Project Structure

```
main.py              - Entry point, Flask app + WebSocket handlers
config.py            - Root-level config (used by main.py)
core/
  brain.py           - LLM integration (Groq), tool parsing, reasoning
  config.py          - Core config class (loaded from environment)
  memory.py          - SQLite + ChromaDB memory system
  context.py         - Project context manager
  router.py          - Tool dispatch router
tools/
  pc_control.py      - Mouse/keyboard/screenshot automation (pyautogui)
  voice_in.py        - Speech-to-text (SpeechRecognition)
  voice_out.py       - Text-to-speech (pyttsx3)
  scheduler.py       - APScheduler for reminders/briefings
  browser.py         - Web browser automation
  file_ops.py        - File system operations
  web_search.py      - Web search
  notes.py           - Notes management
  ... (many more tools)
ui/
  templates/         - Jinja2 HTML templates (index.html)
  static/            - CSS and JS assets
data/
  projects.json      - Project definitions
memory/              - Auto-created: SQLite DB + ChromaDB data
```

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `GROQ_API_KEY` | Yes | - | Groq API key from console.groq.com |
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

- **pyautogui** and **pynput** require a display/X server - they gracefully degrade in server environments
- **pyttsx3** voice output works if a TTS engine is available; otherwise falls back to print
- **ChromaDB** is used for vector memory search if available
- **GROQ_API_KEY** must be set for the AI chat functionality to work

## Replit Configuration

- Workflow: `python main.py` on port 5000 (webview)
- Deployment: vm target (uses WebSockets + persistent state)
