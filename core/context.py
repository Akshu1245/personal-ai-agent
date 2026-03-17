"""
JARVIS Context Module
Manages project context and state

Author: Rashi AI
Built for: Akshay
"""

import json
from pathlib import Path
from typing import Dict, List, Any, Optional


class ProjectContext:
    """JARVIS Project Context Manager"""
    
    def __init__(self):
        self.project_root = Path(__file__).parent.parent
        self.data_dir = self.project_root / 'data'
        self.projects_file = self.data_dir / 'projects.json'
        
        # Current state
        self.current_project: Optional[str] = None
        self.projects: List[Dict] = []
        self.context: Dict[str, Any] = {}
        
        # Default projects
        self.default_projects = [
            {
                'name': 'VORAX',
                'description': 'AI faceless YouTube video SaaS',
                'stack': 'FastAPI + Vite React TS',
                'tech': ['Groq/Llama scripting', 'Sarvam AI voice', 'Pexels footage', 'Shotstack'],
                'path': 'd:/projects/vorax',
                'priority': 'high',
                'status': 'active'
            },
            {
                'name': 'Rashi IDE',
                'description': 'Local Replit-style IDE with 5 agent modes',
                'stack': 'Flask backend',
                'path': 'd:/projects/rashi-ide',
                'priority': 'high',
                'status': 'active'
            },
            {
                'name': 'MarketX Vault',
                'description': 'Flutter Android vault disguised as trading app',
                'stack': 'Flutter',
                'path': 'd:/projects/marketx-vault',
                'priority': 'medium',
                'status': 'planning'
            },
            {
                'name': 'SoulVault',
                'description': 'AI emotional memory simulation app',
                'stack': 'Flutter/Firebase',
                'path': 'd:/projects/soulvault',
                'priority': 'medium',
                'status': 'planning'
            },
            {
                'name': 'Godfather Agent',
                'description': 'Make.com 15-route automation agent',
                'stack': 'Make.com',
                'path': None,
                'priority': 'low',
                'status': 'active'
            }
        ]
        
        # Load projects
        self.load_projects()
        
    def load_projects(self):
        """Load projects from file or use defaults"""
        if self.projects_file.exists():
            try:
                with open(self.projects_file, 'r') as f:
                    self.projects = json.load(f)
            except Exception as e:
                print(f"Error loading projects: {e}")
                self.projects = self.default_projects
        else:
            self.projects = self.default_projects
            self.save_projects()
            
    def save_projects(self):
        """Save projects to file"""
        self.data_dir.mkdir(exist_ok=True)
        with open(self.projects_file, 'w') as f:
            json.dump(self.projects, f, indent=2)
            
    def get_all_projects(self) -> List[Dict]:
        """Get all projects"""
        return self.projects
        
    def get_project(self, name: str) -> Optional[Dict]:
        """Get a specific project by name"""
        for project in self.projects:
            if project['name'].lower() == name.lower():
                return project
        return None
        
    def switch_project(self, name: str) -> bool:
        """Switch to a different project context"""
        project = self.get_project(name)
        if project:
            self.current_project = name
            self.context = {
                'project': project,
                'stack': project.get('stack', ''),
                'path': project.get('path'),
                'priority': project.get('priority', 'medium'),
                'status': project.get('status', 'active')
            }
            return True
        return False
        
    def get_context(self) -> Dict:
        """Get current context"""
        if not self.context and self.current_project:
            self.switch_project(self.current_project)
            
        return {
            'current_project': self.current_project,
            'context': self.context,
            'all_projects': self.projects
        }
        
    def add_project(self, project: Dict):
        """Add a new project"""
        self.projects.append(project)
        self.save_projects()
        
    def update_project(self, name: str, updates: Dict):
        """Update a project"""
        for i, project in enumerate(self.projects):
            if project['name'].lower() == name.lower():
                self.projects[i].update(updates)
                self.save_projects()
                return True
        return False
        
    def remove_project(self, name: str) -> bool:
        """Remove a project"""
        for i, project in enumerate(self.projects):
            if project['name'].lower() == name.lower():
                self.projects.pop(i)
                self.save_projects()
                return True
        return False
        
    def get_active_projects(self) -> List[Dict]:
        """Get all active projects"""
        return [p for p in self.projects if p.get('status') == 'active']
        
    def get_high_priority_projects(self) -> List[Dict]:
        """Get high priority projects"""
        return [p for p in self.projects if p.get('priority') == 'high']


# Singleton
_context = None

def get_context_manager() -> ProjectContext:
    """Get context manager singleton"""
    global _context
    if _context is None:
        _context = ProjectContext()
    return _context
