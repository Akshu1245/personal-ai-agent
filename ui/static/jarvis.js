// JARVIS UI JavaScript

// DOM Elements
const messagesContainer = document.getElementById('messages');
const messageInput = document.getElementById('messageInput');
const sendBtn = document.getElementById('sendBtn');
const voiceBtn = document.getElementById('voiceBtn');
const statusDot = document.getElementById('statusDot');
const statusText = document.getElementById('statusText');
const cpuBar = document.getElementById('cpuBar');
const ramBar = document.getElementById('ramBar');

// State
let isListening = false;
let socket = null;

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    initWebSocket();
    setupEventListeners();
    updateSystemInfo();
});

// WebSocket Connection
function initWebSocket() {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}`;
    
    socket = new WebSocket(wsUrl);
    
    socket.onopen = () => {
        console.log('Connected to JARVIS');
        statusDot.style.background = '#00ff88';
        statusText.textContent = 'Online';
    };
    
    socket.onclose = () => {
        console.log('Disconnected from JARVIS');
        statusDot.style.background = '#ff4466';
        statusText.textContent = 'Offline';
        // Reconnect after 3 seconds
        setTimeout(initWebSocket, 3000);
    };
    
    socket.onmessage = (event) => {
        const data = JSON.parse(event.data);
        handleWebSocketMessage(data);
    };
    
    socket.onerror = (error) => {
        console.error('WebSocket error:', error);
    };
}

// Handle WebSocket messages
function handleWebSocketMessage(data) {
    if (data.status !== undefined) {
        // Status update
        if (data.listening !== undefined) {
            isListening = data.listening;
            voiceBtn.classList.toggle('active', isListening);
        }
    }
    
    if (data.text !== undefined) {
        // JARVIS response
        addMessage('bot', data.text);
    }
}

// Event Listeners
function setupEventListeners() {
    // Send button
    sendBtn.addEventListener('click', sendMessage);
    
    // Enter key
    messageInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') {
            sendMessage();
        }
    });
    
    // Voice button
    voiceBtn.addEventListener('mousedown', startVoice);
    voiceBtn.addEventListener('mouseup', stopVoice);
    voiceBtn.addEventListener('mouseleave', stopVoice);
    
    // Touch support for mobile
    voiceBtn.addEventListener('touchstart', (e) => {
        e.preventDefault();
        startVoice();
    });
    voiceBtn.addEventListener('touchend', (e) => {
        e.preventDefault();
        stopVoice();
    });
}

// Send message
async function sendMessage() {
    const message = messageInput.value.trim();
    if (!message) return;
    
    // Add user message to UI
    addMessage('user', message);
    messageInput.value = '';
    
    // Send to API
    try {
        const response = await fetch('/api/chat', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ message })
        });
        
        const data = await response.json();
        
        if (data.response) {
            addMessage('bot', data.response);
            // Speak response
            speakText(data.response);
        }
        
    } catch (error) {
        console.error('Error:', error);
        addMessage('bot', '⚠️ Sorry, I encountered an error. Please try again.');
    }
}

// Add message to UI
function addMessage(type, text) {
    const messageDiv = document.createElement('div');
    messageDiv.className = `message ${type}`;
    
    const avatar = document.createElement('div');
    avatar.className = 'avatar';
    avatar.innerHTML = `<div class="avatar-inner">${type === 'bot' ? 'J' : 'A'}</div>`;
    
    const content = document.createElement('div');
    content.className = 'content';
    
    // Convert markdown-like formatting
    content.innerHTML = formatMessage(text);
    
    messageDiv.appendChild(avatar);
    messageDiv.appendChild(content);
    
    messagesContainer.appendChild(messageDiv);
    
    // Scroll to bottom
    messagesContainer.scrollTop = messagesContainer.scrollHeight;
}

// Format message text
function formatMessage(text) {
    // Simple formatting
    return text
        .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
        .replace(/\*(.*?)\*/g, '<em>$1</em>')
        .replace(/`(.*?)`/g, '<code>$1</code>')
        .replace(/\n/g, '<br>');
}

// Voice Input
function startVoice() {
    if (!socket || socket.readyState !== WebSocket.OPEN) {
        console.log('WebSocket not connected');
        return;
    }
    
    isListening = true;
    socket.send(JSON.stringify({ voice_start: true }));
    voiceBtn.classList.add('listening');
}

function stopVoice() {
    if (!socket || socket.readyState !== WebSocket.OPEN) return;
    
    isListening = false;
    socket.send(JSON.stringify({ voice_stop: true }));
    voiceBtn.classList.remove('listening');
}

// Text-to-Speech
function speakText(text) {
    fetch('/api/voice/output', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text })
    });
}

// Quick Actions
function quickAction(action) {
    let message = '';
    
    switch(action) {
        case 'screenshot':
            message = 'Take a screenshot';
            break;
        case 'focus':
            message = 'Start focus mode for 30 minutes';
            break;
        case 'crypto':
            message = 'What is Cardano price?';
            break;
        case 'search':
            message = prompt('What do you want to search?') || '';
            break;
    }
    
    if (message) {
        messageInput.value = message;
        sendMessage();
    }
}

// Update system info
async function updateSystemInfo() {
    try {
        const response = await fetch('/api/state');
        const data = await response.json();
        
        // Simulated values - in production, get from API
        cpuBar.style.width = `${Math.random() * 60 + 20}%`;
        ramBar.style.width = `${Math.random() * 40 + 40}%`;
        
    } catch (error) {
        console.error('Error updating system info:', error);
    }
    
    // Update every 10 seconds
    setTimeout(updateSystemInfo, 10000);
}

// Load projects
async function loadProjects() {
    try {
        const response = await fetch('/api/projects');
        const data = await response.json();
        
        const projectList = document.getElementById('projectList');
        projectList.innerHTML = '';
        
        data.forEach(project => {
            const div = document.createElement('div');
            div.className = 'project';
            div.textContent = project.name;
            projectList.appendChild(div);
        });
        
    } catch (error) {
        console.error('Error loading projects:', error);
    }
}

// Load projects on init
loadProjects();
