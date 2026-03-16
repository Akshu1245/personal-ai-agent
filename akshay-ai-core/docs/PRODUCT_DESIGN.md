# AKSHAY AI CORE — Product Design Document

## Overview

Transforming AKSHAY AI CORE from a developer project into a **shareable, installable product** that works on any Windows laptop with zero coding required.

---

## 1. INSTALLATION FOLDER STRUCTURE

When installed, the product will create this structure in the user's home directory:

```
C:\Users\{username}\AkshayAI\
├── core/                      # Application code (read-only)
│   ├── api/
│   ├── automation/
│   ├── core/
│   ├── plugins/
│   ├── ui/
│   └── main.py
│
├── config/                    # User configuration (editable)
│   ├── settings.yaml          # Main settings
│   ├── voice.yaml             # Voice preferences
│   ├── devices.yaml           # IoT device registry
│   └── .env                   # API keys (never shared)
│
├── data/                      # User data (persistent)
│   ├── memory/                # AI memory database
│   ├── face_data/             # Face recognition data
│   ├── vault/                 # Encrypted secrets
│   └── vector_db/             # Embeddings
│
├── logs/                      # Application logs
│   ├── akshay.log
│   ├── security.log
│   └── audit.log
│
├── policies/                  # Security policies
│   ├── default.yaml           # Base policy
│   ├── demo.yaml              # Demo mode policy (restricted)
│   └── custom/                # User policies (advanced)
│
├── plugins/                   # User plugins (sandboxed)
│   └── custom/
│
├── demo/                      # Demo mode assets
│   ├── mock_devices.yaml      # Fake IoT devices
│   ├── mock_filesystem.yaml   # Fake file system
│   └── mock_web.yaml          # Fake web responses
│
├── .akshay/                   # Internal state (hidden)
│   ├── version.txt            # Current version
│   ├── install_id.txt         # Unique install ID
│   ├── admin.key              # Encrypted admin key
│   ├── first_run              # First run flag
│   └── sessions/              # Active sessions
│
├── ai.bat                     # Quick launcher
├── ai.ps1                     # PowerShell launcher
└── uninstall.ps1              # Clean uninstaller
```

---

## 2. INSTALLER FLOW

### Step 1: Download
User downloads `AkshayAI-Setup.zip` containing:
```
AkshayAI-Setup/
├── install.ps1               # Main installer script
├── requirements.txt          # Python dependencies
├── core.zip                  # Application code (compressed)
├── README.txt                # Quick start guide
└── LICENSE.txt               # License information
```

### Step 2: Run Installer
User right-clicks `install.ps1` → "Run with PowerShell"

