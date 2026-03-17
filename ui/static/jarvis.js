// JARVIS UI v2.0

// ── State ─────────────────────────────────
let socket        = null;
let isListening   = false;
let isSending     = false;
let messageCount  = 0;
let userProfile   = { name: 'User', avatar_initial: 'U' };
let memOffset     = 0;
let memActiveSource = null;
let memSearchTimer  = null;
let importSelectedSource = 'auto';
let importFileContent = null;
let importFileName    = '';
let editingProjectId  = null;

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
    setupDropZone();
    checkApiStatus();
    loadProfile();
    loadStats();
    loadMemoryStats();
    loadTasks();
    loadNotes();

    setInterval(loadStats, 8000);
    setInterval(loadMemoryStats, 30000);
});

// ── Socket.IO ─────────────────────────────
function initSocketIO() {
    socket = io({ transports: ['polling', 'websocket'], reconnectionDelay: 2000 });
    socket.on('connect',        () => setStatus('online', 'Online'));
    socket.on('disconnect',     () => setStatus('', 'Offline'));
    socket.on('connect_error',  () => setStatus('', 'Connecting...'));
    socket.on('jarvis_status',  (d) => { if (d.status === 'online') setStatus('online', 'Online'); });
    socket.on('jarvis_thinking',(d) => setThinking(d.thinking));
    socket.on('jarvis_response',(d) => { if (d.text) addMessage('bot', d.text); });
    socket.on('project_switched',(d) => {
        projectBadge.textContent = d.project;
        showToast(`Switched to ${d.project}`, 'info');
    });
}

function setStatus(cls, label) {
    statusDot.className = 'status-dot' + (cls ? ' ' + cls : '');
    statusText.textContent = label;
}

// ── Profile ───────────────────────────────
async function loadProfile() {
    try {
        const r = await fetch('/api/profile');
        userProfile = await r.json();
        applyProfile();
    } catch (e) {}
}

function applyProfile() {
    const initial = (userProfile.name || 'U')[0].toUpperCase();
    userProfile.avatar_initial = initial;
    const btn = document.getElementById('profileAvatarBtn');
    if (btn) btn.textContent = initial;
    // Update welcome message to use name
    const welcome = document.getElementById('welcomeMsg');
    if (welcome) {
        const p = welcome.querySelector('p');
        if (p && p.textContent.includes('Akshay')) {
            p.textContent = `Good to have you back, ${userProfile.name}. I'm online and fully operational.`;
        }
    }
}

function openProfileModal() {
    document.getElementById('profileName').value = userProfile.name || '';
    const modelSel = document.getElementById('profileModel');
    if (modelSel) modelSel.value = userProfile.groq_model || 'llama-3.3-70b-versatile';
    const preview = document.getElementById('profileAvatarPreview');
    if (preview) preview.textContent = (userProfile.name || 'U')[0].toUpperCase();
    document.getElementById('profileName').addEventListener('input', function() {
        const v = this.value.trim();
        if (preview) preview.textContent = (v || 'U')[0].toUpperCase();
    }, { once: false });
    openModal('profileModal');
}

async function submitProfile() {
    const name  = document.getElementById('profileName').value.trim();
    const model = document.getElementById('profileModel').value;
    if (!name) { showToast('Name required', 'error'); return; }
    try {
        const r = await fetch('/api/profile', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name, groq_model: model })
        });
        const d = await r.json();
        if (d.success) {
            userProfile = d.profile;
            applyProfile();
            closeModal('profileModal');
            showToast('Profile saved', 'success');
        }
    } catch (e) { showToast('Save failed', 'error'); }
}

// ── API Key Check ─────────────────────────
async function checkApiStatus() {
    try {
        const r = await fetch('/api/status');
        const d = await r.json();
        const warning = document.getElementById('apiWarning');
        if (!d.groq_configured) warning.classList.remove('hidden');
        if (d.project) projectBadge.textContent = d.project;
    } catch (e) {}
}

