"""
============================================================
AKSHAY AI CORE — Web Dashboard Application
============================================================
FastAPI-based web interface with real-time updates.
============================================================
"""

from pathlib import Path
from typing import Optional

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from core.config import settings

# Paths
UI_DIR = Path(__file__).parent
STATIC_DIR = UI_DIR / "static"
TEMPLATES_DIR = UI_DIR / "templates"


def create_web_app() -> FastAPI:
    """Create the web dashboard application."""
    app = FastAPI(
        title="AKSHAY AI CORE Dashboard",
        version=settings.APP_VERSION,
        docs_url=None,
        redoc_url=None,
    )
    
    # Mount static files
    if STATIC_DIR.exists():
        app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
    
    # Templates
    templates = None
    if TEMPLATES_DIR.exists():
        templates = Jinja2Templates(directory=TEMPLATES_DIR)
    
    @app.get("/", response_class=HTMLResponse)
    async def dashboard(request: Request):
        """Main dashboard page."""
        if templates:
            return templates.TemplateResponse(
                "dashboard.html",
                {"request": request, "title": "AKSHAY AI CORE"},
            )
        return HTMLResponse(content=get_inline_dashboard())
    
    @app.get("/chat", response_class=HTMLResponse)
    async def chat_page(request: Request):
        """Chat interface page."""
        if templates:
            return templates.TemplateResponse(
                "chat.html",
                {"request": request, "title": "AKSHAY Chat"},
            )
        return HTMLResponse(content=get_inline_chat())
    
    @app.get("/plugins", response_class=HTMLResponse)
    async def plugins_page(request: Request):
        """Plugin management page."""
        if templates:
            return templates.TemplateResponse(
                "plugins.html",
                {"request": request, "title": "Plugins"},
            )
        return HTMLResponse(content=get_inline_plugins())
    
    @app.get("/automation", response_class=HTMLResponse)
    async def automation_page(request: Request):
        """Automation rules page."""
        if templates:
            return templates.TemplateResponse(
                "automation.html",
                {"request": request, "title": "Automation"},
            )
        return HTMLResponse(content=get_inline_automation())
    
    @app.get("/settings", response_class=HTMLResponse)
    async def settings_page(request: Request):
        """Settings page."""
        if templates:
            return templates.TemplateResponse(
                "settings.html",
                {"request": request, "title": "Settings"},
            )
        return HTMLResponse(content=get_inline_settings())
    
    return app