### Step 3: Installer Actions
```
┌─────────────────────────────────────────────────────────────────┐
│                    AKSHAY AI CORE INSTALLER                     │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  [■□□□□□□□□□] Checking system requirements...                   │
│                                                                 │
│  ✓ Windows 10/11 detected                                       │
│  ✓ Python 3.11+ found                                           │
│  ✓ 4GB RAM available                                            │
│  ✓ 2GB disk space available                                     │
│                                                                 │
│  [■■■□□□□□□□] Creating installation directory...                │
│  [■■■■□□□□□□] Extracting application files...                   │
│  [■■■■■□□□□□] Creating virtual environment...                   │
│  [■■■■■■□□□□] Installing dependencies...                        │
│  [■■■■■■■□□□] Generating security keys...                       │
│  [■■■■■■■■□□] Creating default policy...                        │
│  [■■■■■■■■■□] Adding to PATH...                                 │
│  [■■■■■■■■■■] Installation complete!                            │
│                                                                 │
│  ─────────────────────────────────────────────────────────────  │
│                                                                 │
│  ✓ AKSHAY AI CORE installed successfully!                       │
│                                                                 │
│  To start:                                                      │
│    • Type 'ai' in any terminal                                  │
│    • Or double-click 'ai.bat' in C:\Users\You\AkshayAI          │
│                                                                 │
│  First run will guide you through setup.                        │
│                                                                 │
│  Press any key to close...                                      │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### Installer Responsibilities:
1. **Check Prerequisites**
   - Windows 10/11
   - Python 3.10+ (offer to install if missing)
   - 4GB RAM minimum
   - 2GB disk space

2. **Create Folder Structure**
   - As defined above in `C:\Users\{username}\AkshayAI\`

3. **Setup Python Environment**
   - Create isolated venv in `core\.venv\`
   - Install all dependencies
   - Verify installation

4. **Generate Security**
   - Create unique install ID
   - Generate admin encryption key
   - Create default security policy

5. **Register Launcher**
   - Add `%USERPROFILE%\AkshayAI` to PATH
   - Create `ai.bat` and `ai.ps1` launchers

6. **Create Shortcuts** (optional)
   - Desktop shortcut
   - Start menu entry

---

## 3. FIRST-RUN WIZARD

When the user first runs `ai`, they see:

### Screen 1: Welcome
```
╔═══════════════════════════════════════════════════════════════════╗
║                                                                   ║
║                    Welcome to AKSHAY AI CORE                      ║
║                                                                   ║
║              Your Personal AI Operating System                    ║
║                                                                   ║
╠═══════════════════════════════════════════════════════════════════╣
║                                                                   ║
║   This wizard will help you set up your AI assistant.             ║
║                                                                   ║
║   You'll configure:                                               ║
║     • Admin account & security                                    ║
║     • Voice preferences                                           ║
║     • Operating mode (Normal or Demo)                             ║
║                                                                   ║
║   Estimated time: 2-3 minutes                                     ║
║                                                                   ║
║                     [ Get Started → ]                             ║
║                                                                   ║
╚═══════════════════════════════════════════════════════════════════╝
```

### Screen 2: Create Admin
```
╔═══════════════════════════════════════════════════════════════════╗
║                     Create Admin Account                          ║
╠═══════════════════════════════════════════════════════════════════╣
║                                                                   ║
║   Your Name:  [____________________________]                      ║
║                                                                   ║
║   Create a PIN (6-12 digits):                                     ║
║               [••••••••]                                          ║
║                                                                   ║
║   Confirm PIN:                                                    ║
║               [••••••••]                                          ║
║                                                                   ║
║   ┌─────────────────────────────────────────────────────────┐     ║
║   │ 🔐 This PIN is your master key. It encrypts all your   │     ║
║   │    data and cannot be recovered if lost.               │     ║
║   │                                                        │     ║
║   │    Write it down and keep it safe!                     │     ║
║   └─────────────────────────────────────────────────────────┘     ║
║                                                                   ║
║               [ ← Back ]          [ Continue → ]                  ║
║                                                                   ║
╚═══════════════════════════════════════════════════════════════════╝
```

### Screen 3: Voice Setup
```
╔═══════════════════════════════════════════════════════════════════╗
║                      Voice Preferences                            ║
╠═══════════════════════════════════════════════════════════════════╣
║                                                                   ║
║   Enable voice input?                                             ║
║     (●) Yes - I'll talk to my AI                                  ║
║     ( ) No  - I'll only type                                      ║
║                                                                   ║
║   Wake word:                                                      ║
║     (●) "Hey Akshay"                                              ║
║     ( ) "Computer"                                                ║
║     ( ) "Assistant"                                               ║
║     ( ) None (push-to-talk only)                                  ║
║                                                                   ║
║   Voice response:                                                 ║
║     (●) Enabled (AI speaks back)                                  ║
║     ( ) Disabled (text only)                                      ║
║                                                                   ║
║               [ ← Back ]          [ Continue → ]                  ║
║                                                                   ║
╚═══════════════════════════════════════════════════════════════════╝
```

### Screen 4: Choose Mode
```
╔═══════════════════════════════════════════════════════════════════╗
║                      Choose Operating Mode                        ║
╠═══════════════════════════════════════════════════════════════════╣
║                                                                   ║
║   ┌─────────────────────────────────────────────────────────┐     ║
║   │  🏠 NORMAL MODE                                         │     ║
║   │                                                         │     ║
║   │  Full AI capabilities:                                  │     ║
║   │    • Real file system access                            │     ║
║   │    • Real web browsing                                  │     ║
║   │    • IoT device control (if configured)                 │     ║
║   │    • Memory & learning                                  │     ║
║   │                                                         │     ║
║   │  Recommended for: Personal use at home                  │     ║
║   │                                         [ Select ]      │     ║
║   └─────────────────────────────────────────────────────────┘     ║
║                                                                   ║
║   ┌─────────────────────────────────────────────────────────┐     ║
║   │  🎮 DEMO MODE (Safe)                                    │     ║
║   │                                                         │     ║
║   │  Simulated environment:                                 │     ║
║   │    • Mock file system (nothing real touched)            │     ║
║   │    • Simulated web browsing                             │     ║
║   │    • Virtual IoT devices                                │     ║
║   │    • Memory resets on exit                              │     ║
║   │                                                         │     ║
║   │  Recommended for: Demos, testing, sharing with friends  │     ║
║   │                                         [ Select ]      │     ║
║   └─────────────────────────────────────────────────────────┘     ║
║                                                                   ║
╚═══════════════════════════════════════════════════════════════════╝
```

### Screen 5: What I Can / Can't Do
```
╔═══════════════════════════════════════════════════════════════════╗
║                     Understanding AKSHAY AI                       ║
╠═══════════════════════════════════════════════════════════════════╣
║                                                                   ║
║   ✅ WHAT I CAN DO:                                               ║
║   ─────────────────                                               ║
║   • Answer questions and have conversations                       ║
║   • Help with writing, coding, and research                       ║
║   • Control IoT devices (lights, switches, etc.)                  ║
║   • Read and organize files (with permission)                     ║
║   • Remember our conversations                                    ║
║   • Automate repetitive tasks                                     ║
║                                                                   ║
║   🚫 WHAT I WILL NOT DO:                                          ║
║   ──────────────────────                                          ║
║   • Access files without asking first                             ║
║   • Send emails or messages without confirmation                  ║
║   • Make purchases or financial decisions                         ║
║   • Share your data with anyone                                   ║
║   • Execute dangerous system commands                             ║
║   • Bypass your security settings                                 ║
║                                                                   ║
║   Your data stays on YOUR computer. Always.                       ║
║                                                                   ║
║                        [ I Understand → ]                         ║
║                                                                   ║
╚═══════════════════════════════════════════════════════════════════╝
```

### Screen 6: Ready!
```
╔═══════════════════════════════════════════════════════════════════╗
║                                                                   ║
║                    🎉 Setup Complete! 🎉                          ║
║                                                                   ║
╠═══════════════════════════════════════════════════════════════════╣
║                                                                   ║
║   AKSHAY AI CORE is ready to use!                                 ║
║                                                                   ║
║   Quick commands:                                                 ║
║   ─────────────────                                               ║
║     ai              → Start AI assistant                          ║
║     ai --demo       → Start in Demo Mode                          ║
║     ai --status     → Check system status                         ║
║     ai --help       → Show all commands                           ║
║                                                                   ║
║   Try saying:                                                     ║
║   ─────────────────                                               ║
║     "Hey Akshay, what can you do?"                                ║
║     "Hey Akshay, tell me a joke"                                  ║
║     "Hey Akshay, turn on demo lights"                             ║
║                                                                   ║
║                    [ Launch AKSHAY AI → ]                         ║
║                                                                   ║
╚═══════════════════════════════════════════════════════════════════╝
```

---

## 4. DEMO MODE DESIGN

### Purpose
Allow friends to experience AKSHAY AI without:
- Touching real files
- Accessing real network
- Controlling real devices
- Leaving permanent changes

### Visual Indicator
```
╔════════════════════════════════════════════════════════════════════╗
║  🎮 DEMO MODE ACTIVE                          [Exit Demo] [Help]   ║
╠════════════════════════════════════════════════════════════════════╣
```

### Mock Systems

#### Mock IoT Devices (`demo/mock_devices.yaml`)
```yaml
devices:
  - id: demo_light_living
    name: "Living Room Light"
    type: light
    state: "off"
    brightness: 100
    
  - id: demo_light_bedroom
    name: "Bedroom Light"
    type: light
    state: "off"
    brightness: 50
    
  - id: demo_thermostat
    name: "Smart Thermostat"
    type: thermostat
    temperature: 72
    mode: "auto"
    
  - id: demo_tv
    name: "Smart TV"
    type: media
    state: "off"
    volume: 30