// ── Input Setup ───────────────────────────
function setupInput() {
    sendBtn.addEventListener('click', sendMessage);
    messageInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendMessage(); }
    });
    messageInput.addEventListener('input', () => {
        messageInput.style.height = 'auto';
        messageInput.style.height = Math.min(messageInput.scrollHeight, 120) + 'px';
        suggestionsEl.style.display = messageInput.value.trim() ? 'none' : '';
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
            if (data.tool_used) showToast(`Tool: ${data.tool_used}`, 'info');
        }
    } catch (err) {
        setThinking(false);
        addMessage('bot', 'Connection error. Please try again.');
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
    avatar.textContent = type === 'bot' ? 'J' : userProfile.avatar_initial || 'U';

    const msgWrap = document.createElement('div');
    msgWrap.className = 'msg-wrap';

    const content = document.createElement('div');
    content.className = 'content';
    if (type === 'bot') {
        try { content.innerHTML = marked.parse(text); } catch { content.textContent = text; }
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
                setTimeout(() => { copyBtn.innerHTML = `<svg viewBox="0 0 24 24" width="11" height="11"><path fill="currentColor" d="M16 1H4c-1.1 0-2 .9-2 2v14h2V3h12V1zm3 4H8c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h11c1.1 0 2-.9 2-2V7c0-1.1-.9-2-2-2zm0 16H8V7h11v14z"/></svg> Copy`; }, 2000);
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
    try { await fetch('/api/chat/clear', { method: 'POST' }); } catch (e) {}
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
    voiceBtn.addEventListener('touchend',   e => { e.preventDefault(); stopVoice(); });
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
        case 'focus':      msg = 'Start focus mode for 30 minutes'; break;
        case 'crypto':     msg = 'What is the current Cardano (ADA) price?'; break;
        case 'search':
            const q = prompt('Search for:');
            if (!q) return;
            msg = `Search the web for: ${q}`;
            break;
        case 'sysinfo': msg = 'Give me a summary of my system info and performance'; break;
    }
    if (msg) { messageInput.value = msg; sendMessage(); }
}

