"""
JARVIS Production WSGI Entry Point
Eventlet monkey-patching must happen before all other imports.

Run in production with:
    gunicorn -w 1 -k eventlet --bind 0.0.0.0:5000 wsgi:application

Author: Rashi AI — Built for Akshay
"""

import eventlet
eventlet.monkey_patch()

from main import app, socketio

# Expose WSGI-compatible application
application = app

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5000)
