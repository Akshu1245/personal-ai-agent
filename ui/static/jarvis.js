// JARVIS UI v2.0

// ── State ─────────────────────────────────
let socket = null;
let isListening = false;
let isSending = false;
let messageCount = 0;

// ── DOM refs ──────────────────────────────
const messagesEl    = document.getElementById('messages');
const messageInput  = document.getElementById('messageInput');
const sendBtn       = document.getElementById('sendBtn');
const voiceBtn      = document.getElementById('voiceBtn');
const statusDot     = document.getElementById('statusDot');
const statusText    = document.getElementById('statusText');
const typingInd     = document.getElementById('typingIndicator');
const suggestionsEl = document.getElementById('suggestions');
const projectBadge  = document.getElementById('currentProjectName');

// ── Init ──────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
    document.getElementById('welcomeTime').textContent = formatTime(new Date());
    initSocketIO();
    setupInput();
    setupVoice();
    checkApiStatus();
    loadProjects();
    loadStats();
    loadMemoryStats();
    loadTasks();
    loadNotes();

    // Auto-refresh stats every 8s
    setInterval(loadStats, 8000);
    setInterval(loadMemoryStats, 30000);
});

// ── Socket.IO ─────────────────────────────
function initSocketIO() {
    socket = io({ transports: ['polling', 'websocket'], reconnectionDelay: 2000 });

    socket.on('connect', () => {
        setStatus('online', 'Online');
    });

    socket.on('disconnect', () => {
        setStatus('', 'Offline');
    });

    socket.on('connect_error', () => {
        setStatus('', 'Connecting...');
    });

    socket.on('jarvis_status', (data) => {
        if (data.status === 'online') setStatus('online', 'Online');
    });

    socket.on('jarvis_thinking', (data) => {
        setThinking(data.thinking);
    });

    socket.on('jarvis_response', (data) => {
        if (data.text) addMessage('bot', data.text);
    });

    socket.on('project_switched', (data) => {
        projectBadge.textContent = data.project;
        showToast(`Switched to ${data.project}`, 'info');
    });
}

function setStatus(cls, label) {
    statusDot.className = 'status-dot' + (cls ? ' ' + cls : '');
    statusText.textContent = label;
}

// ── API Key Check ─────────────────────────
async function checkApiStatus() {
    try {
        const r = await fetch('/api/status');
        const d = await r.json();
        const warning = document.getElementById('apiWarning');
        if (!d.groq_configured) {
            warning.classList.remove('hidden');
        }
        if (d.project) {
            projectBadge.textContent = d.project;
        }
    } catch (e) {}
}

// ── Input Setup ───────────────────────────
function setupInput() {
    sendBtn.addEventListener('click', sendMessage);

    messageInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendMessage();
        }
    });

    messageInput.addEventListener('input', () => {
        // Auto-resize textarea
        messageInput.style.height = 'auto';
        messageInput.style.height = Math.min(messageInput.scrollHeight, 120) + 'px';
        // Hide suggestions once user types
        if (messageInput.value.trim()) {
            suggestionsEl.style.display = 'none';
        } else {
            suggestionsEl.style.display = '';
        }
    });

    messageInput.focus();
}

// ── Send Message ──────────────────────────
async function sendMessage() {
    const msg = messageInput.value.trim();
    if (!msg || isSending) return;

    isSending = true;
    sendBtn.disabled = true;
    messageInput.value = '';
    messageInput.style.height = 'auto';
    suggestionsEl.style.display = 'none';

    addMessage('user', msg);
    setThinking(true);

    try {
        const res = await fetch('/api/chat', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ message: msg })
        });

        const data = await res.json();
        setThinking(false);

        if (data.response) {
            addMessage('bot', data.response, data.tool_used);
            if (data.tool_used) {
                showToast(`Tool used: ${data.tool_used}`, 'info');
            }
        }
    } catch (err) {
        setThinking(false);
        addMessage('bot', '⚠️ Connection error. Please try again.');
        showToast('Request failed', 'error');
    } finally {
        isSending = false;
        sendBtn.disabled = false;
        messageInput.focus();
    }
}