// ── System Stats ──────────────────────────
async function loadStats() {
    try {
        const r = await fetch('/api/system/stats');
        const d = await r.json();
        if (!d.success) return;
        setBar('cpuBar', 'cpuVal', d.cpu.percent);
        setBar('ramBar', 'ramVal', d.memory.percent);
        setBar('diskBar', 'diskVal', d.disk.percent);
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

// ── Memory Stats ──────────────────────────
async function loadMemoryStats() {
    try {
        const r = await fetch('/api/memory/stats');
        const d = await r.json();
        document.getElementById('convCount').textContent  = d.conversations ?? '—';
        document.getElementById('memCount').textContent   = d.memories ?? '—';
        document.getElementById('taskCount').textContent  = d.pending_tasks ?? '—';
        document.getElementById('notesCount').textContent = d.notes ?? '—';
    } catch (e) {}
}

// ── Projects Tab ──────────────────────────
async function loadProjectsTab() {
    try {
        const r = await fetch('/api/projects');
        const projects = await r.json();
        const list = document.getElementById('projectListFull');

        if (!projects.length) {
            list.innerHTML = '<div class="empty-state">No projects yet — add one!</div>';
            return;
        }
        list.innerHTML = '';
        projects.forEach(p => {
            const el = document.createElement('div');
            el.className = 'project-card';
            const statusColor = { active: '#3fb950', planning: '#d29922', paused: '#8b949e', completed: '#00d4ff' }[p.status] || '#8b949e';
            const priorityDot = p.priority === 'high' ? '🔴' : p.priority === 'medium' ? '🟡' : '⚪';
            el.innerHTML = `
                <div class="project-card-header">
                    <div class="project-card-name">${escHtml(p.name)}</div>
                    <div class="project-card-actions">
                        <span class="proj-priority" title="Priority">${priorityDot}</span>
                        <button class="proj-edit-btn" onclick="editProject(${p.id})" title="Edit">✏️</button>
                        <button class="proj-del-btn" onclick="deleteProject(${p.id}, this)" title="Delete">🗑</button>
                    </div>
                </div>
                <div class="project-card-meta">
                    <span class="proj-status-badge" style="color:${statusColor}">${p.status}</span>
                    ${p.stack ? `<span class="proj-stack">${escHtml(p.stack)}</span>` : ''}
                </div>
                ${p.description ? `<div class="project-card-desc">${escHtml(p.description)}</div>` : ''}
                ${p.goals ? `<div class="project-card-goals">${escHtml(p.goals.substring(0, 120))}${p.goals.length > 120 ? '...' : ''}</div>` : ''}
                <button class="proj-switch-btn" onclick="switchProject(${JSON.stringify(p.name)})">Set Active Context</button>
            `;
            list.appendChild(el);
        });

        // Also refresh the sidebar project list in System tab
        const sysProjects = document.getElementById('projectList');
        if (sysProjects) {
            sysProjects.innerHTML = '';
            projects.forEach(p => {
                const el = document.createElement('div');
                el.className = 'project-item' + (p.status === 'active' ? ' active' : '');
                el.innerHTML = `<span>${escHtml(p.name)}</span><span class="project-status">${p.priority === 'high' ? '🔴' : p.priority === 'medium' ? '🟡' : '⚪'}</span>`;
                el.onclick = () => switchProject(p.name);
                sysProjects.appendChild(el);
            });
        }
    } catch (e) {}
}

async function loadProjects() {
    await loadProjectsTab();
}

async function switchProject(name) {
    try {
        await fetch(`/api/projects/${encodeURIComponent(name)}/switch`, { method: 'POST' });
        projectBadge.textContent = name;
        document.querySelectorAll('.project-item').forEach(el => {
            el.classList.toggle('active', el.querySelector('span').textContent === name);
        });
        showToast(`Context → ${name}`, 'success');
    } catch (e) {}
}

function openProjectModal(id = null) {
    editingProjectId = id;
    document.getElementById('projectModalTitle').textContent = id ? 'Edit Project' : 'New Project';
    document.getElementById('editProjectId').value = id || '';
    if (!id) {
        ['projName','projDesc','projStack','projTech','projGoals','projUrl','projPath'].forEach(f => {
            const el = document.getElementById(f);
            if (el) el.value = '';
        });
        document.getElementById('projStatus').value   = 'active';
        document.getElementById('projPriority').value = 'medium';
    }
    openModal('projectModal');
}

async function editProject(id) {
    try {
        const r = await fetch(`/api/projects/${id}`);
        const p = await r.json();
        editingProjectId = id;
        document.getElementById('projectModalTitle').textContent = 'Edit Project';
        document.getElementById('editProjectId').value = id;
        document.getElementById('projName').value     = p.name || '';
        document.getElementById('projDesc').value     = p.description || '';
        document.getElementById('projStack').value    = p.stack || '';
        document.getElementById('projTech').value     = (p.tech || []).join(', ');
        document.getElementById('projGoals').value    = p.goals || '';
        document.getElementById('projUrl').value      = p.url || '';
        document.getElementById('projPath').value     = p.path || '';
        document.getElementById('projStatus').value   = p.status || 'active';
        document.getElementById('projPriority').value = p.priority || 'medium';
        openModal('projectModal');
    } catch (e) { showToast('Failed to load project', 'error'); }
}

async function submitProject() {
    const name = document.getElementById('projName').value.trim();
    if (!name) { showToast('Project name required', 'error'); return; }
    const id = document.getElementById('editProjectId').value;
    const payload = {
        name,
        description: document.getElementById('projDesc').value.trim(),
        stack:       document.getElementById('projStack').value.trim(),
        tech:        document.getElementById('projTech').value,
        goals:       document.getElementById('projGoals').value.trim(),
        url:         document.getElementById('projUrl').value.trim(),
        path:        document.getElementById('projPath').value.trim(),
        status:      document.getElementById('projStatus').value,
        priority:    document.getElementById('projPriority').value,
    };
    try {
        const url    = id ? `/api/projects/${id}` : '/api/projects';
        const method = id ? 'PUT' : 'POST';
        const r = await fetch(url, {
            method,
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        const d = await r.json();
        if (d.success || d.id) {
            closeModal('projectModal');
            loadProjectsTab();
            showToast(id ? 'Project updated' : 'Project created', 'success');
        } else {
            showToast(d.error || 'Failed', 'error');
        }
    } catch (e) { showToast('Save failed', 'error'); }
}

async function deleteProject(id, el) {
    if (!confirm('Delete this project?')) return;
    try {
        await fetch(`/api/projects/${id}`, { method: 'DELETE' });
        el.closest('.project-card').remove();
        showToast('Project deleted', 'info');
    } catch (e) {}
}

// ── Memory Browser ────────────────────────
async function loadMemoryBrowser(reset = false) {
    if (reset) { memOffset = 0; memActiveSource = null; }
    const q = document.getElementById('memSearchInput')?.value.trim() || '';
    const params = new URLSearchParams({ limit: 40, offset: memOffset });
    if (q) params.set('q', q);
    if (memActiveSource) params.set('source', memActiveSource);

    try {
        const r = await fetch('/api/memory/browse?' + params);
        const d = await r.json();
        renderMemoryList(d.memories || []);
        renderSourceFilter(d.sources || []);
    } catch (e) {}
}

function renderSourceFilter(sources) {
    const el = document.getElementById('memSourceFilter');
    if (!el) return;
    el.innerHTML = '';
    if (!sources.length) return;

    const all = document.createElement('button');
    all.className = 'source-chip' + (!memActiveSource ? ' active' : '');
    all.textContent = 'All';
    all.onclick = () => { memActiveSource = null; loadMemoryBrowser(true); };
    el.appendChild(all);

    sources.forEach(s => {
        const btn = document.createElement('button');
        btn.className = 'source-chip' + (memActiveSource === s ? ' active' : '');
        btn.textContent = s;
        btn.onclick = () => { memActiveSource = s; loadMemoryBrowser(true); };
        el.appendChild(btn);
    });
}

function renderMemoryList(memories) {
    const list = document.getElementById('memoryList');
    if (!list) return;
    if (!memories.length) {
        list.innerHTML = '<div class="empty-state">No memories found</div>';
        return;
    }
    list.innerHTML = '';
    memories.forEach(m => {
        const el = document.createElement('div');
        el.className = 'memory-item';
        const source = m.source ? `<span class="mem-source">${escHtml(m.source)}</span>` : '';
        el.innerHTML = `
            <div class="memory-item-body">
                <div class="memory-content">${escHtml(m.content)}</div>
                <div class="memory-meta">${source}<span class="mem-cat">${escHtml(m.category || '')}</span></div>
            </div>
            <button class="del-btn mem-del-btn" onclick="deleteMemory(${m.id}, this)" title="Delete">×</button>
        `;
        list.appendChild(el);
    });
}

async function deleteMemory(id, el) {
    try {
        await fetch(`/api/memory/${id}`, { method: 'DELETE' });
        el.closest('.memory-item').remove();
        loadMemoryStats();
        showToast('Memory deleted', 'info');
    } catch (e) {}
}

function debounceMemSearch() {
    clearTimeout(memSearchTimer);
    memSearchTimer = setTimeout(() => loadMemoryBrowser(true), 400);
}

// ── Teach Modal ───────────────────────────
function openTeachModal() {
    document.getElementById('teachContent').value = '';
    document.getElementById('teachCategory').value = 'user-taught';
    document.getElementById('teachImportance').value = '3';
    openModal('teachModal');
    setTimeout(() => document.getElementById('teachContent').focus(), 100);
}

async function submitTeach() {
    const content    = document.getElementById('teachContent').value.trim();
    const category   = document.getElementById('teachCategory').value;
    const importance = document.getElementById('teachImportance').value;
    if (!content) { showToast('Please enter something to remember', 'error'); return; }
    try {
        const r = await fetch('/api/memory/teach', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ content, category, importance: parseInt(importance) })
        });
        const d = await r.json();
        if (d.success) {
            closeModal('teachModal');
            loadMemoryStats();
            if (document.getElementById('panel-memory')?.classList.contains('active')) {
                loadMemoryBrowser(true);
            }
            showToast('Memory saved — JARVIS will remember this!', 'success');
        }
    } catch (e) { showToast('Save failed', 'error'); }
}

// ── Import Modal ──────────────────────────
function openImportModal() {
    importSelectedSource = 'auto';
    importFileContent    = null;
    importFileName       = '';
    document.getElementById('importPasteArea').value = '';
    document.getElementById('dropFilename').classList.add('hidden');
    document.getElementById('dropFilename').textContent = '';
    document.getElementById('importPreview').classList.add('hidden');
    document.getElementById('importSubmitBtn').disabled = false;
    document.querySelectorAll('.source-btn').forEach(b => {
        b.classList.toggle('active', b.dataset.source === 'auto');
    });
    openModal('importModal');
}

function selectSource(btn, source) {
    importSelectedSource = source;
    document.querySelectorAll('.source-btn').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
}

function handleImportFile(input) {
    const file = input.files[0];
    if (!file) return;
    importFileName = file.name;
    const fn = document.getElementById('dropFilename');
    fn.textContent = `📄 ${file.name} (${(file.size/1024).toFixed(1)} KB)`;
    fn.classList.remove('hidden');

    const reader = new FileReader();
    reader.onload = (e) => {
        importFileContent = e.target.result;
        document.getElementById('importPreview').classList.add('hidden');
    };
    reader.readAsText(file);
}

function setupDropZone() {
    const dz = document.getElementById('dropZone');
    if (!dz) return;
    dz.addEventListener('dragover', e => { e.preventDefault(); dz.classList.add('drag-over'); });
    dz.addEventListener('dragleave', () => dz.classList.remove('drag-over'));
    dz.addEventListener('drop', e => {
        e.preventDefault();
        dz.classList.remove('drag-over');
        const file = e.dataTransfer.files[0];
        if (file) {
            const dt = new DataTransfer();
            dt.items.add(file);
            const inp = document.getElementById('importFile');
            inp.files = dt.files;
            handleImportFile(inp);
        }
    });
}

async function submitImport() {
    const content   = importFileContent || document.getElementById('importPasteArea').value;
    const pasteText = document.getElementById('importPasteArea').value.trim();

    if (!content && !pasteText) {
        showToast('Please upload a file or paste some text', 'error');
        return;
    }

    const btn = document.getElementById('importSubmitBtn');
    btn.disabled = true;
    btn.textContent = 'Importing...';

    try {
        let res;
        if (importFileContent) {
            const blob = new Blob([importFileContent], { type: 'text/plain' });
            const form = new FormData();
            form.append('file', blob, importFileName || 'import.json');
            res = await fetch(`/api/memory/import?source=${importSelectedSource}`, {
                method: 'POST', body: form
            });
        } else {
            res = await fetch('/api/memory/import', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    content: pasteText,
                    filename: 'paste',
                    source: importSelectedSource
                })
            });
        }

        const d = await res.json();
        if (d.success) {
            const preview = document.getElementById('importPreview');
            const count   = document.getElementById('previewCount');
            const samples = document.getElementById('previewSamples');
            count.textContent   = `✓ ${d.imported} memories imported from ${d.format}`;
            samples.innerHTML = (d.preview || []).map(p =>
                `<div class="preview-sample">${escHtml(p.substring(0, 120))}...</div>`
            ).join('');
            preview.classList.remove('hidden');
            loadMemoryStats();
            if (document.getElementById('panel-memory')?.classList.contains('active')) {
                loadMemoryBrowser(true);
            }
            showToast(`${d.imported} memories imported from ${d.format}!`, 'success');
            btn.textContent = `✓ ${d.imported} imported`;
        } else {
            showToast(d.error || 'Import failed', 'error');
            btn.disabled = false;
            btn.textContent = 'Import Memory';
        }
    } catch (e) {
        showToast('Import failed', 'error');
        btn.disabled = false;
        btn.textContent = 'Import Memory';
    }
}

