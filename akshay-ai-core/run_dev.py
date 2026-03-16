#!/usr/bin/env python3
"""
AKSHAY AI CORE - Quick Start Script
====================================
A simple script to get the AI Core running quickly.
"""

import os
import sys

# Change to script directory
script_dir = os.path.dirname(os.path.abspath(__file__))
os.chdir(script_dir)

# Add parent to path
sys.path.insert(0, script_dir)

def main():
    """Main entry point."""
    print("=" * 60)
    print("AKSHAY AI CORE - Personal AI Operating System")
    print("=" * 60)
    print()
    
    # Check for .env file
    if not os.path.exists('.env'):
        print("[WARNING] .env file not found. Creating default .env...")
        print("[INFO] Copy .env.example to .env and configure your settings.")
        print()
    
    try:
        # Import after path is set
        from core.config import settings
        print(f"[OK] Configuration loaded (Environment: {settings.ENVIRONMENT})")
        print()
        
        # Try to import core modules
        from core.security import permission_firewall, tool_dispatcher
        print("[OK] Security modules initialized")
        
        from core.brain import memory_manager
        print("[OK] Brain modules initialized")
        
        print()
        print("=" * 60)
        print("All core modules loaded successfully!")
        print("=" * 60)
        print()
        print("To start the system, run:")
        print("  python main.py run")
        print()
        print("To initialize the database, run:")
        print("  python main.py init")
        print()
        
        return 0
        
    except Exception as e:
        print(f"[ERROR] Failed to initialize: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    sys.exit(main())