def get_inline_dashboard() -> str:
    """Inline dashboard HTML."""
    return """
<!DOCTYPE html>
<html lang="en" data-theme="dark">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AKSHAY AI CORE</title>
    <link href="https://cdn.jsdelivr.net/npm/daisyui@4.4.19/dist/full.min.css" rel="stylesheet">
    <script src="https://cdn.tailwindcss.com"></script>
    <script src="https://unpkg.com/htmx.org@1.9.10"></script>
    <script src="https://unpkg.com/alpinejs@3.x.x/dist/cdn.min.js" defer></script>
    <style>
        .glow { box-shadow: 0 0 20px rgba(0, 255, 255, 0.3); }
        .pulse { animation: pulse 2s infinite; }
        @keyframes pulse {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.5; }
        }
    </style>
</head>
<body class="min-h-screen bg-base-300">
    <!-- Navbar -->
    <div class="navbar bg-base-100 shadow-lg">
        <div class="flex-1">
            <a class="btn btn-ghost text-xl text-primary">
                <span class="text-2xl">🤖</span> AKSHAY AI CORE
            </a>
        </div>
        <div class="flex-none gap-2">
            <div class="badge badge-success gap-2">
                <span class="pulse">●</span> Online
            </div>
            <div class="dropdown dropdown-end">
                <div tabindex="0" role="button" class="btn btn-ghost btn-circle avatar">
                    <div class="w-10 rounded-full bg-primary flex items-center justify-center">
                        <span class="text-lg">A</span>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <!-- Main Content -->
    <div class="container mx-auto p-4">
        <!-- Stats -->
        <div class="stats shadow w-full mb-6">
            <div class="stat">
                <div class="stat-figure text-primary">
                    <svg class="w-8 h-8" fill="currentColor" viewBox="0 0 20 20">
                        <path d="M13 6a3 3 0 11-6 0 3 3 0 016 0zM18 8a2 2 0 11-4 0 2 2 0 014 0zM14 15a4 4 0 00-8 0v3h8v-3z"/>
                    </svg>
                </div>
                <div class="stat-title">Active Sessions</div>
                <div class="stat-value text-primary" id="stat-sessions">1</div>
            </div>
            <div class="stat">
                <div class="stat-figure text-secondary">
                    <svg class="w-8 h-8" fill="currentColor" viewBox="0 0 20 20">
                        <path d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"/>
                    </svg>
                </div>
                <div class="stat-title">Plugins Active</div>
                <div class="stat-value text-secondary" id="stat-plugins">6</div>
            </div>
            <div class="stat">
                <div class="stat-figure text-accent">
                    <svg class="w-8 h-8" fill="currentColor" viewBox="0 0 20 20">
                        <path d="M10 2a8 8 0 100 16 8 8 0 000-16zm1 12H9v-2h2v2zm0-4H9V6h2v4z"/>
                    </svg>
                </div>
                <div class="stat-title">Memories</div>
                <div class="stat-value text-accent" id="stat-memories">0</div>
            </div>
            <div class="stat">
                <div class="stat-figure text-info">
                    <svg class="w-8 h-8" fill="currentColor" viewBox="0 0 20 20">
                        <path d="M3 4a1 1 0 011-1h12a1 1 0 011 1v2a1 1 0 01-1 1H4a1 1 0 01-1-1V4zM3 10a1 1 0 011-1h6a1 1 0 011 1v6a1 1 0 01-1 1H4a1 1 0 01-1-1v-6z"/>
                    </svg>
                </div>
                <div class="stat-title">Automations</div>
                <div class="stat-value text-info" id="stat-automations">0</div>
            </div>
        </div>

        <!-- Grid -->
        <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            <!-- Quick Chat -->
            <div class="card bg-base-100 shadow-xl col-span-2">
                <div class="card-body">
                    <h2 class="card-title">
                        <span>💬</span> Quick Chat
                    </h2>
                    <div class="h-64 overflow-y-auto bg-base-200 rounded-lg p-4" id="chat-messages">
                        <div class="chat chat-start">
                            <div class="chat-bubble chat-bubble-primary">
                                Hello! I'm AKSHAY, your AI assistant. How can I help you today?
                            </div>
                        </div>
                    </div>
                    <div class="join w-full">
                        <input type="text" id="chat-input" placeholder="Type a message..." 
                               class="input input-bordered join-item flex-1"
                               onkeypress="if(event.key==='Enter')sendMessage()">
                        <button class="btn btn-primary join-item" onclick="sendMessage()">Send</button>
                    </div>
                </div>
            </div>

            <!-- System Status -->
            <div class="card bg-base-100 shadow-xl">
                <div class="card-body">
                    <h2 class="card-title">
                        <span>📊</span> System Status
                    </h2>
                    <div class="space-y-4">
                        <div>
                            <div class="flex justify-between mb-1">
                                <span>CPU</span>
                                <span id="cpu-value">0%</span>
                            </div>
                            <progress class="progress progress-primary" id="cpu-bar" value="0" max="100"></progress>
                        </div>
                        <div>
                            <div class="flex justify-between mb-1">
                                <span>Memory</span>
                                <span id="mem-value">0%</span>
                            </div>
                            <progress class="progress progress-secondary" id="mem-bar" value="0" max="100"></progress>
                        </div>
                        <div>
                            <div class="flex justify-between mb-1">
                                <span>Disk</span>
                                <span id="disk-value">0%</span>
                            </div>
                            <progress class="progress progress-accent" id="disk-bar" value="0" max="100"></progress>
                        </div>
                    </div>
                </div>
            </div>

            <!-- Quick Actions -->
            <div class="card bg-base-100 shadow-xl">
                <div class="card-body">
                    <h2 class="card-title">
                        <span>⚡</span> Quick Actions
                    </h2>
                    <div class="grid grid-cols-2 gap-2">
                        <button class="btn btn-outline btn-primary" onclick="executeCommand('screenshot')">
                            📸 Screenshot
                        </button>
                        <button class="btn btn-outline btn-secondary" onclick="executeCommand('lock')">
                            🔒 Lock
                        </button>
                        <button class="btn btn-outline btn-accent" onclick="executeCommand('status')">
                            📊 Status
                        </button>
                        <button class="btn btn-outline btn-info" onclick="executeCommand('search')">
                            🔍 Search
                        </button>
                    </div>
                </div>
            </div>

            <!-- Recent Activity -->
            <div class="card bg-base-100 shadow-xl col-span-2">
                <div class="card-body">
                    <h2 class="card-title">
                        <span>📋</span> Recent Activity
                    </h2>
                    <div class="overflow-x-auto">
                        <table class="table table-zebra">
                            <thead>
                                <tr>
                                    <th>Time</th>
                                    <th>Action</th>
                                    <th>Status</th>
                                </tr>
                            </thead>
                            <tbody id="activity-table">
                                <tr>
                                    <td>Now</td>
                                    <td>System initialized</td>
                                    <td><span class="badge badge-success">Success</span></td>
                                </tr>
                            </tbody>
                        </table>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <!-- Footer -->
    <footer class="footer footer-center p-4 bg-base-100 text-base-content mt-8">
        <aside>
            <p>AKSHAY AI CORE v1.0.0 — Personal AI Operating System</p>
        </aside>
    </footer>

    <script>
        // WebSocket connection
        let ws = null;
        
        function connectWebSocket() {
            const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
            ws = new WebSocket(`${protocol}//${window.location.host}/api/ws`);
            
            ws.onmessage = function(event) {
                const data = JSON.parse(event.data);
                handleMessage(data);
            };
            
            ws.onclose = function() {
                setTimeout(connectWebSocket, 3000);
            };
        }
        
        function handleMessage(data) {
            if (data.type === 'chat_response') {
                addChatMessage(data.content, 'start');
            } else if (data.type === 'status_update') {
                updateStatus(data);
            }
        }
        
        function sendMessage() {
            const input = document.getElementById('chat-input');
            const message = input.value.trim();
            
            if (!message) return;
            
            addChatMessage(message, 'end');
            input.value = '';
            
            fetch('/api/brain/chat', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({message: message})
            })
            .then(r => r.json())
            .then(data => {
                addChatMessage(data.response || data.error, 'start');
            });
        }
        
        function addChatMessage(content, align) {
            const container = document.getElementById('chat-messages');
            const div = document.createElement('div');
            div.className = `chat chat-${align}`;
            div.innerHTML = `<div class="chat-bubble ${align === 'end' ? '' : 'chat-bubble-primary'}">${content}</div>`;
            container.appendChild(div);
            container.scrollTop = container.scrollHeight;
        }
        
        function executeCommand(cmd) {
            fetch(`/api/brain/command`, {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({command: cmd})
            })
            .then(r => r.json())
            .then(data => {
                addActivity(cmd, data.status || 'executed');
            });
        }
        
        function addActivity(action, status) {
            const table = document.getElementById('activity-table');
            const row = table.insertRow(0);
            row.innerHTML = `
                <td>${new Date().toLocaleTimeString()}</td>
                <td>${action}</td>
                <td><span class="badge badge-${status === 'success' ? 'success' : 'warning'}">${status}</span></td>
            `;
        }
        
        function updateStatus(data) {
            if (data.cpu) {
                document.getElementById('cpu-value').textContent = data.cpu + '%';
                document.getElementById('cpu-bar').value = data.cpu;
            }
            if (data.memory) {
                document.getElementById('mem-value').textContent = data.memory + '%';
                document.getElementById('mem-bar').value = data.memory;
            }
            if (data.disk) {
                document.getElementById('disk-value').textContent = data.disk + '%';
                document.getElementById('disk-bar').value = data.disk;
            }
        }
        
        // Initialize
        document.addEventListener('DOMContentLoaded', function() {
            // connectWebSocket();
            
            // Fetch initial stats
            fetch('/api/system/status')
                .then(r => r.json())
                .then(data => {
                    if (data.system) {
                        updateStatus({
                            cpu: Math.round(data.system.cpu_percent || 0),
                            memory: Math.round(data.system.memory_percent || 0),
                            disk: Math.round(data.system.disk_percent || 0)
                        });
                    }
                });
        });
    </script>
</body>
</html>
"""