// ── Sidebar Tabs ──────────────────────────
function switchTab(tab) {
    document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
    document.querySelectorAll('.tab-panel').forEach(p => p.classList.remove('active'));
    document.getElementById('tab-' + tab)?.classList.add('active');
    document.getElementById('panel-' + tab)?.classList.add('active');

    if (tab === 'tasks')    loadTasks();
    if (tab === 'notes')    loadNotes();
    if (tab === 'memory')   loadMemoryBrowser(true);
    if (tab === 'projects') loadProjectsTab();
}

// ── Tasks ─────────────────────────────────
function showAddTask() {
    const f = document.getElementById('addTaskForm');
    f.classList.toggle('hidden');
    if (!f.classList.contains('hidden')) document.getElementById('taskTitle').focus();
}

async function submitTask() {
    const title   = document.getElementById('taskTitle').value.trim();
    const project = document.getElementById('taskProject').value.trim();
    if (!title) return;
    try {
        await fetch('/api/tasks', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ title, project: project || null })
        });
        document.getElementById('taskTitle').value   = '';
        document.getElementById('taskProject').value = '';
        document.getElementById('addTaskForm').classList.add('hidden');
        loadTasks();
        loadMemoryStats();
        showToast('Task added', 'success');
    } catch (e) { showToast('Failed to add task', 'error'); }
}