function sendSuggestion(text) {
    messageInput.value = text;
    sendMessage();
}

// ── Add Message ───────────────────────────
function addMessage(type, text, toolUsed) {
    messageCount++;

    const wrapper = document.createElement('div');
    wrapper.className = `message ${type}`;

    const avatar = document.createElement('div');
    avatar.className = 'avatar ' + (type === 'bot' ? 'bot-avatar' : 'user-avatar');
    avatar.textContent = type === 'bot' ? 'J' : 'A';

    const msgWrap = document.createElement('div');
    msgWrap.className = 'msg-wrap';

    const content = document.createElement('div');
    content.className = 'content';

    if (type === 'bot') {
        // Render markdown for bot messages
        try {
            content.innerHTML = marked.parse(text);
        } catch {
            content.textContent = text;
        }
    } else {
        content.textContent = text;
    }

    const meta = document.createElement('div');
    meta.className = 'msg-meta';

    const timeEl = document.createElement('span');
    timeEl.className = 'msg-time';
    timeEl.textContent = formatTime(new Date());
    meta.appendChild(timeEl);

    if (type === 'bot') {
        const copyBtn = document.createElement('button');
        copyBtn.className = 'copy-btn';
        copyBtn.innerHTML = `<svg viewBox="0 0 24 24" width="11" height="11"><path fill="currentColor" d="M16 1H4c-1.1 0-2 .9-2 2v14h2V3h12V1zm3 4H8c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h11c1.1 0 2-.9 2-2V7c0-1.1-.9-2-2-2zm0 16H8V7h11v14z"/></svg> Copy`;
        copyBtn.onclick = () => {
            navigator.clipboard.writeText(text).then(() => {
                copyBtn.textContent = '✓ Copied';
                setTimeout(() => {
                    copyBtn.innerHTML = `<svg viewBox="0 0 24 24" width="11" height="11"><path fill="currentColor" d="M16 1H4c-1.1 0-2 .9-2 2v14h2V3h12V1zm3 4H8c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h11c1.1 0 2-.9 2-2V7c0-1.1-.9-2-2-2zm0 16H8V7h11v14z"/></svg> Copy`;
                }, 2000);
            });
        };
        meta.appendChild(copyBtn);
    }

    msgWrap.appendChild(content);
    msgWrap.appendChild(meta);

    wrapper.appendChild(avatar);
    wrapper.appendChild(msgWrap);

    messagesEl.appendChild(wrapper);
    messagesEl.scrollTop = messagesEl.scrollHeight;
}

// ── Thinking indicator ────────────────────
function setThinking(on) {
    typingInd.classList.toggle('hidden', !on);
    if (on) messagesEl.scrollTop = messagesEl.scrollHeight;
}

// ── Clear chat ────────────────────────────
async function clearChat() {
    try {
        await fetch('/api/chat/clear', { method: 'POST' });
    } catch (e) {}

    // Clear UI except welcome message
    const msgs = messagesEl.querySelectorAll('.message:not(#welcomeMsg)');
    msgs.forEach(m => m.remove());
    suggestionsEl.style.display = '';
    showToast('Chat cleared', 'success');
}

// ── Voice ─────────────────────────────────
function setupVoice() {
    voiceBtn.addEventListener('mousedown', startVoice);
    voiceBtn.addEventListener('mouseup', stopVoice);
    voiceBtn.addEventListener('mouseleave', stopVoice);
    voiceBtn.addEventListener('touchstart', e => { e.preventDefault(); startVoice(); });
    voiceBtn.addEventListener('touchend', e => { e.preventDefault(); stopVoice(); });
}

function startVoice() {
    if (!socket?.connected) return;
    isListening = true;
    voiceBtn.classList.add('listening');
    socket.emit('voice_start');
    showToast('Listening...', 'info');
}

function stopVoice() {
    if (!isListening) return;
    isListening = false;
    voiceBtn.classList.remove('listening');
    if (socket?.connected) socket.emit('voice_stop');
}