def get_inline_chat() -> str:
    """Inline chat page HTML."""
    return """
<!DOCTYPE html>
<html lang="en" data-theme="dark">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AKSHAY Chat</title>
    <link href="https://cdn.jsdelivr.net/npm/daisyui@4.4.19/dist/full.min.css" rel="stylesheet">
    <script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="min-h-screen bg-base-300 flex flex-col">
    <div class="navbar bg-base-100">
        <a href="/" class="btn btn-ghost">← Back</a>
        <span class="text-xl font-bold ml-4">💬 Chat with AKSHAY</span>
    </div>
    
    <div class="flex-1 container mx-auto p-4 flex flex-col">
        <div class="flex-1 bg-base-100 rounded-lg p-4 overflow-y-auto" id="messages">
            <div class="chat chat-start">
                <div class="chat-bubble chat-bubble-primary">
                    Hello! I'm AKSHAY. Ask me anything or give me a command.
                </div>
            </div>
        </div>
        
        <div class="mt-4 join w-full">
            <input type="text" id="input" placeholder="Type your message..." 
                   class="input input-bordered join-item flex-1"
                   onkeypress="if(event.key==='Enter')send()">
            <button class="btn btn-primary join-item" onclick="send()">Send</button>
        </div>
    </div>
    
    <script>
        async function send() {
            const input = document.getElementById('input');
            const msg = input.value.trim();
            if (!msg) return;
            
            addMessage(msg, 'end');
            input.value = '';
            
            const res = await fetch('/api/brain/chat', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({message: msg})
            });
            const data = await res.json();
            addMessage(data.response || data.error, 'start');
        }
        
        function addMessage(text, align) {
            const div = document.createElement('div');
            div.className = `chat chat-${align}`;
            div.innerHTML = `<div class="chat-bubble ${align === 'start' ? 'chat-bubble-primary' : ''}">${text}</div>`;
            document.getElementById('messages').appendChild(div);
            div.scrollIntoView();
        }
    </script>
</body>
</html>
"""


