/**
 * EduBot Modern Admin Panel JavaScript
 * Author: EduBot Pro
 */

const AdminApp = {
    currentTab: 'dashboard',
    cachedUsers: [],
    selectedUserId: null,

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
        ['dashboard', 'users', 'files', 'broadcast', 'system'].forEach(name => {
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
    }
};

document.addEventListener('DOMContentLoaded', () => {
    AdminApp.init();
});
