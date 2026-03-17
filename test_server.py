"""
Simple JARVIS test runner - bypasses problematic components
"""
import os
import sys
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))

# Set up basic logging
import logging
logging.basicConfig(level=logging.INFO, format='[%(asctime)s] %(levelname)s: %(message)s')
log = logging.getLogger('jarvis_test')

# Try to start Flask without complex components
try:
    from flask import Flask, render_template, jsonify
    from flask_socketio import SocketIO
    
    app = Flask(__name__, 
                template_folder='ui/templates',
                static_folder='ui/static')
    
    app.config['SECRET_KEY'] = 'test_key_for_jarvis'
    
    # Simple SocketIO setup without eventlet
    socketio = SocketIO(app, cors_allowed_origins="*", logger=False, engineio_logger=False)
    
    @app.route('/')
    def home():
        return '''
        <html>
        <head><title>JARVIS Test</title></head>
        <body>
            <h1>🤖 JARVIS is Running!</h1>
            <p>Basic Flask server is working</p>
            <p>Time to add the full features back</p>
            <a href="/health">Health Check</a>
        </body>
        </html>
        '''
    
    @app.route('/health')
    def health():
        return jsonify({
            'status': 'ok',
            'message': 'JARVIS basic server is running',
            'version': '2.0-test'
        })
    
    if __name__ == '__main__':
        print("=" * 50)
        print("🧪 JARVIS Test Server Starting...")
        print("🌐 Open: http://localhost:5000")
        print("❤️  Health: http://localhost:5000/health")
        print("=" * 50)
        
        # Run simple server
        socketio.run(app, 
                    host='localhost', 
                    port=5000, 
                    debug=False,
                    allow_unsafe_werkzeug=True)

except Exception as e:
    log.error(f"Failed to start test server: {e}")
    import traceback
    traceback.print_exc()
    input("Press Enter to exit...")