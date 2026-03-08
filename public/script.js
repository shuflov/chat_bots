async function loadPersonalities() {
    try {
        const res = await fetch('/api/personalities');
        const data = await res.json();
        const personalities = data.personalities || [];
        
        const bot1 = document.getElementById('bot1');
        const bot2 = document.getElementById('bot2');
        const customList = document.getElementById('custom-personalities');
        
        if (bot1 && bot2) {
            const options = personalities.map(p => 
                `<option value="${p.id}">${escapeHtml(p.name)}</option>`
            ).join('');
            bot1.innerHTML = options;
            bot2.innerHTML = options;
            if (personalities.length >= 2) {
                bot2.value = personalities[1].id;
            }
        }
        
        if (customList) {
            const custom = personalities.filter(p => !p.is_preset);
            if (custom.length > 0) {
                customList.innerHTML = '<h3>Your Personalities</h3>' + custom.map(p => `
                    <div class="personality-item">
                        <span>${escapeHtml(p.name)}</span>
                        <button onclick="deletePersonality(${p.id})" class="btn-delete">Delete</button>
                    </div>
                `).join('');
            } else {
                customList.innerHTML = '';
            }
        }
    } catch (e) {
        console.error('Error loading personalities:', e);
    }
}

async function deletePersonality(id) {
    if (!confirm('Delete this personality?')) return;
    await fetch(`/api/personalities/${id}`, {method: 'DELETE'});
    loadPersonalities();
}

async function loadConversations() {
    try {
        const res = await fetch('/api/conversations');
        const convs = await res.json();
        const list = document.getElementById('conversations-list');
        
        if (convs.length === 0) {
            list.innerHTML = '<p class="empty">No conversations yet. Click "Start Conversation" to create one!</p>';
            return;
        }
        
        list.innerHTML = convs.map(c => {
            let statusText = c.status;
            if (c.status === 'running') {
                statusText = `Turn ${c.current_turn}/${c.max_turns}`;
            } else if (c.status === 'stopped') {
                statusText = `Stopped (${c.current_turn}/${c.max_turns})`;
            }
            return `
            <div class="conv-item">
                <a href="/conversation/${c.id}" class="conv-link">
                    <span class="conv-title">${escapeHtml(c.title)}</span>
                    <span class="conv-meta">
                        <span class="status-${c.status}">${statusText}</span>
                        <span class="conv-date">${new Date(c.created_at).toLocaleString()}</span>
                        <span class="tokens">${c.total_tokens || 0} tokens</span>
                    </span>
                </a>
                <button class="btn-delete-small" onclick="event.preventDefault(); deleteConversation(${c.id})">🗑️</button>
            </div>
        `}).join('');
    } catch (e) {
        document.getElementById('conversations-list').innerHTML = '<p class="error">Error loading conversations</p>';
    }
}

async function deleteConversation(id) {
    if (confirm('Delete this conversation?')) {
        await fetch(`/api/conversations/${id}`, {method: 'DELETE'});
        loadConversations();
    }
}

async function loadConversation(id) {
    try {
        const res = await fetch(`/api/conversations/${id}`);
        if (!res.ok) throw new Error('Not found');
        const conv = await res.json();
        
        document.getElementById('conv-title').textContent = conv.title;
        document.getElementById('delete-btn').style.display = (conv.status === 'completed' || conv.status === 'stopped') ? 'block' : 'none';
        
        const progress = document.getElementById('progress');
        const stopBtn = document.getElementById('stop-btn');
        const completionMsg = document.getElementById('completion-msg');
        
        if (conv.status === 'running') {
            progress.innerHTML = `<span class="status-running">Turn ${conv.current_turn}/${conv.max_turns} • ${conv.remaining} remaining</span> <span class="tokens">• ${conv.total_tokens || 0} tokens</span>`;
            stopBtn.style.display = 'block';
            completionMsg.style.display = 'none';
        } else if (conv.status === 'stopped') {
            progress.innerHTML = `<span class="status-stopped">Stopped at turn ${conv.current_turn}/${conv.max_turns}</span> <span class="tokens">• ${conv.total_tokens || 0} tokens</span>`;
            stopBtn.style.display = 'none';
            completionMsg.style.display = 'none';
        } else if (conv.status === 'completed') {
            progress.innerHTML = `<span class="status-completed">Completed (${conv.max_turns} turns)</span> <span class="tokens">• ${conv.total_tokens || 0} tokens</span>`;
            stopBtn.style.display = 'none';
            completionMsg.style.display = 'block';
        } else {
            progress.innerHTML = '';
            stopBtn.style.display = 'none';
            completionMsg.style.display = 'none';
        }
        
        const msgs = document.getElementById('messages');
        if (conv.messages.length === 0) {
            msgs.innerHTML = '<p class="empty">Conversation starting...</p>';
        } else {
            msgs.innerHTML = conv.messages.map(m => `
                <div class="message ${m.sender === 'You' ? 'user' : m.sender === conv.bot1_personality ? 'bot1' : 'bot2'}">
                    <div class="sender">${escapeHtml(m.sender)}${m.total_tokens ? `<span class="tokens">${m.total_tokens} tokens</span>` : ''}</div>
                    <div class="content">${escapeHtml(m.content)}</div>
                </div>
            `).join('');
            msgs.scrollTop = msgs.scrollHeight;
        }
        
        if (conv.status === 'running') {
            setTimeout(() => loadConversation(id), 5000);
        }
    } catch (e) {
        document.getElementById('conv-title').textContent = 'Error loading conversation';
    }
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}