def get_inline_plugins() -> str:
    """Inline plugins page HTML."""
    return """
<!DOCTYPE html>
<html lang="en" data-theme="dark">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Plugins - AKSHAY</title>
    <link href="https://cdn.jsdelivr.net/npm/daisyui@4.4.19/dist/full.min.css" rel="stylesheet">
    <script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="min-h-screen bg-base-300">
    <div class="navbar bg-base-100">
        <a href="/" class="btn btn-ghost">← Back</a>
        <span class="text-xl font-bold ml-4">🔌 Plugin Manager</span>
    </div>
    
    <div class="container mx-auto p-4">
        <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4" id="plugins">
            <!-- Plugins loaded here -->
        </div>
    </div>
    
    <script>
        async function loadPlugins() {
            const res = await fetch('/api/plugins/');
            const data = await res.json();
            
            const container = document.getElementById('plugins');
            container.innerHTML = data.plugins.map(p => `
                <div class="card bg-base-100 shadow-xl">
                    <div class="card-body">
                        <h2 class="card-title">${p.id}</h2>
                        <p class="text-sm opacity-70">v${p.version || '1.0.0'}</p>
                        <p>${p.description || 'No description'}</p>
                        <div class="card-actions justify-end">
                            <span class="badge badge-${p.status === 'loaded' ? 'success' : 'warning'}">${p.status}</span>
                        </div>
                    </div>
                </div>
            `).join('');
        }
        
        loadPlugins();
    </script>
</body>
</html>
"""


