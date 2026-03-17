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
from config import Config
from tools.voice_out import VoiceOutput

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
        cpu = psutil.cpu_percent(interval=0.1)
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

# ── Projects ──────────────────────────────
@app.route('/api/projects', methods=['GET'])
def get_projects():
    return jsonify(project_context.get_all_projects())

@app.route('/api/projects/<project_name>', methods=['POST'])
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

    project_context.load_projects()
    log.info(f"Projects loaded: {len(project_context.projects)}")

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
