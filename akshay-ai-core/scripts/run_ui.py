import sys
import os
# Ensure project root is on path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from ui.web.app import create_web_app
import uvicorn

if __name__ == '__main__':
    app = create_web_app()
    uvicorn.run(app, host='127.0.0.1', port=3000, log_level='info')