```

#### Mock File System (`demo/mock_filesystem.yaml`)
```yaml
filesystem:
  /home/demo/:
    Documents/:
      - report.docx: "Quarterly sales report..."
      - notes.txt: "Meeting notes from Monday..."
    Photos/:
      - vacation.jpg: "[Image: Beach sunset]"
      - family.png: "[Image: Family portrait]"
    Downloads/:
      - setup.exe: "[Installer file]"
```

#### Mock Web (`demo/mock_web.yaml`)
```yaml
web_responses:
  "weather":
    response: "Current weather: 72°F, Sunny with light clouds"
  "news":
    response: "Top headlines: [Demo news stories]"
  "search:*":
    response: "Demo search results for: {query}"
```

### Auto-Reset
- All changes reset when demo mode exits
- Memory is ephemeral (not saved)
- No files are created/modified
- No network calls to external services

---

## 5. LAUNCHER DESIGN

### `ai.bat` (Windows Batch)
```batch
@echo off
cd /d "%USERPROFILE%\AkshayAI"
call core\.venv\Scripts\activate.bat
python core\main.py %*
```

### `ai.ps1` (PowerShell)
```powershell
$env:AKSHAY_HOME = "$env:USERPROFILE\AkshayAI"
Push-Location $env:AKSHAY_HOME
& "core\.venv\Scripts\Activate.ps1"
python core\main.py @args
Pop-Location
```

### Command Line Interface
```
Usage: ai [OPTIONS] [COMMAND]