// ── Quick Actions ─────────────────────────
function quickAction(action) {
    let msg = '';
    switch (action) {
        case 'screenshot': msg = 'Take a screenshot'; break;
        case 'focus': msg = 'Start focus mode for 30 minutes'; break;
        case 'crypto': msg = 'What is the current Cardano (ADA) price?'; break;
        case 'search':
            const q = prompt('What do you want to search for?');
            if (!q) return;
            msg = `Search the web for: ${q}`;
            break;
        case 'sysinfo': msg = 'Give me a summary of my system info and performance'; break;
    }
    if (msg) {
        messageInput.value = msg;
        sendMessage();
    }
}

// ── System Stats ──────────────────────────
async function loadStats() {
    try {
        const r = await fetch('/api/system/stats');
        const d = await r.json();
        if (!d.success) return;

        const cpu = d.cpu.percent;
        const ram = d.memory.percent;
        const disk = d.disk.percent;

        setBar('cpuBar', 'cpuVal', cpu);
        setBar('ramBar', 'ramVal', ram);
        setBar('diskBar', 'diskVal', disk);

        document.getElementById('memDetail').textContent =
            `${d.memory.used_gb}GB / ${d.memory.total_gb}GB RAM  ·  ${d.disk.used_gb}GB / ${d.disk.total_gb}GB disk`;
    } catch (e) {}
}

function setBar(barId, valId, pct) {
    const bar = document.getElementById(barId);
    const val = document.getElementById(valId);
    if (!bar || !val) return;
    bar.style.width = pct + '%';
    bar.className = 'stat-fill' + (pct > 85 ? ' danger' : pct > 70 ? ' warn' : '');
    val.textContent = Math.round(pct) + '%';
}

// ── Projects ──────────────────────────────
async function loadProjects() {
    try {
        const r = await fetch('/api/projects');
        const projects = await r.json();
        const list = document.getElementById('projectList');
        list.innerHTML = '';

        projects.forEach(p => {
            const el = document.createElement('div');
            el.className = 'project-item' + (p.status === 'active' ? ' active' : '');
            el.innerHTML = `<span>${p.name}</span><span class="project-status">${p.priority === 'high' ? '🔴' : p.priority === 'medium' ? '🟡' : '⚪'}</span>`;
            el.title = p.description || '';
            el.onclick = () => switchProject(p.name);
            list.appendChild(el);
        });
    } catch (e) {}
}

async function switchProject(name) {
    try {
        await fetch(`/api/projects/${encodeURIComponent(name)}`, { method: 'POST' });
        projectBadge.textContent = name;
        document.querySelectorAll('.project-item').forEach(el => {
            el.classList.toggle('active', el.querySelector('span').textContent === name);
        });
        showToast(`Context → ${name}`, 'success');
    } catch (e) {}
}

// ── Memory Stats ──────────────────────────
async function loadMemoryStats() {
    try {
        const r = await fetch('/api/memory/stats');
        const d = await r.json();
        document.getElementById('convCount').textContent = d.conversations ?? '—';
        document.getElementById('memCount').textContent = d.memories ?? '—';
        document.getElementById('taskCount').textContent = d.pending_tasks ?? '—';
        document.getElementById('notesCount').textContent = d.notes ?? '—';
    } catch (e) {}
}

// ── Sidebar Tabs ──────────────────────────
function switchTab(tab) {
    document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
    document.querySelectorAll('.tab-panel').forEach(p => p.classList.remove('active'));
    document.getElementById('tab-' + tab).classList.add('active');
    document.getElementById('panel-' + tab).classList.add('active');

    if (tab === 'tasks') loadTasks();
    if (tab === 'notes') loadNotes();
}

// ── Tasks ─────────────────────────────────
function showAddTask() {
    const f = document.getElementById('addTaskForm');
    f.classList.toggle('hidden');
    if (!f.classList.contains('hidden')) document.getElementById('taskTitle').focus();
}

