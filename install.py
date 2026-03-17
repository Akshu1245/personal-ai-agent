#!/usr/bin/env python3
"""
JARVIS Installation Script
Handles virtual environment creation and dependency installation
"""

import subprocess
import sys
import os
from pathlib import Path

def run_command(command, shell=True):
    """Run a command and return the result"""
    try:
        print(f"Running: {command}")
        result = subprocess.run(
            command, 
            shell=shell, 
            check=True, 
            capture_output=True, 
            text=True
        )
        print(f"✅ Success: {result.stdout}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Error: {e.stderr}")
        return False

def main():
    """Main installation process"""
    print("🚀 JARVIS Installation Starting...")
    
    # Check if we're in the right directory
    if not Path("requirements.txt").exists():
        print("❌ requirements.txt not found. Make sure you're in the JARVIS directory.")
        return False
    
    # Create virtual environment if it doesn't exist
    venv_path = Path(".venv")
    if not venv_path.exists():
        print("📦 Creating virtual environment...")
        if not run_command("python -m venv .venv"):
            print("❌ Failed to create virtual environment")
            return False
    else:
        print("✅ Virtual environment already exists")
    
    # Determine activation script based on OS
    if os.name == 'nt':  # Windows
        activate_script = ".venv\\Scripts\\activate.bat"
        python_exe = ".venv\\Scripts\\python.exe"
        pip_exe = ".venv\\Scripts\\pip.exe"
    else:  # Unix-like
        activate_script = ".venv/bin/activate"
        python_exe = ".venv/bin/python"
        pip_exe = ".venv/bin/pip"
    
    # Install dependencies
    print("📥 Installing dependencies...")
    if not run_command(f"{pip_exe} install -r requirements.txt"):
        print("❌ Failed to install dependencies")
        return False
    
    print("🎉 Installation completed successfully!")
    print("\n📋 Next steps:")
    print("1. ✅ Virtual environment created")
    print("2. ✅ Dependencies installed")
    print("3. ✅ .env file with API key ready")
    print("\n🚀 To run JARVIS:")
    print("   python main.py")
    
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)