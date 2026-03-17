"""
JARVIS - Just A Rather Very Intelligent System
Akshay's Personal AI Desktop Agent
Entry Point - Starts Flask UI + Agent Loop

Author: Rashi AI
Built for: Akshay
"""

import os
import sys
import json
import threading
from pathlib import Path
from datetime import datetime

PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))

from flask import Flask, render_template, request, jsonify, Response, stream_with_context
from flask_socketio import SocketIO

from core.brain import ask_jarvis
from core.memory import Memory
from core.context import ProjectContext
from config import Config
from tools.voice_in import VoiceInput
from tools.voice_out import VoiceOutput

app = Flask(__name__,
            template_folder='ui/templates',
            static_folder='ui/static')
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'jarvis-secret-key-change-me')
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

config = Config()
memory = Memory()
project_context = ProjectContext()
voice_input = VoiceInput()
voice_output = VoiceOutput()

jarvis_state = {
    'is_listening': False,
    'wake_word_enabled': True,
    'focus_mode_active': False,
    'current_project': None,
    'last_command': None,
    'conversation_history': []
}

# ==================== ROUTES ====================

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/status', methods=['GET'])
def api_status():
    """API health + key status"""
    groq_key = os.environ.get('GROQ_API_KEY', '')
    return jsonify({
        'online': True,
        'groq_configured': bool(groq_key),
        'model': config.groq_model,
        'version': '2.0',
        'user': config.user_name
    })

@app.route('/api/chat', methods=['POST'])
def chat():
    data = request.json
    user_input = data.get('message', '')

    context = project_context.get_context()
    history = jarvis_state['conversation_history'][-10:]

    # Emit thinking event
    socketio.emit('jarvis_thinking', {'thinking': True})

    response = ask_jarvis(user_input, history, context)

    jarvis_state['conversation_history'].append({'role': 'user', 'content': user_input})
    jarvis_state['conversation_history'].append({'role': 'assistant', 'content': response['reply']})
    jarvis_state['last_command'] = user_input

    # Emit done thinking
    socketio.emit('jarvis_thinking', {'thinking': False})

    return jsonify({
        'response': response['reply'],
        'tool_used': response.get('tool', None),
        'success': True,
        'timestamp': datetime.now().isoformat()
    })

@app.route('/api/chat/clear', methods=['POST'])
def clear_chat():
    """Clear conversation history"""
    jarvis_state['conversation_history'] = []
    return jsonify({'success': True, 'message': 'Conversation cleared'})

@app.route('/api/voice/input', methods=['POST'])
def voice_input_endpoint():
    return jsonify({'transcription': '', 'success': False})

@app.route('/api/voice/output', methods=['POST'])
def voice_output_endpoint():
    data = request.json
    text = data.get('text', '')
    voice_output.speak(text)
    return jsonify({'success': True})

@app.route('/api/state', methods=['GET'])
def get_state():
    return jsonify(jarvis_state)

@app.route('/api/state', methods=['POST'])
def update_state():
    data = request.json
    for key, value in data.items():
        if key in jarvis_state:
            jarvis_state[key] = value
    return jsonify({'success': True, 'state': jarvis_state})

# ==================== SYSTEM STATS ====================