async function submitTask() {
    const title = document.getElementById('taskTitle').value.trim();
    const project = document.getElementById('taskProject').value.trim();
    if (!title) return;

    try {
        await fetch('/api/tasks', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ title, project: project || null })
        });
        document.getElementById('taskTitle').value = '';
        document.getElementById('taskProject').value = '';
        document.getElementById('addTaskForm').classList.add('hidden');
        loadTasks();
        loadMemoryStats();
        showToast('Task added', 'success');
    } catch (e) {
        showToast('Failed to add task', 'error');
    }
}

async function completeTask(id, el) {
    try {
        await fetch(`/api/tasks/${id}/complete`, { method: 'POST' });
        el.closest('.task-item').style.opacity = '0.4';
        setTimeout(() => { el.closest('.task-item').remove(); }, 400);
        loadMemoryStats();
        showToast('Task completed ✓', 'success');
    } catch (e) {}
}

async function loadTasks() {
    try {
        const r = await fetch('/api/tasks');
        const d = await r.json();
        const list = document.getElementById('taskList');

        if (!d.tasks || d.tasks.length === 0) {
            list.innerHTML = '<div class="empty-state">No pending tasks 🎉</div>';
            return;
        }

        list.innerHTML = '';
        d.tasks.forEach(t => {
            const el = document.createElement('div');
            el.className = 'task-item';
            el.innerHTML = `
                <div class="task-check" onclick="completeTask(${t.id}, this)" title="Mark complete"></div>
                <div class="task-body">
                    <div class="task-title">${escHtml(t.title)}</div>
                    ${t.project ? `<div class="task-project">📁 ${escHtml(t.project)}</div>` : ''}
                </div>
            `;
            list.appendChild(el);
        });
    } catch (e) {}
}

// ── Notes ─────────────────────────────────
function showAddNote() {
    const f = document.getElementById('addNoteForm');
    f.classList.toggle('hidden');
    if (!f.classList.contains('hidden')) document.getElementById('noteTitle').focus();
}

async function submitNote() {
    const title = document.getElementById('noteTitle').value.trim();
    const content = document.getElementById('noteContent').value.trim();
    if (!title) return;

    try {
        await fetch('/api/notes', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ title, content })
        });
        document.getElementById('noteTitle').value = '';
        document.getElementById('noteContent').value = '';
        document.getElementById('addNoteForm').classList.add('hidden');
        loadNotes();
        loadMemoryStats();
        showToast('Note saved', 'success');
    } catch (e) {
        showToast('Failed to save note', 'error');
    }
}

async function deleteNote(id, el) {
    try {
        await fetch(`/api/notes/${id}`, { method: 'DELETE' });
        el.closest('.note-item').remove();
        loadMemoryStats();
        showToast('Note deleted', 'info');
    } catch (e) {}
}

async function loadNotes() {
    try {
        const r = await fetch('/api/notes');
        const d = await r.json();
        const list = document.getElementById('notesList');

        if (!d.notes || d.notes.length === 0) {
            list.innerHTML = '<div class="empty-state">No notes yet</div>';
            return;
        }

        list.innerHTML = '';
        // Show latest first
        [...d.notes].reverse().forEach(n => {
            const el = document.createElement('div');
            el.className = 'note-item';
            const date = n.created_at ? new Date(n.created_at).toLocaleDateString() : '';
            el.innerHTML = `
                <div class="note-title-row">
                    <span class="note-title">${escHtml(n.title)}</span>
                    <button class="del-btn" onclick="deleteNote(${n.id}, this)" title="Delete">×</button>
                </div>
                ${n.content ? `<div class="note-content">${escHtml(n.content)}</div>` : ''}
                <div class="note-date">${date}</div>
            `;
            list.appendChild(el);
        });
    } catch (e) {}
}

// ── Toast ─────────────────────────────────
function showToast(msg, type = 'info', duration = 3000) {
    const container = document.getElementById('toastContainer');
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.textContent = msg;
    container.appendChild(toast);
    setTimeout(() => {
        toast.style.opacity = '0';
        toast.style.transition = 'opacity 0.3s';
        setTimeout(() => toast.remove(), 300);
    }, duration);
}

// ── Helpers ───────────────────────────────
function formatTime(d) {
    return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
}

function escHtml(str) {
    return String(str)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;');
}
