const dropdown = document.querySelector('.custom-dropdown');
const button = dropdown.querySelector('.dropdown-btn');
const recentChatsList = document.getElementById('recentChatsList');
const newChatBtn = document.getElementById('newChatBtn');
const searchChatsBtn = document.getElementById('searchChatsBtn');

const hamburgerBtn = document.getElementById('hamburgerBtn');
const sidebarEl = document.getElementById('sidebarEl');
const sidebarBackdrop = document.getElementById('sidebarBackdrop');

const MOBILE_BREAKPOINT = 768;

function isMobile() {
    return window.innerWidth <= MOBILE_BREAKPOINT;
}

function toggleSidebar() {
    if (isMobile()) {
        // Mobile: slide in from left / fully hide
        if (sidebarEl.classList.contains('open')) {
            sidebarEl.classList.remove('open');
            sidebarBackdrop.classList.remove('show');
        } else {
            sidebarEl.classList.add('open');
            sidebarBackdrop.classList.remove('show'); // backdrop handles close
            sidebarBackdrop.classList.add('show');
        }
    } else {
        // Desktop: toggle icons-only collapsed state
        sidebarEl.classList.toggle('collapsed');
    }
}

function closeSidebar() {
    sidebarEl.classList.remove('open');
    sidebarBackdrop.classList.remove('show');
}

hamburgerBtn.addEventListener('click', toggleSidebar);
sidebarBackdrop.addEventListener('click', closeSidebar);

// Clean up stale classes when resizing between mobile/desktop
window.addEventListener('resize', () => {
    if (!isMobile()) {
        sidebarEl.classList.remove('open');
        sidebarBackdrop.classList.remove('show');
    } else {
        sidebarEl.classList.remove('collapsed');
    }
});

const searchModalOverlay = document.getElementById('searchModalOverlay');
const searchInput = document.getElementById('searchInput');
const searchResults = document.getElementById('searchResults');

const promptInput = document.getElementById('promptInput');
const sendBtn = document.getElementById('sendBtn');
const chatHistory = document.getElementById('chatHistory');
let ableToSend = true;

const plusBtn = document.getElementById('plusBtn');
const uploadMenu = document.getElementById('uploadMenu');
const uploadFilesBtn = document.getElementById('uploadFilesBtn');
const fileInput = document.getElementById('fileInput');
const attachmentsPreview = document.getElementById('attachmentsPreview');

const chatContainer = document.getElementById('chatContainer');
const welcomeGreeting = document.getElementById('welcomeGreetingText');

const STORAGE_KEY = 'grepChatsData';
const ACTIVE_CHAT_KEY = 'grepActiveChatId';

let chatsData = { chats: {} };
let currentChatId = null;

if (document.readyState === 'complete') {
    init();
} else {
    window.addEventListener('load', init);
}

async function init() {
    promptInput.focus();
    button.style.backgroundColor = '#000000';
    await loadChatsFromStorage();
    renderRecentChats();

    const savedActiveId = localStorage.getItem(ACTIVE_CHAT_KEY);
    if (savedActiveId && chatsData.chats[savedActiveId]) {
        loadChat(savedActiveId);
    } else {
        startNewChat();
    }
}



const sidebarOptions = [newChatBtn, searchChatsBtn, button];

function setActiveSidebarOption(activeEl) {
    sidebarOptions.forEach(el => el.classList.remove('active'));
    if (activeEl) {
        activeEl.classList.add('active');
    }
}



async function loadChatsFromStorage() {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (stored) {
        chatsData = JSON.parse(stored);
        return;
    }

    
    chatsData = { chats: {} };
    saveChatsToStorage();
}

function saveChatsToStorage() {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(chatsData));
}

function getNextChatId() {
    const existingNums = Object.keys(chatsData.chats)
        .map(id => parseInt(id.replace('chat', ''), 10))
        .filter(n => !isNaN(n));
    const max = existingNums.length ? Math.max(...existingNums) : 0;
    return 'chat' + (max + 1);
}

function getMessageCount(chatId) {
    const chat = chatsData.chats[chatId];
    if (!chat) return 0;
    const userKeys = Object.keys(chat).filter(k => k.startsWith('user-response'));
    return userKeys.length;
}

