#!/usr/bin/env bash
# ============================================================
#  JARVIS v2.0 — One-Command Installer
#  Just A Rather Very Intelligent System
#  Built for Akshay by Rashi AI
# ============================================================
set -e

CYAN='\033[0;36m'
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'
BOLD='\033[1m'

banner() {
cat << 'EOF'
  ╔══════════════════════════════════════════╗
  ║   JARVIS v2.0 — Installation Script     ║
  ║   Just A Rather Very Intelligent System  ║
  ║   Built for Akshay                       ║
  ╚══════════════════════════════════════════╝
EOF
}

info()    { echo -e "${CYAN}[INFO]${NC}  $1"; }
success() { echo -e "${GREEN}[OK]${NC}    $1"; }
warn()    { echo -e "${YELLOW}[WARN]${NC}  $1"; }
error()   { echo -e "${RED}[ERR]${NC}   $1"; exit 1; }
step()    { echo -e "\n${BOLD}${CYAN}━━ $1${NC}"; }

banner

# ── 1. Python check ───────────────────────
step "Checking Python"
if ! command -v python3 &>/dev/null; then
    error "Python 3.10+ is required. Install it from python.org"
fi
PYVER=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
info "Found Python $PYVER"
if python3 -c "import sys; exit(0 if sys.version_info >= (3,10) else 1)"; then
    success "Python version OK"
else
    error "Python 3.10+ required (found $PYVER)"
fi

# ── 2. Pip ────────────────────────────────
step "Checking pip"
if ! python3 -m pip --version &>/dev/null; then
    info "Installing pip..."
    python3 -m ensurepip --upgrade
fi
success "pip ready"

# ── 3. Virtual environment (optional) ─────
step "Virtual Environment"
if [ ! -d "venv" ] && [ -z "$VIRTUAL_ENV" ] && [ -z "$REPL_ID" ]; then
    info "Creating virtual environment..."
    python3 -m venv venv
    source venv/bin/activate
    success "venv created and activated"
elif [ -n "$REPL_ID" ]; then
    info "Running in Replit — skipping venv"
elif [ -n "$VIRTUAL_ENV" ]; then
    info "Already in venv: $VIRTUAL_ENV"
else
    source venv/bin/activate
    info "Activated existing venv"
fi

# ── 4. Install Python packages ────────────
step "Installing Python packages"
pip install --upgrade pip --quiet
pip install -r requirements.txt --quiet
success "All packages installed"

# ── 5. Create necessary directories ───────
step "Creating directories"
for dir in logs memory/data memory/chroma_db data journal; do
    mkdir -p "$dir"
    info "  ✓ $dir"
done
success "Directories ready"

# ── 6. Environment file ───────────────────
step "Environment Configuration"
if [ ! -f ".env" ]; then
    if [ -f ".env.example" ]; then
        cp .env.example .env
        info ".env created from .env.example"
    else
        cat > .env << 'ENVEOF'
# JARVIS Environment Configuration
GROQ_API_KEY=your_groq_api_key_here
GROQ_MODEL=llama-3.3-70b-versatile
SECRET_KEY=change_this_in_production
VOICE_ENABLED=false
DEBUG=false
ENVEOF
        info ".env created with defaults"
    fi
    warn "📝 Open .env and set your GROQ_API_KEY before starting JARVIS"
else
    success ".env already exists"
fi

# ── 7. Check GROQ_API_KEY ─────────────────
step "API Key Check"
if [ -f ".env" ]; then
    source .env 2>/dev/null || true
fi
if [ -z "$GROQ_API_KEY" ] || [ "$GROQ_API_KEY" = "your_groq_api_key_here" ]; then
    warn "GROQ_API_KEY not set — AI responses will be disabled"
    warn "Get a free key at: https://console.groq.com"
    warn "Then set it in .env or as a Replit Secret: GROQ_API_KEY=gsk_..."
else
    success "GROQ_API_KEY is set"
fi

# ── 8. Verify key imports ─────────────────
step "Verifying Python imports"
python3 -c "import flask; import flask_socketio; import psutil; import groq; print('Core imports OK')" && success "All core imports working" || warn "Some imports failed — check requirements"

# ── 9. Done ───────────────────────────────
echo ""
echo -e "${GREEN}╔════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║  JARVIS v2.0 installation complete! 🤖 ║${NC}"
echo -e "${GREEN}╚════════════════════════════════════════╝${NC}"
echo ""
echo -e "  Start (development):  ${CYAN}python main.py${NC}"
echo -e "  Start (production):   ${CYAN}gunicorn -c gunicorn.conf.py wsgi:application${NC}"
echo -e "  Setup wizard:         ${CYAN}http://localhost:5000/setup${NC}"
echo -e "  Health check:         ${CYAN}http://localhost:5000/health${NC}"
echo ""
