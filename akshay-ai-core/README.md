# AKSHAY AI CORE

> Personal AI Operating System — A modular, secure, extensible intelligence system

[![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-green.svg)](https://fastapi.tiangolo.com)
[![License](https://img.shields.io/badge/License-Proprietary-red.svg)]()

## 🎯 Overview

AKSHAY AI CORE is not a chatbot. It's a **Personal AI Operating System** that:

- 🧠 **Thinks with memory** — Long-term semantic, event, and secure memory systems
- 🛠️ **Controls tools** — Plugin-based tool execution with sandboxing
- ⚡ **Automates workflows** — Scheduled jobs, triggers, and background workers
- 🔐 **Protects access** — Face auth, encryption, role-based permissions
- 🔌 **Grows via plugins** — Extensible architecture for unlimited capabilities

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    ACCESS & SECURITY                     │
│         Face Auth │ PIN │ Voice Lock │ RBAC             │
├─────────────────────────────────────────────────────────┤
│                       AI BRAIN                           │
│    LLM Abstraction │ Memory System │ Truth-Check        │
├─────────────────────────────────────────────────────────┤
│                    COMMAND ENGINE                        │
│    NL Parser │ Task Planner │ Tool Router │ Executor    │
├─────────────────────────────────────────────────────────┤
│   PLUGINS    │   AUTOMATION   │      INTERFACE          │
│  Extensible  │   Scheduler    │   Desktop/Mobile/Voice  │
└─────────────────────────────────────────────────────────┘
```

## 🚀 Quick Start

### Prerequisites

- Python 3.11+
- Node.js 18+ (for web UI)
- Flutter 3.16+ (for desktop/mobile)
- Redis (optional, for caching)

### Installation

```bash
# Clone and setup
cd akshay-ai-core

# Create virtual environment
python -m venv venv
.\venv\Scripts\activate  # Windows
source venv/bin/activate  # Linux/Mac

# Install dependencies
pip install -r requirements.txt

# Setup environment
copy .env.example .env
# Edit .env with your API keys

# Initialize database
python -m core.init_db

# Run the system
python main.py
```

### First Run

1. System will prompt for initial face registration
2. Set your PIN as fallback
3. Configure your preferred AI model
4. Start using natural language commands

## 📁 Project Structure

```
akshay-ai-core/
├── core/                    # Core system modules
│   ├── brain/              # AI brain (LLM, memory, reasoning)
│   ├── security/           # Auth, encryption, permissions
│   ├── command/            # Command parsing and execution
│   └── config/             # Configuration management
├── plugins/                 # Plugin system
│   ├── builtin/            # Built-in plugins
│   └── custom/             # User plugins
├── automation/             # Automation engine
├── api/                    # FastAPI backend
├── ui/                     # User interfaces
│   ├── web/               # React web dashboard
│   └── flutter/           # Flutter desktop/mobile
├── data/                   # Data storage (gitignored)
├── logs/                   # System logs (gitignored)
├── tests/                  # Test suite
└── docs/                   # Documentation
```

## 🔐 Security Features

- **Face Authentication** — MediaPipe-based facial recognition
- **AES-256 Encryption** — All sensitive data encrypted at rest
- **Role-Based Access** — Granular permission system
- **Immutable Audit Logs** — Tamper-proof activity logging
- **Emergency Voice Lock** — Say "LOCK SYSTEM" to instantly secure

## 🧠 AI Capabilities

- **Multi-Model Support** — OpenAI, Claude, Gemini, Ollama (local)
- **Long-Term Memory** — Remember everything with semantic search
- **Context Compression** — Weekly summaries to maintain efficiency
- **Truth-Check Mode** — Challenge assumptions and verify claims

## 🔌 Plugin System

Create custom plugins easily:

```python
from core.plugins import Plugin, PluginConfig

class MyPlugin(Plugin):
    config = PluginConfig(
        name="my_plugin",
        version="1.0.0",
        permissions=["file_read", "network"]
    )
    
    async def execute(self, command: str, params: dict):
        # Your plugin logic here
        return {"status": "success", "data": result}
```

## 📊 Built-in Plugins

| Plugin | Description |
|--------|-------------|
| `web_automation` | Browser automation with Playwright |
| `system_control` | OS-level commands and control |
| `esp32_iot` | Smart device control via ESP32 |
| `file_vault` | Encrypted file storage |
| `cyber_tools` | Security analysis tools |
| `data_analysis` | Data processing and visualization |

## 🤖 Automation

```yaml
# Example automation rule
- name: "Daily Backup"
  trigger:
    type: schedule
    cron: "0 2 * * *"
  actions:
    - plugin: file_vault
      command: backup
      params:
        source: "~/Documents"
        encrypt: true
```

## 📱 Interfaces

- **Desktop Dashboard** — Full-featured control center
- **Mobile App** — On-the-go access and monitoring
- **Voice Terminal** — Hands-free operation
- **Admin Panel** — System configuration and monitoring
- **Flow Visualizer** — Real-time decision tree visualization

## 🧪 Testing

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=core --cov-report=html

# Run specific module tests
pytest tests/test_brain.py -v
```

## 📝 License

Proprietary — AKSHAY AI CORE © 2024-2026

## 🛣️ Roadmap

- [x] Phase 1: System Skeleton
- [ ] Phase 2: Core Brain
- [ ] Phase 3: Security Core
- [ ] Phase 4: Automation Engine
- [ ] Phase 5: User Interfaces
- [ ] Phase 6: Plugin Marketplace
- [ ] Phase 7: Cloud Sync (Optional)

---

**AKSHAY AI CORE** — Your Personal AI Operating System