function saveMessageToChat(chatId, sender, text) {
    if (!chatsData.chats[chatId]) {
        chatsData.chats[chatId] = {};
    }
    const chat = chatsData.chats[chatId];

    if (sender === 'user') {
        const nextIndex = getMessageCount(chatId) + 1;
        chat['user-response' + nextIndex] = text;
    } else {
        
        const index = getMessageCount(chatId);
        chat['ai-response' + index] = text;
    }

    saveChatsToStorage();
    renderRecentChats();
}

function getGreeting() {
    const hour = new Date().getHours();
    const name = (typeof USER_FIRST_NAME !== 'undefined' && USER_FIRST_NAME) ? USER_FIRST_NAME : '';

    if (hour >= 21 || hour <= 6) return 'Hello, Night Owl.';

    if (!name) {
        if (hour >= 7 && hour <= 11) return 'Good morning.';
        if (hour >= 12 && hour <= 16) return 'Good afternoon.';
        return 'Good evening.';
    }

    if (hour >= 7 && hour <= 11) return `Morning, ${name}.`;
    if (hour >= 12 && hour <= 16) return `Afternoon, ${name}.`;
    return `Evening, ${name}.`;
}

function updateEmptyState() {
    const isEmpty = chatHistory.children.length === 0;
    chatContainer.classList.toggle('empty-chat', isEmpty);
    if (isEmpty) {
        welcomeGreeting.textContent = getGreeting();
    }
}

function startNewChat() {
    currentChatId = null;
    localStorage.removeItem(ACTIVE_CHAT_KEY);

    chatHistory.innerHTML = '';
    renderRecentChats();
    setActiveSidebarOption(newChatBtn);
    updateEmptyState();
    closeSidebar();
    promptInput.focus();
}

function loadChat(chatId) {
    if (!chatsData.chats[chatId]) return;

    currentChatId = chatId;
    localStorage.setItem(ACTIVE_CHAT_KEY, chatId);
    chatHistory.innerHTML = '';

    const chat = chatsData.chats[chatId];
    const messageCount = getMessageCount(chatId);

    for (let i = 1; i <= messageCount; i++) {
        if (chat['user-response' + i] !== undefined) {
            appendMessage(chat['user-response' + i], 'user', false);
        }
        if (chat['ai-response' + i] !== undefined) {
            appendMessage(chat['ai-response' + i], 'ai', false);
        }
    }

    renderRecentChats();
    setActiveSidebarOption(button);
    updateEmptyState();
    closeSidebar();
}

function deleteChat(chatId) {
    delete chatsData.chats[chatId];
    saveChatsToStorage();

    if (chatId === currentChatId) {
        const remainingIds = Object.keys(chatsData.chats);
        if (remainingIds.length > 0) {
            loadChat(remainingIds[0]);
        } else {
            startNewChat();
        }
    } else {
        renderRecentChats();
    }
}



function getDisplayText(text) {
    if (text.startsWith('img::')) return 'Image';
    if (text.startsWith('file::')) return text.slice(6);
    return text;
}

function getChatPreview(chatId) {
    const chat = chatsData.chats[chatId];
    if (!chat) return chatId;

    // Use AI-generated title if available
    if (chat['title']) {
        const t = chat['title'];
        return t.length > 30 ? t.slice(0, 30) + '…' : t;
    }

    // Fall back to first message while title is being generated
    if (chat['user-response1']) {
        const preview = getDisplayText(chat['user-response1']);
        return preview.length > 24 ? preview.slice(0, 24) + '…' : preview;
    }
    return chatId;
}

async function fetchAndSaveTitle(chatId, firstMessage) {
    // Only generate a title once (when the chat has no title yet)
    if (chatsData.chats[chatId]?.title) return;

    try {
        const resp = await fetch('/generate-title', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ message: firstMessage })
        });
        const data = await resp.json();
        if (data.title && chatsData.chats[chatId]) {
            chatsData.chats[chatId]['title'] = data.title;
            saveChatsToStorage();
            renderRecentChats();
        }
    } catch (err) {
        console.warn('Title generation failed:', err);
    }
}

