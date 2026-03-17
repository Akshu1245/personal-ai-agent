"""
JARVIS — Just A Rather Very Intelligent System
Personal AI Desktop Agent for Akshay
Production-ready Flask + Socket.IO backend

Author: Rashi AI
Built for: Akshay
Version: 2.0
"""

import os
import sys
import logging
import threading
from pathlib import Path
from datetime import datetime

# ── Force UTF-8 output so Unicode banners/emoji don't crash on Windows cp1252 ──
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))

# ── Logging setup (must happen before Flask imports) ──
LOG_DIR = PROJECT_ROOT / 'logs'
LOG_DIR.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s %(name)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(LOG_DIR / 'jarvis.log', encoding='utf-8'),
    ]
)
log = logging.getLogger('jarvis')

# Silence noisy loggers in production
logging.getLogger('werkzeug').setLevel(logging.WARNING)
logging.getLogger('engineio').setLevel(logging.WARNING)
logging.getLogger('socketio').setLevel(logging.WARNING)

# ── Flask app ─────────────────────────────
from flask import Flask, render_template, request, jsonify, redirect, url_for
from flask_socketio import SocketIO

from core.brain import ask_jarvis
from core.memory import Memory
from core.context import ProjectContext
from core.importer import parse_import
from config import Config
from tools.voice_out import VoiceOutput
from tools.computer_use import ComputerUseAgent

app = Flask(__name__,
            template_folder='ui/templates',
            static_folder='ui/static')

app.config.update(
    SECRET_KEY=os.environ.get('SECRET_KEY', 'jarvis-change-this-in-production'),
    MAX_CONTENT_LENGTH=16 * 1024 * 1024,  # 16 MB max upload
    JSON_SORT_KEYS=False,
)

# Auto-detect async mode: eventlet if available, else threading
try:
    import eventlet
    ASYNC_MODE = 'eventlet'
except ImportError:
    ASYNC_MODE = 'threading'

socketio = SocketIO(
    app,
    cors_allowed_origins="*",
    async_mode=ASYNC_MODE,
    ping_timeout=60,
    ping_interval=25,
    max_http_buffer_size=10 * 1024 * 1024
)

# ── Core singletons ───────────────────────
config = Config()
memory = Memory()
project_context = ProjectContext()
voice_output = VoiceOutput()

# ── Computer use agent (singleton, one task at a time) ────
computer_agent = ComputerUseAgent()

# ── Module-level startup (runs under gunicorn too) ────────
config.load()
memory.initialize()
_json_path = PROJECT_ROOT / 'data' / 'projects.json'
memory.seed_projects_from_json(str(_json_path))
try:
    project_context.load_projects()
except Exception:
    pass

# ── App state ─────────────────────────────
jarvis_state = {
    'is_listening': False,
    'focus_mode_active': False,
    'current_project': None,
    'last_command': None,
    'conversation_history': []
}

# ── Simple rate limiter ───────────────────
from collections import defaultdict
import time
_rate_store = defaultdict(list)

def is_rate_limited(ip: str, limit: int = 30, window: int = 60) -> bool:
    now = time.time()
    _rate_store[ip] = [t for t in _rate_store[ip] if now - t < window]
    if len(_rate_store[ip]) >= limit:
        return True
    _rate_store[ip].append(now)
    return False

# ── Security headers ──────────────────────
@app.after_request
def security_headers(response):
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'SAMEORIGIN'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
    return response

# ═══════════════════════════════════════════
#  ROUTES
# ═══════════════════════════════════════════

@app.route('/')
def index():
    groq_key = os.environ.get('GROQ_API_KEY', '')
    if not groq_key:
        return render_template('index.html', setup_needed=True)
    return render_template('index.html', setup_needed=False)

@app.route('/setup')
def setup_page():
    """First-run setup wizard"""
    return render_template('setup.html')

@app.route('/sw.js')
def service_worker():
    """Service worker served from root so it can control the full scope"""
    resp = app.send_static_file('sw.js')
    resp.headers['Content-Type'] = 'application/javascript'
    resp.headers['Service-Worker-Allowed'] = '/'
    resp.headers['Cache-Control'] = 'no-cache'
    return resp

@app.route('/manifest.json')
def pwa_manifest():
    """PWA manifest"""
    resp = app.send_static_file('manifest.json')
    resp.headers['Content-Type'] = 'application/manifest+json'
    return resp

@app.route('/health')
def health():
    """Health check — used by load balancers and monitoring"""
    groq_key = os.environ.get('GROQ_API_KEY', '')
    return jsonify({
        'status': 'healthy',
        'version': '2.0',
        'timestamp': datetime.utcnow().isoformat() + 'Z',
        'groq_configured': bool(groq_key),
        'async_mode': ASYNC_MODE,
    }), 200