async function completeTask(id, el) {
    try {
        await fetch(`/api/tasks/${id}/complete`, { method: 'POST' });
        el.closest('.task-item').style.opacity = '0.4';
        setTimeout(() => el.closest('.task-item').remove(), 400);
        loadMemoryStats();
        showToast('Task completed ✓', 'success');
    } catch (e) {}
}

async function loadTasks() {
    try {
        const r = await fetch('/api/tasks');
        const d = await r.json();
        const list = document.getElementById('taskList');
        if (!d.tasks || !d.tasks.length) {
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
    const title   = document.getElementById('noteTitle').value.trim();
    const content = document.getElementById('noteContent').value.trim();
    if (!title) return;
    try {
        await fetch('/api/notes', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ title, content })
        });
        document.getElementById('noteTitle').value   = '';
        document.getElementById('noteContent').value = '';
        document.getElementById('addNoteForm').classList.add('hidden');
        loadNotes();
        loadMemoryStats();
        showToast('Note saved', 'success');
    } catch (e) { showToast('Failed to save note', 'error'); }
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
        if (!d.notes || !d.notes.length) {
            list.innerHTML = '<div class="empty-state">No notes yet</div>';
            return;
        }
        list.innerHTML = '';
        [...d.notes].forEach(n => {
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

// ── Modal helpers ─────────────────────────
function openModal(id) {
    document.getElementById(id)?.classList.remove('hidden');
    document.body.style.overflow = 'hidden';
}
function closeModal(id) {
    document.getElementById(id)?.classList.add('hidden');
    document.body.style.overflow = '';
}
// Close on overlay click
document.addEventListener('click', (e) => {
    if (e.target.classList.contains('modal-overlay')) {
        e.target.classList.add('hidden');
        document.body.style.overflow = '';
    }
});
// Close on Escape
document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
        document.querySelectorAll('.modal-overlay:not(.hidden)').forEach(m => {
            m.classList.add('hidden');
        });
        document.body.style.overflow = '';
    }
});

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
    return String(str || '')
        .replace(/&/g, '&amp;').replace(/</g, '&lt;')
        .replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}