function renderRecentChats() {
    recentChatsList.innerHTML = '';

    const chatIds = Object.keys(chatsData.chats).sort((a, b) => {
        const numA = parseInt(a.replace('chat', ''), 10);
        const numB = parseInt(b.replace('chat', ''), 10);
        return numB - numA; 
    });

    chatIds.forEach(chatId => {
        const row = document.createElement('div');
        row.classList.add('dropdown-item-row');
        if (chatId === currentChatId) {
            row.classList.add('active');
        }

        const label = document.createElement('p');
        label.classList.add('dropdown-item', 'option');
        label.textContent = getChatPreview(chatId);
        label.addEventListener('click', (event) => {
            event.stopPropagation();
            loadChat(chatId);
        });

        const deleteBtn = document.createElement('button');
        deleteBtn.classList.add('delete-chat-btn');
        deleteBtn.setAttribute('aria-label', 'Delete chat');
        deleteBtn.innerHTML = `
        <svg viewBox="0 0 16 16" xmlns="http://www.w3.org/2000/svg" fill="currentColor">
            <path d="M5.5 5.5A.5.5 0 0 1 6 6v6a.5.5 0 0 1-1 0V6a.5.5 0 0 1 .5-.5zm2.5 0a.5.5 0 0 1 .5.5v6a.5.5 0 0 1-1 0V6a.5.5 0 0 1 .5-.5zm3 .5a.5.5 0 0 0-1 0v6a.5.5 0 0 0 1 0V6z"/>
            <path fill-rule="evenodd" d="M14.5 3a1 1 0 0 1-1 1H13v9a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V4h-.5a1 1 0 0 1-1-1V2a1 1 0 0 1 1-1H6a1 1 0 0 1 1-1h2a1 1 0 0 1 1 1h3.5a1 1 0 0 1 1 1v1zM4.118 4 4 4.059V13a1 1 0 0 0 1 1h6a1 1 0 0 0 1-1V4.059L11.882 4H4.118zM2.5 3V2h11v1h-11z"/>
        </svg>
        `;
        deleteBtn.style.color = 'var(--text-light)';
        deleteBtn.querySelector('svg').style.width = '20px';
        deleteBtn.querySelector('svg').style.height = '20px';
        deleteBtn.style.margin = '0';
        deleteBtn.addEventListener('click', (event) => {
            event.stopPropagation();
            deleteChat(chatId);
        });

        row.appendChild(label);
        row.appendChild(deleteBtn);
        recentChatsList.appendChild(row);
    });
}



button.addEventListener('click', () => {
    dropdown.classList.toggle('open');
    const isOpen = dropdown.classList.contains('open');
    button.setAttribute('aria-expanded', isOpen);
    if (isOpen) {
        setActiveSidebarOption(button);
    }
});

window.addEventListener('click', (event) => {
    if (!dropdown.contains(event.target)) {
        dropdown.classList.remove('open');
        button.setAttribute('aria-expanded', 'false');
    }
});

newChatBtn.addEventListener('click', startNewChat);



function openSearchModal() {
    setActiveSidebarOption(searchChatsBtn);
    searchModalOverlay.classList.add('show');
    searchInput.value = '';
    renderSearchResults('');
    searchInput.focus();
}

function closeSearchModal() {
    searchModalOverlay.classList.remove('show');
}

function getChatFullText(chatId) {
    const chat = chatsData.chats[chatId];
    return Object.values(chat).join(' ').toLowerCase();
}