# ── API Status ────────────────────────────
@app.route('/api/status', methods=['GET'])
def api_status():
    groq_key = os.environ.get('GROQ_API_KEY', '')
    return jsonify({
        'online': True,
        'groq_configured': bool(groq_key),
        'model': config.groq_model,
        'version': '2.0',
        'user': config.user_name,
        'async_mode': ASYNC_MODE,
    })

# ── Chat ──────────────────────────────────
@app.route('/api/chat', methods=['POST'])
def chat():
    ip = request.remote_addr
    if is_rate_limited(ip):
        return jsonify({'error': 'Rate limit exceeded. Please slow down.'}), 429

    data = request.json or {}
    user_input = data.get('message', '').strip()

    if not user_input:
        return jsonify({'error': 'Message cannot be empty'}), 400

    if len(user_input) > 8000:
        return jsonify({'error': 'Message too long (max 8000 chars)'}), 400

    context = project_context.get_context()
    history = jarvis_state['conversation_history'][-10:]

    socketio.emit('jarvis_thinking', {'thinking': True})

    try:
        response = ask_jarvis(user_input, history, context)
        reply = response.get('reply', 'I had trouble processing that.')
        tool_used = response.get('tool', None)
    except Exception as e:
        log.error(f"Brain error: {e}", exc_info=True)
        reply = "I encountered an error while thinking. Please try again."
        tool_used = None
    finally:
        socketio.emit('jarvis_thinking', {'thinking': False})

    jarvis_state['conversation_history'].append({'role': 'user', 'content': user_input})
    jarvis_state['conversation_history'].append({'role': 'assistant', 'content': reply})
    jarvis_state['last_command'] = user_input

    # Persist to memory
    try:
        memory.add_conversation('user', user_input)
        memory.add_conversation('assistant', reply)
    except Exception as e:
        log.warning(f"Memory persist error: {e}")

    log.info(f"Chat | user={ip[:8]}... | len={len(user_input)} | tool={tool_used}")

    return jsonify({
        'response': reply,
        'tool_used': tool_used,
        'success': True,
        'timestamp': datetime.now().isoformat()
    })

@app.route('/api/chat/clear', methods=['POST'])
def clear_chat():
    jarvis_state['conversation_history'] = []
    return jsonify({'success': True, 'message': 'Conversation cleared'})

# ── Voice ─────────────────────────────────
@app.route('/api/voice/output', methods=['POST'])
def voice_output_endpoint():
    data = request.json or {}
    text = data.get('text', '')[:500]
    if text:
        threading.Thread(target=voice_output.speak, args=(text,), daemon=True).start()
    return jsonify({'success': True})

# ── State ─────────────────────────────────
@app.route('/api/state', methods=['GET'])
def get_state():
    return jsonify(jarvis_state)

@app.route('/api/state', methods=['POST'])
def update_state():
    data = request.json or {}
    for key, value in data.items():
        if key in jarvis_state:
            jarvis_state[key] = value
    return jsonify({'success': True})