@app.route('/api/system/stats', methods=['GET'])
def system_stats():
    """Get real system stats via psutil"""
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
    except ImportError:
        return jsonify({'success': False, 'error': 'psutil not available'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

# ==================== MEMORY ====================

@app.route('/api/memory/search', methods=['POST'])
def memory_search():
    data = request.json
    query = data.get('query', '')
    results = memory.search(query)
    return jsonify({'results': results})

@app.route('/api/memory/save', methods=['POST'])
def memory_save():
    data = request.json
    content = data.get('content', '')
    memory.add(content)
    return jsonify({'success': True})

@app.route('/api/memory/stats', methods=['GET'])
def memory_stats():
    """Get memory statistics"""
    stats = memory.get_stats()
    return jsonify(stats)

# ==================== TASKS ====================

@app.route('/api/tasks', methods=['GET'])
def get_tasks():
    """Get all pending tasks"""
    project = request.args.get('project')
    tasks = memory.get_tasks(project=project, completed=False)
    return jsonify({'tasks': tasks, 'count': len(tasks)})

@app.route('/api/tasks', methods=['POST'])
def add_task():
    """Add a new task"""
    data = request.json
    title = data.get('title', '')
    description = data.get('description', '')
    project = data.get('project')
    due_date = data.get('due_date')

    if not title:
        return jsonify({'success': False, 'error': 'Title required'}), 400

    memory.add_task(title, description, project, due_date)
    return jsonify({'success': True, 'message': f'Task added: {title}'})

@app.route('/api/tasks/<int:task_id>/complete', methods=['POST'])
def complete_task(task_id):
    """Mark task as complete"""
    memory.complete_task(task_id)
    return jsonify({'success': True})

# ==================== NOTES ====================

@app.route('/api/notes', methods=['GET'])
def get_notes_api():
    """Get notes from SQLite memory store"""
    notes = memory.get_notes()
    return jsonify({'success': True, 'notes': notes, 'count': len(notes)})

@app.route('/api/notes', methods=['POST'])
def add_note_api():
    """Add a note to SQLite memory store"""
    data = request.json
    title = data.get('title', '')
    content = data.get('content', '')
    tags = data.get('tags', '')
    if not title:
        return jsonify({'success': False, 'error': 'Title required'}), 400
    memory.add_note(title, content, tags)
    return jsonify({'success': True, 'message': f'Note saved: {title}'})

@app.route('/api/notes/<int:note_id>', methods=['DELETE'])
def delete_note_api(note_id):
    """Delete a note"""
    memory.delete_note(note_id)
    return jsonify({'success': True, 'message': f'Note {note_id} deleted'})

# ==================== PROJECTS ====================

@app.route('/api/projects', methods=['GET'])
def get_projects():
    return jsonify(project_context.get_all_projects())

@app.route('/api/projects/<project_name>', methods=['POST'])
def switch_project(project_name):
    project_context.switch_project(project_name)
    jarvis_state['current_project'] = project_name
    socketio.emit('project_switched', {'project': project_name})
    return jsonify({'success': True, 'project': project_name})

# ==================== WEB SEARCH ====================

@app.route('/api/search', methods=['POST'])
def web_search_api():
    """Web search endpoint"""
    from tools.web_search import search
    data = request.json
    query = data.get('query', '')
    results = search(query)
    return jsonify(results)

# ==================== WEBSOCKET EVENTS ====================

@socketio.on('connect')
def handle_connect():
    print(f"Client connected to JARVIS")
    socketio.emit('jarvis_status', {'status': 'online', 'state': jarvis_state})

@socketio.on('disconnect')
def handle_disconnect():
    print(f"Client disconnected from JARVIS")

@socketio.on('voice_start')
def handle_voice_start():
    jarvis_state['is_listening'] = True
    socketio.emit('jarvis_status', {'listening': True})

@socketio.on('voice_stop')
def handle_voice_stop():
    jarvis_state['is_listening'] = False
    socketio.emit('jarvis_status', {'listening': False})

@socketio.on('transcription')
def handle_transcription(data):
    text = data.get('text', '')
    if text:
        context = project_context.get_context()
        history = jarvis_state['conversation_history'][-10:]
        response = ask_jarvis(text, history, context)
        voice_output.speak(response['reply'])
        socketio.emit('jarvis_response', {
            'text': response['reply'],
            'tool': response.get('tool', None)
        })

# ==================== BACKGROUND TASKS ====================

def start_background_tasks():
    from tools.scheduler import start_scheduler
    scheduler_thread = threading.Thread(target=start_scheduler, daemon=True)
    scheduler_thread.start()
    print("Background scheduler started")

def print_banner():
    banner = """
    ╔═══════════════════════════════════════════════════════════╗
    ║                                                           ║
    ║     ██╗   ██╗ ██████╗ ██╗██████╗                        ║
    ║     ██║   ██║██╔═══██╗██║██╔══██╗                       ║
    ║     ██║   ██║██║   ██║██║██║  ██║                       ║
    ║     ╚██╗ ██╔╝██║   ██║██║██║  ██║                       ║
    ║      ╚████╔╝ ╚██████╔╝██║██████╔╝                       ║
    ║       ╚═══╝   ╚═════╝ ╚═╝╚═════╝                        ║
    ║                                                           ║
    ║      Just A Rather Very Intelligent System               ║
    ║              Version 2.0                                  ║
    ║              Built for Akshay (Rashi AI)                  ║
    ║                                                           ║
    ╚═══════════════════════════════════════════════════════════╝
    """
    print(banner)

# ==================== MAIN ====================

def main():
    print_banner()

    config.load()
    print(f"✅ Configuration loaded")
    print(f"   - Groq Model: {config.groq_model}")
    print(f"   - Voice Enabled: {config.voice_enabled}")

    memory.initialize()
    print("✅ Memory system initialized")

    project_context.load_projects()
    print(f"✅ Project context loaded: {len(project_context.projects)} projects")

    start_background_tasks()

    print("\n" + "="*60)
    print("🌐 JARVIS v2.0 is running!")
    print("="*60)
    print("   Web UI: http://localhost:5000")
    print("   API: http://localhost:5000/api")
    print("\n   Press Ctrl+C to stop\n")

    socketio.run(
        app,
        host='0.0.0.0',
        port=5000,
        debug=config.debug,
        allow_unsafe_werkzeug=True
    )

if __name__ == '__main__':
    main()