function renderSearchResults(query) {
    searchResults.innerHTML = '';
    const lowerQuery = query.trim().toLowerCase();

    const chatIds = Object.keys(chatsData.chats).sort((a, b) => {
        const numA = parseInt(a.replace('chat', ''), 10);
        const numB = parseInt(b.replace('chat', ''), 10);
        return numB - numA;
    });

    const matches = chatIds.filter(chatId => {
        if (lowerQuery === '') return true;
        return getChatFullText(chatId).includes(lowerQuery);
    });

    if (matches.length === 0) {
        const empty = document.createElement('p');
        empty.classList.add('search-no-results');
        empty.textContent = 'No chats found';
        searchResults.appendChild(empty);
        return;
    }

    matches.forEach(chatId => {
        const chat = chatsData.chats[chatId];
        const item = document.createElement('div');
        item.classList.add('search-result-item');

        const title = document.createElement('p');
        title.classList.add('search-result-title');
        title.textContent = getChatPreview(chatId);

        const snippet = document.createElement('p');
        snippet.classList.add('search-result-snippet');
        const rawSnippet = chat['ai-response1'] || chat['user-response2'] || '';
        snippet.textContent = rawSnippet ? getDisplayText(rawSnippet) : '';

        item.appendChild(title);
        item.appendChild(snippet);

        item.addEventListener('click', () => {
            loadChat(chatId);
            closeSearchModal();
        });

        searchResults.appendChild(item);
    });
}

searchChatsBtn.addEventListener('click', openSearchModal);

searchInput.addEventListener('input', () => {
    renderSearchResults(searchInput.value);
});

searchModalOverlay.addEventListener('click', (event) => {
    if (event.target === searchModalOverlay) {
        closeSearchModal();
    }
});

document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape') {
        closeSearchModal();
    }
});

// ---- Plus / upload menu ----

function openUploadMenu() {
    plusBtn.classList.add('active');
    plusBtn.setAttribute('aria-expanded', 'true');
    uploadMenu.classList.add('show');
}

function closeUploadMenu() {
    plusBtn.classList.remove('active');
    plusBtn.setAttribute('aria-expanded', 'false');
    uploadMenu.classList.remove('show');
}

plusBtn.addEventListener('click', (event) => {
    event.stopPropagation();
    if (uploadMenu.classList.contains('show')) {
        closeUploadMenu();
    } else {
        openUploadMenu();
    }
});

document.addEventListener('click', (event) => {
    if (!plusBtn.contains(event.target) && !uploadMenu.contains(event.target)) {
        closeUploadMenu();
    }
});

uploadFilesBtn.addEventListener('click', (event) => {
    event.stopPropagation();
    fileInput.click();
});

// ---- Staged attachments (restricted to VisionConfig: image_channels=3, image_size=224) ----

// Only these MIME types are reliably RGB (3-channel). RGBA PNGs and grayscale
// images are caught later by the canvas channel check.
const ALLOWED_IMAGE_TYPES = ['image/jpeg', 'image/jpg', 'image/png', 'image/webp', 'image/bmp'];
const VISION_IMAGE_SIZE = 224; // matches VisionConfig.image_size

let pendingAttachments = [];

function validateImageFile(file) {
    if (!file.type.startsWith('image/')) {
        return { ok: false, reason: `"${file.name}" is not an image. Only images are accepted.` };
    }
    if (!ALLOWED_IMAGE_TYPES.includes(file.type)) {
        return { ok: false, reason: `"${file.name}" — unsupported format. Use JPG, PNG, WebP, or BMP.` };
    }
    return { ok: true };
}

function checkRgbAndStage(file, id) {
    const reader = new FileReader();
    reader.onload = () => {
        const img = new Image();
        img.onload = () => {
            const canvas = document.createElement('canvas');
            canvas.width = VISION_IMAGE_SIZE;
            canvas.height = VISION_IMAGE_SIZE;
            const ctx = canvas.getContext('2d');
            ctx.drawImage(img, 0, 0, VISION_IMAGE_SIZE, VISION_IMAGE_SIZE);

            // Sample the center pixel to detect grayscale (R=G=B) or full transparency (alpha=0)
            const [r, g, b, a] = ctx.getImageData(VISION_IMAGE_SIZE / 2, VISION_IMAGE_SIZE / 2, 1, 1).data;
            if (a === 0) {
                alert(`"${file.name}" appears to be fully transparent and can't be used (VisionConfig requires image_channels=3).`);
                return;
            }

            // Get the resized 224x224 data URL to send to the model
            const resizedDataUrl = canvas.toDataURL('image/jpeg', 0.92);
            pendingAttachments.push({ id, type: 'image', name: file.name, dataUrl: resizedDataUrl });
            renderAttachmentsPreview();
        };
        img.onerror = () => {
            alert(`"${file.name}" couldn't be read as a valid image.`);
        };
        img.src = reader.result;
    };
    reader.readAsDataURL(file);
}