Commands:
  (default)     Start interactive AI assistant
  --demo        Start in Demo Mode
  --status      Show system status
  --settings    Open settings
  --update      Check for updates
  --help        Show this help

Options:
  --voice       Enable voice input (default: from settings)
  --no-voice    Disable voice input
  --quiet       Minimal output
  --debug       Enable debug logging
```

---

## 6. UNINSTALLER DESIGN

### `uninstall.ps1`
```
╔═══════════════════════════════════════════════════════════════════╗
║                  AKSHAY AI CORE UNINSTALLER                       ║
╠═══════════════════════════════════════════════════════════════════╣
║                                                                   ║
║   This will completely remove AKSHAY AI CORE from your system.    ║
║                                                                   ║
║   What will be removed:                                           ║
║     • Application files                                           ║
║     • Configuration                                               ║
║     • Logs                                                        ║
║     • PATH entries                                                ║
║                                                                   ║
║   ⚠️  Your data folder will be KEPT unless you choose to delete:  ║
║       C:\Users\You\AkshayAI\data\                                 ║
║                                                                   ║
║   [ ] Also delete my data (memories, face data, vault)            ║
║                                                                   ║
║            [ Cancel ]              [ Uninstall ]                  ║
║                                                                   ║
╚═══════════════════════════════════════════════════════════════════╝
```

### Uninstall Actions:
1. Stop any running services
2. Remove PATH entries
3. Delete application folders (except data if preserved)
4. Remove shortcuts
5. Clean registry entries (if any)
6. Confirm completion

---

## 7. FRIEND SHARE KIT

### Contents of `/share/`
```
share/
├── AkshayAI-v1.0.0.zip        # Complete installer package
├── README.txt                  # Simple instructions
├── QUICKSTART.pdf             # Visual guide with screenshots
└── demo_commands.txt          # Fun commands to try
```

### README.txt Content
```
═══════════════════════════════════════════════════════════
           AKSHAY AI CORE — Quick Start Guide
═══════════════════════════════════════════════════════════

WHAT IS THIS?
─────────────
Akshay AI is a personal AI assistant that runs entirely on
your computer. It can chat, control smart devices, and help
with everyday tasks.

INSTALLATION (2 minutes)
────────────────────────
1. Extract AkshayAI-v1.0.0.zip to any folder
2. Right-click 'install.ps1' → "Run with PowerShell"
3. Follow the on-screen wizard
4. Done!

