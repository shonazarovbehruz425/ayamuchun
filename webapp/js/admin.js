/**
 * EduBot Modern Admin Panel JavaScript
 * Author: EduBot Pro
 */

const AdminApp = {
    currentTab: 'dashboard',
    cachedUsers: [],
    selectedUserId: null,
    
    // AI Test State
    currentAiReply: '',
    aiPresets: {},

    // Real-time Logs State
    logPollingInterval: null,
    latestLogId: 0,
    logLevelFilter: '',
    logAutoScroll: true,
    isLogStreaming: false,
    allLogs: [],

    getAuthToken() {
        // Priority 1: Telegram WebApp initData if inside Telegram
        if (window.TelegramApp && window.TelegramApp.getInitData()) {
            return window.TelegramApp.getInitData();
        }
        // Priority 2: URL query param token e.g. ?token=... or ?admin_key=...
        const urlParams = new URLSearchParams(window.location.search);
        const queryToken = urlParams.get('token') || urlParams.get('key') || urlParams.get('admin_key');
        if (queryToken) {
            sessionStorage.setItem('edubot_admin_token', queryToken);
            return queryToken;
        }
        // Priority 3: Stored token from session/localStorage
        const stored = sessionStorage.getItem('edubot_admin_token') || localStorage.getItem('edubot_admin_token');
        if (stored) return stored;

        return '';
    },

    async apiFetch(url, options = {}) {
        let token = this.getAuthToken();
        if (!token) {
            token = prompt("Administrator paroli / maxfiy kalitini kiriting (Admin Secret Key):");
            if (token) {
                token = token.trim();
                sessionStorage.setItem('edubot_admin_token', token);
            }
        }

        const headers = {
            'Authorization': `Bearer ${token || ''}`,
            ...(options.headers || {})
        };

        const res = await fetch(url, { ...options, headers });
        if (res.status === 401 || res.status === 403) {
            sessionStorage.removeItem('edubot_admin_token');
            const retryKey = prompt("Kirish huquqi yo'q yoki kalit noto'g'ri! Iltimos, to'g'ri Administrator kalitini kiriting:");
            if (retryKey) {
                sessionStorage.setItem('edubot_admin_token', retryKey.trim());
                headers['Authorization'] = `Bearer ${retryKey.trim()}`;
                return fetch(url, { ...options, headers });
            }
        }
        return res;
    },

    init() {
        if (window.TelegramApp) {
            try { window.TelegramApp.init(); } catch (e) {}
        }
        this.initTheme();
        this.initLucide();
        this.refreshAll();

        // Auto refresh stats every 30 seconds
        setInterval(() => {
            if (this.currentTab === 'dashboard') {
                this.loadStats();
            }
        }, 30000);
    },

    initTheme() {
        const themeBtn = document.getElementById('theme-toggle-btn');
        const sunIcon = document.getElementById('theme-icon-sun');
        const moonIcon = document.getElementById('theme-icon-moon');

        const savedTheme = localStorage.getItem('theme') || 'light';
        if (savedTheme === 'dark') {
            document.documentElement.classList.add('dark');
            if (sunIcon) sunIcon.classList.remove('hidden');
            if (moonIcon) moonIcon.classList.add('hidden');
        }

        if (themeBtn) {
            themeBtn.addEventListener('click', () => {
                const isDark = document.documentElement.classList.toggle('dark');
                localStorage.setItem('theme', isDark ? 'dark' : 'light');
                if (sunIcon && moonIcon) {
                    sunIcon.classList.toggle('hidden', !isDark);
                    moonIcon.classList.toggle('hidden', isDark);
                }
            });
        }
    },

    initLucide(container) {
        if (window.lucide) {
            try {
                if (container) {
                    window.lucide.createIcons({ root: container });
                } else {
                    window.lucide.createIcons();
                }
            } catch (e) {
                try { window.lucide.createIcons(); } catch (err) {}
            }
        }
    },

    switchTab(tabName) {
        this.currentTab = tabName;
        
        // Update nav buttons
        document.querySelectorAll('.admin-tab-btn').forEach(btn => btn.classList.remove('active'));
        const activeBtn = document.getElementById(`tab-btn-${tabName}`);
        if (activeBtn) activeBtn.classList.add('active');

        // Toggle sections
        ['dashboard', 'users', 'files', 'broadcast', 'aitest', 'logs', 'system'].forEach(name => {
            const el = document.getElementById(`tab-content-${name}`);
            if (el) {
                if (name === tabName) {
                    el.classList.remove('hidden');
                } else {
                    el.classList.add('hidden');
                }
            }
        });

        if (tabName === 'users') {
            this.loadUsers();
        } else if (tabName === 'files') {
            this.loadFiles();
        } else if (tabName === 'dashboard') {
            this.loadStats();
        } else if (tabName === 'aitest') {
            this.loadAiInfo();
        } else if (tabName === 'logs') {
            this.startLogStream();
        }

        // Stop polling if we left logs tab
        if (tabName !== 'logs') {
            this.pauseLogStream();
        }
        
        this.initLucide();
    },

    async refreshAll(notify = false) {
        await this.loadStats();
        if (this.currentTab === 'users') await this.loadUsers();
        if (this.currentTab === 'files') await this.loadFiles();
        if (notify) {
            this.showToast('✅ Barcha ma\'lumotlar yangilandi');
        }
    },

    async loadStats() {
        try {
            const res = await this.apiFetch('/api/admin/stats');
            const data = await res.json();
            if (data.status === 'ok') {
                const ov = data.overview;
                const sys = data.system;

                document.getElementById('stat-total-users').innerText = ov.total_users;
                document.getElementById('stat-active-today').innerText = ov.active_today;
                document.getElementById('stat-total-files').innerText = ov.total_files;
                document.getElementById('stat-total-quizzes').innerText = ov.total_quizzes;
                document.getElementById('stat-storage-size').innerText = ov.disk_storage_formatted;
                document.getElementById('stat-storage-files').innerText = `${ov.disk_files_count} ta fayl saqlanmoqda`;

                document.getElementById('sys-uptime').innerText = sys.uptime;
                document.getElementById('sys-python').innerText = `Python ${sys.python_version}`;
                document.getElementById('sys-os').innerText = sys.os;
                document.getElementById('sys-time').innerText = sys.server_time;

                const botEl = document.getElementById('sys-bot-status');
                if (botEl) {
                    botEl.innerText = sys.bot_configured ? "Faol (Ulangan ✓)" : "Lokal Sinov Rejimida";
                    botEl.className = sys.bot_configured ? "font-bold text-emerald-600 text-xs sm:text-sm" : "font-bold text-amber-500 text-xs sm:text-sm";
                }

                const aiEl = document.getElementById('sys-ai-status');
                const aiLabel = document.getElementById('sys-ai-label');
                if (aiLabel && sys.ai_display_name) {
                    aiLabel.innerText = `${sys.ai_display_name} (${(sys.ai_provider || 'AI').toUpperCase()})`;
                }
                if (aiEl) {
                    aiEl.innerText = sys.ai_configured ? `Faol (${sys.ai_model || 'Ulangan'} ✓)` : "API Key Kutilyapti";
                    aiEl.className = sys.ai_configured ? "font-bold text-emerald-600 text-xs sm:text-sm" : "font-bold text-amber-500 text-xs sm:text-sm";
                }
            }
        } catch (e) {
            console.error("loadStats error:", e);
        }
    },

    async loadUsers(search = '') {
        const container = document.getElementById('users-list-container');
        if (!container) return;

        try {
            const url = search ? `/api/admin/users?search=${encodeURIComponent(search)}` : '/api/admin/users';
            const res = await this.apiFetch(url);
            const data = await res.json();

            if (data.status === 'ok') {
                this.cachedUsers = data.users;
                if (data.users.length === 0) {
                    container.innerHTML = `
                        <div class="p-8 text-center text-xs text-slate-400">
                            <i data-lucide="user-x" class="w-8 h-8 mx-auto mb-2 text-slate-300"></i>
                            Foydalanuvchilar topilmadi
                        </div>
                    `;
                } else {
                    container.innerHTML = data.users.map(u => `
                        <div class="liquid-glass-card p-3.5 sm:p-4 flex flex-col sm:flex-row sm:items-center justify-between gap-3 hover:border-brand-500/40 transition-all">
                            <div class="flex items-center gap-3 min-w-0">
                                <div class="w-10 h-10 rounded-xl bg-gradient-to-tr from-brand-600 to-indigo-600 text-white flex items-center justify-center font-bold text-sm shadow-md shrink-0">
                                    ${(u.full_name || 'O').charAt(0).toUpperCase()}
                                </div>
                                <div class="min-w-0">
                                    <div class="flex items-center gap-2 flex-wrap">
                                        <h4 class="font-bold text-slate-900 dark:text-white text-xs sm:text-sm truncate">${u.full_name}</h4>
                                        ${u.username ? `
                                            <a href="https://t.me/${u.username}" target="_blank" class="text-[11px] text-brand-600 hover:underline font-medium flex items-center gap-0.5">
                                                @${u.username}
                                                <i data-lucide="external-link" class="w-2.5 h-2.5"></i>
                                            </a>
                                        ` : ''}
                                    </div>
                                    <div class="flex items-center gap-2.5 mt-0.5 text-[11px] text-slate-500 dark:text-slate-400 font-mono flex-wrap">
                                        <span>ID: #${u.telegram_id}</span>
                                        ${u.phone_number ? `<span class="text-emerald-600 font-semibold">📞 ${u.phone_number}</span>` : ''}
                                        <span>• Hujjatlar: <b>${u.file_count}</b> ta</span>
                                        <span>• Oxirgi faollik: ${u.last_active || 'Yangi'}</span>
                                    </div>
                                </div>
                            </div>
                            <div class="flex items-center gap-2 self-end sm:self-auto shrink-0">
                                <button onclick="AdminApp.openMsgModal(${u.telegram_id}, '${u.full_name.replace(/'/g, "\\'")}')" class="px-3 py-1.5 rounded-xl bg-brand-500/10 hover:bg-brand-500/20 text-brand-600 font-bold text-xs flex items-center gap-1.5 transition-colors cursor-pointer">
                                    <i data-lucide="message-square" class="w-3.5 h-3.5"></i>
                                    <span>Xabar yozish</span>
                                </button>
                            </div>
                        </div>
                    `).join('');
                }
                this.initLucide(container);
            }
        } catch (e) {
            console.error("loadUsers error:", e);
            container.innerHTML = `<div class="p-6 text-center text-xs text-rose-500">Yuklashda xatolik yuz berdi.</div>`;
        }
    },

    searchTimeout: null,
    searchUsers(val) {
        clearTimeout(this.searchTimeout);
        this.searchTimeout = setTimeout(() => {
            this.loadUsers(val.trim());
        }, 300);
    },

    async loadFiles() {
        const container = document.getElementById('files-list-container');
        if (!container) return;

        try {
            const res = await this.apiFetch('/api/admin/files');
            const data = await res.json();

            if (data.status === 'ok') {
                if (data.files.length === 0) {
                    container.innerHTML = `
                        <div class="p-8 text-center text-xs text-slate-400">
                            <i data-lucide="file-x" class="w-8 h-8 mx-auto mb-2 text-slate-300"></i>
                            Fayllar hali mavjud emas
                        </div>
                    `;
                } else {
                    container.innerHTML = data.files.map(f => `
                        <div class="liquid-glass-card p-3 sm:p-3.5 flex items-center justify-between gap-3 text-xs">
                            <div class="flex items-center gap-3 min-w-0">
                                <div class="w-9 h-9 rounded-xl bg-slate-100 dark:bg-white/5 border border-slate-200 dark:border-white/10 flex items-center justify-center text-brand-600 shrink-0">
                                    <i data-lucide="file" class="w-4 h-4"></i>
                                </div>
                                <div class="min-w-0">
                                    <h4 class="font-bold text-slate-900 dark:text-white truncate text-xs sm:text-sm">${f.file_name}</h4>
                                    <div class="flex items-center gap-2 mt-0.5 text-[11px] text-slate-500 dark:text-slate-400 flex-wrap">
                                        <span class="font-mono text-brand-600 font-bold">${f.formatted_size}</span>
                                        <span>• Egasi: <b>${f.user_name}</b></span>
                                        <span>• Vaqt: ${f.uploaded_at}</span>
                                    </div>
                                </div>
                            </div>
                            <span class="liquid-glass-pill px-2 py-0.5 rounded-md text-[10px] font-bold text-slate-600 dark:text-slate-300 shrink-0 font-mono">
                                ${f.file_type.toUpperCase()}
                            </span>
                        </div>
                    `).join('');
                }
                this.initLucide(container);
            }
        } catch (e) {
            console.error("loadFiles error:", e);
            container.innerHTML = `<div class="p-6 text-center text-xs text-rose-500">Fayllarni yuklashda xatolik yuz berdi.</div>`;
        }
    },

    async downloadBackup() {
        try {
            const res = await this.apiFetch('/api/admin/backup-db');
            if (!res.ok) {
                const err = await res.json().catch(() => ({}));
                alert("Zaxira yuklab olishda xatolik: " + (err.detail || res.statusText));
                return;
            }
            const blob = await res.blob();
            const link = document.createElement('a');
            link.href = URL.createObjectURL(blob);
            link.download = `edubot_backup_${new Date().toISOString().slice(0,10)}.db`;
            document.body.appendChild(link);
            link.click();
            document.body.removeChild(link);
            URL.revokeObjectURL(link.href);
            this.showToast("📥 Baza zaxira fayli yuklab olindi!");
        } catch (e) {
            alert("Yuklab olishda xatolik yuz berdi: " + e.message);
        }
    },

    async cleanupStorage() {
        if (!confirm("Haqiqatdan ham 48 soatdan eski vaqtinchalik konvertatsiya keshlarini tozalamoqchimisiz?")) return;
        
        try {
            const res = await this.apiFetch('/api/admin/cleanup', { method: 'POST' });
            const data = await res.json();
            if (data.status === 'ok') {
                this.showToast(`🧹 ${data.deleted_files} ta eski fayl o'chirildi, ${data.freed_formatted} joy bo'shatildi!`);
                this.loadStats();
            } else {
                alert("Tozalashda xatolik yuz berdi.");
            }
        } catch (e) {
            alert("Tozalash so'rovi amalga oshmadi: " + e.message);
        }
    },

    async sendBroadcast() {
        const txt = document.getElementById('broadcast-message-text')?.value?.trim();
        if (!txt) {
            alert("Iltimos, xabar matnini kiriting!");
            return;
        }

        if (!confirm("Ushbu xabar barcha bot foydalanuvchilariga yuboriladi. Tasdiqlaysizmi?")) return;

        const btn = document.getElementById('broadcast-send-btn');
        const resBox = document.getElementById('broadcast-result-box');
        if (btn) btn.disabled = true;

        try {
            const res = await this.apiFetch('/api/admin/broadcast', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ message: txt })
            });
            const data = await res.json();

            if (resBox) {
                resBox.classList.remove('hidden');
                if (data.status === 'ok' || data.status === 'mock') {
                    resBox.className = "p-3.5 rounded-xl border border-emerald-500/30 bg-emerald-500/10 text-emerald-700 dark:text-emerald-300 text-xs leading-relaxed";
                    resBox.innerHTML = `
                        <b>✓ Xabar muvaffaqiyatli tarqatildi!</b><br>
                        • Yetkazildi: <b>${data.sent_count}</b> ta foydalanuvchiga<br>
                        • Xatolar: <b>${data.failed_count || 0}</b> ta<br>
                        ${data.message ? `<i>${data.message}</i>` : ''}
                    `;
                } else {
                    resBox.className = "p-3.5 rounded-xl border border-rose-500/30 bg-rose-500/10 text-rose-700 dark:text-rose-300 text-xs";
                    resBox.innerText = `Xatolik: ${data.message || 'Nomaʼlum xato'}`;
                }
            }
        } catch (e) {
            alert("Yuborishda xatolik: " + e.message);
        } finally {
            if (btn) btn.disabled = false;
        }
    },

    openMsgModal(telegramId, userName) {
        this.selectedUserId = telegramId;
        const modal = document.getElementById('user-msg-modal');
        const nameEl = document.getElementById('msg-modal-user-name');
        const idEl = document.getElementById('msg-modal-user-id');
        const input = document.getElementById('direct-msg-text');

        if (nameEl) nameEl.innerText = userName;
        if (idEl) idEl.innerText = `#${telegramId}`;
        if (input) input.value = '';
        if (modal) modal.classList.remove('hidden');
        this.initLucide(modal);
        setTimeout(() => input?.focus(), 100);
    },

    closeMsgModal() {
        const modal = document.getElementById('user-msg-modal');
        if (modal) modal.classList.add('hidden');
        this.selectedUserId = null;
    },

    async sendDirectMessage() {
        if (!this.selectedUserId) return;
        const input = document.getElementById('direct-msg-text');
        const msg = input?.value?.trim();
        if (!msg) {
            alert("Iltimos, xabar matnini kiriting!");
            return;
        }

        const btn = document.getElementById('direct-msg-btn');
        if (btn) btn.disabled = true;

        try {
            const res = await this.apiFetch('/api/admin/send-message', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ telegram_id: this.selectedUserId, message: msg })
            });
            const data = await res.json();
            if (data.status === 'ok' || data.status === 'mock') {
                this.closeMsgModal();
                this.showToast("✓ Xabar muvaffaqiyatli yuborildi!");
            } else {
                alert(`Xatolik: ${data.detail || 'Xabar yuborilmadi'}`);
            }
        } catch (e) {
            alert("Xatolik yuz berdi: " + e.message);
        } finally {
            if (btn) btn.disabled = false;
        }
    },

    showToast(msg) {
        const toast = document.createElement('div');
        toast.className = 'fixed bottom-5 right-5 z-50 px-4 py-3 rounded-2xl bg-slate-900 text-white dark:bg-white dark:text-slate-900 text-xs font-bold shadow-2xl animate-fade-in flex items-center gap-2';
        toast.innerText = msg;
        document.body.appendChild(toast);
        setTimeout(() => toast.remove(), 3500);
    },

    // ═════════════════════════════════════════════════════════════════════════
    // AI TESTING LABORATORY METHODS
    // ═════════════════════════════════════════════════════════════════════════

    async loadAiInfo() {
        const badge = document.getElementById('ai-active-provider-badge');
        const charCounter = document.getElementById('ai-char-counter');
        const promptInput = document.getElementById('ai-test-prompt');

        if (promptInput && !promptInput._boundCount) {
            promptInput._boundCount = true;
            promptInput.addEventListener('input', () => {
                if (charCounter) charCounter.innerText = `${promptInput.value.length} / 10000`;
            });
        }

        try {
            const res = await this.apiFetch('/api/admin/ai-models');
            if (res.ok) {
                const data = await res.json();
                const cur = data.current || {};
                if (badge) {
                    badge.innerText = `${(cur.provider || 'gemini').toUpperCase()} (${cur.model || 'standart'})`;
                }
                this.aiPresets = {
                    'nemotron': { provider: 'openrouter', model: 'nvidia/nemotron-3.5-lightning:free', base_url: 'https://openrouter.ai/api/v1' },
                    'deepseek': { provider: 'openrouter', model: 'deepseek/deepseek-chat:free', base_url: 'https://openrouter.ai/api/v1' },
                    'gemini-2': { provider: 'gemini', model: 'gemini-2.0-flash', base_url: '' },
                    'gpt4o': { provider: 'openai', model: 'gpt-4o-mini', base_url: 'https://api.openai.com/v1' }
                };
            }
        } catch (e) {
            if (badge) badge.innerText = "Xato";
        }
    },

    applyAiPreset(presetKey) {
        const provInput = document.getElementById('ai-override-provider');
        const modelInput = document.getElementById('ai-override-model');
        const baseUrlInput = document.getElementById('ai-override-base-url');
        if (presetKey === 'default') {
            if (provInput) provInput.value = '';
            if (modelInput) modelInput.value = '';
            if (baseUrlInput) baseUrlInput.value = '';
            return;
        }
        const preset = this.aiPresets ? this.aiPresets[presetKey] : null;
        if (preset) {
            if (provInput) provInput.value = preset.provider || '';
            if (modelInput) modelInput.value = preset.model || '';
            if (baseUrlInput) baseUrlInput.value = preset.base_url || '';
        }
    },

    setAiPrompt(text) {
        const promptInput = document.getElementById('ai-test-prompt');
        const charCounter = document.getElementById('ai-char-counter');
        if (promptInput) {
            promptInput.value = text;
            promptInput.focus();
            if (charCounter) charCounter.innerText = `${text.length} / 10000`;
        }
    },

    resetAiSystemPrompt() {
        const sys = document.getElementById('ai-test-system');
        if (sys) sys.value = "Siz ta'lim va pedagogika bo'yicha kuchli, yordamchi AI konsultantsiz. O'zbek tilida aniq, ravon va to'liq javob bering.";
    },

    clearAiTest() {
        const p = document.getElementById('ai-test-prompt');
        const r = document.getElementById('ai-response-container');
        const tb = document.getElementById('ai-telemetry-box');
        if (p) p.value = '';
        if (r) r.innerHTML = `
            <div class="h-[280px] flex flex-col items-center justify-center text-slate-400 dark:text-slate-500 text-center space-y-2">
                <i data-lucide="bot" class="w-10 h-10 stroke-[1.5] text-slate-300 dark:text-slate-600"></i>
                <p class="text-xs">Maydon tozalandi. Yangi prompt yozing va jo'nating.</p>
            </div>
        `;
        if (tb) tb.classList.add('hidden');
        this.currentAiReply = '';
        this.initLucide(r);
    },

    async sendAiTestQuery() {
        const promptInput = document.getElementById('ai-test-prompt');
        const systemInput = document.getElementById('ai-test-system');
        const provInput = document.getElementById('ai-override-provider');
        const modelInput = document.getElementById('ai-override-model');
        const baseUrlInput = document.getElementById('ai-override-base-url');
        const keyInput = document.getElementById('ai-override-key');
        const sendBtn = document.getElementById('ai-test-send-btn');
        const responseBox = document.getElementById('ai-response-container');
        const telemetryBox = document.getElementById('ai-telemetry-box');
        const noteEl = document.getElementById('ai-status-note');

        const prompt = promptInput?.value?.trim();
        if (!prompt) {
            alert("Iltimos, AI uchun prompt yoki savol matnini kiriting!");
            promptInput?.focus();
            return;
        }

        // Loading UI state
        if (sendBtn) {
            sendBtn.disabled = true;
            sendBtn.innerHTML = `
                <svg class="animate-spin -ml-1 mr-2 h-4 w-4 text-white" fill="none" viewBox="0 0 24 24">
                    <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
                    <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                </svg>
                <span>AI o'ylamoqda...</span>
            `;
        }

        if (responseBox) {
            responseBox.innerHTML = `
                <div class="h-[280px] flex flex-col items-center justify-center text-slate-500 space-y-3">
                    <div class="w-8 h-8 rounded-full border-2 border-purple-500 border-t-transparent animate-spin"></div>
                    <span class="text-xs font-semibold animate-pulse">Sun'iy intellekt javob tayyorlamoqda...</span>
                </div>
            `;
        }
        if (noteEl) noteEl.innerText = "So'rov yuborildi...";

        const payload = {
            prompt: prompt,
            system_instruction: systemInput?.value?.trim() || null,
            provider: provInput?.value?.trim() || null,
            model: modelInput?.value?.trim() || null,
            base_url: baseUrlInput?.value?.trim() || null,
            api_key: keyInput?.value?.trim() || null
        };

        try {
            const res = await this.apiFetch('/api/admin/ai-test', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });

            const data = await res.json();
            if (res.ok && data.status === 'ok') {
                this.currentAiReply = data.reply || '';
                
                // Render nicely formatted text
                if (responseBox) {
                    responseBox.innerText = this.currentAiReply;
                }

                // Show telemetry badge
                if (telemetryBox) {
                    telemetryBox.classList.remove('hidden');
                    const speedTag = document.getElementById('ai-speed-tag');
                    const tokTag = document.getElementById('ai-tokens-tag');
                    const modelTag = document.getElementById('ai-model-tag');

                    if (speedTag) speedTag.innerText = `⚡ ${data.elapsed_ms}ms`;
                    const totalTok = data.tokens?.total_tokens || 0;
                    if (tokTag) tokTag.innerText = `🎯 ${totalTok} tok`;
                    if (modelTag) modelTag.innerText = `🤖 ${data.model || data.provider}`;
                }

                if (noteEl) noteEl.innerText = `Muvaffaqiyatli bajarildi: ${data.timestamp}`;
                this.showToast("✓ AI javobi qabul qilindi!");
            } else {
                const errMsg = data.detail || 'Noma\'lum xatolik yuz berdi';
                if (responseBox) {
                    responseBox.innerHTML = `
                        <div class="p-4 rounded-xl bg-rose-500/10 border border-rose-500/20 text-rose-600 dark:text-rose-400 text-xs">
                            <b class="font-bold">❌ AI Xatoligi:</b>
                            <p class="mt-1 font-mono">${errMsg}</p>
                        </div>
                    `;
                }
                if (noteEl) noteEl.innerText = "Xatolik yuz berdi";
            }
        } catch (err) {
            if (responseBox) {
                responseBox.innerHTML = `
                    <div class="p-4 rounded-xl bg-rose-500/10 border border-rose-500/20 text-rose-600 dark:text-rose-400 text-xs">
                        <b class="font-bold">❌ Tarmoq / Server Xatoligi:</b>
                        <p class="mt-1 font-mono">${err.message}</p>
                    </div>
                `;
            }
            if (noteEl) noteEl.innerText = "Tarmoq xatosi";
        } finally {
            if (sendBtn) {
                sendBtn.disabled = false;
                sendBtn.innerHTML = `
                    <i data-lucide="sparkles" class="w-4 h-4"></i>
                    <span>AI ga So'rov Yuborish</span>
                `;
                this.initLucide(sendBtn);
            }
        }
    },

    copyAiResponse() {
        if (!this.currentAiReply) {
            alert("Nusxa olish uchun hali javob mavjud emas!");
            return;
        }
        navigator.clipboard.writeText(this.currentAiReply).then(() => {
            this.showToast("📋 AI javobi clipboardga nusxalandi!");
        }).catch(() => {
            alert("Nusxalab bo'lmadi, brauzer ruxsat bermadi.");
        });
    },

    // ═════════════════════════════════════════════════════════════════════════
    // REAL-TIME SYSTEM LOGS METHODS
    // ═════════════════════════════════════════════════════════════════════════

    startLogStream() {
        this.isLogStreaming = true;
        this.updateLogPauseUI();
        
        // Initial fetch
        this.fetchLogs();

        // Start repeating poll every 2 seconds
        if (this.logPollingInterval) clearInterval(this.logPollingInterval);
        this.logPollingInterval = setInterval(() => {
            if (this.isLogStreaming && this.currentTab === 'logs') {
                this.fetchLogs();
            }
        }, 2000);
    },

    pauseLogStream() {
        this.isLogStreaming = false;
        if (this.logPollingInterval) {
            clearInterval(this.logPollingInterval);
            this.logPollingInterval = null;
        }
        this.updateLogPauseUI();
    },

    toggleLogStream() {
        if (this.isLogStreaming) {
            this.pauseLogStream();
            this.showToast("⏸ Jonli log oqimi to'xtatildi");
        } else {
            this.startLogStream();
            this.showToast("▶ Jonli log oqimi davom ettirilmoqda");
        }
    },

    updateLogPauseUI() {
        const btnText = document.getElementById('log-pause-text');
        const btnIcon = document.getElementById('log-pause-icon');
        const indicator = document.getElementById('log-connection-indicator');
        const badge = document.getElementById('live-log-badge');

        if (this.isLogStreaming) {
            if (btnText) btnText.innerText = "Pauza";
            if (btnIcon) btnIcon.setAttribute('data-lucide', 'pause');
            if (indicator) {
                indicator.innerHTML = '<span class="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse"></span><span>Jonli efir (Har 2 soniya)</span>';
                indicator.className = "flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-bold bg-emerald-500/10 text-emerald-600 border border-emerald-500/20";
            }
            if (badge) badge.classList.add('animate-ping');
        } else {
            if (btnText) btnText.innerText = "Davom etish";
            if (btnIcon) btnIcon.setAttribute('data-lucide', 'play');
            if (indicator) {
                indicator.innerHTML = '<span class="w-1.5 h-1.5 rounded-full bg-amber-500"></span><span>To\'xtatilgan</span>';
                indicator.className = "flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-bold bg-amber-500/10 text-amber-600 border border-amber-500/20";
            }
            if (badge) badge.classList.remove('animate-ping');
        }
        this.initLucide();
    },

    changeLogLevelFilter(level) {
        this.logLevelFilter = level;
        this.renderAllLogs();
    },

    toggleLogAutoScroll() {
        this.logAutoScroll = !this.logAutoScroll;
        const btn = document.getElementById('log-autoscroll-toggle');
        if (btn) {
            if (this.logAutoScroll) {
                btn.className = "p-1.5 px-3 rounded-xl border border-brand-500/30 bg-brand-500/10 text-brand-600 dark:text-brand-400 text-xs font-bold flex items-center gap-1.5 transition-all";
                btn.innerHTML = '<i data-lucide="arrow-down-circle" class="w-3.5 h-3.5"></i><span>Avto-surish: YOQILGAN</span>';
                this.scrollToTerminalBottom();
            } else {
                btn.className = "p-1.5 px-3 rounded-xl border border-slate-200 dark:border-slate-700 text-slate-500 text-xs font-bold flex items-center gap-1.5 transition-all";
                btn.innerHTML = '<i data-lucide="circle-slash" class="w-3.5 h-3.5"></i><span>Avto-surish: O\'CHIK</span>';
            }
            this.initLucide(btn);
        }
    },

    scrollToTerminalBottom() {
        const terminal = document.getElementById('terminal-window');
        const jumpBtn = document.getElementById('terminal-scroll-bottom-btn');
        if (terminal) {
            terminal.scrollTop = terminal.scrollHeight;
        }
        if (jumpBtn) jumpBtn.classList.add('hidden');
    },

    async fetchLogs() {
        try {
            const url = `/api/admin/logs?since_id=${this.latestLogId}&limit=200`;
            const res = await this.apiFetch(url);
            if (!res.ok) return;

            const data = await res.json();
            const newLogs = data.logs || [];
            
            if (newLogs.length > 0) {
                this.allLogs = this.allLogs.concat(newLogs);
                // Keep max 1000 logs in frontend memory
                if (this.allLogs.length > 1000) {
                    this.allLogs = this.allLogs.slice(this.allLogs.length - 1000);
                }
                this.latestLogId = data.latest_id || this.allLogs[this.allLogs.length - 1].id;
                this.appendLogsToTerminal(newLogs);
            }

            const countDisplay = document.getElementById('log-count-display');
            const syncDisplay = document.getElementById('log-last-sync-time');
            if (countDisplay) countDisplay.innerText = this.allLogs.length;
            if (syncDisplay) {
                const now = new Date();
                syncDisplay.innerText = now.toTimeString().split(' ')[0];
            }
        } catch (e) {
            // Silently handle polling glitch
        }
    },

    appendLogsToTerminal(logs) {
        const container = document.getElementById('log-lines-container');
        const terminal = document.getElementById('terminal-window');
        if (!container) return;

        // If it was initial loading message, clear it
        if (container.firstElementChild && container.firstElementChild.innerText.includes('Tizim loglari yuklanmoqda')) {
            container.innerHTML = '';
        }

        const fragment = document.createDocumentFragment();
        logs.forEach(log => {
            if (this.logLevelFilter && log.level !== this.logLevelFilter) {
                return;
            }
            const div = this.createLogElement(log);
            fragment.appendChild(div);
        });

        container.appendChild(fragment);

        if (this.logAutoScroll && terminal) {
            terminal.scrollTop = terminal.scrollHeight;
        }
    },

    renderAllLogs() {
        const container = document.getElementById('log-lines-container');
        const terminal = document.getElementById('terminal-window');
        if (!container) return;

        container.innerHTML = '';
        const fragment = document.createDocumentFragment();
        this.allLogs.forEach(log => {
            if (this.logLevelFilter && log.level !== this.logLevelFilter) {
                return;
            }
            const div = this.createLogElement(log);
            fragment.appendChild(div);
        });
        container.appendChild(fragment);

        if (this.logAutoScroll && terminal) {
            terminal.scrollTop = terminal.scrollHeight;
        }
    },

    createLogElement(log) {
        const div = document.createElement('div');
        div.className = 'flex items-start gap-2 py-0.5 hover:bg-white/5 px-1.5 rounded transition-colors group font-mono text-[11px]';

        let levelBadge = '';
        if (log.level === 'ERROR' || log.level === 'CRITICAL') {
            levelBadge = '<span class="px-1.5 py-0.2 rounded bg-rose-500/20 text-rose-400 font-bold border border-rose-500/30 text-[10px]">ERROR</span>';
        } else if (log.level === 'WARNING') {
            levelBadge = '<span class="px-1.5 py-0.2 rounded bg-amber-500/20 text-amber-400 font-bold border border-amber-500/30 text-[10px]">WARN</span>';
        } else if (log.level === 'DEBUG') {
            levelBadge = '<span class="px-1.5 py-0.2 rounded bg-slate-700/50 text-slate-400 text-[10px]">DEBUG</span>';
        } else {
            levelBadge = '<span class="px-1.5 py-0.2 rounded bg-emerald-500/20 text-emerald-400 font-bold text-[10px]">INFO</span>';
        }

        div.innerHTML = `
            <span class="text-slate-500 shrink-0 text-[10px] select-none">${log.time || ''}</span>
            <div class="shrink-0">${levelBadge}</div>
            <span class="text-slate-400 font-semibold shrink-0 select-none">[${log.logger || 'app'}]</span>
            <span class="text-slate-200 break-all select-text">${this.escapeHtml(log.message)}</span>
        `;
        return div;
    },

    escapeHtml(str) {
        if (!str) return '';
        return String(str)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;');
    },

    async clearServerLogs() {
        if (!confirm("Barcha saqlangan tizim loglarini xotiradan tozalashni tasdiqlaysizmi?")) return;
        try {
            await this.apiFetch('/api/admin/logs/clear', { method: 'POST' });
            this.allLogs = [];
            this.latestLogId = 0;
            const container = document.getElementById('log-lines-container');
            if (container) {
                container.innerHTML = '<div class="text-slate-500 italic py-2">Loglar tozalandi. Yangi yozuvlar kutilmoqda...</div>';
            }
            const countDisplay = document.getElementById('log-count-display');
            if (countDisplay) countDisplay.innerText = "0";
            this.showToast("✓ Tizim loglari tozalandi");
        } catch (e) {
            alert("Loglarni tozalashda xatolik: " + e.message);
        }
    }
};

document.addEventListener('DOMContentLoaded', () => {
    AdminApp.init();
});