function removeAttachment(id) {
    pendingAttachments = pendingAttachments.filter(a => a.id !== id);
    renderAttachmentsPreview();
}

function renderAttachmentsPreview() {
    attachmentsPreview.innerHTML = '';

    pendingAttachments.forEach(att => {
        const wrapper = document.createElement('div');
        wrapper.classList.add('attachment-image-preview');

        const img = document.createElement('img');
        img.src = att.dataUrl;
        img.alt = att.name;

        const removeBtn = document.createElement('button');
        removeBtn.classList.add('remove-btn');
        removeBtn.setAttribute('aria-label', 'Remove attachment');
        removeBtn.innerHTML = `
            <svg viewBox="0 0 24 24" fill="none">
                <path d="M5 5l14 14M19 5L5 19" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>
            </svg>
        `;
        removeBtn.addEventListener('click', () => removeAttachment(att.id));

        wrapper.appendChild(img);
        wrapper.appendChild(removeBtn);
        attachmentsPreview.appendChild(wrapper);
    });

    updateSendButtonState();
}

fileInput.addEventListener('change', () => {
    const files = Array.from(fileInput.files);

    files.forEach(file => {
        const { ok, reason } = validateImageFile(file);
        if (!ok) {
            alert(reason);
            return;
        }
        const id = 'att-' + Date.now() + '-' + Math.random().toString(36).slice(2, 7);
        checkRgbAndStage(file, id);
    });

    fileInput.value = '';
    closeUploadMenu();
});

// ---- Prompt input ----

promptInput.addEventListener('keydown', function (e) {
    if (e.key === 'Enter' && !e.shiftKey && ableToSend) {
        e.preventDefault();
        sendMessage();
    }
});

promptInput.addEventListener('input', () => {
    promptInput.style.height = 'auto';
    promptInput.style.height = promptInput.scrollHeight + 'px';
    updateSendButtonState();
});

function updateSendButtonState() {
    const hasText = promptInput.value.trim() !== '';
    sendBtn.disabled = !hasText && pendingAttachments.length === 0;
}

sendBtn.addEventListener('click', sendMessage);

function sendMessage() {
    const text = promptInput.value.trim();
    if (text === '' && pendingAttachments.length === 0) return;

    if (!currentChatId) {
        currentChatId = getNextChatId();
        localStorage.setItem(ACTIVE_CHAT_KEY, currentChatId);
    }

    pendingAttachments.forEach(att => {
        if (att.type === 'image') {
            appendMessage('img::' + att.dataUrl, 'user', true);
        } else {
            appendMessage('file::' + att.name, 'user', true);
        }
    });
    pendingAttachments = [];
    renderAttachmentsPreview();

    if (text !== '') {
        appendMessage(text, 'user', true);
    }

    promptInput.value = '';
    promptInput.style.height = 'auto';

    if (text === '') return; // nothing to send to the AI, just an attachment

    ableToSend = false;
    sendBtn.disabled = true;

    fetchAiResponse(text);
}

function buildThinkingIndicator() {
    const wrapper = document.createElement('div');
    wrapper.classList.add('thinking-indicator');

    const anim = document.createElement('div');
    anim.classList.add('thinking-anim');

    const center = 16;
    const radius = 13; // shared by both the dots' placement and the line's half-length

    const dotCount = 8;
    for (let i = 0; i < dotCount; i++) {
        const angle = (360 / dotCount) * i;
        const rad = (angle * Math.PI) / 180;
        const x = center + radius * Math.cos(rad);
        const y = center + radius * Math.sin(rad);

        const dot = document.createElement('span');
        dot.classList.add('thinking-dot');
        dot.style.left = x + 'px';
        dot.style.top = y + 'px';

        // Opposite dots are crossed by the diameter line at the same moments,
        // so they share the same animation phase.
        const phase = (angle % 180) / 90; // seconds, matches the line's 4s rotation
        dot.style.animationDelay = '-' + phase + 's';

        anim.appendChild(dot);
    }

    const line = document.createElement('span');
    line.classList.add('thinking-line');
    line.style.width = (radius * 2) + 'px';
    line.style.marginLeft = -radius + 'px';
    anim.appendChild(line);

    const centerDot = document.createElement('span');
    centerDot.classList.add('thinking-center');
    anim.appendChild(centerDot);

    const label = document.createElement('span');
    label.classList.add('thinking-label');
    label.textContent = 'Thinking…';

    wrapper.appendChild(anim);
    wrapper.appendChild(label);
    return wrapper;
}