STARTING THE AI
───────────────
• Open any terminal (Command Prompt or PowerShell)
• Type: ai
• Press Enter

For Demo Mode (safe, simulated):
• Type: ai --demo

VOICE COMMANDS TO TRY
─────────────────────
• "Hey Akshay, what can you do?"
• "Hey Akshay, turn on the living room light"
• "Hey Akshay, what's the weather?"
• "Hey Akshay, tell me a joke"
• "Hey Akshay, set a timer for 5 minutes"

TO UNINSTALL
────────────
• Navigate to C:\Users\YourName\AkshayAI
• Right-click 'uninstall.ps1' → "Run with PowerShell"

TROUBLESHOOTING
───────────────
• "Python not found" → Install Python from python.org
• "ai command not found" → Restart your terminal
• Need help? See docs/TROUBLESHOOTING.md

═══════════════════════════════════════════════════════════
                   Enjoy your AI! 🤖
═══════════════════════════════════════════════════════════
```

---

## 8. UI COMPONENTS

### System Status Bar
```
┌──────────────────────────────────────────────────────────────┐
│ 🟢 System OK │ 🎮 Demo Mode │ 🔒 Safe Mode │ 🎤 Voice ON    │
└──────────────────────────────────────────────────────────────┘
```

Status Colors:
- 🟢 Green: All systems operational
- 🟡 Yellow: Degraded (e.g., no internet)
- 🔴 Red: Critical issue

### Activity Feed
```
┌─ Recent Activity ──────────────────────────────────────────┐
│ 14:32  Voice: "turn on lights" → Living Room Light ON      │
│ 14:31  Checked weather → 72°F Sunny                        │
│ 14:30  Started Demo Mode                                   │
│ 14:28  System initialized                                  │
└────────────────────────────────────────────────────────────┘
```

### Emergency Lock Button
```
┌──────────────────────┐
│    🔴 EMERGENCY      │
│       LOCK           │
│                      │
│  (Press & Hold 3s)   │
└──────────────────────┘
```

When triggered:
- Immediately stops all operations
- Locks AI from all commands
- Requires PIN to unlock
- Logs security event

---

## 9. SAFETY HARDENING (Demo Mode)

### Restricted in Demo Mode:
| Feature | Normal Mode | Demo Mode |
|---------|-------------|-----------|
| Real file access | ✅ | ❌ (mock) |
| Real web requests | ✅ | ❌ (mock) |
| Real IoT control | ✅ | ❌ (virtual) |
| Policy editing | ✅ | ❌ |
| Plugin install | ✅ | ❌ |
| System commands | ✅ | ❌ |
| Memory persistence | ✅ | ❌ (resets) |
| Voice destructive cmds | Confirm | ❌ |

### Rate Limits (Demo Mode):
- API calls: 100/minute
- Voice commands: 30/minute
- File operations: Blocked
- Web requests: 50/minute (to mock)

---

## 10. BUILD ORDER

| Phase | Task | Deliverable |
|-------|------|-------------|
| 1 | Installer | `install.ps1` |
| 2 | Launcher | `ai.bat`, `ai.ps1` |
| 3 | Demo Mode | Mock systems, restrictions |
| 4 | First-Run Wizard | Interactive setup UI |
| 5 | UI Polish | Status bar, indicators |
| 6 | Auto-Update | Version check, safe update |
| 7 | Share Kit | ZIP package, README |
| 8 | Uninstaller | `uninstall.ps1` |
| 9 | Documentation | User guides |
| 10 | E2E Testing | Full test script |

---

## APPROVAL CHECKPOINT

**Before proceeding to implementation, please confirm:**

1. ✅ Folder structure looks correct?
2. ✅ Installer flow is appropriate?
3. ✅ First-run wizard screens are good?
4. ✅ Demo mode restrictions are sufficient?
5. ✅ Any changes to the design?

**Reply with:**
- "Approved" to proceed with Phase 1 (Installer)
- Or specific changes you'd like to see

---

*Document created: January 19, 2026*
*Version: 1.0-DRAFT*
