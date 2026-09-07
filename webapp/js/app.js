/**
 * EduBot Modern SaaS Frontend Architecture (Linear / Vercel style)
 * 7 Core Tools working with direct, instant, responsive flows:
 * 1. PDF ➔ Word (DOCX)
 * 2. Word ➔ PDF
 * 3. Doc tahrirlash (Matn tahrirlash & So'z almashtirish)
 * 4. PDF tahrirlash (Matn tahrirlash & So'z almashtirish)
 * 5. Rasmlarni PDF qilish (A4 standart birlashtirish)
 * 6. PDF rasmlarini olish (ZIP)
 * 7. AI Yordamchi (Gemini 2.0 Flash)
 */

document.addEventListener('DOMContentLoaded', () => {
    const appDiv = document.getElementById('app');

    function cleanDisplayName(str) {
        if (!str) return "O'qituvchi";
        try {
            // Strip combining marks, enclosing marks, dotted circles and special control unicode
            let cleaned = str.normalize('NFKD')
                .replace(/[\u0300-\u036f\u20d0-\u20ff\ufe20-\ufe2f\u25cc]/g, '')
                .trim();
            return cleaned || str;
        } catch (e) {
            return str;
        }
    }

    const rawUser = TelegramApp.getUserData() || { first_name: "O'qituvchi", id: "000000" };
    const tgUser = { ...rawUser, first_name: cleanDisplayName(rawUser.first_name) };
    const headerUserName = document.getElementById('header-user-name');
    if (headerUserName && tgUser.first_name) {
        headerUserName.innerText = tgUser.first_name;
    }

    let isCurrentUserAdmin = false;
    api.getMe().then(res => {
        if (res && res.is_admin) {
            isCurrentUserAdmin = true;
            const badge = document.getElementById('header-user-name');
            if (badge) badge.innerText = `${tgUser.first_name || "Admin"} (Admin)`;
        }
    }).catch(() => {});

    function refreshIcons(rootNode) {
        if (window.lucide) {
            try {
                if (rootNode && (rootNode instanceof HTMLElement || rootNode instanceof DocumentFragment)) {
                    window.lucide.createIcons({ root: rootNode });
                } else {
                    window.lucide.createIcons();
                }
            } catch (e) {
                try { window.lucide.createIcons(); } catch (err) {}
            }
        }
    }

    // ── Day / Night Theme Controller ──
    const themeToggleBtn = document.getElementById('theme-toggle-btn');
    const themeIconMoon = document.getElementById('theme-icon-moon');
    const themeIconSun = document.getElementById('theme-icon-sun');

    function applyTheme(isDark) {
        if (isDark) {
            document.documentElement.classList.add('dark');
            if (themeIconMoon) themeIconMoon.classList.add('hidden');
            if (themeIconSun) themeIconSun.classList.remove('hidden');
        } else {
            document.documentElement.classList.remove('dark');
            if (themeIconMoon) themeIconMoon.classList.remove('hidden');
            if (themeIconSun) themeIconSun.classList.add('hidden');
        }
        localStorage.setItem('edubot_theme', isDark ? 'dark' : 'light');
        refreshIcons();
    }

    const savedTheme = localStorage.getItem('edubot_theme');
    const tgTheme = window.Telegram?.WebApp?.colorScheme;
    const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
    const initialDark = savedTheme ? (savedTheme === 'dark') : (tgTheme ? tgTheme === 'dark' : prefersDark);
    applyTheme(initialDark);

    if (themeToggleBtn) {
        themeToggleBtn.addEventListener('click', () => {
            TelegramApp.hapticFeedback('medium');
            const isCurrentlyDark = document.documentElement.classList.contains('dark');
            applyTheme(!isCurrentlyDark);
        });
    }

    // ── iOS 26 Liquid Glass Dock & Capsule Motion ──
    const mercuryPill = document.getElementById('mercuryPill');

    function alignPillToTab(tabElement, animateMorph = true) {
        if (!mercuryPill || !tabElement) return;
        const parent = tabElement.parentElement;
        if (!parent) return;

        const parentRect = parent.getBoundingClientRect();
        const tabRect = tabElement.getBoundingClientRect();

        const offsetLeft = tabRect.left - parentRect.left;
        const targetWidth = tabRect.width;

        if (animateMorph) {
            mercuryPill.classList.add('morphing');
            setTimeout(() => {
                mercuryPill.classList.remove('morphing');
            }, 300);
        }

        mercuryPill.style.left = `${offsetLeft}px`;
        mercuryPill.style.width = `${targetWidth}px`;
    }

    const handleViewportChange = () => {
        const activeItem = document.querySelector('.nav-item.active-tab');
        if (activeItem) alignPillToTab(activeItem, false);
    };

    window.addEventListener('resize', handleViewportChange);
    window.addEventListener('orientationchange', () => {
        setTimeout(handleViewportChange, 150);
    });

    if (window.Telegram?.WebApp) {
        window.Telegram.WebApp.onEvent('viewportChanged', handleViewportChange);
    }

    function updateNav(hash) {
        let activeEl = null;
        document.querySelectorAll('.nav-item').forEach(item => {
            const route = item.getAttribute('data-route');
            const isActive = route === hash || (hash === '' && route === '#/');
            const icon = item.querySelector('svg');
            
            if (isActive) {
                item.classList.add('active-tab', 'text-white', 'font-bold');
                item.classList.remove('text-slate-700');
                if (icon) icon.classList.add('scale-110');
                activeEl = item;
            } else {
                item.classList.remove('active-tab', 'text-white', 'font-bold');
                item.classList.add('text-slate-700');
                if (icon) icon.classList.remove('scale-110');
            }
        });

        if (activeEl) {
            alignPillToTab(activeEl, true);
        }
    }

    // ── Modal Management ──
    function openModal(modalHtml) {
        let modalContainer = document.getElementById('modal-overlay-container');
        if (!modalContainer) {
            modalContainer = document.createElement('div');
            modalContainer.id = 'modal-overlay-container';
            document.body.appendChild(modalContainer);
        }
        modalContainer.innerHTML = modalHtml;
        modalContainer.classList.remove('hidden');
        refreshIcons();
    }

    function closeModal() {
        const modalContainer = document.getElementById('modal-overlay-container');
        if (modalContainer) {
            modalContainer.innerHTML = '';
            modalContainer.classList.add('hidden');
        }
    }
    window.closeModal = closeModal;

    // ─────────────────────────────────────────────────────────────
    // 1. DASHBOARD VIEW (Interactive Hub for All 7 Tools)
    // ─────────────────────────────────────────────────────────────
    async function renderDashboard() {
        appDiv.innerHTML = `
            <div class="space-y-5 animate-fade-in">
                <!-- Welcome Banner (Liquid Glass) -->
                <div class="liquid-glass-card p-5 text-white relative overflow-hidden bg-gradient-to-br from-brand-600/85 via-indigo-600/80 to-purple-700/85 backdrop-blur-xl border border-white/40 shadow-xl shadow-brand-500/15">
                    <div class="absolute -right-8 -bottom-8 w-40 h-40 bg-white/15 rounded-full blur-2xl pointer-events-none"></div>
                    <div class="relative z-10">
                        <span class="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-white/20 backdrop-blur-md text-xs font-bold text-white mb-2.5 border border-white/30 shadow-sm">
                            <i data-lucide="sparkles" class="w-3.5 h-3.5"></i> EduBot Pro Workspace
                        </span>
                        <h2 class="text-xl sm:text-2xl font-extrabold tracking-tight">Xush kelibsiz, ${tgUser.first_name}!</h2>
                        <p class="text-xs sm:text-sm text-indigo-100 mt-1 max-w-md font-medium">Istalgan asbobni tanlang — bir zumda ishlaydi va natijani olasiz.</p>
                    </div>
                </div>

                <!-- 7 CORE TOOLS DIRECT ACTIONS -->
                <div>
                    <div class="flex items-center justify-between mb-3 px-0.5">
                        <h3 class="text-xs font-bold text-slate-500 uppercase tracking-wider">Asosiy 7 ta Asbob</h3>
                        <span class="text-[11px] text-emerald-600 font-bold font-mono">Tezkor amallar ✓</span>
                    </div>

                    <div class="grid grid-cols-1 sm:grid-cols-2 gap-3">
                        <!-- Tool 1: PDF to Word -->
                        <div onclick="openPdfToWordModal()" class="liquid-glass-interactive p-4 cursor-pointer group hover:border-rose-400/50 transition-all">
                            <div class="flex items-center gap-3">
                                <div class="w-10 h-10 rounded-2xl bg-gradient-to-tr from-rose-50 to-red-100 text-rose-600 flex items-center justify-center shadow-sm border border-white shrink-0 group-hover:scale-105 transition-transform">
                                    <i data-lucide="file-type-2" class="w-5 h-5"></i>
                                </div>
                                <div class="min-w-0">
                                    <div class="flex items-center gap-1.5">
                                        <h4 class="text-sm font-bold text-slate-900">PDF ➔ Word</h4>
                                        <span class="px-1.5 py-0.5 rounded text-[10px] font-bold bg-rose-500/10 text-rose-600">DOCX</span>
                                    </div>
                                    <p class="text-xs text-slate-500 mt-0.5 truncate">PDF ni Word formatiga o'zgartirish</p>
                                </div>
                            </div>
                        </div>

                        <!-- Tool 2: Word to PDF -->
                        <div onclick="openWordToPdfModal()" class="liquid-glass-interactive p-4 cursor-pointer group hover:border-blue-400/50 transition-all">
                            <div class="flex items-center gap-3">
                                <div class="w-10 h-10 rounded-2xl bg-gradient-to-tr from-blue-50 to-indigo-100 text-blue-600 flex items-center justify-center shadow-sm border border-white shrink-0 group-hover:scale-105 transition-transform">
                                    <i data-lucide="file-text" class="w-5 h-5"></i>
                                </div>
                                <div class="min-w-0">
                                    <div class="flex items-center gap-1.5">
                                        <h4 class="text-sm font-bold text-slate-900">Word ➔ PDF</h4>
                                        <span class="px-1.5 py-0.5 rounded text-[10px] font-bold bg-blue-500/10 text-blue-600">PDF</span>
                                    </div>
                                    <p class="text-xs text-slate-500 mt-0.5 truncate">DOCX hujjatini PDF qilish</p>
                                </div>
                            </div>
                        </div>

                        <!-- Tool 3: Word Editing -->
                        <div onclick="openDocEditModal()" class="liquid-glass-interactive p-4 cursor-pointer group hover:border-indigo-400/50 transition-all">
                            <div class="flex items-center gap-3">
                                <div class="w-10 h-10 rounded-2xl bg-gradient-to-tr from-indigo-50 to-violet-100 text-indigo-600 flex items-center justify-center shadow-sm border border-white shrink-0 group-hover:scale-105 transition-transform">
                                    <i data-lucide="file-edit" class="w-5 h-5"></i>
                                </div>
                                <div class="min-w-0">
                                    <div class="flex items-center gap-1.5">
                                        <h4 class="text-sm font-bold text-slate-900">Doc tahrirlash</h4>
                                        <span class="px-1.5 py-0.5 rounded text-[10px] font-bold bg-indigo-500/10 text-indigo-600">Tahrirlash</span>
                                    </div>
                                    <p class="text-xs text-slate-500 mt-0.5 truncate">Word matnini tahrirlash va almashtirish</p>
                                </div>
                            </div>
                        </div>

                        <!-- Tool 4: PDF Editing -->
                        <div onclick="openPdfEditModal()" class="liquid-glass-interactive p-4 cursor-pointer group hover:border-amber-400/50 transition-all">
                            <div class="flex items-center gap-3">
                                <div class="w-10 h-10 rounded-2xl bg-gradient-to-tr from-amber-50 to-orange-100 text-amber-600 flex items-center justify-center shadow-sm border border-white shrink-0 group-hover:scale-105 transition-transform">
                                    <i data-lucide="edit-3" class="w-5 h-5"></i>
                                </div>
                                <div class="min-w-0">
                                    <div class="flex items-center gap-1.5">
                                        <h4 class="text-sm font-bold text-slate-900">PDF tahrirlash</h4>
                                        <span class="px-1.5 py-0.5 rounded text-[10px] font-bold bg-amber-500/10 text-amber-600">Matn</span>
                                    </div>
                                    <p class="text-xs text-slate-500 mt-0.5 truncate">PDF matnini tahrirlash va almashtirish</p>
                                </div>
                            </div>
                        </div>

                        <!-- Tool 5: Images to PDF -->
                        <div onclick="openImagesToPdfModal()" class="liquid-glass-interactive p-4 cursor-pointer group hover:border-emerald-400/50 transition-all">
                            <div class="flex items-center gap-3">
                                <div class="w-10 h-10 rounded-2xl bg-gradient-to-tr from-emerald-50 to-teal-100 text-emerald-600 flex items-center justify-center shadow-sm border border-white shrink-0 group-hover:scale-105 transition-transform">
                                    <i data-lucide="images" class="w-5 h-5"></i>
                                </div>
                                <div class="min-w-0">
                                    <div class="flex items-center gap-1.5">
                                        <h4 class="text-sm font-bold text-slate-900">Rasmlarni PDF qilish</h4>
                                        <span class="px-1.5 py-0.5 rounded text-[10px] font-bold bg-emerald-500/10 text-emerald-600">A4 PDF</span>
                                    </div>
                                    <p class="text-xs text-slate-500 mt-0.5 truncate">Rasmlarni bitta tartibli PDF ga yig'ish</p>
                                </div>
                            </div>
                        </div>

                        <!-- Tool 6: Extract Images from PDF -->
                        <div onclick="openExtractImagesModal()" class="liquid-glass-interactive p-4 cursor-pointer group hover:border-cyan-400/50 transition-all">
                            <div class="flex items-center gap-3">
                                <div class="w-10 h-10 rounded-2xl bg-gradient-to-tr from-cyan-50 to-sky-100 text-cyan-600 flex items-center justify-center shadow-sm border border-white shrink-0 group-hover:scale-105 transition-transform">
                                    <i data-lucide="folder-archive" class="w-5 h-5"></i>
                                </div>
                                <div class="min-w-0">
                                    <div class="flex items-center gap-1.5">
                                        <h4 class="text-sm font-bold text-slate-900">PDF rasmlarini olish</h4>
                                        <span class="px-1.5 py-0.5 rounded text-[10px] font-bold bg-cyan-500/10 text-cyan-600">ZIP</span>
                                    </div>
                                    <p class="text-xs text-slate-500 mt-0.5 truncate">PDF ichidagi suratlarni ajratib olish</p>
                                </div>
                            </div>
                        </div>

                        <!-- Tool 7: AI Assistant -->
                        <div onclick="window.location.hash='#/ai'" class="sm:col-span-2 liquid-glass-interactive p-4 cursor-pointer group bg-gradient-to-r from-purple-500/5 via-indigo-500/5 to-brand-500/5 border-purple-500/20 hover:border-purple-400/50 transition-all">
                            <div class="flex items-center justify-between">
                                <div class="flex items-center gap-3">
                                    <div class="w-10 h-10 rounded-2xl bg-gradient-to-tr from-purple-500 to-indigo-600 text-white flex items-center justify-center shadow-md shadow-purple-500/25 shrink-0 group-hover:scale-105 transition-transform">
                                        <i data-lucide="sparkles" class="w-5 h-5"></i>
                                    </div>
                                    <div>
                                        <div class="flex items-center gap-1.5">
                                            <h4 class="text-sm font-bold text-slate-900">AI Pedagogik Yordamchi</h4>
                                            <span class="px-2 py-0.5 rounded-full text-[10px] font-extrabold bg-gradient-to-r from-purple-600 to-indigo-600 text-white">Gemini 2.0</span>
                                        </div>
                                        <p class="text-xs text-slate-500 mt-0.5">Xulosa qilish, dars rejasi tuzish, tarjima va savollarga javob</p>
                                    </div>
                                </div>
                                <i data-lucide="chevron-right" class="w-5 h-5 text-slate-400 group-hover:text-purple-600 transition-colors"></i>
                            </div>
                        </div>
                    </div>
                </div>

                <!-- RECENT RESULTS & FILES -->
                <div class="liquid-glass-card overflow-hidden">
                    <div class="px-4 py-3 border-b border-white/60 flex items-center justify-between">
                        <div class="flex items-center gap-2">
                            <i data-lucide="clock" class="w-4 h-4 text-brand-600"></i>
                            <h3 class="text-xs font-bold text-slate-700 uppercase tracking-wider">Mening tayyor fayllarim</h3>
                        </div>
                        <div class="flex items-center gap-2">
                            <span id="dash-files-badge" class="text-[11px] font-mono liquid-glass-pill text-slate-700 px-2.5 py-0.5 rounded-full font-semibold">0 ta</span>
                            <button onclick="clearAllUserFiles()" title="Barchasini tozalash" class="p-1 rounded-lg text-slate-400 hover:text-rose-600 hover:bg-rose-50/50 transition-colors">
                                <i data-lucide="trash-2" class="w-3.5 h-3.5"></i>
                            </button>
                        </div>
                    </div>

                    <div id="dash-files-container" class="divide-y divide-slate-100/70">
                        <div class="p-6 text-center text-xs text-slate-400">Yuklanmoqda...</div>
                    </div>
                </div>
            </div>
        `;
        refreshIcons();
        loadRecentFiles();
    }

    async function loadRecentFiles() {
        const container = document.getElementById('dash-files-container');
        const badge = document.getElementById('dash-files-badge');
        if (!container) return;

        try {
            const files = await api.getFiles();
            if (badge) badge.innerText = `${files.length} ta`;

            if (files.length === 0) {
                container.innerHTML = `
                    <div class="py-8 text-center text-slate-400">
                        <i data-lucide="inbox" class="w-8 h-8 mx-auto stroke-1 text-slate-300 mb-1.5"></i>
                        <p class="text-xs font-medium text-slate-500">Hozircha saqlangan fayllar yo'q</p>
                        <p class="text-[11px] text-slate-400 mt-0.5">Yuqoridagi asboblardan foydalaning</p>
                    </div>
                `;
                refreshIcons();
                return;
            }

            container.innerHTML = files.slice(0, 15).map(f => {
                const ext = (f.file_type || '').toLowerCase();
                const isPdf = ext === 'pdf';
                const isWord = ['docx', 'doc'].includes(ext);
                const isZip = ext === 'zip';
                const sizeMb = (f.file_size / (1024 * 1024)).toFixed(2);
                
                let badgeColor = isPdf ? 'bg-rose-500/10 text-rose-600' : isWord ? 'bg-blue-500/10 text-blue-600' : 'bg-cyan-500/10 text-cyan-600';
                let iconName = isPdf ? 'file-text' : isWord ? 'file' : 'archive';

                return `
                    <div class="p-3 sm:p-3.5 flex items-center justify-between hover:bg-white/70 dark:hover:bg-slate-800/60 active:bg-white/90 transition-all cursor-pointer group" onclick="openFileWorkPage(${f.id}, '${f.file_name.replace(/'/g, "\\'")}', '${ext}')">
                        <div class="flex items-center gap-2.5 min-w-0 pr-2">
                            <div class="w-9 h-9 shrink-0 rounded-xl ${badgeColor} flex items-center justify-center border border-white/60 shadow-xs group-hover:scale-105 transition-transform">
                                <i data-lucide="${iconName}" class="w-4 h-4"></i>
                            </div>
                            <div class="truncate">
                                <h4 class="text-xs font-bold text-slate-900 dark:text-white truncate group-hover:text-indigo-600 dark:group-hover:text-indigo-400 transition-colors">${f.file_name}</h4>
                                <div class="flex items-center gap-1.5 mt-0.5">
                                    <span class="text-[10px] text-slate-500 font-mono">${sizeMb} MB • ${ext.toUpperCase()}</span>
                                    <span class="text-[9px] px-1.5 py-0.2 rounded bg-slate-200/60 dark:bg-slate-700/60 text-slate-600 dark:text-slate-300 font-medium">Ochish uchun bosing</span>
                                </div>
                            </div>
                        </div>

                        <div class="flex items-center gap-1.5 shrink-0" onclick="event.stopPropagation()">
                            ${(isWord || isPdf) ? `
                            <button onclick="openDirectDocumentEditor(${f.id}, '${f.file_name.replace(/'/g, "\\'")}', '${ext}')" title="Tahrirlash sahifasi" class="px-2.5 py-1 rounded-lg liquid-glass-pill text-[11px] font-bold text-indigo-600 dark:text-indigo-400 hover:bg-white transition-colors inline-flex items-center gap-1">
                                <i data-lucide="edit-3" class="w-3 h-3"></i> Tahrirlash
                            </button>
                            ` : ''}
                            <button onclick="TelegramApp.downloadFile('/api/files/${f.id}/download')" title="Yuklab olish" class="px-2.5 py-1 rounded-lg liquid-glass-pill text-[11px] font-bold text-brand-600 hover:bg-white transition-colors inline-flex items-center gap-1">
                                <i data-lucide="download" class="w-3 h-3"></i>
                            </button>
                            <button onclick="deleteFileFromDash(${f.id})" title="O'chirish" class="p-1.5 rounded-lg text-slate-400 hover:text-rose-600 hover:bg-rose-50 dark:hover:bg-rose-950/40 transition-colors">
                                <i data-lucide="trash-2" class="w-3.5 h-3.5"></i>
                            </button>
                            <i data-lucide="chevron-right" class="w-4 h-4 text-slate-300 group-hover:text-indigo-500 group-hover:translate-x-0.5 transition-all"></i>
                        </div>
                    </div>
                `;
            }).join('');
            refreshIcons();
        } catch (e) {
            container.innerHTML = `<div class="p-4 text-center text-xs text-red-500">${e.message}</div>`;
        }
    }

    window.deleteFileFromDash = async (id) => {
        TelegramApp.showConfirm("Faylni o'chirishga ishonchingiz komilmi?", async (confirmed) => {
            if (confirmed) {
                try {
                    await api.deleteFile(id);
                    TelegramApp.showAlert("Fayl o'chirildi.");
                    loadRecentFiles();
                } catch (e) {
                    TelegramApp.showAlert(`Xato: ${e.message}`);
                }
            }
        });
    };

    window.clearAllUserFiles = async () => {
        TelegramApp.showConfirm("Barcha saqlangan fayllarni tozalashni xohlaysizmi?", async (confirmed) => {
            if (confirmed) {
                try {
                    await api.clearAllFiles();
                    TelegramApp.showAlert("Barcha fayllar muvaffaqiyatli tozalandi.");
                    loadRecentFiles();
                } catch (e) {
                    TelegramApp.showAlert(`Xato: ${e.message}`);
                }
            }
        });
    };

    window.openFileWorkPage = async (id, fileName, ext) => {
        TelegramApp.hapticFeedback('medium');
        const lowerExt = (ext || '').toLowerCase();
        
        // Agar Word (docx/doc) yoki PDF bo'lsa, to'g'ridan-to'g'ri o'sha faylning mukammal tahrirlash/ko'rish sahifasini ochamiz
        if (['docx', 'doc', 'pdf'].includes(lowerExt)) {
            openDirectDocumentEditor(id, fileName, lowerExt);
            return;
        }

        // Agar boshqa format bo'lsa, to'g'ridan-to'g'ri yuklab olish yoki ma'lumot oynasini ko'rsatish
        TelegramApp.downloadFile(`/api/files/${id}/download`);
    };

    // ─────────────────────────────────────────────────────────────
    // TOOL 1: PDF ➔ Word (DOCX) Modal (Instant Processing)
    // ─────────────────────────────────────────────────────────────
    window.openPdfToWordModal = () => {
        TelegramApp.hapticFeedback();
        openModal(`
            <div class="fixed inset-0 z-50 flex items-center justify-center p-3 sm:p-5 bg-slate-900/60 backdrop-blur-md animate-fade-in">
                <div class="liquid-glass-card max-w-md w-full flex flex-col overflow-hidden bg-white/95 dark:bg-slate-900/95 border border-white/80 dark:border-slate-700/80 shadow-2xl">
                    <div class="p-4 border-b border-white/60 dark:border-slate-800 flex items-center justify-between">
                        <div class="flex items-center gap-2">
                            <div class="w-8 h-8 rounded-xl bg-rose-500/10 text-rose-600 flex items-center justify-center">
                                <i data-lucide="file-type-2" class="w-4 h-4"></i>
                            </div>
                            <h3 class="text-sm font-bold text-slate-900">PDF ni Word ga aylantirish</h3>
                        </div>
                        <button onclick="closeModal()" class="p-1.5 rounded-lg text-slate-400 hover:text-slate-600">
                            <i data-lucide="x" class="w-4 h-4"></i>
                        </button>
                    </div>

                    <div class="p-5 space-y-4">
                        <div id="p2w-upload-box" class="p-6 rounded-2xl border-2 border-dashed border-rose-300/80 text-center hover:border-rose-500 transition-colors bg-rose-50/20 cursor-pointer" onclick="document.getElementById('p2w-file-input').click()">
                            <i data-lucide="upload-cloud" class="w-9 h-9 mx-auto text-rose-500 mb-2"></i>
                            <span class="text-xs font-bold text-slate-800 block">PDF faylni tanlang</span>
                            <span class="text-[11px] text-slate-500 mt-1 block">Tanlashingiz bilan Word ga aylantiriladi</span>
                            <input type="file" id="p2w-file-input" accept=".pdf" class="hidden">
                        </div>

                        <!-- Processing indicator -->
                        <div id="p2w-loading" class="hidden py-8 text-center space-y-3">
                            <i data-lucide="loader-2" class="w-9 h-9 mx-auto text-rose-600 animate-spin"></i>
                            <p class="text-xs font-bold text-slate-800">Word (DOCX) ga aylantirilmoqda...</p>
                            <p class="text-[11px] text-slate-500">Jadvallar, matn va shriftlar saqlanmoqda</p>
                        </div>

                        <!-- Result Box -->
                        <div id="p2w-result" class="hidden p-4 rounded-2xl bg-emerald-500/10 border border-emerald-500/20 text-center space-y-3">
                            <div class="w-10 h-10 mx-auto rounded-full bg-emerald-500 text-white flex items-center justify-center shadow-md">
                                <i data-lucide="check" class="w-5 h-5"></i>
                            </div>
                            <div>
                                <h4 class="text-xs font-bold text-slate-900" id="p2w-out-name">Fayl</h4>
                                <p class="text-[11px] text-emerald-600 font-semibold mt-0.5">Word formati tayyor! Telegramingizga ham yuborildi ✓</p>
                            </div>
                            <button id="p2w-dl-btn" class="w-full py-2.5 px-4 rounded-xl bg-gradient-to-r from-emerald-600 to-teal-600 text-white text-xs font-bold shadow-md shadow-emerald-500/20 inline-flex items-center justify-center gap-1.5">
                                <i data-lucide="download" class="w-4 h-4"></i> Word faylni yuklab olish
                            </button>
                        </div>
                    </div>

                    <div class="p-3 border-t border-white/60 dark:border-slate-800 flex items-center justify-end bg-slate-50/50 dark:bg-slate-950/40">
                        <button onclick="closeModal()" class="px-4 py-2 rounded-xl text-xs font-semibold text-slate-600 hover:bg-slate-100">
                            Yopish
                        </button>
                    </div>
                </div>
            </div>
        `);

        const input = document.getElementById('p2w-file-input');
        const uploadBox = document.getElementById('p2w-upload-box');
        const loadingBox = document.getElementById('p2w-loading');
        const resultBox = document.getElementById('p2w-result');
        const outName = document.getElementById('p2w-out-name');
        const dlBtn = document.getElementById('p2w-dl-btn');

        input.onchange = async () => {
            if (!input.files.length) return;
            const file = input.files[0];
            uploadBox.classList.add('hidden');
            loadingBox.classList.remove('hidden');
            refreshIcons();

            try {
                const fd = new FormData();
                fd.append('file', file);
                const uploaded = await api.uploadFile(fd);

                const converted = await api.convertFile(uploaded.file_id, 'docx');
                TelegramApp.hapticFeedback('medium');

                loadingBox.classList.add('hidden');
                resultBox.classList.remove('hidden');
                outName.innerText = converted.new_file_name;
                dlBtn.onclick = () => {
                    TelegramApp.downloadFile(`/api/files/${converted.new_file_id}/download`);
                };
                refreshIcons();
                loadRecentFiles();
            } catch (err) {
                loadingBox.classList.add('hidden');
                uploadBox.classList.remove('hidden');
                TelegramApp.showAlert(`Xatolik: ${err.message}`);
            }
        };
    };

    // ─────────────────────────────────────────────────────────────
    // TOOL 2: Word ➔ PDF Modal (Instant Processing via Word COM)
    // ─────────────────────────────────────────────────────────────
    window.openWordToPdfModal = () => {
        TelegramApp.hapticFeedback();
        openModal(`
            <div class="fixed inset-0 z-50 flex items-center justify-center p-3 sm:p-5 bg-slate-900/60 backdrop-blur-md animate-fade-in">
                <div class="liquid-glass-card max-w-md w-full flex flex-col overflow-hidden bg-white/95 dark:bg-slate-900/95 border border-white/80 dark:border-slate-700/80 shadow-2xl">
                    <div class="p-4 border-b border-white/60 dark:border-slate-800 flex items-center justify-between">
                        <div class="flex items-center gap-2">
                            <div class="w-8 h-8 rounded-xl bg-blue-500/10 text-blue-600 flex items-center justify-center">
                                <i data-lucide="file-text" class="w-4 h-4"></i>
                            </div>
                            <h3 class="text-sm font-bold text-slate-900">Word ni PDF ga aylantirish</h3>
                        </div>
                        <button onclick="closeModal()" class="p-1.5 rounded-lg text-slate-400 hover:text-slate-600">
                            <i data-lucide="x" class="w-4 h-4"></i>
                        </button>
                    </div>

                    <div class="p-5 space-y-4">
                        <div id="w2p-upload-box" class="p-6 rounded-2xl border-2 border-dashed border-blue-300/80 text-center hover:border-blue-500 transition-colors bg-blue-50/20 cursor-pointer" onclick="document.getElementById('w2p-file-input').click()">
                            <i data-lucide="upload-cloud" class="w-9 h-9 mx-auto text-blue-500 mb-2"></i>
                            <span class="text-xs font-bold text-slate-800 block">Word (.docx, .doc) faylni tanlang</span>
                            <span class="text-[11px] text-slate-500 mt-1 block">Tanlashingiz bilan PDF ga aylantiriladi</span>
                            <input type="file" id="w2p-file-input" accept=".docx,.doc" class="hidden">
                        </div>

                        <!-- Processing indicator -->
                        <div id="w2p-loading" class="hidden py-8 text-center space-y-3">
                            <i data-lucide="loader-2" class="w-9 h-9 mx-auto text-blue-600 animate-spin"></i>
                            <p class="text-xs font-bold text-slate-800">PDF ga aylantirilmoqda...</p>
                            <p class="text-[11px] text-slate-500">Asl format va shriftlar saqlanmoqda</p>
                        </div>

                        <!-- Result Box -->
                        <div id="w2p-result" class="hidden p-4 rounded-2xl bg-emerald-500/10 border border-emerald-500/20 text-center space-y-3">
                            <div class="w-10 h-10 mx-auto rounded-full bg-emerald-500 text-white flex items-center justify-center shadow-md">
                                <i data-lucide="check" class="w-5 h-5"></i>
                            </div>
                            <div>
                                <h4 class="text-xs font-bold text-slate-900" id="w2p-out-name">Fayl</h4>
                                <p class="text-[11px] text-emerald-600 font-semibold mt-0.5">PDF tayyor! Telegramingizga ham yuborildi ✓</p>
                            </div>
                            <button id="w2p-dl-btn" class="w-full py-2.5 px-4 rounded-xl bg-gradient-to-r from-emerald-600 to-teal-600 text-white text-xs font-bold shadow-md shadow-emerald-500/20 inline-flex items-center justify-center gap-1.5">
                                <i data-lucide="download" class="w-4 h-4"></i> PDF faylni yuklab olish
                            </button>
                        </div>
                    </div>

                    <div class="p-3 border-t border-white/60 dark:border-slate-800 flex items-center justify-end bg-slate-50/50 dark:bg-slate-950/40">
                        <button onclick="closeModal()" class="px-4 py-2 rounded-xl text-xs font-semibold text-slate-600 hover:bg-slate-100">
                            Yopish
                        </button>
                    </div>
                </div>
            </div>
        `);

        const input = document.getElementById('w2p-file-input');
        const uploadBox = document.getElementById('w2p-upload-box');
        const loadingBox = document.getElementById('w2p-loading');
        const resultBox = document.getElementById('w2p-result');
        const outName = document.getElementById('w2p-out-name');
        const dlBtn = document.getElementById('w2p-dl-btn');

        input.onchange = async () => {
            if (!input.files.length) return;
            const file = input.files[0];
            uploadBox.classList.add('hidden');
            loadingBox.classList.remove('hidden');
            refreshIcons();

            try {
                const fd = new FormData();
                fd.append('file', file);
                const uploaded = await api.uploadFile(fd);

                const converted = await api.convertFile(uploaded.file_id, 'pdf');
                TelegramApp.hapticFeedback('medium');

                loadingBox.classList.add('hidden');
                resultBox.classList.remove('hidden');
                outName.innerText = converted.new_file_name;
                dlBtn.onclick = () => {
                    TelegramApp.downloadFile(`/api/files/${converted.new_file_id}/download`);
                };
                refreshIcons();
                loadRecentFiles();
            } catch (err) {
                loadingBox.classList.add('hidden');
                uploadBox.classList.remove('hidden');
                TelegramApp.showAlert(`Xatolik: ${err.message}`);
            }
        };
    };

    // ─────────────────────────────────────────────────────────────
    // TOOL 3 & 4: DEDICATED FULL-PAGE WYSIWYG DOCUMENT EDITOR
    // Pixel-perfect A4 document rendering, table editing, Word & PDF roundtrip
    // ─────────────────────────────────────────────────────────────

    let currentDocTarget = null;
    let savedSelectionRange = null;
    let isDocDirty = false;

    // Helper: Update active page and total pages indicator (RAF throttled for 60fps mobile scrolling)
    let _docPaginationRaf = null;
    function _executeDocPagination() {
        const iframe = document.getElementById('doc-active-iframe');
        const totalPagesEl = document.getElementById('doc-total-pages');
        const activePageEl = document.getElementById('doc-active-page');
        const viewport = document.getElementById('doc-viewport');
        if (!iframe || !totalPagesEl || !activePageEl) return;

        try {
            const iDoc = iframe.contentDocument || iframe.contentWindow.document;
            if (!iDoc || !iDoc.body) return;

            // 1. Total pages from body data-total-pages attribute or calculated from scrollHeight
            const breaks = iDoc.querySelectorAll('.doc-page-break, .page-divider-row');
            let total = parseInt(iDoc.body.getAttribute('data-total-pages') || '0', 10);
            if (!total || total < 1) {
                total = Math.max(1, breaks.length + 1, Math.ceil(iDoc.body.scrollHeight / 1123));
            }
            totalPagesEl.innerText = total;

            // 2. Determine currently visible page based on viewport scroll position
            let current = 1;
            if (viewport) {
                const scrollPos = viewport.scrollTop + 200;
                breaks.forEach((b, idx) => {
                    const rect = b.getBoundingClientRect();
                    if (rect.top <= 250) {
                        current = Math.min(total, idx + 2);
                    }
                });
            }
            activePageEl.innerText = current;
        } catch (e) {}
    }

    window.updateDocPagination = function() {
        if (_docPaginationRaf) return;
        _docPaginationRaf = requestAnimationFrame(() => {
            _docPaginationRaf = null;
            _executeDocPagination();
        });
    };

    // Helper: Adjust iframe height to fit document content (Debounced for zero-lag mobile typing)
    let _adjustHeightDebounceTimer = null;
    function _executeAdjustIframeHeight() {
        const iframe = document.getElementById('doc-active-iframe');
        const frameBox = document.getElementById('doc-frame-box');
        if (!iframe || !frameBox) return;
        try {
            const iDoc = iframe.contentDocument || iframe.contentWindow.document;
            if (iDoc && iDoc.body) {
                iDoc.documentElement.style.overflow = 'hidden';
                iDoc.body.style.overflow = 'hidden';
                const scrollH = Math.max(
                    1123,
                    iDoc.documentElement.scrollHeight || 0,
                    iDoc.documentElement.offsetHeight || 0,
                    iDoc.body.scrollHeight || 0,
                    iDoc.body.offsetHeight || 0
                );
                const targetH = scrollH + 50;
                iframe.style.height = `${targetH}px`;
                frameBox.style.height = `${targetH}px`;
                frameBox.style.minHeight = `${targetH}px`;
                window.updateDocPagination();
            }
        } catch (e) {}
    }

    window.adjustIframeHeight = function(immediate = false) {
        if (immediate === true) {
            if (_adjustHeightDebounceTimer) clearTimeout(_adjustHeightDebounceTimer);
            _executeAdjustIframeHeight();
            return;
        }
        if (_adjustHeightDebounceTimer) clearTimeout(_adjustHeightDebounceTimer);
        _adjustHeightDebounceTimer = setTimeout(_executeAdjustIframeHeight, 100);
    };

    // Helper: Restore last saved selection inside iframe
    function restoreDocSelection() {
        const iframe = document.getElementById('doc-active-iframe');
        if (!iframe || !iframe.contentWindow || !savedSelectionRange) return;
        try {
            const sel = iframe.contentWindow.getSelection();
            sel.removeAllRanges();
            sel.addRange(savedSelectionRange);
        } catch (e) {}
    }

    // Helper: Execute formatting commands on the active iframe document
    window.execDocCmd = function(command, value = null) {
        const iframe = document.getElementById('doc-active-iframe');
        if (!iframe || !iframe.contentWindow) return;
        const iDoc = iframe.contentDocument || iframe.contentWindow.document;
        iframe.contentWindow.focus();
        restoreDocSelection();

        try {
            if (command === 'hiliteColor') {
                const ok = iDoc.execCommand('hiliteColor', false, value);
                if (!ok) {
                    iDoc.execCommand('backColor', false, value);
                }
            } else {
                iDoc.execCommand(command, false, value);
            }
            isDocDirty = true;
            TelegramApp.hapticFeedback('light');
            window.adjustIframeHeight();
        } catch (err) {
            console.warn('execDocCmd error:', err);
        }
    };

    // Helper: Change document color
    window.changeDocColor = function(color, type = 'foreColor') {
        window.execDocCmd(type, color);
    };

    // Helper: Insert Table Row below current active row
    window.insertDocTableRow = function() {
        const iframe = document.getElementById('doc-active-iframe');
        if (!iframe || !iframe.contentDocument) return;
        const iDoc = iframe.contentDocument;

        let target = null;
        const sel = iframe.contentWindow.getSelection();
        if (sel && sel.anchorNode) {
            target = sel.anchorNode.nodeType === 1 ? sel.anchorNode : sel.anchorNode.parentElement;
        }
        if (!target && currentDocTarget) {
            target = currentDocTarget;
        }

        const tr = target ? target.closest('tr') : null;
        if (!tr) {
            TelegramApp.showAlert("Qator qo'shish uchun avval jadval ichidagi biron katakka bosing!");
            return;
        }

        const newRow = tr.cloneNode(true);
        newRow.querySelectorAll('td, th').forEach(cell => {
            cell.innerHTML = '&nbsp;';
        });

        tr.parentNode.insertBefore(newRow, tr.nextSibling);
        isDocDirty = true;
        TelegramApp.hapticFeedback('light');
        window.adjustIframeHeight();
        TelegramApp.showAlert("✅ Yangi qator qo'shildi");
    };

    // Helper: Delete current Table Row
    window.deleteDocTableRow = function() {
        const iframe = document.getElementById('doc-active-iframe');
        if (!iframe || !iframe.contentDocument) return;
        const iDoc = iframe.contentDocument;

        let target = null;
        const sel = iframe.contentWindow.getSelection();
        if (sel && sel.anchorNode) {
            target = sel.anchorNode.nodeType === 1 ? sel.anchorNode : sel.anchorNode.parentElement;
        }
        if (!target && currentDocTarget) {
            target = currentDocTarget;
        }

        const tr = target ? target.closest('tr') : null;
        if (!tr) {
            TelegramApp.showAlert("O'chirish uchun avval jadval qatoriga bosing!");
            return;
        }

        const table = tr.closest('table');
        if (table && table.rows.length <= 1) {
            TelegramApp.showAlert("Jadvalning so'nggi qatorini o'chirib bo'lmaydi!");
            return;
        }

        tr.remove();
        currentDocTarget = null;
        isDocDirty = true;
        TelegramApp.hapticFeedback('medium');
        window.adjustIframeHeight();
        TelegramApp.showAlert("🗑️ Qator o'chirildi");
    };

    // Helper: Insert Table Column right of current active column
    window.insertDocTableCol = function() {
        const iframe = document.getElementById('doc-active-iframe');
        if (!iframe || !iframe.contentDocument) return;
        const iDoc = iframe.contentDocument;

        let target = null;
        const sel = iframe.contentWindow.getSelection();
        if (sel && sel.anchorNode) {
            target = sel.anchorNode.nodeType === 1 ? sel.anchorNode : sel.anchorNode.parentElement;
        }
        if (!target && currentDocTarget) {
            target = currentDocTarget;
        }

        const cell = target ? target.closest('td, th') : null;
        if (!cell) {
            TelegramApp.showAlert("Ustun qo'shish uchun avval jadval katagiga bosing!");
            return;
        }

        const colIndex = cell.cellIndex;
        const table = cell.closest('table');
        if (table) {
            Array.from(table.rows).forEach(row => {
                const targetCell = row.cells[colIndex];
                if (targetCell) {
                    const newCell = targetCell.cloneNode(true);
                    newCell.innerHTML = '&nbsp;';
                    targetCell.parentNode.insertBefore(newCell, targetCell.nextSibling);
                }
            });
            isDocDirty = true;
            TelegramApp.hapticFeedback('light');
            window.adjustIframeHeight();
            TelegramApp.showAlert("✅ Yangi ustun qo'shildi");
        }
    };

    // Helper: Delete current Table Column
    window.deleteDocTableCol = function() {
        const iframe = document.getElementById('doc-active-iframe');
        if (!iframe || !iframe.contentDocument) return;
        const iDoc = iframe.contentDocument;

        let target = null;
        const sel = iframe.contentWindow.getSelection();
        if (sel && sel.anchorNode) {
            target = sel.anchorNode.nodeType === 1 ? sel.anchorNode : sel.anchorNode.parentElement;
        }
        if (!target && currentDocTarget) {
            target = currentDocTarget;
        }

        const cell = target ? target.closest('td, th') : null;
        if (!cell) {
            TelegramApp.showAlert("Ustunni o'chirish uchun avval jadval katagiga bosing!");
            return;
        }

        const colIndex = cell.cellIndex;
        const table = cell.closest('table');
        if (table) {
            Array.from(table.rows).forEach(row => {
                if (row.cells[colIndex]) {
                    row.cells[colIndex].remove();
                }
            });
            currentDocTarget = null;
            isDocDirty = true;
            TelegramApp.hapticFeedback('medium');
            window.adjustIframeHeight();
            TelegramApp.showAlert("🗑️ Ustun o'chirildi");
        }
    };

    // Helper: Search and Replace with case-insensitivity support
    window.docSearchAndReplace = function(findText, replaceText, matchCase = false) {
        const iframe = document.getElementById('doc-active-iframe');
        if (!iframe || !iframe.contentDocument) return 0;
        const iDoc = iframe.contentDocument;
        if (!findText) return 0;

        const body = iDoc.body;
        let count = 0;
        const walker = iDoc.createTreeWalker(body, NodeFilter.SHOW_TEXT, null, false);
        const nodesToChange = [];

        const escaped = findText.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
        const regex = new RegExp(escaped, matchCase ? 'g' : 'gi');

        let node;
        while (node = walker.nextNode()) {
            if (node.nodeValue && regex.test(node.nodeValue)) {
                nodesToChange.push(node);
            }
        }

        nodesToChange.forEach(n => {
            const matches = n.nodeValue.match(regex);
            if (matches) {
                count += matches.length;
                n.nodeValue = n.nodeValue.replace(regex, replaceText);
            }
        });

        if (count > 0) isDocDirty = true;
        window.adjustIframeHeight();
        return count;
    };

    // Main Full-Page Document Editor Launcher
    async function openDocumentEditorPage(fileId, fileName, fileType, initialHtml = null) {
        TelegramApp.hapticFeedback('heavy');
        isDocDirty = false;

        // Hide navigation dock while editing for maximum screen space
        const bottomNav = document.getElementById('bottom-nav');
        if (bottomNav) bottomNav.style.display = 'none';

        // Create or get full-page editor container
        let editorContainer = document.getElementById('doc-full-editor-page');
        if (!editorContainer) {
            editorContainer = document.createElement('div');
            editorContainer.id = 'doc-full-editor-page';
            editorContainer.className = 'doc-editor-view animate-fade-in';
            document.body.appendChild(editorContainer);
        }
        editorContainer.classList.remove('hidden');

        // Show loading state while fetching document HTML
        editorContainer.innerHTML = `
            <div class="flex-1 flex flex-col items-center justify-center p-6 text-center space-y-4 bg-slate-900 text-white">
                <div class="relative">
                    <div class="w-16 h-16 rounded-3xl bg-gradient-to-tr from-indigo-500 to-purple-600 flex items-center justify-center shadow-xl shadow-indigo-500/30 animate-pulse">
                        <i data-lucide="file-text" class="w-8 h-8 text-white"></i>
                    </div>
                    <i data-lucide="loader-2" class="w-6 h-6 text-indigo-400 absolute -bottom-2 -right-2 animate-spin"></i>
                </div>
                <div>
                    <h3 class="text-base font-bold tracking-tight">${fileName}</h3>
                    <p class="text-xs text-slate-400 mt-1">Hujjatning asl formati, sahifalari va jadvallari yuklanmoqda...</p>
                </div>
            </div>
        `;
        refreshIcons();

        let docHtml = initialHtml;
        if (!docHtml) {
            try {
                const res = await api.getFileHtml(fileId);
                docHtml = res.html || '';
            } catch (err) {
                TelegramApp.showAlert(`Hujjatni ochishda xatolik: ${err.message}`);
                closeDocumentEditor();
                return;
            }
        }

        // Render full modern document workspace with liquid glass buttons & page counter
        editorContainer.innerHTML = `
            <!-- Top App Bar (Modern Header) -->
            <header class="doc-editor-header px-3 sm:px-4 py-2 flex items-center justify-between gap-2 z-20">
                <div class="flex items-center gap-2 min-w-0">
                    <button id="doc-btn-exit" class="h-8 px-2.5 rounded-xl bg-slate-100 hover:bg-slate-200 dark:bg-slate-800 dark:hover:bg-slate-700 text-xs font-bold text-slate-700 dark:text-slate-200 transition-all flex items-center gap-1.5 shrink-0 border border-slate-200 dark:border-slate-700">
                        <i data-lucide="arrow-left" class="w-4 h-4"></i>
                        <span class="hidden xs:inline">Chiqish</span>
                    </button>
                    <div class="min-w-0">
                        <div class="flex items-center gap-1.5">
                            <h2 class="text-xs sm:text-sm font-bold text-slate-900 dark:text-slate-100 truncate max-w-[140px] sm:max-w-[220px]">${fileName}</h2>
                            <span class="px-1.5 py-0.5 rounded text-[10px] font-mono font-bold bg-indigo-500/10 text-indigo-600 dark:text-indigo-400 shrink-0 uppercase">${fileType}</span>
                        </div>
                    </div>
                </div>

                <div class="flex items-center gap-2 shrink-0">
                    <!-- Dynamic Page Counter Badge -->
                    <div id="doc-page-counter-badge" class="flex items-center gap-1 px-2.5 h-8 rounded-xl bg-slate-100 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 text-[11px] font-bold text-slate-700 dark:text-slate-200 select-none">
                        <i data-lucide="book-open" class="w-3.5 h-3.5 text-indigo-500"></i>
                        <span>Sahifa <b id="doc-active-page" class="text-indigo-600 dark:text-indigo-400">1</b> / <span id="doc-total-pages">1</span></span>
                    </div>

                    <!-- Zoom control -->
                    <div class="hidden sm:flex items-center gap-0.5 px-1 h-8 rounded-xl bg-slate-100 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 text-xs select-none">
                        <button id="btn-zoom-out" title="Kichraytirish" class="p-1 hover:bg-white dark:hover:bg-slate-700 rounded text-slate-600 dark:text-slate-300">
                            <i data-lucide="minus" class="w-3 h-3"></i>
                        </button>
                        <span id="label-zoom-level" class="font-mono text-[11px] px-1 font-bold text-slate-800 dark:text-slate-200">100%</span>
                        <button id="btn-zoom-in" title="Kattalashtirish" class="p-1 hover:bg-white dark:hover:bg-slate-700 rounded text-slate-600 dark:text-slate-300">
                            <i data-lucide="plus" class="w-3 h-3"></i>
                        </button>
                        <button id="btn-zoom-fit" title="Ekranga moslash" class="px-1.5 py-0.5 text-[10px] font-bold bg-indigo-50 dark:bg-indigo-900/40 text-indigo-600 dark:text-indigo-300 rounded ml-0.5">
                            Fit
                        </button>
                    </div>

                    <!-- Save DOCX button -->
                    <button id="btn-save-doc" class="h-8 px-3 rounded-xl bg-blue-600 hover:bg-blue-700 active:scale-95 text-white text-xs font-bold shadow-md shadow-blue-500/25 transition-all flex items-center gap-1.5 cursor-pointer">
                        <i data-lucide="file-text" class="w-3.5 h-3.5"></i>
                        <span>Word</span>
                    </button>

                    <!-- Save PDF button -->
                    <button id="btn-save-pdf" class="h-8 px-3 rounded-xl bg-rose-600 hover:bg-rose-700 active:scale-95 text-white text-xs font-bold shadow-md shadow-rose-500/25 transition-all flex items-center gap-1.5 cursor-pointer">
                        <i data-lucide="file-check" class="w-3.5 h-3.5"></i>
                        <span>PDF</span>
                    </button>
                </div>
            </header>

            <!-- Formatting Ribbon Toolbar -->
            <div class="doc-editor-ribbon z-10 select-none">
                <button onmousedown="event.preventDefault()" onclick="window.execDocCmd('undo')" class="ribbon-btn" title="Bekor qilish (Ctrl+Z)"><i data-lucide="undo-2" class="w-4 h-4"></i></button>
                <button onmousedown="event.preventDefault()" onclick="window.execDocCmd('redo')" class="ribbon-btn" title="Qaytarish (Ctrl+Y)"><i data-lucide="redo-2" class="w-4 h-4"></i></button>
                <div class="ribbon-separator"></div>

                <button onmousedown="event.preventDefault()" onclick="window.execDocCmd('bold')" class="ribbon-btn font-black text-sm" title="Qalin (Ctrl+B)">B</button>
                <button onmousedown="event.preventDefault()" onclick="window.execDocCmd('italic')" class="ribbon-btn italic font-serif text-sm" title="Qiya (Ctrl+I)">I</button>
                <button onmousedown="event.preventDefault()" onclick="window.execDocCmd('underline')" class="ribbon-btn underline text-sm" title="Tagiga chizilgan (Ctrl+U)">U</button>
                <button onmousedown="event.preventDefault()" onclick="window.execDocCmd('strikeThrough')" class="ribbon-btn line-through text-sm" title="Ustiga chizilgan">S</button>
                <div class="ribbon-separator"></div>

                <!-- Font Sizes -->
                <button onmousedown="event.preventDefault()" onclick="window.execDocCmd('fontSize', '4')" class="ribbon-btn font-bold text-xs" title="Kattaroq shrift">A+</button>
                <button onmousedown="event.preventDefault()" onclick="window.execDocCmd('fontSize', '2')" class="ribbon-btn font-bold text-xs" title="Kichikroq shrift">A-</button>
                <div class="ribbon-separator"></div>

                <!-- Colors -->
                <label onmousedown="event.preventDefault()" class="ribbon-btn cursor-pointer" title="Matn rangi">
                    <i data-lucide="palette" class="w-4 h-4 text-indigo-600 dark:text-indigo-400"></i>
                    <input type="color" id="doc-fore-color-input" onchange="window.changeDocColor(this.value, 'foreColor')" class="hidden">
                </label>
                <label onmousedown="event.preventDefault()" class="ribbon-btn cursor-pointer" title="Fon rangi (Highlight)">
                    <i data-lucide="highlighter" class="w-4 h-4 text-amber-500"></i>
                    <input type="color" id="doc-back-color-input" value="#ffff00" onchange="window.changeDocColor(this.value, 'hiliteColor')" class="hidden">
                </label>
                <div class="ribbon-separator"></div>

                <!-- Alignment -->
                <button onmousedown="event.preventDefault()" onclick="window.execDocCmd('justifyLeft')" class="ribbon-btn" title="Chapga tekislash"><i data-lucide="align-left" class="w-4 h-4"></i></button>
                <button onmousedown="event.preventDefault()" onclick="window.execDocCmd('justifyCenter')" class="ribbon-btn" title="O'rtaga tekislash"><i data-lucide="align-center" class="w-4 h-4"></i></button>
                <button onmousedown="event.preventDefault()" onclick="window.execDocCmd('justifyRight')" class="ribbon-btn" title="O'ngga tekislash"><i data-lucide="align-right" class="w-4 h-4"></i></button>
                <button onmousedown="event.preventDefault()" onclick="window.execDocCmd('justifyFull')" class="ribbon-btn" title="Ikkala tomonga tekislash"><i data-lucide="align-justify" class="w-4 h-4"></i></button>
                <div class="ribbon-separator"></div>

                <!-- Table Controls -->
                <button onmousedown="event.preventDefault()" onclick="window.insertDocTableRow()" class="ribbon-btn text-emerald-600 dark:text-emerald-400 gap-1 font-bold" title="Tanlangan katak ostidan yangi qator qo'shish">
                    <i data-lucide="rows-4" class="w-3.5 h-3.5"></i> +Qator
                </button>
                <button onmousedown="event.preventDefault()" onclick="window.deleteDocTableRow()" class="ribbon-btn text-rose-500 gap-1 font-bold" title="Faol qatorni o'chirish">
                    <i data-lucide="trash-2" class="w-3.5 h-3.5"></i> -Qator
                </button>
                <button onmousedown="event.preventDefault()" onclick="window.insertDocTableCol()" class="ribbon-btn text-emerald-600 dark:text-emerald-400 gap-1 font-bold" title="Tanlangan katak yonidan yangi ustun qo'shish">
                    <i data-lucide="columns-3" class="w-3.5 h-3.5"></i> +Ustun
                </button>
                <button onmousedown="event.preventDefault()" onclick="window.deleteDocTableCol()" class="ribbon-btn text-rose-500 gap-1 font-bold" title="Faol ustunni o'chirish">
                    <i data-lucide="trash-2" class="w-3.5 h-3.5"></i> -Ustun
                </button>
                <div class="ribbon-separator"></div>

                <!-- Search & Replace Toggle -->
                <button id="btn-toggle-replace" onmousedown="event.preventDefault()" class="ribbon-btn text-brand-600 dark:text-brand-400 gap-1 font-bold" title="So'z qidirish va almashtirish (Ctrl+F)">
                    <i data-lucide="replace" class="w-3.5 h-3.5"></i> So'z almashtirish
                </button>
            </div>

            <!-- In-Document Search & Replace Bar (Collapsible) -->
            <div id="doc-replace-panel" class="hidden p-3 bg-white/95 dark:bg-slate-900/95 border-b border-slate-200 dark:border-slate-800 flex flex-wrap items-center gap-2.5 z-10 shadow-md">
                <div class="flex items-center gap-1.5 flex-1 min-w-[140px]">
                    <span class="text-[11px] font-bold text-slate-500">Qidirish:</span>
                    <input type="text" id="doc-search-find" placeholder="Masalan: Saidova" class="w-full text-xs p-1.5 rounded-lg border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-800">
                </div>
                <div class="flex items-center gap-1.5 flex-1 min-w-[140px]">
                    <span class="text-[11px] font-bold text-slate-500">Yangi so'z:</span>
                    <input type="text" id="doc-search-rep" placeholder="Masalan: Karimova" class="w-full text-xs p-1.5 rounded-lg border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-800">
                </div>
                <button id="btn-do-replace" class="px-3 py-1.5 rounded-xl bg-indigo-600 text-white text-xs font-bold hover:bg-indigo-700 transition-colors flex items-center gap-1">
                    <i data-lucide="check" class="w-3.5 h-3.5"></i> Almashtirish
                </button>
                <button id="btn-close-replace" class="p-1.5 rounded-lg text-slate-400 hover:text-slate-600">
                    <i data-lucide="x" class="w-4 h-4"></i>
                </button>
            </div>

            <!-- Document Canvas Viewport -->
            <div id="doc-viewport" class="doc-canvas-viewport">
                <div id="doc-frame-wrapper" style="display: inline-block; transform-origin: top center;">
                    <div id="doc-frame-box" class="doc-page-frame-container">
                        <iframe id="doc-active-iframe" class="doc-page-iframe" scrolling="no" frameborder="0" title="Document WYSIWYG View"></iframe>
                    </div>
                </div>
            </div>
        `;
        refreshIcons();

        // Exit handler with unsaved changes protection
        document.getElementById('doc-btn-exit').onclick = () => {
            if (isDocDirty) {
                TelegramApp.showConfirm("Hujjatda saqlanmagan o'zgarishlar bor. Chiqishni xohlaysizmi?", (confirmed) => {
                    if (confirmed) closeDocumentEditor();
                });
            } else {
                closeDocumentEditor();
            }
        };

        // Initialize iframe with document HTML and designMode='on'
        const iframe = document.getElementById('doc-active-iframe');
        const frameBox = document.getElementById('doc-frame-box');
        const frameWrapper = document.getElementById('doc-frame-wrapper');
        const viewport = document.getElementById('doc-viewport');
        const iDoc = iframe.contentDocument || iframe.contentWindow.document;

        // Injected styling for smooth editing, table outlines, and page breaks
        const editorInjectStyle = `
            <style id="edubot-injected-style">
                * {
                    user-select: text !important;
                    -webkit-user-select: text !important;
                }
                html, body {
                    cursor: text !important;
                    outline: none !important;
                    background: #ffffff !important;
                    padding-bottom: 60px !important;
                    overflow: hidden !important;
                    overflow-x: hidden !important;
                    overflow-y: hidden !important;
                    scrollbar-width: none !important;
                    -ms-overflow-style: none !important;
                    margin: 0 !important;
                }
                ::-webkit-scrollbar {
                    display: none !important;
                    width: 0 !important;
                    height: 0 !important;
                }
                table {
                    border-collapse: collapse !important;
                }
                td, th {
                    transition: background 0.15s ease;
                    min-height: 24px !important;
                }
                td:focus, th:focus, td:focus-within, th:focus-within {
                    background-color: rgba(99, 102, 241, 0.08) !important;
                    outline: 1.5px dashed #6366f1 !important;
                }
                img {
                    max-width: 100% !important;
                    height: auto !important;
                }
                .doc-page-break {
                    margin: 30px -40px;
                    padding: 10px 0;
                    background: #f8fafc;
                    border-top: 2px dashed #94a3b8;
                    border-bottom: 2px dashed #94a3b8;
                    text-align: center;
                    position: relative;
                    user-select: none;
                    cursor: default;
                }
                .page-tag {
                    display: inline-block;
                    padding: 3px 12px;
                    background: #4f46e5;
                    color: #ffffff;
                    font-size: 11px;
                    font-family: system-ui, -apple-system, sans-serif;
                    font-weight: 700;
                    border-radius: 9999px;
                    box-shadow: 0 2px 6px rgba(79, 70, 229, 0.25);
                }
            </style>
        `;

        let fullHtmlToWrite = docHtml;
        if (fullHtmlToWrite.includes('</head>')) {
            fullHtmlToWrite = fullHtmlToWrite.replace('</head>', `${editorInjectStyle}</head>`);
        } else {
            fullHtmlToWrite = `${editorInjectStyle}${fullHtmlToWrite}`;
        }

        iDoc.open();
        iDoc.write(fullHtmlToWrite);
        iDoc.close();
        iDoc.designMode = 'on';
        if (iDoc.body) {
            iDoc.body.contentEditable = 'true';
        }

        // Auto-observe size changes so page height is always exact without any inner scrollbar
        if (window.ResizeObserver && iDoc.body) {
            try {
                const ro = new ResizeObserver(() => {
                    window.adjustIframeHeight(true);
                });
                ro.observe(iDoc.body);
            } catch (roErr) {}
        }

        // Forward mouse wheel events to outer workspace viewport (unified Word-style scrolling)
        iDoc.addEventListener('wheel', (e) => {
            if (viewport) {
                viewport.scrollTop += e.deltaY;
                viewport.scrollLeft += e.deltaX;
            }
        }, { passive: true });

        // Selection and node tracking inside iframe
        iDoc.addEventListener('selectionchange', () => {
            const sel = iframe.contentWindow.getSelection();
            if (sel && sel.rangeCount > 0) {
                savedSelectionRange = sel.getRangeAt(0).cloneRange();
                if (sel.anchorNode) {
                    currentDocTarget = sel.anchorNode.nodeType === 1 ? sel.anchorNode : sel.anchorNode.parentElement;
                }
            }
        });

        iDoc.addEventListener('click', (e) => {
            currentDocTarget = e.target;
            const sel = iframe.contentWindow.getSelection();
            if (sel && sel.rangeCount > 0) {
                savedSelectionRange = sel.getRangeAt(0).cloneRange();
            }
        });

        iDoc.addEventListener('focusin', (e) => {
            currentDocTarget = e.target;
        });

        // Keydown shortcuts inside iframe (Ctrl+S to save, Ctrl+F to find)
        iDoc.addEventListener('keydown', (e) => {
            if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 's') {
                e.preventDefault();
                handleSaveDocument('docx');
            } else if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'f') {
                e.preventDefault();
                document.getElementById('btn-toggle-replace').click();
            }
        });

        setTimeout(() => window.adjustIframeHeight(true), 200);
        iDoc.addEventListener('input', () => {
            isDocDirty = true;
            window.adjustIframeHeight(false);
        }, { passive: true });
        iDoc.addEventListener('keyup', () => {
            window.adjustIframeHeight(false);
        }, { passive: true });

        // Passive scroll listener on viewport to update active page number smoothly
        if (viewport) {
            viewport.addEventListener('scroll', window.updateDocPagination, { passive: true });
        }

        // Zoom Management
        let currentZoom = 1.0;
        const zoomLabel = document.getElementById('label-zoom-level');

        function applyZoom(z) {
            currentZoom = Math.max(0.35, Math.min(2.0, z));
            if (zoomLabel) zoomLabel.innerText = `${Math.round(currentZoom * 100)}%`;
            
            // Prefer CSS zoom for native scaling without ghost margins
            if ('zoom' in frameWrapper.style) {
                frameWrapper.style.zoom = currentZoom;
                frameWrapper.style.transform = '';
            } else {
                frameWrapper.style.transform = `scale(${currentZoom})`;
            }
        }

        function autoFitWidth() {
            const viewportWidth = window.innerWidth - 32;
            if (viewportWidth < 794) {
                applyZoom(viewportWidth / 794);
            } else {
                applyZoom(1.0);
            }
        }

        // Auto fit on small mobile screens
        if (window.innerWidth < 820) {
            autoFitWidth();
        }

        const zIn = document.getElementById('btn-zoom-in');
        const zOut = document.getElementById('btn-zoom-out');
        const zFit = document.getElementById('btn-zoom-fit');
        if (zIn) zIn.onclick = () => applyZoom(currentZoom + 0.1);
        if (zOut) zOut.onclick = () => applyZoom(currentZoom - 0.1);
        if (zFit) zFit.onclick = autoFitWidth;

        // Search & Replace Panel Handlers
        const replacePanel = document.getElementById('doc-replace-panel');
        document.getElementById('btn-toggle-replace').onclick = () => {
            replacePanel.classList.toggle('hidden');
            if (!replacePanel.classList.contains('hidden')) {
                document.getElementById('doc-search-find').focus();
            }
            refreshIcons();
        };

        document.getElementById('btn-close-replace').onclick = () => {
            replacePanel.classList.add('hidden');
        };

        document.getElementById('btn-do-replace').onclick = () => {
            const findW = document.getElementById('doc-search-find').value.trim();
            const repW = document.getElementById('doc-search-rep').value;
            if (!findW) {
                TelegramApp.showAlert("Qidirilayotgan so'zni kiriting!");
                return;
            }
            const count = window.docSearchAndReplace(findW, repW);
            TelegramApp.hapticFeedback('medium');
            if (count > 0) {
                TelegramApp.showAlert(`${count} ta "${findW}" so'zi muvaffaqiyatli almashtirildi!`);
            } else {
                TelegramApp.showAlert(`Hujjat ichida "${findW}" so'zi topilmadi.`);
            }
        };

        // Save Functionality (Word DOCX & PDF)
        async function handleSaveDocument(formatToSave) {
            TelegramApp.hapticFeedback('medium');

            // Clean up injected style tag before saving to Word
            let outputHtml = iDoc.documentElement.outerHTML;
            outputHtml = outputHtml.replace(/<style id="edubot-injected-style">[\s\S]*?<\/style>/gi, '');

            openModal(`
                <div class="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/70 backdrop-blur-md animate-fade-in">
                    <div class="liquid-glass-card max-w-sm w-full p-6 text-center space-y-4 bg-white/95 dark:bg-slate-900/95 border border-white/80 shadow-2xl">
                        <div class="w-12 h-12 mx-auto rounded-2xl bg-indigo-500/10 text-indigo-600 flex items-center justify-center">
                            <i data-lucide="loader-2" class="w-7 h-7 animate-spin"></i>
                        </div>
                        <div>
                            <h3 class="text-sm font-bold text-slate-900 dark:text-slate-100">Hujjat saqlanmoqda...</h3>
                            <p class="text-xs text-slate-500 mt-1">Microsoft Word (DOCX) va PDF formatlari yaratilmoqda</p>
                        </div>
                    </div>
                </div>
            `);
            refreshIcons();

            try {
                const saveRes = await api.saveFileHtml(fileId, outputHtml, formatToSave);
                isDocDirty = false;
                TelegramApp.hapticFeedback('heavy');

                const isDocx = formatToSave === 'docx';
                const mainFileName = isDocx ? (saveRes.docx_file_name || saveRes.new_file_name) : (saveRes.pdf_file_name || saveRes.new_file_name);

                openModal(`
                    <div class="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/70 backdrop-blur-md animate-fade-in">
                        <div class="liquid-glass-card max-w-md w-full p-6 text-center space-y-4 bg-white/95 dark:bg-slate-900/95 border border-white/80 shadow-2xl">
                            <div class="w-12 h-12 mx-auto rounded-full bg-emerald-500 text-white flex items-center justify-center shadow-lg shadow-emerald-500/30">
                                <i data-lucide="check" class="w-6 h-6"></i>
                            </div>
                            <div>
                                <h3 class="text-sm font-bold text-slate-900 dark:text-slate-100">${mainFileName}</h3>
                                <p class="text-xs text-emerald-600 font-semibold mt-1">Hujjat muvaffaqiyatli saqlandi va Telegramingizga yuborildi ✓</p>
                            </div>

                            <div class="space-y-2 pt-2">
                                ${saveRes.docx_file_id ? `
                                    <button onclick="TelegramApp.downloadFile('/api/files/${saveRes.docx_file_id}/download')" class="w-full py-2.5 px-4 rounded-xl bg-gradient-to-r from-blue-600 to-indigo-600 text-white text-xs font-bold shadow-md shadow-blue-500/20 flex items-center justify-center gap-2">
                                        <i data-lucide="download" class="w-4 h-4"></i> Word (.docx) yuklab olish
                                    </button>
                                ` : ''}

                                ${saveRes.pdf_file_id ? `
                                    <button onclick="TelegramApp.downloadFile('/api/files/${saveRes.pdf_file_id}/download')" class="w-full py-2.5 px-4 rounded-xl bg-gradient-to-r from-rose-600 to-red-600 text-white text-xs font-bold shadow-md shadow-rose-500/20 flex items-center justify-center gap-2">
                                        <i data-lucide="file-check" class="w-4 h-4"></i> PDF (.pdf) yuklab olish
                                    </button>
                                ` : ''}
                            </div>

                            <div class="pt-2 flex items-center justify-between border-t border-slate-100 dark:border-slate-800">
                                <button onclick="closeModal()" class="px-4 py-2 rounded-xl text-xs font-semibold text-slate-600 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800">
                                    Tahrirlashda davom etish
                                </button>
                                <button onclick="closeModal(); closeDocumentEditor();" class="px-4 py-2 rounded-xl text-xs font-bold text-indigo-600 dark:text-indigo-400 hover:bg-indigo-50 dark:hover:bg-indigo-950/40">
                                    Bosh sahifaga qaytish
                                </button>
                            </div>
                        </div>
                    </div>
                `);
                refreshIcons();
                loadRecentFiles();
            } catch (saveErr) {
                closeModal();
                TelegramApp.showAlert(`Saqlashda xatolik: ${saveErr.message}`);
            }
        }

        document.getElementById('btn-save-doc').onclick = () => handleSaveDocument('docx');
        document.getElementById('btn-save-pdf').onclick = () => handleSaveDocument('pdf');
    }

    function closeDocumentEditor() {
        const editorContainer = document.getElementById('doc-full-editor-page');
        if (editorContainer) {
            editorContainer.classList.add('hidden');
            editorContainer.innerHTML = '';
        }
        const bottomNav = document.getElementById('bottom-nav');
        if (bottomNav) bottomNav.style.display = '';
        isDocDirty = false;
        loadRecentFiles();
    }

    // Modal to choose or upload file for editing
    function openDocumentPickerModal(targetType = 'docx') {
        const isWord = targetType === 'docx';
        const title = isWord ? "Word (DOCX) Tahrirlash" : "PDF Tahrirlash";
        const iconName = isWord ? "file-edit" : "edit-3";
        const colorClass = isWord ? "text-indigo-600 bg-indigo-500/10 border-indigo-300/80" : "text-amber-600 bg-amber-500/10 border-amber-300/80";
        const acceptExt = isWord ? ".docx,.doc" : ".pdf";
        const descText = isWord ? ".docx yoki .doc formatdagi Word hujjati" : ".pdf formatdagi hujjat";

        TelegramApp.hapticFeedback();
        openModal(`
            <div class="fixed inset-0 z-50 flex items-center justify-center p-3 sm:p-5 bg-slate-900/60 backdrop-blur-md animate-fade-in">
                <div class="liquid-glass-card max-w-md w-full flex flex-col overflow-hidden bg-white/95 dark:bg-slate-900/95 border border-white/80 dark:border-slate-700/80 shadow-2xl">
                    <div class="p-4 border-b border-white/60 dark:border-slate-800 flex items-center justify-between">
                        <div class="flex items-center gap-2">
                            <div class="w-8 h-8 rounded-xl ${colorClass.split(' ')[1]} ${colorClass.split(' ')[0]} flex items-center justify-center">
                                <i data-lucide="${iconName}" class="w-4 h-4"></i>
                            </div>
                            <h3 class="text-sm font-bold text-slate-900 dark:text-slate-100">${title}</h3>
                        </div>
                        <button onclick="closeModal()" class="p-1.5 rounded-lg text-slate-400 hover:text-slate-600">
                            <i data-lucide="x" class="w-4 h-4"></i>
                        </button>
                    </div>

                    <div class="p-5 space-y-4">
                        <div id="doc-picker-box" class="p-6 rounded-2xl border-2 border-dashed ${colorClass.split(' ')[2]} text-center hover:opacity-90 transition-all bg-indigo-50/10 cursor-pointer" onclick="document.getElementById('doc-picker-file-input').click()">
                            <i data-lucide="upload-cloud" class="w-9 h-9 mx-auto ${colorClass.split(' ')[0]} mb-2"></i>
                            <span class="text-xs font-bold text-slate-800 dark:text-slate-200 block">Tahrirlash uchun faylni tanlang</span>
                            <span class="text-[11px] text-slate-500 mt-1 block">${descText}</span>
                            <input type="file" id="doc-picker-file-input" accept="${acceptExt}" class="hidden">
                        </div>

                        <!-- Processing State -->
                        <div id="doc-picker-loading" class="hidden py-8 text-center space-y-3">
                            <i data-lucide="loader-2" class="w-8 h-8 mx-auto ${colorClass.split(' ')[0]} animate-spin"></i>
                            <p class="text-xs font-bold text-slate-800 dark:text-slate-200">Hujjat tayyorlanmoqda...</p>
                            <p class="text-[11px] text-slate-500">Asl format, jadvallar va shriftlar yuklanmoqda</p>
                        </div>
                    </div>

                    <div class="p-3 border-t border-white/60 dark:border-slate-800 flex items-center justify-end bg-slate-50/50 dark:bg-slate-950/40">
                        <button onclick="closeModal()" class="px-4 py-2 rounded-xl text-xs font-semibold text-slate-600 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800">
                            Bekor qilish
                        </button>
                    </div>
                </div>
            </div>
        `);
        refreshIcons();

        const input = document.getElementById('doc-picker-file-input');
        const pickerBox = document.getElementById('doc-picker-box');
        const loadingBox = document.getElementById('doc-picker-loading');

        input.onchange = async () => {
            if (!input.files.length) return;
            const file = input.files[0];
            pickerBox.classList.add('hidden');
            loadingBox.classList.remove('hidden');
            refreshIcons();

            try {
                const fd = new FormData();
                fd.append('file', file);
                const uploaded = await api.uploadFile(fd);

                closeModal();
                openDocumentEditorPage(uploaded.file_id, uploaded.file_name, targetType);
            } catch (err) {
                loadingBox.classList.add('hidden');
                pickerBox.classList.remove('hidden');
                TelegramApp.showAlert(`Xatolik: ${err.message}`);
            } finally {
                input.value = '';
            }
        };
    }

    // Public window handlers for Tool 3 and Tool 4
    window.openDocEditModal = () => {
        openDocumentPickerModal('docx');
    };

    window.openPdfEditModal = () => {
        openDocumentPickerModal('pdf');
    };

    window.openDirectDocumentEditor = (fileId, fileName, fileType) => {
        openDocumentEditorPage(fileId, fileName, fileType);
    };


    // TOOL 5: Rasmlarni PDF qilish Modal (Mukammal funksiyalar, sodda va chiroyli interfeys)
    // ─────────────────────────────────────────────────────────────
    window.openImagesToPdfModal = () => {
        TelegramApp.hapticFeedback();
        openModal(`
            <div class="fixed inset-0 z-50 flex items-center justify-center p-3 sm:p-5 bg-slate-900/60 backdrop-blur-md animate-fade-in">
                <div class="liquid-glass-card max-w-lg w-full flex flex-col max-h-[90vh] overflow-hidden bg-white/95 dark:bg-slate-900/95 border border-white/80 dark:border-slate-700/80 shadow-2xl">
                    <!-- Header -->
                    <div class="p-4 border-b border-white/60 dark:border-slate-800 flex items-center justify-between shrink-0">
                        <div class="flex items-center gap-2.5">
                            <div class="w-8 h-8 rounded-xl bg-emerald-500/10 text-emerald-600 flex items-center justify-center">
                                <i data-lucide="images" class="w-4 h-4"></i>
                            </div>
                            <div>
                                <h3 class="text-sm font-bold text-slate-900 dark:text-white">Rasmlardan PDF yaratish</h3>
                                <p class="text-[11px] text-slate-500 dark:text-slate-400">Rasmlarni tartiblash, formatlash va PDF ga yig'ish</p>
                            </div>
                        </div>
                        <button onclick="closeModal()" class="p-1.5 rounded-lg text-slate-400 hover:text-slate-600 dark:hover:text-slate-200">
                            <i data-lucide="x" class="w-4 h-4"></i>
                        </button>
                    </div>

                    <!-- Body -->
                    <div class="p-4 sm:p-5 space-y-4 overflow-y-auto flex-1">
                        <!-- Upload Box -->
                        <div id="img2pdf-box" class="p-5 rounded-2xl border-2 border-dashed border-emerald-300/80 hover:border-emerald-500 transition-colors bg-emerald-50/20 dark:bg-emerald-950/10 text-center cursor-pointer" onclick="document.getElementById('modal-images-input').click()">
                            <i data-lucide="image-plus" class="w-8 h-8 mx-auto text-emerald-600 mb-1.5"></i>
                            <span class="text-xs font-bold text-slate-800 dark:text-slate-200 block">Rasmlarni tanlang (JPG, PNG, WEBP)</span>
                            <span class="text-[11px] text-slate-500 dark:text-slate-400 mt-0.5 block">Bir nechta rasmni birdaniga tanlashingiz mumkin</span>
                            <input type="file" id="modal-images-input" multiple accept="image/*" class="hidden">
                        </div>

                        <!-- Selected Images Grid & Management -->
                        <div id="img2pdf-preview-area" class="hidden space-y-3">
                            <div class="flex items-center justify-between">
                                <span class="text-xs font-bold text-slate-700 dark:text-slate-300 flex items-center gap-1.5">
                                    <i data-lucide="layers" class="w-3.5 h-3.5 text-emerald-600"></i>
                                    Tanlangan rasmlar: <span id="img2pdf-count-badge" class="px-2 py-0.5 rounded-full bg-emerald-100 dark:bg-emerald-900/40 text-emerald-700 dark:text-emerald-300 font-mono text-[10px] font-bold">0 ta</span>
                                </span>
                                <div class="flex items-center gap-2">
                                    <button onclick="document.getElementById('modal-images-input').click()" class="text-[11px] font-bold text-emerald-600 hover:text-emerald-700 inline-flex items-center gap-1">
                                        <i data-lucide="plus" class="w-3 h-3"></i> Yana qo'shish
                                    </button>
                                    <button onclick="window.clearSelectedImages()" class="text-[11px] font-bold text-rose-500 hover:text-rose-600 inline-flex items-center gap-1">
                                        <i data-lucide="trash" class="w-3 h-3"></i> Tozalash
                                    </button>
                                </div>
                            </div>

                            <!-- Thumbnails container with reordering -->
                            <div id="img2pdf-thumbs-list" class="grid grid-cols-3 sm:grid-cols-4 gap-2.5 max-h-52 overflow-y-auto p-1.5 rounded-xl bg-slate-50/70 dark:bg-slate-800/40 border border-slate-200/60 dark:border-slate-700/60">
                            </div>

                            <!-- PDF Visual Customization Options -->
                            <div class="pt-3 border-t border-slate-200/80 dark:border-slate-800 space-y-4">
                                <!-- 1. Varaq yo'nalishi (Visual Orientation Selector) -->
                                <div>
                                    <div class="flex items-center justify-between mb-1.5">
                                        <label class="text-[11px] font-bold text-slate-700 dark:text-slate-300 flex items-center gap-1.5">
                                            <i data-lucide="compass" class="w-3.5 h-3.5 text-emerald-600"></i>
                                            Varaq yo'nalishi
                                        </label>
                                        <span id="img2pdf-orient-label" class="text-[10px] font-bold text-emerald-600 dark:text-emerald-400">Tik (Vertikal)</span>
                                    </div>
                                    <div class="grid grid-cols-3 gap-2" id="img2pdf-orient-group">
                                        <button type="button" onclick="window.selectImgPdfOption('orient', 'portrait')" data-val="portrait" class="img2pdf-opt-btn active p-2.5 rounded-xl border-2 transition-all flex flex-col items-center gap-1.5 bg-emerald-50/40 dark:bg-emerald-950/20 border-emerald-500 text-emerald-700 dark:text-emerald-300 shadow-sm">
                                            <!-- Portrait visual sheet icon -->
                                            <div class="w-6 h-8 rounded border-2 border-current flex flex-col items-center justify-center p-0.5 gap-0.5">
                                                <div class="w-3.5 h-1 bg-current opacity-60 rounded-xs"></div>
                                                <div class="w-3.5 h-1 bg-current opacity-40 rounded-xs"></div>
                                            </div>
                                            <span class="text-[11px] font-bold">Tik (Vertikal)</span>
                                        </button>

                                        <button type="button" onclick="window.selectImgPdfOption('orient', 'landscape')" data-val="landscape" class="img2pdf-opt-btn p-2.5 rounded-xl border-2 transition-all flex flex-col items-center gap-1.5 bg-white/60 dark:bg-slate-800/40 border-slate-200 dark:border-slate-700 text-slate-600 dark:text-slate-400 hover:border-emerald-300">
                                            <!-- Landscape visual sheet icon -->
                                            <div class="w-8 h-6 rounded border-2 border-current flex flex-col items-center justify-center p-0.5 gap-0.5">
                                                <div class="w-5 h-1 bg-current opacity-60 rounded-xs"></div>
                                                <div class="w-5 h-1 bg-current opacity-40 rounded-xs"></div>
                                            </div>
                                            <span class="text-[11px] font-bold">Yotiq (Albom)</span>
                                        </button>

                                        <button type="button" onclick="window.selectImgPdfOption('orient', 'auto')" data-val="auto" class="img2pdf-opt-btn p-2.5 rounded-xl border-2 transition-all flex flex-col items-center gap-1.5 bg-white/60 dark:bg-slate-800/40 border-slate-200 dark:border-slate-700 text-slate-600 dark:text-slate-400 hover:border-emerald-300">
                                            <!-- Auto visual sheet icon -->
                                            <div class="w-7 h-7 rounded-lg border-2 border-dashed border-current flex items-center justify-center">
                                                <i data-lucide="refresh-cw" class="w-3.5 h-3.5"></i>
                                            </div>
                                            <span class="text-[11px] font-bold">Avtomatik</span>
                                        </button>
                                    </div>
                                    <input type="hidden" id="img2pdf-orient" value="portrait">
                                </div>

                                <!-- 2. Varaq o'lchami (Visual Page Size Selector) -->
                                <div>
                                    <div class="flex items-center justify-between mb-1.5">
                                        <label class="text-[11px] font-bold text-slate-700 dark:text-slate-300 flex items-center gap-1.5">
                                            <i data-lucide="file-text" class="w-3.5 h-3.5 text-emerald-600"></i>
                                            Varaq o'lchami
                                        </label>
                                        <span id="img2pdf-size-label" class="text-[10px] font-bold text-emerald-600 dark:text-emerald-400">A4 Standart</span>
                                    </div>
                                    <div class="grid grid-cols-3 gap-2" id="img2pdf-size-group">
                                        <button type="button" onclick="window.selectImgPdfOption('size', 'A4')" data-val="A4" class="img2pdf-opt-btn active p-2.5 rounded-xl border-2 transition-all flex flex-col items-center gap-1 bg-emerald-50/40 dark:bg-emerald-950/20 border-emerald-500 text-emerald-700 dark:text-emerald-300 shadow-sm">
                                            <span class="text-xs font-black tracking-wider">A4</span>
                                            <span class="text-[9px] opacity-75 font-medium">Standart kitob</span>
                                        </button>

                                        <button type="button" onclick="window.selectImgPdfOption('size', 'A3')" data-val="A3" class="img2pdf-opt-btn p-2.5 rounded-xl border-2 transition-all flex flex-col items-center gap-1 bg-white/60 dark:bg-slate-800/40 border-slate-200 dark:border-slate-700 text-slate-600 dark:text-slate-400 hover:border-emerald-300">
                                            <span class="text-xs font-black tracking-wider">A3</span>
                                            <span class="text-[9px] opacity-75 font-medium">Katta format</span>
                                        </button>

                                        <button type="button" onclick="window.selectImgPdfOption('size', 'ORIGINAL')" data-val="ORIGINAL" class="img2pdf-opt-btn p-2.5 rounded-xl border-2 transition-all flex flex-col items-center gap-1 bg-white/60 dark:bg-slate-800/40 border-slate-200 dark:border-slate-700 text-slate-600 dark:text-slate-400 hover:border-emerald-300">
                                            <span class="text-xs font-black tracking-wider">100%</span>
                                            <span class="text-[9px] opacity-75 font-medium">Asl rasm o'lchami</span>
                                        </button>
                                    </div>
                                    <input type="hidden" id="img2pdf-size" value="A4">
                                </div>

                                <!-- 3. Moslashtirish va Hoshiya (Visual Fit & Margin) -->
                                <div class="grid grid-cols-1 sm:grid-cols-2 gap-3">
                                    <!-- Moslashtirish -->
                                    <div>
                                        <label class="text-[11px] font-bold text-slate-700 dark:text-slate-300 block mb-1.5 flex items-center gap-1.5">
                                            <i data-lucide="maximize-2" class="w-3.5 h-3.5 text-emerald-600"></i>
                                            Moslashtirish
                                        </label>
                                        <div class="grid grid-cols-2 gap-2" id="img2pdf-fit-group">
                                            <button type="button" onclick="window.selectImgPdfOption('fit', 'fit')" data-val="fit" class="img2pdf-opt-btn active p-2 rounded-xl border-2 transition-all flex items-center gap-2 bg-emerald-50/40 dark:bg-emerald-950/20 border-emerald-500 text-emerald-700 dark:text-emerald-300 shadow-sm">
                                                <div class="w-5 h-5 rounded border border-current flex items-center justify-center p-0.5">
                                                    <div class="w-2.5 h-3 bg-current opacity-70 rounded-xs"></div>
                                                </div>
                                                <div class="text-left">
                                                    <span class="text-[11px] font-bold block leading-tight">Asl nisbat</span>
                                                    <span class="text-[9px] opacity-75 block">Buzilmaydi</span>
                                                </div>
                                            </button>

                                            <button type="button" onclick="window.selectImgPdfOption('fit', 'fill')" data-val="fill" class="img2pdf-opt-btn p-2 rounded-xl border-2 transition-all flex items-center gap-2 bg-white/60 dark:bg-slate-800/40 border-slate-200 dark:border-slate-700 text-slate-600 dark:text-slate-400 hover:border-emerald-300">
                                                <div class="w-5 h-5 rounded border border-current flex items-center justify-center p-0.5">
                                                    <div class="w-full h-full bg-current opacity-70 rounded-xs"></div>
                                                </div>
                                                <div class="text-left">
                                                    <span class="text-[11px] font-bold block leading-tight">To'ldirish</span>
                                                    <span class="text-[9px] opacity-75 block">Chetigacha</span>
                                                </div>
                                            </button>
                                        </div>
                                        <input type="hidden" id="img2pdf-fit" value="fit">
                                    </div>

                                    <!-- Chetdan masofa (Hoshiya) -->
                                    <div>
                                        <label class="text-[11px] font-bold text-slate-700 dark:text-slate-300 block mb-1.5 flex items-center gap-1.5">
                                            <i data-lucide="frame" class="w-3.5 h-3.5 text-emerald-600"></i>
                                            Hoshiya (Cheti)
                                        </label>
                                        <div class="grid grid-cols-3 gap-1.5" id="img2pdf-margin-group">
                                            <button type="button" onclick="window.selectImgPdfOption('margin', '0')" data-val="0" class="img2pdf-opt-btn p-2 rounded-xl border-2 transition-all flex flex-col items-center gap-0.5 bg-white/60 dark:bg-slate-800/40 border-slate-200 dark:border-slate-700 text-slate-600 dark:text-slate-400 hover:border-emerald-300">
                                                <div class="w-4 h-5 border-2 border-current bg-current/20 rounded-xs"></div>
                                                <span class="text-[10px] font-bold">0 mm</span>
                                            </button>

                                            <button type="button" onclick="window.selectImgPdfOption('margin', '20')" data-val="20" class="img2pdf-opt-btn active p-2 rounded-xl border-2 transition-all flex flex-col items-center gap-0.5 bg-emerald-50/40 dark:bg-emerald-950/20 border-emerald-500 text-emerald-700 dark:text-emerald-300 shadow-sm">
                                                <div class="w-4 h-5 border border-dashed border-current flex items-center justify-center p-0.5">
                                                    <div class="w-2.5 h-3.5 bg-current opacity-60 rounded-xs"></div>
                                                </div>
                                                <span class="text-[10px] font-bold">O'rtacha</span>
                                            </button>

                                            <button type="button" onclick="window.selectImgPdfOption('margin', '40')" data-val="40" class="img2pdf-opt-btn p-2 rounded-xl border-2 transition-all flex flex-col items-center gap-0.5 bg-white/60 dark:bg-slate-800/40 border-slate-200 dark:border-slate-700 text-slate-600 dark:text-slate-400 hover:border-emerald-300">
                                                <div class="w-4 h-5 border border-dashed border-current flex items-center justify-center p-1">
                                                    <div class="w-1.5 h-2 bg-current opacity-60 rounded-xs"></div>
                                                </div>
                                                <span class="text-[10px] font-bold">Keng</span>
                                            </button>
                                        </div>
                                        <input type="hidden" id="img2pdf-margin" value="20">
                                    </div>
                                </div>

                                <!-- 4. PDF Fayl Nomi -->
                                <div>
                                    <label class="text-[11px] font-bold text-slate-700 dark:text-slate-300 block mb-1 flex items-center gap-1.5">
                                        <i data-lucide="tag" class="w-3.5 h-3.5 text-emerald-600"></i>
                                        PDF fayl nomi (ixtiyoriy)
                                    </label>
                                    <div class="relative">
                                        <input type="text" id="img2pdf-title" placeholder="Masalan: Hujjatlar_to'plami" class="w-full text-xs py-2 pl-3 pr-12 rounded-xl border border-slate-200 dark:border-slate-700 bg-white/90 dark:bg-slate-800/90 text-slate-900 dark:text-white placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-emerald-500">
                                        <span class="absolute right-3 top-2 text-[11px] font-mono text-slate-400">.pdf</span>
                                    </div>
                                </div>
                            </div>
                        </div>

                        <!-- Processing State -->
                        <div id="img2pdf-loading" class="hidden py-8 text-center space-y-3">
                            <i data-lucide="loader-2" class="w-9 h-9 mx-auto text-emerald-600 animate-spin"></i>
                            <p class="text-xs font-bold text-slate-800 dark:text-white">Yuqori sifatli PDF tayyorlanmoqda...</p>
                            <p class="text-[11px] text-slate-500 dark:text-slate-400">Rasmlar tartiblanib, sahifalarga joylashtirilmoqda</p>
                        </div>

                        <!-- Success Result Box -->
                        <div id="img2pdf-result" class="hidden p-4 rounded-2xl bg-emerald-500/10 border border-emerald-500/20 text-center space-y-3">
                            <div class="w-11 h-11 mx-auto rounded-full bg-emerald-500 text-white flex items-center justify-center shadow-md">
                                <i data-lucide="check" class="w-6 h-6"></i>
                            </div>
                            <div>
                                <h4 class="text-xs font-bold text-slate-900 dark:text-white" id="img2pdf-out-name">PDF Tayyor</h4>
                                <p class="text-[11px] text-emerald-600 dark:text-emerald-400 font-semibold mt-0.5">PDF fayl Telegramingizga ham yuborildi ✓</p>
                            </div>
                            <div class="flex gap-2">
                                <button id="img2pdf-dl-btn" class="flex-1 py-2.5 px-4 rounded-xl bg-gradient-to-r from-emerald-600 to-teal-600 text-white text-xs font-bold shadow-md shadow-emerald-500/20 inline-flex items-center justify-center gap-1.5">
                                    <i data-lucide="download" class="w-4 h-4"></i> Yuklab olish
                                </button>
                                <button onclick="window.resetImagesToPdf()" class="py-2.5 px-3 rounded-xl border border-slate-200 dark:border-slate-700 text-slate-700 dark:text-slate-300 text-xs font-bold hover:bg-slate-100 dark:hover:bg-slate-800">
                                    Yangi PDF
                                </button>
                            </div>
                        </div>
                    </div>

                    <!-- Footer Action Buttons -->
                    <div class="p-3.5 border-t border-white/60 dark:border-slate-800 flex items-center justify-between bg-slate-50/50 dark:bg-slate-950/40 shrink-0">
                        <button onclick="closeModal()" class="px-4 py-2 rounded-xl text-xs font-semibold text-slate-600 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800">
                            Bekor qilish
                        </button>
                        <button id="img2pdf-generate-btn" disabled onclick="window.generatePdfFromSelectedImages()" class="px-5 py-2 rounded-xl bg-emerald-600 hover:bg-emerald-700 disabled:opacity-40 disabled:cursor-not-allowed text-white text-xs font-bold shadow-md shadow-emerald-600/20 inline-flex items-center gap-1.5 transition-all">
                            <i data-lucide="file-check" class="w-4 h-4"></i> PDF yaratish
                        </button>
                    </div>
                </div>
            </div>
        `);

        refreshIcons();

        // Local state for uploaded image files
        let selectedFiles = [];

        const fileInput = document.getElementById('modal-images-input');
        const box = document.getElementById('img2pdf-box');
        const previewArea = document.getElementById('img2pdf-preview-area');
        const thumbsList = document.getElementById('img2pdf-thumbs-list');
        const countBadge = document.getElementById('img2pdf-count-badge');
        const generateBtn = document.getElementById('img2pdf-generate-btn');
        const loading = document.getElementById('img2pdf-loading');
        const result = document.getElementById('img2pdf-result');
        const outName = document.getElementById('img2pdf-out-name');
        const dlBtn = document.getElementById('img2pdf-dl-btn');

        fileInput.onchange = (e) => {
            const files = Array.from(e.target.files || []);
            if (!files.length) return;
            selectedFiles = [...selectedFiles, ...files];
            fileInput.value = '';
            renderThumbnails();
        };

        window.selectImgPdfOption = (type, val) => {
            TelegramApp.hapticFeedback('light');
            const hiddenInput = document.getElementById(`img2pdf-${type}`);
            if (hiddenInput) hiddenInput.value = val;

            const group = document.getElementById(`img2pdf-${type}-group`);
            if (group) {
                const buttons = group.querySelectorAll('button');
                buttons.forEach(btn => {
                    const btnVal = btn.getAttribute('data-val');
                    if (btnVal === val) {
                        btn.className = 'img2pdf-opt-btn active p-2.5 rounded-xl border-2 transition-all flex flex-col items-center gap-1.5 bg-emerald-50/40 dark:bg-emerald-950/20 border-emerald-500 text-emerald-700 dark:text-emerald-300 shadow-sm';
                        if (type === 'fit') {
                            btn.className = 'img2pdf-opt-btn active p-2 rounded-xl border-2 transition-all flex items-center gap-2 bg-emerald-50/40 dark:bg-emerald-950/20 border-emerald-500 text-emerald-700 dark:text-emerald-300 shadow-sm';
                        } else if (type === 'margin') {
                            btn.className = 'img2pdf-opt-btn active p-2 rounded-xl border-2 transition-all flex flex-col items-center gap-0.5 bg-emerald-50/40 dark:bg-emerald-950/20 border-emerald-500 text-emerald-700 dark:text-emerald-300 shadow-sm';
                        }
                    } else {
                        btn.className = 'img2pdf-opt-btn p-2.5 rounded-xl border-2 transition-all flex flex-col items-center gap-1.5 bg-white/60 dark:bg-slate-800/40 border-slate-200 dark:border-slate-700 text-slate-600 dark:text-slate-400 hover:border-emerald-300';
                        if (type === 'fit') {
                            btn.className = 'img2pdf-opt-btn p-2 rounded-xl border-2 transition-all flex items-center gap-2 bg-white/60 dark:bg-slate-800/40 border-slate-200 dark:border-slate-700 text-slate-600 dark:text-slate-400 hover:border-emerald-300';
                        } else if (type === 'margin') {
                            btn.className = 'img2pdf-opt-btn p-2 rounded-xl border-2 transition-all flex flex-col items-center gap-0.5 bg-white/60 dark:bg-slate-800/40 border-slate-200 dark:border-slate-700 text-slate-600 dark:text-slate-400 hover:border-emerald-300';
                        }
                    }
                });
            }

            // Update human readable label if present
            const label = document.getElementById(`img2pdf-${type}-label`);
            if (label) {
                if (type === 'orient') {
                    label.innerText = val === 'portrait' ? 'Tik (Vertikal)' : val === 'landscape' ? 'Yotiq (Albom)' : 'Avtomatik';
                } else if (type === 'size') {
                    label.innerText = val === 'A4' ? 'A4 Standart' : val === 'A3' ? 'A3 Katta' : '100% Asl o\'lcham';
                }
            }
        };

        function renderThumbnails() {
            if (selectedFiles.length === 0) {
                previewArea.classList.add('hidden');
                box.classList.remove('hidden');
                generateBtn.disabled = true;
                return;
            }

            box.classList.add('hidden');
            previewArea.classList.remove('hidden');
            generateBtn.disabled = false;
            countBadge.innerText = `${selectedFiles.length} ta`;

            thumbsList.innerHTML = selectedFiles.map((file, idx) => {
                const tempUrl = URL.createObjectURL(file);
                return `
                    <div class="relative group rounded-lg overflow-hidden border border-slate-200/80 dark:border-slate-700/80 aspect-square bg-slate-100 dark:bg-slate-800 shadow-sm flex items-center justify-center">
                        <img src="${tempUrl}" class="w-full h-full object-cover">
                        <span class="absolute top-1 left-1 px-1.5 py-0.5 rounded bg-black/60 text-white font-mono text-[9px] font-bold">#${idx + 1}</span>
                        <!-- Actions overlay -->
                        <div class="absolute inset-0 bg-black/50 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center gap-1.5">
                            ${idx > 0 ? `
                            <button onclick="window.moveImageOrder(${idx}, -1)" title="Chapga" class="w-6 h-6 rounded bg-white/90 text-slate-800 flex items-center justify-center hover:bg-white text-[11px]">
                                ◀
                            </button>
                            ` : ''}
                            ${idx < selectedFiles.length - 1 ? `
                            <button onclick="window.moveImageOrder(${idx}, 1)" title="O'ngga" class="w-6 h-6 rounded bg-white/90 text-slate-800 flex items-center justify-center hover:bg-white text-[11px]">
                                ▶
                            </button>
                            ` : ''}
                            <button onclick="window.removeSelectedImage(${idx})" title="O'chirish" class="w-6 h-6 rounded bg-rose-600 text-white flex items-center justify-center hover:bg-rose-700 text-[11px]">
                                ✕
                            </button>
                        </div>
                    </div>
                `;
            }).join('');
            refreshIcons();
        }

        window.moveImageOrder = (index, delta) => {
            const newIndex = index + delta;
            if (newIndex < 0 || newIndex >= selectedFiles.length) return;
            const temp = selectedFiles[index];
            selectedFiles[index] = selectedFiles[newIndex];
            selectedFiles[newIndex] = temp;
            renderThumbnails();
        };

        window.removeSelectedImage = (index) => {
            selectedFiles.splice(index, 1);
            renderThumbnails();
        };

        window.clearSelectedImages = () => {
            selectedFiles = [];
            renderThumbnails();
        };

        window.resetImagesToPdf = () => {
            selectedFiles = [];
            result.classList.add('hidden');
            loading.classList.add('hidden');
            previewArea.classList.add('hidden');
            box.classList.remove('hidden');
            generateBtn.disabled = true;
            generateBtn.classList.remove('hidden');
            refreshIcons();
        };

        window.generatePdfFromSelectedImages = async () => {
            if (selectedFiles.length === 0) return;
            TelegramApp.hapticFeedback('medium');

            previewArea.classList.add('hidden');
            box.classList.add('hidden');
            generateBtn.classList.add('hidden');
            loading.classList.remove('hidden');
            refreshIcons();

            const fd = new FormData();
            selectedFiles.forEach(file => {
                fd.append('files', file);
            });

            const pageSize = document.getElementById('img2pdf-size')?.value || 'A4';
            const orient = document.getElementById('img2pdf-orient')?.value || 'portrait';
            const fitMode = document.getElementById('img2pdf-fit')?.value || 'fit';
            const margin = document.getElementById('img2pdf-margin')?.value || '20';
            const title = document.getElementById('img2pdf-title')?.value || '';

            fd.append('page_size', pageSize);
            fd.append('orientation', orient);
            fd.append('fit_mode', fitMode);
            fd.append('margin', margin);
            if (title.trim()) fd.append('title', title.trim());

            try {
                const res = await api.imagesToPdf(fd);
                TelegramApp.hapticFeedback('heavy');

                loading.classList.add('hidden');
                result.classList.remove('hidden');
                outName.innerText = res.new_file_name;
                dlBtn.onclick = () => {
                    TelegramApp.downloadFile(`/api/files/${res.new_file_id}/download`);
                };
                refreshIcons();
                loadRecentFiles();
            } catch (err) {
                loading.classList.add('hidden');
                previewArea.classList.remove('hidden');
                generateBtn.classList.remove('hidden');
                TelegramApp.showAlert(`Xatolik: ${err.message}`);
                refreshIcons();
            }
        };
    };

    // ─────────────────────────────────────────────────────────────
    // TOOL 6: Extract Images from PDF Modal (Instant ZIP)
    // ─────────────────────────────────────────────────────────────
    window.openExtractImagesModal = () => {
        TelegramApp.hapticFeedback();
        openModal(`
            <div class="fixed inset-0 z-50 flex items-center justify-center p-3 sm:p-5 bg-slate-900/60 backdrop-blur-md animate-fade-in">
                <div class="liquid-glass-card max-w-md w-full flex flex-col overflow-hidden bg-white/95 dark:bg-slate-900/95 border border-white/80 dark:border-slate-700/80 shadow-2xl">
                    <div class="p-4 border-b border-white/60 dark:border-slate-800 flex items-center justify-between">
                        <div class="flex items-center gap-2">
                            <div class="w-8 h-8 rounded-xl bg-cyan-500/10 text-cyan-600 flex items-center justify-center">
                                <i data-lucide="folder-archive" class="w-4 h-4"></i>
                            </div>
                            <h3 class="text-sm font-bold text-slate-900">PDF dan rasmlarni ajratish</h3>
                        </div>
                        <button onclick="closeModal()" class="p-1.5 rounded-lg text-slate-400 hover:text-slate-600">
                            <i data-lucide="x" class="w-4 h-4"></i>
                        </button>
                    </div>

                    <div class="p-5 space-y-4">
                        <div id="ext-upload-box" class="p-6 rounded-2xl border-2 border-dashed border-cyan-300/80 text-center hover:border-cyan-500 transition-colors bg-cyan-50/20 cursor-pointer" onclick="document.getElementById('ext-pdf-input').click()">
                            <i data-lucide="upload-cloud" class="w-9 h-9 mx-auto text-cyan-500 mb-2"></i>
                            <span class="text-xs font-bold text-slate-800 block">PDF faylni tanlang</span>
                            <span class="text-[11px] text-slate-500 mt-1 block">Barcha rasmlar ZIP arxivga yig'iladi</span>
                            <input type="file" id="ext-pdf-input" accept=".pdf" class="hidden">
                        </div>

                        <!-- Processing -->
                        <div id="ext-loading" class="hidden py-8 text-center space-y-3">
                            <i data-lucide="loader-2" class="w-9 h-9 mx-auto text-cyan-600 animate-spin"></i>
                            <p class="text-xs font-bold text-slate-800">Rasmlar ajratilmoqda...</p>
                            <p class="text-[11px] text-slate-500">Asl sifatdagi fotosuratlar saqlanmoqda</p>
                        </div>

                        <!-- Result -->
                        <div id="ext-result" class="hidden p-4 rounded-2xl bg-emerald-500/10 border border-emerald-500/20 text-center space-y-3">
                            <div class="w-10 h-10 mx-auto rounded-full bg-emerald-500 text-white flex items-center justify-center shadow-md">
                                <i data-lucide="check" class="w-5 h-5"></i>
                            </div>
                            <h4 class="text-xs font-bold text-slate-900" id="ext-out-msg">Rasmlar arxivlandi</h4>
                            <p class="text-[11px] text-emerald-600 font-semibold">ZIP arxiv tayyor va Telegramingizga ham yuborildi ✓</p>
                            <button id="ext-dl-btn" class="w-full py-2.5 px-4 rounded-xl bg-gradient-to-r from-cyan-600 to-teal-600 text-white text-xs font-bold shadow-md shadow-cyan-500/20 inline-flex items-center justify-center gap-1.5">
                                <i data-lucide="download" class="w-4 h-4"></i> ZIP arxivni yuklab olish
                            </button>
                        </div>
                    </div>

                    <div class="p-3 border-t border-white/60 dark:border-slate-800 flex items-center justify-end bg-slate-50/50 dark:bg-slate-950/40">
                        <button onclick="closeModal()" class="px-4 py-2 rounded-xl text-xs font-semibold text-slate-600 hover:bg-slate-100">
                            Yopish
                        </button>
                    </div>
                </div>
            </div>
        `);

        const input = document.getElementById('ext-pdf-input');
        const box = document.getElementById('ext-upload-box');
        const loading = document.getElementById('ext-loading');
        const result = document.getElementById('ext-result');
        const outMsg = document.getElementById('ext-out-msg');
        const dlBtn = document.getElementById('ext-dl-btn');

        input.onchange = async () => {
            if (!input.files.length) return;
            box.classList.add('hidden');
            loading.classList.remove('hidden');
            refreshIcons();

            try {
                const fd = new FormData();
                fd.append('file', input.files[0]);
                const uploaded = await api.uploadFile(fd);

                const extracted = await api.extractImages(uploaded.file_id);
                TelegramApp.hapticFeedback('medium');

                loading.classList.add('hidden');
                result.classList.remove('hidden');
                outMsg.innerText = `${extracted.images_count} ta rasm ZIP arxivga yig'ildi!`;
                dlBtn.onclick = () => {
                    TelegramApp.downloadFile(`/api/files/${extracted.new_file_id}/download`);
                };
                refreshIcons();
                loadRecentFiles();
            } catch (err) {
                loading.classList.add('hidden');
                box.classList.remove('hidden');
                TelegramApp.showAlert(`Xatolik: ${err.message}`);
            }
        };
    };

    // ─────────────────────────────────────────────────────────────
    // 2. AI ASSISTANT VIEW (Tool 7)
    // ─────────────────────────────────────────────────────────────
    // 2. AI PEDAGOGICAL STUDIO (Clear, Intuitive, 7 Special Tools)
    // ─────────────────────────────────────────────────────────────
    const AI_STUDIO_TOOLS = [
        {
            id: 'lesson',
            title: "Dars Rejasi (Konspekt)",
            shortTitle: "Dars Rejasi",
            badge: "Konspekt",
            icon: "book-open",
            color: "from-blue-600 to-indigo-600",
            bgActive: "bg-blue-600 text-white shadow-blue-500/25",
            desc: "Fan, mavzu va sinfni kiriting. AI 45 daqiqalik darsning har bir bosqichini to'liq pedagogik konspekt qilib beradi.",
            label: "Fan va Mavzuni kiriting:",
            placeholder: "Masalan: Matematika — Kvadrat tenglamalarni diskriminant orqali yechish",
            chips: [
                "5-sinf Matematika — Oddiy kasrlar ustida amallar",
                "8-sinf Fizika — Nyutonning 2-qonuni va formulasi",
                "7-sinf Ingliz tili — Present Perfect zamoni",
                "9-sinf Kimyo — Davriy qonun va elementlar",
                "6-sinf Tarix — Qadimgi Baqtriya davlati"
            ]
        },
        {
            id: 'quiz',
            title: "Test & Savollar Tuzish",
            shortTitle: "Test Tuzish",
            badge: "A/B/C/D",
            icon: "help-circle",
            color: "from-amber-500 to-orange-600",
            bgActive: "bg-amber-600 text-white shadow-amber-500/25",
            desc: "Mavzu bo'yicha to'g'ri va noto'g'ri variantli (A/B/C/D), javob izohlari bilan tayyor testlar tuzadi.",
            label: "Qaysi mavzudan test tuzish kerak?",
            placeholder: "Masalan: 5 ta test: O'zbekistonning daryolari va tabiiy boyliklari",
            chips: [
                "5 ta test: 8-sinf Biologiya — Hujayra tuzilishi",
                "5 ta test: O'zbekiston tarixi — Amir Temur davri",
                "5 ta test: 9-sinf Geometriya — Pifagor teoremasi",
                "5 ta test: Ona tili — Ot so'z turkumi va uning yasalishi"
            ]
        },
        {
            id: 'summarize',
            title: "Katta Matnni Xulosa Qilish",
            shortTitle: "Xulosa",
            badge: "Tezislar",
            icon: "file-text",
            color: "from-emerald-500 to-teal-600",
            bgActive: "bg-emerald-600 text-white shadow-emerald-500/25",
            desc: "Katta maqola, qonun hujjati yoki mavzudan eng muhim nuqta, tezis va xulosalarni ajratib beradi.",
            label: "Xulosa qilinadigan matnni kiriting:",
            placeholder: "Maqola, matn yoki darslik parchasini shu yerga yozing...",
            chips: [
                "O'qituvchilarning yangi milliy baholash tizimi va mezonlari",
                "Zamonaviy interaktiv pedagogik metodlar va ularning samaradorligi",
                "STEAM ta'limining maktabdagi asosiy tamoyillari"
            ]
        },
        {
            id: 'explain',
            title: "Mavzuni Sodda Tushuntirish",
            shortTitle: "Tushuntirish",
            badge: "Sodda til",
            icon: "lightbulb",
            color: "from-violet-500 to-purple-600",
            bgActive: "bg-purple-600 text-white shadow-purple-500/25",
            desc: "Murakkab ilmiy tushunchalarni o'quvchilar tez va oson tushunishi uchun qiziqarli hayotiy misollar bilan tushuntiradi.",
            label: "Qaysi murakkab mavzuni tushuntirish kerak?",
            placeholder: "Masalan: Nima uchun samolyot havoda uchadi va tushib ketmaydi?",
            chips: [
                "Fotosintez jarayoni o'zi nima va u qanday sodir bo'ladi?",
                "Sun'iy intellekt (AI) inson hayotiga qanday ta'sir qilmoqda?",
                "Yerning tortishish kuchi (Gravitatsiya) qanday ishlaydi?",
                "Nima uchun osmon kunduzi ko'k, quyosh botganda qizil ko'rinadi?"
            ]
        },
        {
            id: 'grammar',
            title: "Grammatika & Imlo Tekshiruvi",
            shortTitle: "Grammatika",
            badge: "Xatosiz",
            icon: "check-circle",
            color: "from-rose-500 to-red-600",
            bgActive: "bg-rose-600 text-white shadow-rose-500/25",
            desc: "Matndagi harflar, tinish belgilari va grammatik xatolarni topib, to'g'irlangan variantini ko'rsatadi.",
            label: "Tekshiriladigan matnni kiriting:",
            placeholder: "Imlosi tekshirilishi kerak bo'lgan matnni shu yerga yozing...",
            chips: [
                "Maktab ma'muriyatiga taqdim etiladigan rasmiy hisobot matni",
                "Dars ishlanmasi matnini imlo xatolaridan tozalash"
            ]
        },
        {
            id: 'translate',
            title: "Professional Tarjima",
            shortTitle: "Tarjima",
            badge: "3 ta til",
            icon: "languages",
            color: "from-sky-500 to-blue-600",
            bgActive: "bg-sky-600 text-white shadow-sky-500/25",
            desc: "Akademik va pedagogik atamalarni saqlagan holda O'zbekcha, Ruscha va Inglizcha tillarga tarjima qiladi.",
            label: "Tarjima qilinadigan matnni kiriting:",
            placeholder: "Tarjima qilinadigan matnni shu yerga yozing...",
            chips: [
                "Ta'lim berish jarayonida interaktiv metodlardan foydalanish afzalliklari",
                "O'quvchilarning mantiqiy va tanqidiy fikrlashini rivojlantirish yo'llari",
                "Innovative methods in modern primary school education"
            ]
        },
        {
            id: 'improve',
            title: "Matnni Sayqallash & Boyitish",
            shortTitle: "Sayqallash",
            badge: "Pedagogik",
            icon: "wand-2",
            color: "from-fuchsia-500 to-pink-600",
            bgActive: "bg-fuchsia-600 text-white shadow-fuchsia-500/25",
            desc: "Matn mazmunini saqlagan holda, yanada jozibador, rasmiy va professional pedagogik uslubda qayta yozadi.",
            label: "Sayqallanadigan matnni kiriting:",
            placeholder: "Oddiy tilda yozilgan matningizni shu yerga kiriting...",
            chips: [
                "Ota-onalar majlisi uchun nutq matnini yaxshilash va ta'sirchan qilish",
                "A'lochi o'quvchiga beriladigan tavsifnomani chiroyli boyitish"
            ]
        }
    ];

    function renderMarkdownToHtml(md) {
        if (!md) return '';
        let html = md
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/^### (.*$)/gim, '<h3 class="text-sm font-bold text-slate-900 dark:text-white mt-3 mb-1">$1</h3>')
            .replace(/^## (.*$)/gim, '<h2 class="text-base font-bold text-slate-900 dark:text-white mt-4 mb-1.5 pb-1 border-b border-slate-200 dark:border-slate-800">$1</h2>')
            .replace(/^# (.*$)/gim, '<h1 class="text-lg font-black text-slate-900 dark:text-white mt-4 mb-2 pb-1 border-b-2 border-indigo-500">$1</h1>')
            .replace(/\*\*(.*?)\*\*/g, '<strong class="font-bold text-slate-900 dark:text-white">$1</strong>')
            .replace(/\*(.*?)\*/g, '<em class="italic text-slate-700 dark:text-slate-300">$1</em>')
            .replace(/^\s*[•\-\*]\s+(.*$)/gim, '<li class="ml-4 list-disc text-slate-800 dark:text-slate-200 my-0.5">$1</li>')
            .replace(/^\s*(\d+)\.\s+(.*$)/gim, '<li class="ml-4 list-decimal text-slate-800 dark:text-slate-200 my-0.5"><span class="font-bold text-indigo-600 dark:text-indigo-400">$1.</span> $2</li>')
            .replace(/\n\n/g, '<div class="h-2"></div>')
            .replace(/\n/g, '<br>');
        return html;
    }

    function renderAI() {
        let activeToolId = window.activeAiToolId || 'lesson';
        let targetLanguage = window.aiTargetLang || 'uz';

        appDiv.innerHTML = `
            <div class="space-y-4 animate-fade-in pb-4">
                <!-- Header Banner -->
                <div class="flex items-center justify-between">
                    <div>
                        <div class="flex items-center gap-2">
                            <h2 class="text-lg sm:text-xl font-black text-slate-900 dark:text-white tracking-tight">AI Pedagogik Studiya</h2>
                            <span class="px-2 py-0.5 rounded-full text-[10px] font-extrabold bg-gradient-to-r from-brand-600 to-indigo-600 text-white shadow-sm shadow-brand-500/20">Gemini 2.0</span>
                        </div>
                        <p class="text-xs text-slate-500 dark:text-slate-400 mt-0.5">Dars rejalari, testlar, tarjima va tushuntirishlarni bir zumda tayyorlaydi</p>
                    </div>
                </div>

                <!-- Horizontal Tool Selector Bar (Sleek & Scrollable) -->
                <div class="overflow-x-auto pb-1 -mx-4 px-4 sm:mx-0 sm:px-0 scrollbar-none">
                    <div class="flex gap-2 min-w-max p-1 liquid-glass-pill rounded-2xl">
                        ${AI_STUDIO_TOOLS.map(tool => {
                            const isActive = tool.id === activeToolId;
                            return `
                                <button onclick="selectAiStudioTool('${tool.id}')" class="ai-tool-pill px-3 py-2 rounded-xl text-xs font-bold transition-all flex items-center gap-2 shrink-0 ${isActive ? tool.bgActive + ' shadow-md' : 'text-slate-700 dark:text-slate-300 hover:text-slate-900 dark:hover:text-white hover:bg-white/40 dark:hover:bg-slate-800/40'}">
                                    <i data-lucide="${tool.icon}" class="w-3.5 h-3.5"></i>
                                    <span>${tool.shortTitle}</span>
                                </button>
                            `;
                        }).join('')}
                    </div>
                </div>

                <!-- Dynamic Active Tool Card -->
                <div id="ai-active-card-container" class="liquid-glass-card p-4 sm:p-5 space-y-4">
                    <!-- Injected dynamically by updateAiToolView() -->
                </div>

                <!-- AI Output Result Section -->
                <div id="ai-output-box" class="hidden liquid-glass-card p-4 sm:p-5 space-y-3 border-brand-500/30">
                    <div class="flex items-center justify-between border-b border-slate-200/80 dark:border-slate-800 pb-3">
                        <div class="flex items-center gap-2">
                            <div class="w-7 h-7 rounded-lg bg-brand-500/10 text-brand-600 dark:text-brand-400 flex items-center justify-center font-bold">
                                <i data-lucide="sparkles" class="w-4 h-4"></i>
                            </div>
                            <div>
                                <span id="ai-output-title" class="text-xs font-bold text-slate-900 dark:text-white">Tayyorlangan Natija</span>
                                <span class="block text-[10px] text-emerald-600 font-bold">Muvaffaqiyatli yakunlandi ✓</span>
                            </div>
                        </div>

                        <!-- Action Toolbar -->
                        <div class="flex items-center gap-1.5">
                            <button id="ai-btn-copy" onclick="copyAiOutput()" class="liquid-glass-pill px-2.5 py-1.5 rounded-lg text-xs font-bold text-slate-700 dark:text-slate-200 hover:text-brand-600 transition-all flex items-center gap-1 cursor-pointer" title="Nusxa olish">
                                <i data-lucide="copy" class="w-3.5 h-3.5"></i>
                                <span class="hidden xs:inline text-[11px]">Nusxalash</span>
                            </button>
                            <button id="ai-btn-docx" onclick="exportAiDocx()" class="px-2.5 py-1.5 rounded-lg text-xs font-bold bg-blue-600 hover:bg-blue-700 active:scale-95 text-white transition-all flex items-center gap-1 cursor-pointer shadow-sm shadow-blue-500/25" title="Word (.docx) qilib yuklab olish">
                                <i data-lucide="file-text" class="w-3.5 h-3.5"></i>
                                <span class="text-[11px]">Word</span>
                            </button>
                            <button id="ai-btn-telegram" onclick="sendAiToTelegram()" class="px-2.5 py-1.5 rounded-lg text-xs font-bold bg-sky-500 hover:bg-sky-600 active:scale-95 text-white transition-all flex items-center gap-1 cursor-pointer shadow-sm shadow-sky-500/25" title="Telegram shaxsiy chatiga yuborish">
                                <i data-lucide="send" class="w-3.5 h-3.5"></i>
                                <span class="text-[11px]">Telegram</span>
                            </button>
                        </div>
                    </div>

                    <!-- Rendered HTML Content -->
                    <div id="ai-output-rendered" class="text-xs sm:text-sm text-slate-800 dark:text-slate-200 leading-relaxed font-sans max-h-[600px] overflow-y-auto pr-1"></div>

                    <!-- Reset button -->
                    <div class="flex justify-end pt-2 border-t border-slate-200/60 dark:border-slate-800">
                        <button onclick="clearAiOutput()" class="text-xs text-slate-500 hover:text-rose-500 font-semibold transition-colors flex items-center gap-1 cursor-pointer">
                            <i data-lucide="trash-2" class="w-3 h-3"></i> Natijani tozalash
                        </button>
                    </div>
                </div>
            </div>
        `;
        refreshIcons();

        function updateAiToolView() {
            const container = document.getElementById('ai-active-card-container');
            if (!container) return;
            const current = AI_STUDIO_TOOLS.find(t => t.id === activeToolId) || AI_STUDIO_TOOLS[0];

            let extraOptionsHtml = '';
            if (current.id === 'translate') {
                extraOptionsHtml = `
                    <div class="flex items-center gap-2 pt-1">
                        <span class="text-[11px] font-bold text-slate-500">Qaysi tilga:</span>
                        <div class="flex gap-1.5">
                            <button onclick="setAiTargetLang('uz')" class="px-2.5 py-1 rounded-lg text-[11px] font-bold transition-all ${targetLanguage === 'uz' ? 'bg-brand-600 text-white' : 'liquid-glass-pill text-slate-700 dark:text-slate-300'}">🇺🇿 O'zbekcha</button>
                            <button onclick="setAiTargetLang('ru')" class="px-2.5 py-1 rounded-lg text-[11px] font-bold transition-all ${targetLanguage === 'ru' ? 'bg-brand-600 text-white' : 'liquid-glass-pill text-slate-700 dark:text-slate-300'}">🇷🇺 Ruscha</button>
                            <button onclick="setAiTargetLang('en')" class="px-2.5 py-1 rounded-lg text-[11px] font-bold transition-all ${targetLanguage === 'en' ? 'bg-brand-600 text-white' : 'liquid-glass-pill text-slate-700 dark:text-slate-300'}">🇬🇧 Inglizcha</button>
                        </div>
                    </div>
                `;
            }

            container.innerHTML = `
                <!-- Tool Header Details -->
                <div class="flex items-start justify-between gap-3">
                    <div class="flex items-center gap-2.5">
                        <div class="w-9 h-9 rounded-xl bg-gradient-to-tr ${current.color} text-white flex items-center justify-center shadow-md shrink-0">
                            <i data-lucide="${current.icon}" class="w-4 h-4"></i>
                        </div>
                        <div>
                            <h3 class="text-sm font-bold text-slate-900 dark:text-white">${current.title}</h3>
                            <p class="text-xs text-slate-500 dark:text-slate-400 mt-0.5">${current.desc}</p>
                        </div>
                    </div>
                    <span class="px-2 py-0.5 rounded-md text-[10px] font-mono font-bold border ${current.pillColor} shrink-0">${current.badge}</span>
                </div>

                ${extraOptionsHtml}

                <!-- Quick Prompt Chips (One-click instant fill) -->
                <div>
                    <div class="text-[11px] font-bold text-slate-500 dark:text-slate-400 mb-1.5 flex items-center gap-1">
                        <i data-lucide="zap" class="w-3 h-3 text-amber-500"></i>
                        <span>Tezkor namunalar (1 marta bosing):</span>
                    </div>
                    <div class="flex flex-wrap gap-1.5">
                        ${current.chips.map(chip => `
                            <button onclick="fillAiChip('${chip.replace(/'/g, "\\'")}')" class="px-2.5 py-1 rounded-lg text-[11px] font-medium bg-slate-100 hover:bg-slate-200 dark:bg-slate-800 dark:hover:bg-slate-700 text-slate-700 dark:text-slate-300 hover:text-brand-600 dark:hover:text-brand-400 transition-all border border-slate-200/80 dark:border-slate-700 flex items-center gap-1 text-left">
                                <span class="text-amber-500 font-bold">⚡</span> ${chip}
                            </button>
                        `).join('')}
                    </div>
                </div>

                <!-- Input Field -->
                <div class="space-y-1.5">
                    <div class="flex items-center justify-between">
                        <label class="text-xs font-bold text-slate-800 dark:text-slate-200">${current.label}</label>
                        <button onclick="document.getElementById('ai-studio-textarea').value=''; document.getElementById('ai-studio-textarea').focus();" class="text-[11px] text-slate-400 hover:text-rose-500 transition-colors">
                            Tozalash ✕
                        </button>
                    </div>
                    <textarea id="ai-studio-textarea" rows="4" class="w-full rounded-2xl border border-slate-200 dark:border-slate-700/80 bg-white/70 dark:bg-slate-900/80 backdrop-blur-sm p-3 text-xs sm:text-sm text-slate-900 dark:text-white placeholder:text-slate-400 focus:outline-none focus:border-brand-500 focus:ring-2 focus:ring-brand-500/20 shadow-inner transition-all resize-none" placeholder="${current.placeholder}"></textarea>
                </div>

                <!-- Action Button -->
                <button id="ai-generate-btn" onclick="executeAiStudio()" class="w-full py-3 rounded-2xl bg-gradient-to-r from-brand-600 via-indigo-600 to-purple-600 hover:from-brand-700 hover:to-purple-700 active:scale-[0.99] text-white text-xs sm:text-sm font-bold shadow-lg shadow-brand-500/25 transition-all flex items-center justify-center gap-2 cursor-pointer">
                    <i data-lucide="sparkles" class="w-4 h-4"></i>
                    <span>Generatsiya qilish</span>
                </button>
            `;
            refreshIcons(container);
        }

        window.selectAiStudioTool = (toolId) => {
            TelegramApp.hapticFeedback();
            activeToolId = toolId;
            window.activeAiToolId = toolId;
            document.querySelectorAll('.ai-tool-pill').forEach(b => {
                b.className = 'ai-tool-pill px-3 py-2 rounded-xl text-xs font-bold transition-all flex items-center gap-2 shrink-0 text-slate-700 dark:text-slate-300 hover:text-slate-900 dark:hover:text-white hover:bg-white/40 dark:hover:bg-slate-800/40';
            });
            event.currentTarget.className = `ai-tool-pill px-3 py-2 rounded-xl text-xs font-bold transition-all flex items-center gap-2 shrink-0 ${AI_STUDIO_TOOLS.find(t=>t.id===toolId)?.bgActive || 'bg-brand-600 text-white'} shadow-md`;
            updateAiToolView();
        };

        window.setAiTargetLang = (lang) => {
            TelegramApp.hapticFeedback();
            targetLanguage = lang;
            window.aiTargetLang = lang;
            updateAiToolView();
        };

        window.fillAiChip = (text) => {
            TelegramApp.hapticFeedback('light');
            const txt = document.getElementById('ai-studio-textarea');
            if (txt) {
                txt.value = text;
                txt.focus();
            }
        };

        let lastAiTitle = '';
        let lastAiRawResult = '';

        window.executeAiStudio = async () => {
            const inputEl = document.getElementById('ai-studio-textarea');
            const textVal = inputEl ? inputEl.value.trim() : '';
            if (!textVal) {
                TelegramApp.showAlert("Iltimos, mavzu yoki matnni kiriting!");
                if (inputEl) inputEl.focus();
                return;
            }

            const btn = document.getElementById('ai-generate-btn');
            const box = document.getElementById('ai-output-box');
            const outRendered = document.getElementById('ai-output-rendered');
            const outTitle = document.getElementById('ai-output-title');
            const current = AI_STUDIO_TOOLS.find(t => t.id === activeToolId) || AI_STUDIO_TOOLS[0];

            btn.disabled = true;
            btn.innerHTML = `<i data-lucide="loader-2" class="w-4 h-4 animate-spin"></i> <span>AI fikrlamoqda va yozmoqda...</span>`;
            refreshIcons(btn);

            box.classList.remove('hidden');
            outRendered.innerHTML = `
                <div class="py-8 flex flex-col items-center justify-center text-center space-y-3 text-slate-500">
                    <div class="w-12 h-12 rounded-2xl bg-brand-500/10 text-brand-600 flex items-center justify-center animate-pulse">
                        <i data-lucide="bot" class="w-6 h-6"></i>
                    </div>
                    <p class="text-xs font-semibold">Google Gemini 2.0 Flash dars ishlanmasini tayyorlamoqda...</p>
                </div>
            `;
            refreshIcons(outRendered);
            box.scrollIntoView({ behavior: 'smooth', block: 'nearest' });

            try {
                let res;
                if (activeToolId === 'lesson') {
                    res = await api.lessonPlan(textVal);
                } else if (activeToolId === 'quiz') {
                    res = await api.createQuizAI(textVal);
                } else if (activeToolId === 'summarize') {
                    res = await api.summarizeText(textVal);
                } else if (activeToolId === 'explain') {
                    res = await api.explainTopic(textVal);
                } else if (activeToolId === 'grammar') {
                    res = await api.checkGrammar(textVal);
                } else if (activeToolId === 'translate') {
                    res = await api.translateText(textVal, targetLanguage);
                } else if (activeToolId === 'improve') {
                    res = await api.improveText(textVal);
                }

                lastAiTitle = `${current.title}: ${textVal.substring(0, 30)}`;
                lastAiRawResult = res.result || '';

                if (outTitle) outTitle.innerText = lastAiTitle;
                outRendered.innerHTML = renderMarkdownToHtml(lastAiRawResult);
                TelegramApp.hapticFeedback('medium');
            } catch (err) {
                outRendered.innerHTML = `
                    <div class="p-3 rounded-xl bg-rose-50 dark:bg-rose-950/40 border border-rose-200 dark:border-rose-900 text-rose-600 dark:text-rose-400 text-xs">
                        <strong>Xatolik:</strong> ${err.message}
                    </div>
                `;
            } finally {
                btn.disabled = false;
                btn.innerHTML = `<i data-lucide="sparkles" class="w-4 h-4"></i> <span>Qayta generatsiya qilish</span>`;
                refreshIcons(btn);
            }
        };

        window.copyAiOutput = () => {
            if (!lastAiRawResult) return;
            navigator.clipboard.writeText(lastAiRawResult).then(() => {
                TelegramApp.hapticFeedback('light');
                TelegramApp.showAlert("Natija buferga nusxalandi!");
            }).catch(() => {
                TelegramApp.showAlert("Nusxa olindi!");
            });
        };

        window.exportAiDocx = async () => {
            if (!lastAiRawResult) return;
            const btn = document.getElementById('ai-btn-docx');
            const originalText = btn ? btn.innerHTML : '';
            if (btn) {
                btn.disabled = true;
                btn.innerHTML = `<i data-lucide="loader-2" class="w-3.5 h-3.5 animate-spin"></i> <span>Kutilmoqda...</span>`;
                refreshIcons(btn);
            }

            try {
                const res = await api.exportAIDocx(lastAiTitle || "Dars_Rejasi", lastAiRawResult);
                if (res && res.download_url) {
                    TelegramApp.hapticFeedback('medium');
                    // Trigger native browser download
                    const link = document.createElement('a');
                    link.href = res.download_url;
                    link.download = res.file_name;
                    document.body.appendChild(link);
                    link.click();
                    document.body.removeChild(link);
                    TelegramApp.showAlert("Word (.docx) hujjati tayyorlandi va yuklab olindi!");
                }
            } catch (err) {
                TelegramApp.showAlert(`Word eksport xatosi: ${err.message}`);
            } finally {
                if (btn) {
                    btn.disabled = false;
                    btn.innerHTML = originalText;
                    refreshIcons(btn);
                }
            }
        };

        window.sendAiToTelegram = async () => {
            if (!lastAiRawResult) return;
            const btn = document.getElementById('ai-btn-telegram');
            const originalText = btn ? btn.innerHTML : '';
            if (btn) {
                btn.disabled = true;
                btn.innerHTML = `<i data-lucide="loader-2" class="w-3.5 h-3.5 animate-spin"></i> <span>Yuborilmoqda...</span>`;
                refreshIcons(btn);
            }

            try {
                const res = await api.sendAIToTelegram(lastAiTitle || "AI Natijasi", lastAiRawResult, "file");
                TelegramApp.hapticFeedback('medium');
                TelegramApp.showAlert(res.message || "Hujjat Telegramingizga yuborildi!");
            } catch (err) {
                TelegramApp.showAlert(`Telegramga yuborishda xatolik: ${err.message}`);
            } finally {
                if (btn) {
                    btn.disabled = false;
                    btn.innerHTML = originalText;
                    refreshIcons(btn);
                }
            }
        };

        window.clearAiOutput = () => {
            TelegramApp.hapticFeedback('light');
            lastAiRawResult = '';
            lastAiTitle = '';
            const box = document.getElementById('ai-output-box');
            if (box) box.classList.add('hidden');
        };

        updateAiToolView();
    }

    // ─────────────────────────────────────────────────────────────
    // 3. SETTINGS & PROFILE VIEW
    // ─────────────────────────────────────────────────────────────
    function renderSettings() {
        const adminSection = isCurrentUserAdmin ? `
            <div class="liquid-glass-card p-4 space-y-3">
                <div class="flex items-center gap-2 text-slate-900 font-bold text-xs">
                    <i data-lucide="shield-check" class="w-4 h-4 text-emerald-600"></i>
                    <span>Tizim Zaxira Bazasi (Administrator paneli)</span>
                </div>
                <p class="text-xs text-slate-500 leading-relaxed">
                    Ma'lumotlar bazasi xavfsiz avtomatik sinxronizatsiya qilingan.
                </p>
                <div class="p-2.5 rounded-xl bg-white/50 border border-white/80 flex items-center justify-between text-xs">
                    <span class="text-slate-600 font-medium">Holati:</span>
                    <span class="font-mono text-emerald-600 font-bold">Faol va himoyalangan ✓</span>
                </div>
            </div>
        ` : '';

        appDiv.innerHTML = `
            <div class="space-y-4 animate-fade-in">
                <div>
                    <h2 class="text-lg font-bold text-slate-900 tracking-tight">Foydalanuvchi Profili</h2>
                    <p class="text-xs text-slate-500">Shaxsiy ma'lumotlar va ilova parametrlari</p>
                </div>

                <div class="liquid-glass-card p-4 flex items-center gap-3.5">
                    <div class="w-13 h-13 sm:w-14 sm:h-14 rounded-2xl bg-gradient-to-tr from-brand-600 via-indigo-600 to-purple-600 text-white flex items-center justify-center font-extrabold text-lg shadow-md shadow-brand-500/25 ring-1 ring-white/60">
                        ${(tgUser.first_name || 'O').charAt(0)}
                    </div>
                    <div class="flex-1 min-w-0">
                        <div class="flex items-center gap-2">
                            <h3 class="text-sm sm:text-base font-bold text-slate-900 truncate">${tgUser.first_name || "O'qituvchi"} ${tgUser.last_name || ""}</h3>
                            <span class="liquid-glass-pill px-2 py-0.5 rounded-md text-[10px] font-bold text-brand-600">${isCurrentUserAdmin ? 'Admin' : "Foydalanuvchi"}</span>
                        </div>
                        <p class="text-xs text-slate-500 font-medium mt-0.5">${tgUser.username ? '@' + tgUser.username : 'EduBot foydalanuvchisi'}</p>
                    </div>
                </div>

                <div class="liquid-glass-card p-4 space-y-3">
                    <div class="flex items-center gap-2 text-slate-900 font-bold text-xs">
                        <i data-lucide="check-check" class="w-4 h-4 text-brand-600"></i>
                        <span>Ulangan Asboblar (7 ta)</span>
                    </div>
                    <div class="grid grid-cols-2 gap-2 text-xs">
                        <div class="p-2.5 rounded-xl bg-white/40 border border-white/70">
                            <span class="text-slate-500 text-[10px] block">1. PDF ➔ DOCX</span>
                            <span class="font-bold text-slate-800">Tayyor</span>
                        </div>
                        <div class="p-2.5 rounded-xl bg-white/40 border border-white/70">
                            <span class="text-slate-500 text-[10px] block">2. DOCX ➔ PDF</span>
                            <span class="font-bold text-slate-800">Tayyor (Word COM)</span>
                        </div>
                        <div class="p-2.5 rounded-xl bg-white/40 border border-white/70">
                            <span class="text-slate-500 text-[10px] block">3. DOCX tahrirlash</span>
                            <span class="font-bold text-slate-800">Tayyor</span>
                        </div>
                        <div class="p-2.5 rounded-xl bg-white/40 border border-white/70">
                            <span class="text-slate-500 text-[10px] block">4. PDF tahrirlash</span>
                            <span class="font-bold text-slate-800">Tayyor</span>
                        </div>
                        <div class="p-2.5 rounded-xl bg-white/40 border border-white/70">
                            <span class="text-slate-500 text-[10px] block">5. Rasmlar ➔ PDF</span>
                            <span class="font-bold text-slate-800">Tayyor (A4)</span>
                        </div>
                        <div class="p-2.5 rounded-xl bg-white/40 border border-white/70">
                            <span class="text-slate-500 text-[10px] block">6. Rasmlarni ajratish</span>
                            <span class="font-bold text-slate-800">Tayyor (ZIP)</span>
                        </div>
                        <div class="col-span-2 p-2.5 rounded-xl bg-white/40 border border-white/70">
                            <span class="text-slate-500 text-[10px] block">7. AI Yordamchi</span>
                            <span class="font-bold text-slate-800">Gemini 2.0 Flash</span>
                        </div>
                    </div>
                </div>

                ${adminSection}

                <div class="liquid-glass-card p-4">
                    <div class="flex items-center justify-between text-xs">
                        <span class="text-slate-600 font-medium">Ilova talqini:</span>
                        <span class="font-mono text-brand-600 font-bold liquid-glass-pill px-2.5 py-1 rounded-lg">v2.3 Pro</span>
                    </div>
                </div>
            </div>
        `;
        refreshIcons();
    }

    // ─────────────────────────────────────────────────────────────
    // ROUTER
    // ─────────────────────────────────────────────────────────────
    function router() {
        const hash = window.location.hash || '#/';
        TelegramApp.hapticFeedback();
        updateNav(hash);

        switch (hash) {
            case '#/ai': renderAI(); break;
            case '#/settings': renderSettings(); break;
            default: renderDashboard(); break;
        }
    }

    window.addEventListener('hashchange', router);
    router();
});
