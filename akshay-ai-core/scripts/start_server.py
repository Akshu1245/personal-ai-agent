"""
============================================================
AKSHAY AI CORE — Quick Start Server
============================================================
Starts both API backend and Web UI on localhost.
============================================================
"""

import sys
import os
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))
os.chdir(project_root)

def main():
    import uvicorn
    from fastapi import FastAPI
    from fastapi.middleware.cors import CORSMiddleware
    from fastapi.responses import HTMLResponse, JSONResponse
    from fastapi.staticfiles import StaticFiles
    
    # Create combined app
    app = FastAPI(
        title="AKSHAY AI CORE",
        version="1.0.0",
        description="Personal AI Operating System"
    )
    
    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Import the web UI
    try:
        from ui.web.app import create_web_app
        web_app = create_web_app()
        app.mount("/ui", web_app)
        print("[OK] Web UI mounted at /ui")
    except Exception as e:
        print(f"[WARN] Could not mount Web UI: {e}")
    
    # Health check
    @app.get("/health")
    async def health():
        return {"status": "healthy", "version": "1.0.0"}
    
    # System status API
    @app.get("/api/status")
    async def system_status():
        return {
            "status": "running",
            "mode": "normal",
            "version": "1.0.0",
            "components": {
                "api": "online",
                "ui": "online",
                "policy_engine": "ready",
                "key_store": "locked"
            }
        }
    
    # System status with metrics (for UI dashboard)
    @app.get("/api/system/status")
    async def system_status_detailed():
        import psutil
        return {
            "status": "running",
            "mode": "normal", 
            "version": "1.0.0",
            "system": {
                "cpu_percent": psutil.cpu_percent(interval=0.1),
                "memory_percent": psutil.virtual_memory().percent,
                "disk_percent": psutil.disk_usage('/').percent
            },
            "components": {
                "api": "online",
                "ui": "online",
                "policy_engine": "ready",
                "key_store": "locked"
            }
        }
    
    # Simple chat API endpoint
    @app.post("/api/chat")
    async def chat(request: dict):
        message = request.get("message", "")
        return {
            "response": f"Hello! You said: '{message}'. The AI system is running but LLM is not configured.",
            "status": "success"
        }
    
    # Root redirect to UI
    @app.get("/", response_class=HTMLResponse)
    async def root():
        return """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AKSHAY AI CORE</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%);
            min-height: 100vh;
            display: flex;
            justify-content: center;
            align-items: center;
            color: #fff;
        }
        .container {
            text-align: center;
            padding: 40px;
            background: rgba(255,255,255,0.05);
            border-radius: 20px;
            backdrop-filter: blur(10px);
            border: 1px solid rgba(255,255,255,0.1);
            max-width: 600px;
        }
        h1 {
            font-size: 3rem;
            margin-bottom: 10px;
            background: linear-gradient(90deg, #00d9ff, #00ff88);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }
        .subtitle { color: #888; margin-bottom: 30px; }
        .status {
            display: inline-block;
            padding: 8px 20px;
            background: #00ff8833;
            border: 1px solid #00ff88;
            border-radius: 20px;
            color: #00ff88;
            margin-bottom: 30px;
        }
        .links { display: flex; gap: 15px; justify-content: center; flex-wrap: wrap; }
        .links a {
            padding: 12px 30px;
            background: linear-gradient(135deg, #00d9ff, #00ff88);
            color: #1a1a2e;
            text-decoration: none;
            border-radius: 10px;
            font-weight: 600;
            transition: transform 0.2s, box-shadow 0.2s;
        }
        .links a:hover {
            transform: translateY(-2px);
            box-shadow: 0 10px 30px rgba(0,217,255,0.3);
        }
        .links a.secondary {
            background: transparent;
            border: 2px solid #00d9ff;
            color: #00d9ff;
        }
        .info {
            margin-top: 30px;
            padding: 20px;
            background: rgba(0,0,0,0.2);
            border-radius: 10px;
            text-align: left;
        }
        .info h3 { color: #00d9ff; margin-bottom: 10px; }
        .info code {
            background: #000;
            padding: 2px 8px;
            border-radius: 4px;
            font-family: monospace;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>AKSHAY AI CORE</h1>
        <p class="subtitle">Personal AI Operating System v1.0.0</p>
        <div class="status">● System Online</div>
        <div class="links">
            <a href="/ui">Open Dashboard</a>
            <a href="/ui/chat">Chat Interface</a>
            <a href="/docs" class="secondary">API Docs</a>
        </div>
        <div class="info">
            <h3>Quick Start</h3>
            <p>• Dashboard: <code>http://localhost:8000/ui</code></p>
            <p>• Chat: <code>http://localhost:8000/ui/chat</code></p>
            <p>• API: <code>http://localhost:8000/api/status</code></p>
        </div>
    </div>
</body>
</html>
"""
    
    print("\n" + "="*60)
    print("  AKSHAY AI CORE - Server Starting")
    print("="*60)
    print(f"\n  Dashboard:  http://localhost:8000/ui")
    print(f"  Chat:       http://localhost:8000/ui/chat")
    print(f"  API:        http://localhost:8000/api/status")
    print(f"  Health:     http://localhost:8000/health")
    print("\n" + "="*60 + "\n")
    
    uvicorn.run(app, host="127.0.0.1", port=8000, log_level="info")


if __name__ == "__main__":
    main()
