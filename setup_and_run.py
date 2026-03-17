#!/usr/bin/env python
"""
JARVIS Quick Setup Script
Installs dependencies and starts the application
"""
import os
import sys
import subprocess
from pathlib import Path

def run_command(cmd, description):
    """Run a command and handle errors"""
    print(f"🔄 {description}")
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, cwd=Path(__file__).parent)
        if result.returncode != 0:
            print(f"❌ Error: {result.stderr}")
            return False
        print(f"✅ {description} - Done")
        return True
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def main():
    print("=" * 50)
    print("🤖 JARVIS - Personal AI Agent")
    print("🚀 Quick Setup and Launch")
    print("=" * 50)
    
    # Check Python version
    python_version = sys.version_info
    if python_version.major < 3 or (python_version.major == 3 and python_version.minor < 8):
        print("❌ Python 3.8+ required. Current version:", sys.version)
        return False
    
    print(f"✅ Python {python_version.major}.{python_version.minor} detected")
    
    # Install dependencies
    if not run_command("python -m pip install --upgrade pip", "Upgrading pip"):
        return False
    
    if not run_command("python -m pip install -r requirements.txt", "Installing dependencies"):
        return False
    
    # Create directories
    dirs = ["logs", "memory/data", "memory/chroma_db", "data", "journal"]
    for dir_name in dirs:
        Path(dir_name).mkdir(parents=True, exist_ok=True)
    print("✅ Created directories")
    
    # Check .env file
    env_file = Path(".env")
    if not env_file.exists():
        print("⚠️  .env file not found - using defaults")
        print("📝 To set up your Groq API key, edit the .env file")
    
    print("\n" + "=" * 50)
    print("🎉 Setup complete!")
    print("🌐 Starting JARVIS on http://localhost:5000")
    print("=" * 50)
    
    # Start the application
    try:
        subprocess.run("python main.py", shell=True, cwd=Path(__file__).parent)
    except KeyboardInterrupt:
        print("\n👋 JARVIS stopped")
    
if __name__ == "__main__":
    main()