function buildThoughtSummary(seconds) {
    const wrapper = document.createElement('div');
    wrapper.classList.add('thought-summary');
    wrapper.innerHTML = `
        <svg viewBox="0 0 24 24" fill="none">
            <path d="M9 18h6M10 21h4M12 3a6 6 0 0 0-3.5 10.9c.5.4.8 1 .8 1.6V16h5.4v-.5c0-.6.3-1.2.8-1.6A6 6 0 0 0 12 3z" stroke="currentColor" stroke-width="1.6" stroke-linejoin="round" stroke-linecap="round"/>
        </svg>
        <span>Thought for ${seconds} second${seconds === 1 ? '' : 's'}</span>
    `;
    return wrapper;
}

async function fetchAiResponse(prompt) {
    const thinkingEl = buildThinkingIndicator();
    chatHistory.appendChild(thinkingEl);
    chatHistory.scrollTop = chatHistory.scrollHeight;

    const minDisplayTime = new Promise(resolve => setTimeout(resolve, 1000));

    try {
        const [response] = await Promise.all([
            fetch('/chat', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ prompt: prompt })
            }),
            minDisplayTime
        ]);

        if (!response.ok) {
            throw new Error('Server responded with status ' + response.status);
        }

        const data = await response.json();

        thinkingEl.remove();
        chatHistory.appendChild(buildThoughtSummary(1));
        appendMessage(data.response, 'ai', true);

        // Generate a title after the very first exchange
        const chat = chatsData.chats[currentChatId];
        const isFirstExchange = chat && getMessageCount(currentChatId) === 1;
        if (isFirstExchange && chat['user-response1']) {
            fetchAndSaveTitle(currentChatId, getDisplayText(chat['user-response1']));
        }
    } catch (err) {
        await minDisplayTime;
        thinkingEl.remove();
        appendMessage('Something went wrong reaching Grepmind: ' + err.message, 'ai', true);
    } finally {
        ableToSend = true;
        updateSendButtonState();
    }
}

function appendMessage(text, sender, shouldSave) {
    const messageDiv = document.createElement('div');
    messageDiv.classList.add('message', sender);

    if (text.startsWith('img::')) {
        messageDiv.classList.add('message-image');
        const img = document.createElement('img');
        img.src = text.slice(5);
        messageDiv.appendChild(img);
    } else if (text.startsWith('file::')) {
        messageDiv.classList.add('message-file');

        const icon = document.createElement('span');
        icon.innerHTML = `
            <svg viewBox="0 0 24 24" fill="none">
                <path d="M14 3H6a1 1 0 0 0-1 1v16a1 1 0 0 0 1 1h12a1 1 0 0 0 1-1V8l-5-5z" stroke="currentColor" stroke-width="1.6" stroke-linejoin="round"/>
                <path d="M14 3v5h5" stroke="currentColor" stroke-width="1.6" stroke-linejoin="round"/>
            </svg>
        `;

        const name = document.createElement('span');
        name.classList.add('file-name');
        name.textContent = text.slice(6);

        messageDiv.appendChild(icon.firstElementChild || icon);
        messageDiv.appendChild(name);
    } else {
        messageDiv.textContent = text;
    }

    chatHistory.appendChild(messageDiv);
    chatHistory.scrollTop = chatHistory.scrollHeight;
    chatContainer.classList.remove('empty-chat');

    if (shouldSave) {
        saveMessageToChat(currentChatId, sender, text);
    }
}