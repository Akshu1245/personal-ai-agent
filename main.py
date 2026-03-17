"""
JARVIS - Just A Rather Very Intelligent System
Akshay's Personal AI Desktop Agent
Entry Point - Starts Flask UI + Agent Loop

Author: Rashi AI
Built for: Akshay
"""

import os
import sys
import asyncio
import threading
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))

from flask import Flask, render_template, request, jsonify
from flask_socketio import SocketIO
import uvicorn

from core.brain import ask_jarvis
from core.memory import Memory
from core.context import ProjectContext
from core.config import Config
from tools.voice_in import VoiceInput
from tools.voice_out import VoiceOutput

# Initialize Flask app
app = Flask(__name__, 
            template_folder='ui/templates',
            static_folder='ui/static')
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'jarvis-secret-key-change-me')
socketio = SocketIO(app, cors_allowed_origins="*")

# Initialize core components
config = Config()
memory = Memory()
project_context = ProjectContext()
voice_input = VoiceInput()
voice_output = VoiceOutput()

# Global state
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
    """Main UI page"""
    return render_template('index.html')

@app.route('/api/chat', methods=['POST'])
def chat():
    """Handle text chat with JARVIS"""
    data = request.json
    user_input = data.get('message', '')
    
    # Get conversation context
    context = project_context.get_context()
    history = jarvis_state['conversation_history'][-10:]
    
    # Process through brain
    response = ask_jarvis(user_input, history, context)
    
    # Update history
    jarvis_state['conversation_history'].append({
        'role': 'user', 
        'content': user_input
    })
    jarvis_state['conversation_history'].append({
        'role': 'assistant', 
        'content': response['reply']
    })
    
    jarvis_state['last_command'] = user_input
    
    return jsonify({
        'response': response['reply'],
        'tool_used': response.get('tool', None),
        'success': True
    })

@app.route('/api/voice/input', methods=['POST'])
def voice_input_endpoint():
    """Handle voice input transcription"""
    # For now, return a placeholder - actual implementation needs audio file
    return jsonify({'transcription': '', 'success': False})

@app.route('/api/voice/output', methods=['POST'])
def voice_output_endpoint():
    """Generate voice output"""
    data = request.json
    text = data.get('text', '')
    
    # Generate speech
    voice_output.speak(text)
    
    return jsonify({'success': True})

@app.route('/api/state', methods=['GET'])
def get_state():
    """Get JARVIS current state"""
    return jsonify(jarvis_state)

@app.route('/api/state', methods=['POST'])
def update_state():
    """Update JARVIS state"""
    data = request.json
    for key, value in data.items():
        if key in jarvis_state:
            jarvis_state[key] = value
    return jsonify({'success': True, 'state': jarvis_state})

@app.route('/api/memory/search', methods=['POST'])
def memory_search():
    """Search long-term memory"""
    data = request.json
    query = data.get('query', '')
    results = memory.search(query)
    return jsonify({'results': results})

@app.route('/api/memory/save', methods=['POST'])
def memory_save():
    """Save to long-term memory"""
    data = request.json
    content = data.get('content', '')
    memory.add(content)
    return jsonify({'success': True})

@app.route('/api/projects', methods=['GET'])
def get_projects():
    """Get active projects"""
    return jsonify(project_context.get_all_projects())

@app.route('/api/projects/<project_name>', methods=['POST'])
def switch_project(project_name):
    """Switch to a different project context"""
    project_context.switch_project(project_name)
    jarvis_state['current_project'] = project_name
    return jsonify({'success': True, 'project': project_name})

# ==================== WEBSOCKET EVENTS ====================

@socketio.on('connect')
def handle_connect():
    """Client connected"""
    print(f"Client connected to JARVIS")
    socketio.emit('jarvis_status', {'status': 'online', 'state': jarvis_state})

@socketio.on('disconnect')
def handle_disconnect():
    """Client disconnected"""
    print(f"Client disconnected from JARVIS")

@socketio.on('voice_start')
def handle_voice_start():
    """Start voice listening"""
    jarvis_state['is_listening'] = True
    socketio.emit('jarvis_status', {'listening': True})

@socketio.on('voice_stop')
def handle_voice_stop():
    """Stop voice listening"""
    jarvis_state['is_listening'] = False
    socketio.emit('jarvis_status', {'listening': False})

@socketio.on('transcription')
def handle_transcription(data):
    """Process voice transcription"""
    text = data.get('text', '')
    if text:
        # Process through brain
        context = project_context.get_context()
        history = jarvis_state['conversation_history'][-10:]
        response = ask_jarvis(text, history, context)
        
        # Speak response
        voice_output.speak(response['reply'])
        
        # Emit response
        socketio.emit('jarvis_response', {
            'text': response['reply'],
            'tool': response.get('tool', None)
        })

# ==================== BACKGROUND TASKS ====================

def start_background_tasks():
    """Start background tasks like scheduler"""
    from tools.scheduler import start_scheduler
    scheduler_thread = threading.Thread(target=start_scheduler, daemon=True)
    scheduler_thread.start()
    print("Background scheduler started")

def print_banner():
    """Print JARVIS startup banner"""
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
    ║              Version 1.0                                  ║
    ║              Built for Akshay (Rashi AI)                  ║
    ║                                                           ║
    ╚═══════════════════════════════════════════════════════════╝
    """
    print(banner)

# ==================== MAIN ====================

def main():
    """Main entry point"""
    print_banner()
    
    # Load configuration
    config.load()
    print(f"✅ Configuration loaded")
    print(f"   - Groq Model: {config.groq_model}")
    print(f"   - Voice Enabled: {config.voice_enabled}")
    
    # Initialize memory
    memory.initialize()
    print("✅ Memory system initialized")
    
    # Load projects
    project_context.load_projects()
    print(f"✅ Project context loaded: {len(project_context.projects)} projects")
    
    # Start background tasks
    start_background_tasks()
    
    # Print startup info
    print("\n" + "="*60)
    print("🌐 JARVIS is running!")
    print("="*60)
    print("   Web UI: http://localhost:5000")
    print("   API: http://localhost:5000/api")
    print("\n   Commands:")
    print("   - Type in chat or use voice input")
    print("   - Say 'Hey JARVIS' to activate wake word")
    print("   - Press Ctrl+C to stop\n")
    
    # Run Flask app with SocketIO
    socketio.run(
        app, 
        host='0.0.0.0', 
        port=5000, 
        debug=config.debug,
        allow_unsafe_werkzeug=True
    )

if __name__ == '__main__':
    main()