# ── System Stats ──────────────────────────
@app.route('/api/system/stats', methods=['GET'])
def system_stats():
    try:
        import psutil
        import threading
        
        # Use non-blocking call
        cpu = psutil.cpu_percent(interval=None)
        mem = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        net = psutil.net_io_counters()
        return jsonify({
            'success': True,
            'cpu': {
                'percent': cpu,
                'cores': psutil.cpu_count(logical=True)
            },
            'memory': {
                'percent': mem.percent,
                'used_gb': round(mem.used / (1024**3), 1),
                'total_gb': round(mem.total / (1024**3), 1)
            },
            'disk': {
                'percent': disk.percent,
                'used_gb': round(disk.used / (1024**3), 1),
                'total_gb': round(disk.total / (1024**3), 1)
            },
            'network': {
                'bytes_sent_mb': round(net.bytes_sent / (1024**2), 1),
                'bytes_recv_mb': round(net.bytes_recv / (1024**2), 1)
            }
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

# ── Memory ────────────────────────────────
@app.route('/api/memory/stats', methods=['GET'])
def memory_stats():
    try:
        return jsonify(memory.get_stats())
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/memory/search', methods=['POST'])
def memory_search():
    data = request.json or {}
    query = data.get('query', '')
    results = memory.search(query)
    return jsonify({'results': results})

@app.route('/api/memory/save', methods=['POST'])
def memory_save():
    data = request.json or {}
    content = data.get('content', '')
    if content:
        memory.add(content)
    return jsonify({'success': True})

# ── Tasks ─────────────────────────────────
@app.route('/api/tasks', methods=['GET'])
def get_tasks():
    project = request.args.get('project')
    tasks = memory.get_tasks(project=project, completed=False)
    return jsonify({'tasks': tasks, 'count': len(tasks)})

@app.route('/api/tasks', methods=['POST'])
def add_task():
    data = request.json or {}
    title = data.get('title', '').strip()
    if not title:
        return jsonify({'success': False, 'error': 'Title required'}), 400
    memory.add_task(
        title=title,
        description=data.get('description', ''),
        project=data.get('project') or None,
        due_date=data.get('due_date') or None
    )
    log.info(f"Task added: {title}")
    return jsonify({'success': True, 'message': f'Task added: {title}'})

@app.route('/api/tasks/<int:task_id>/complete', methods=['POST'])
def complete_task(task_id):
    memory.complete_task(task_id)
    return jsonify({'success': True})

# ── Notes ─────────────────────────────────
@app.route('/api/notes', methods=['GET'])
def get_notes_api():
    notes = memory.get_notes()
    return jsonify({'success': True, 'notes': notes, 'count': len(notes)})

@app.route('/api/notes', methods=['POST'])
def add_note_api():
    data = request.json or {}
    title = data.get('title', '').strip()
    if not title:
        return jsonify({'success': False, 'error': 'Title required'}), 400
    memory.add_note(title, data.get('content', ''), data.get('tags', ''))
    return jsonify({'success': True, 'message': f'Note saved: {title}'})

@app.route('/api/notes/<int:note_id>', methods=['DELETE'])
def delete_note_api(note_id):
    memory.delete_note(note_id)
    return jsonify({'success': True})

# ── Memory Browse / Teach / Delete ────────
@app.route('/api/memory/browse', methods=['GET'])
def browse_memories():
    category = request.args.get('category')
    source   = request.args.get('source')
    limit    = int(request.args.get('limit', 50))
    offset   = int(request.args.get('offset', 0))
    q        = request.args.get('q', '').strip()
    if q:
        items = memory.search(q, limit=limit)
    else:
        items = memory.get_all_memories(category=category, source=source, limit=limit, offset=offset)
    sources = memory.get_memory_sources()
    return jsonify({'memories': items, 'sources': sources, 'total': len(items)})

@app.route('/api/memory/teach', methods=['POST'])
def teach_memory():
    data = request.json or {}
    content  = data.get('content', '').strip()
    category = data.get('category', 'user-taught').strip() or 'user-taught'
    importance = int(data.get('importance', 3))
    if not content:
        return jsonify({'success': False, 'error': 'Content required'}), 400
    memory.add(content, category=category, importance=importance, source='manual')
    return jsonify({'success': True, 'message': 'Memory saved'})

@app.route('/api/memory/<int:memory_id>', methods=['DELETE'])
def delete_memory(memory_id):
    memory.delete_memory(memory_id)
    return jsonify({'success': True})

@app.route('/api/memory/import', methods=['POST'])
def import_memory():
    # Support both JSON body and file upload
    source_hint = request.args.get('source', 'auto')

    if request.files.get('file'):
        f = request.files['file']
        filename = f.filename or 'upload'
        try:
            content = f.read().decode('utf-8', errors='replace')
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 400
    else:
        data = request.json or {}
        content  = data.get('content', '')
        filename = data.get('filename', 'manual')
        source_hint = data.get('source', 'auto')

    if not content.strip():
        return jsonify({'success': False, 'error': 'No content provided'}), 400

    memories, detected = parse_import(content, filename, source=source_hint)
    if not memories:
        return jsonify({'success': False, 'error': 'No memories could be extracted from the file'}), 400

    # Limit to 2000 items per import
    memories = memories[:2000]
    category = f"imported-{detected}"
    memory.bulk_add(memories, category=category, source=detected)
    memory.log_import(detected, filename, len(memories))
    log.info(f"Memory import: {len(memories)} items from '{filename}' (format: {detected})")
    return jsonify({
        'success': True,
        'imported': len(memories),
        'format': detected,
        'preview': memories[:3]
    })

@app.route('/api/memory/import/history', methods=['GET'])
def import_history():
    return jsonify(memory.get_import_history())

# ── Projects ──────────────────────────────
@app.route('/api/projects', methods=['GET'])
def get_projects():
    return jsonify(memory.get_projects())

@app.route('/api/projects', methods=['POST'])
def create_project():
    data = request.json or {}
    name = data.get('name', '').strip()
    if not name:
        return jsonify({'success': False, 'error': 'Project name required'}), 400
    try:
        tech = data.get('tech', [])
        if isinstance(tech, str):
            tech = [t.strip() for t in tech.split(',') if t.strip()]
        new_id = memory.add_project(
            name=name,
            description=data.get('description', ''),
            stack=data.get('stack', ''),
            tech=tech,
            goals=data.get('goals', ''),
            url=data.get('url', ''),
            path=data.get('path', ''),
            status=data.get('status', 'active'),
            priority=data.get('priority', 'medium'),
            color=data.get('color', '#00d4ff'),
        )
        return jsonify({'success': True, 'id': new_id})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 400

@app.route('/api/projects/<int:project_id>', methods=['GET'])
def get_project(project_id):
    p = memory.get_project(project_id)
    if not p:
        return jsonify({'error': 'Project not found'}), 404
    return jsonify(p)

@app.route('/api/projects/<int:project_id>', methods=['PUT'])
def update_project(project_id):
    data = request.json or {}
    if 'tech' in data and isinstance(data['tech'], str):
        data['tech'] = [t.strip() for t in data['tech'].split(',') if t.strip()]
    memory.update_project(project_id, data)
    return jsonify({'success': True})

@app.route('/api/projects/<int:project_id>', methods=['DELETE'])
def delete_project(project_id):
    memory.delete_project(project_id)
    return jsonify({'success': True})

@app.route('/api/projects/<project_name>/switch', methods=['POST'])
def switch_project(project_name):
    project_context.switch_project(project_name)
    jarvis_state['current_project'] = project_name
    socketio.emit('project_switched', {'project': project_name})
    return jsonify({'success': True, 'project': project_name})

# ── Web Search ────────────────────────────
@app.route('/api/search', methods=['POST'])
def web_search_api():
    data = request.json or {}
    query = data.get('query', '')
    if not query:
        return jsonify({'success': False, 'error': 'Query required'}), 400
    from tools.web_search import search
    return jsonify(search(query))

# ═══════════════════════════════════════════
#  ERROR HANDLERS
# ═══════════════════════════════════════════

@app.errorhandler(404)
def not_found(e):
    if request.path.startswith('/api/'):
        return jsonify({'error': 'Endpoint not found', 'path': request.path}), 404
    return render_template('404.html'), 404

@app.errorhandler(429)
def rate_limited(e):
    return jsonify({'error': 'Too many requests. Please slow down.'}), 429

@app.errorhandler(500)
def server_error(e):
    log.error(f"500 error: {e}", exc_info=True)
    if request.path.startswith('/api/'):
        return jsonify({'error': 'Internal server error'}), 500
    return render_template('500.html'), 500

# ═══════════════════════════════════════════
#  SOCKET.IO EVENTS
# ═══════════════════════════════════════════

# ═══════════════════════════════════════════
#  COMPUTER USE AGENT ROUTES
# ═══════════════════════════════════════════

@app.route('/api/computer-use/screenshot', methods=['GET'])
def cu_screenshot():
    """Take a screenshot and return it as base64 for the live preview."""
    from tools.pc_control import PYAUTOGUI_AVAILABLE
    if not PYAUTOGUI_AVAILABLE:
        return jsonify({
            'success': False,
            'error': 'pyautogui not available — run JARVIS locally via JARVIS-Setup.bat'
        }), 200
    b64 = computer_agent.take_screenshot()
    if b64:
        return jsonify({'success': True, 'screenshot': b64})
    return jsonify({'success': False, 'error': 'Screenshot failed'})


@app.route('/api/computer-use/run', methods=['POST'])
def cu_run():
    """Start a computer use agent task (runs in background thread, streams via Socket.IO)."""
    if computer_agent.running:
        return jsonify({'success': False, 'error': 'Agent already running — stop it first'}), 400

    data = request.json or {}
    task = (data.get('task') or '').strip()
    max_steps = min(int(data.get('max_steps', 25)), 50)

    if not task:
        return jsonify({'success': False, 'error': 'task is required'}), 400

    groq_key = os.environ.get('GROQ_API_KEY', '')
    if not groq_key:
        return jsonify({'success': False, 'error': 'GROQ_API_KEY not set'}), 400

    try:
        from groq import Groq
        computer_agent.groq_client = Groq(api_key=groq_key)
    except Exception as e:
        return jsonify({'success': False, 'error': f'Groq init failed: {e}'}), 500

    def on_step(step_info):
        payload = {
            'step': step_info['step'],
            'description': step_info.get('description', ''),
            'action_type': step_info.get('action', {}).get('type', ''),
            'result': step_info.get('result', {}),
            'error': step_info.get('error', ''),
            'screenshot': step_info.get('screenshot', ''),
        }
        socketio.emit('cu_step', payload)

    def on_screenshot(b64, step_num):
        socketio.emit('cu_screenshot', {'screenshot': b64, 'step': step_num})

    def run_task():
        socketio.emit('cu_started', {'task': task, 'max_steps': max_steps})
        result = computer_agent.run(
            task=task,
            max_steps=max_steps,
            on_step=on_step,
            on_screenshot=on_screenshot,
        )
        socketio.emit('cu_finished', {
            'success': result.get('success', False),
            'message': result.get('message', ''),
            'error': result.get('error', ''),
            'stopped': result.get('stopped', False),
            'total_steps': len(result.get('steps', [])),
        })

    t = threading.Thread(target=run_task, daemon=True)
    t.start()

    return jsonify({'success': True, 'message': f'Agent started on task: {task}'})


@app.route('/api/computer-use/stop', methods=['POST'])
def cu_stop():
    """Stop the running computer use agent."""
    computer_agent.stop()
    return jsonify({'success': True, 'message': 'Stop signal sent'})


@app.route('/api/computer-use/status', methods=['GET'])
def cu_status():
    """Return current agent status."""
    return jsonify({
        'running': computer_agent.running,
        'task': computer_agent.current_task,
        'steps_taken': len(computer_agent.steps),
        'pyautogui_available': bool(__import__('tools.pc_control', fromlist=['PYAUTOGUI_AVAILABLE']).PYAUTOGUI_AVAILABLE),
    })


@socketio.on('connect')
def handle_connect():
    log.info(f"Socket.IO client connected")
    socketio.emit('jarvis_status', {'status': 'online', 'version': '2.0'})

@socketio.on('disconnect')
def handle_disconnect():
    log.info(f"Socket.IO client disconnected")

@socketio.on('voice_start')
def handle_voice_start():
    jarvis_state['is_listening'] = True
    socketio.emit('jarvis_status', {'listening': True})

@socketio.on('voice_stop')
def handle_voice_stop():
    jarvis_state['is_listening'] = False
    socketio.emit('jarvis_status', {'listening': False})

# ═══════════════════════════════════════════
#  STARTUP
# ═══════════════════════════════════════════

def start_background_tasks():
    try:
        from tools.scheduler import start_scheduler
        t = threading.Thread(target=start_scheduler, daemon=True)
        t.start()
        log.info("Background scheduler started")
    except Exception as e:
        log.warning(f"Scheduler start failed: {e}")

def _print_banner():
    banner = r"""
    ╔═══════════════════════════════════════════════════╗
    ║   ██╗ █████╗ ██████╗ ██╗   ██╗██╗███████╗       ║
    ║   ██║██╔══██╗██╔══██╗██║   ██║██║██╔════╝       ║
    ║   ██║███████║██████╔╝██║   ██║██║███████╗       ║
    ║██ ██║██╔══██║██╔══██╗╚██╗ ██╔╝██║╚════██║       ║
    ║╚████╔╝██║  ██║██║  ██║ ╚████╔╝ ██║███████║       ║
    ║ ╚═══╝ ╚═╝  ╚═╝╚═╝  ╚═╝  ╚═══╝  ╚═╝╚══════╝      ║
    ║    Just A Rather Very Intelligent System  v2.0   ║
    ║                Built for Akshay                   ║
    ╚═══════════════════════════════════════════════════╝
"""
    print(banner)

def main():
    _print_banner()
    config.load()
    log.info(f"Model: {config.groq_model} | Async: {ASYNC_MODE} | Debug: {config.debug}")

    memory.initialize()
    log.info("Memory initialized")

    # One-time migration: seed projects from JSON into SQLite
    json_path = PROJECT_ROOT / 'data' / 'projects.json'
    seeded = memory.seed_projects_from_json(str(json_path))
    if seeded:
        log.info(f"Seeded {seeded} projects from projects.json")

    project_context.load_projects()
    log.info(f"Projects loaded: {len(project_context.projects)}")

    profile = memory.get_profile()
    log.info(f"User profile: {profile.get('name', 'User')}")

    start_background_tasks()

    print("\n" + "=" * 55)
    print("🌐  JARVIS v2.0 — http://localhost:5000")
    print("📋  Setup wizard — http://localhost:5000/setup")
    print("❤️   Health check — http://localhost:5000/health")
    print("=" * 55 + "\n")

    socketio.run(
        app,
        host='0.0.0.0',
        port=5000,
        debug=config.debug,
        allow_unsafe_werkzeug=True,
        use_reloader=False
    )

if __name__ == '__main__':
    main()