def get_inline_automation() -> str:
    """Inline automation page HTML."""
    return """
<!DOCTYPE html>
<html lang="en" data-theme="dark">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Automation - AKSHAY</title>
    <link href="https://cdn.jsdelivr.net/npm/daisyui@4.4.19/dist/full.min.css" rel="stylesheet">
    <script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="min-h-screen bg-base-300">
    <div class="navbar bg-base-100">
        <a href="/" class="btn btn-ghost">← Back</a>
        <span class="text-xl font-bold ml-4">⚙️ Automation Rules</span>
        <button class="btn btn-primary ml-auto" onclick="showCreateModal()">+ New Rule</button>
    </div>
    
    <div class="container mx-auto p-4">
        <div class="overflow-x-auto">
            <table class="table bg-base-100">
                <thead>
                    <tr>
                        <th>Name</th>
                        <th>Trigger</th>
                        <th>Status</th>
                        <th>Actions</th>
                    </tr>
                </thead>
                <tbody id="rules">
                    <tr>
                        <td colspan="4" class="text-center opacity-50">No rules configured</td>
                    </tr>
                </tbody>
            </table>
        </div>
    </div>
    
    <dialog id="createModal" class="modal">
        <div class="modal-box">
            <h3 class="font-bold text-lg">Create Automation Rule</h3>
            <form method="dialog">
                <div class="form-control">
                    <label class="label">Name</label>
                    <input type="text" class="input input-bordered" id="ruleName">
                </div>
                <div class="form-control">
                    <label class="label">Trigger Type</label>
                    <select class="select select-bordered" id="triggerType">
                        <option value="schedule">Schedule (Cron)</option>
                        <option value="interval">Interval</option>
                        <option value="event">Event</option>
                        <option value="keyword">Keyword</option>
                    </select>
                </div>
                <div class="modal-action">
                    <button class="btn">Cancel</button>
                    <button class="btn btn-primary" onclick="createRule()">Create</button>
                </div>
            </form>
        </div>
    </dialog>
    
    <script>
        function showCreateModal() {
            document.getElementById('createModal').showModal();
        }
        
        async function loadRules() {
            const res = await fetch('/api/automation/rules');
            const data = await res.json();
            
            const tbody = document.getElementById('rules');
            if (data.rules && data.rules.length > 0) {
                tbody.innerHTML = data.rules.map(r => `
                    <tr>
                        <td>${r.name}</td>
                        <td>${r.trigger_type}</td>
                        <td><span class="badge badge-${r.is_enabled ? 'success' : 'warning'}">${r.is_enabled ? 'Enabled' : 'Disabled'}</span></td>
                        <td>
                            <button class="btn btn-sm btn-ghost" onclick="toggleRule('${r.id}')">Toggle</button>
                            <button class="btn btn-sm btn-error" onclick="deleteRule('${r.id}')">Delete</button>
                        </td>
                    </tr>
                `).join('');
            }
        }
        
        loadRules();
    </script>
</body>
</html>
"""


def get_inline_settings() -> str:
    """Inline settings page HTML."""
    return """
<!DOCTYPE html>
<html lang="en" data-theme="dark">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Settings - AKSHAY</title>
    <link href="https://cdn.jsdelivr.net/npm/daisyui@4.4.19/dist/full.min.css" rel="stylesheet">
    <script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="min-h-screen bg-base-300">
    <div class="navbar bg-base-100">
        <a href="/" class="btn btn-ghost">← Back</a>
        <span class="text-xl font-bold ml-4">⚙️ Settings</span>
    </div>
    
    <div class="container mx-auto p-4">
        <div class="card bg-base-100 shadow-xl">
            <div class="card-body">
                <h2 class="card-title">AI Settings</h2>
                <div class="form-control">
                    <label class="label">AI Provider</label>
                    <select class="select select-bordered">
                        <option>OpenAI</option>
                        <option>Anthropic</option>
                        <option>Google</option>
                        <option>Ollama (Local)</option>
                    </select>
                </div>
                <div class="form-control">
                    <label class="label">Default Model</label>
                    <input type="text" class="input input-bordered" value="gpt-4">
                </div>
                <div class="form-control">
                    <label class="label">Temperature</label>
                    <input type="range" min="0" max="100" value="70" class="range">
                </div>
            </div>
        </div>
        
        <div class="card bg-base-100 shadow-xl mt-4">
            <div class="card-body">
                <h2 class="card-title">Security</h2>
                <div class="form-control">
                    <label class="cursor-pointer label">
                        <span class="label-text">Enable Face Authentication</span>
                        <input type="checkbox" class="toggle toggle-primary" checked>
                    </label>
                </div>
                <div class="form-control">
                    <label class="cursor-pointer label">
                        <span class="label-text">Enable PIN Authentication</span>
                        <input type="checkbox" class="toggle toggle-primary" checked>
                    </label>
                </div>
                <div class="form-control">
                    <label class="cursor-pointer label">
                        <span class="label-text">Voice Lock Phrase</span>
                        <input type="checkbox" class="toggle toggle-primary">
                    </label>
                </div>
            </div>
        </div>
        
        <div class="mt-4">
            <button class="btn btn-primary">Save Settings</button>
        </div>
    </div>
</body>
</html>
"""
