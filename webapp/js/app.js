/**
 * EduBot Modern SaaS Frontend Architecture (Linear / Vercel style)
 * Fully interactive with dynamic Lucide icons and Tailwind components.
 */

document.addEventListener('DOMContentLoaded', () => {
    const appDiv = document.getElementById('app');

    // Update user display in top header
    const tgUser = TelegramApp.getUserData() || { first_name: "O'qituvchi", id: "000000" };
    const headerUserName = document.getElementById('header-user-name');
    if (headerUserName && tgUser.first_name) {
        headerUserName.innerText = tgUser.first_name;
    }

    // Refresh Lucide icons helper
    function refreshIcons() {
        if (window.lucide) {
            window.lucide.createIcons();
        }
    }

    // Update navigation active state
    function updateNav(hash) {
        document.querySelectorAll('.nav-item').forEach(item => {
            const route = item.getAttribute('data-route');
            if (route === hash || (hash === '' && route === '#/')) {
                item.className = 'nav-item active flex flex-col sm:flex-row items-center gap-1 px-3.5 py-1.5 rounded-full bg-brand-600 text-white shadow-sm shadow-brand-500/20 font-semibold transition-all duration-200';
            } else {
                item.className = 'nav-item flex flex-col sm:flex-row items-center gap-1 px-3.5 py-1.5 rounded-full text-slate-500 transition-all duration-200 hover:text-slate-900';
            }
        });
        refreshIcons();
    }

    // ─────────────────────────────────────────────────────────────
    // 1. DASHBOARD VIEW (Modern Linear/Stripe style)
    // ─────────────────────────────────────────────────────────────
    async function renderDashboard() {
        appDiv.innerHTML = `
            <div class="space-y-5 animate-fade-in">
                <!-- Welcome Banner -->
                <div class="bg-gradient-to-br from-brand-600 to-indigo-700 rounded-2xl p-5 text-white shadow-sm relative overflow-hidden">
                    <div class="absolute -right-6 -bottom-6 w-32 h-32 bg-white/10 rounded-full blur-xl pointer-events-none"></div>
                    <div class="relative z-10">
                        <span class="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full bg-white/20 backdrop-blur-sm text-xs font-medium text-white mb-2">
                            <i data-lucide="sparkles" class="w-3.5 h-3.5"></i> EduBot Workspace
                        </span>
                        <h2 class="text-xl font-bold tracking-tight">Xush kelibsiz, ${tgUser.first_name}!</h2>
                        <p class="text-xs text-indigo-100 mt-1 max-w-sm">Hujjatlar tahlili, AI yordamchi va tezkor testlar tayyorlash markazi.</p>
                    </div>
                </div>

                <!-- KPI Metric Cards (Tabular Numbers) -->
                <div class="grid grid-cols-2 gap-3">
                    <div class="bg-white border border-slate-200/80 rounded-xl p-4 shadow-sm">
                        <div class="flex items-center justify-between">
                            <span class="text-xs font-medium text-slate-500">Hujjatlar</span>
                            <div class="w-8 h-8 rounded-lg bg-blue-50 text-blue-600 flex items-center justify-center">
                                <i data-lucide="file-text" class="w-4 h-4"></i>
                            </div>
                        </div>
                        <div class="mt-2 flex items-baseline gap-2">
                            <span id="stat-files" class="text-2xl font-bold text-slate-900 font-mono tracking-tight">-</span>
                            <span class="text-[11px] text-slate-400 font-medium">fayl</span>
                        </div>
                    </div>

                    <div class="bg-white border border-slate-200/80 rounded-xl p-4 shadow-sm">
                        <div class="flex items-center justify-between">
                            <span class="text-xs font-medium text-slate-500">Tuzilgan testlar</span>
                            <div class="w-8 h-8 rounded-lg bg-emerald-50 text-emerald-600 flex items-center justify-center">
                                <i data-lucide="check-circle-2" class="w-4 h-4"></i>
                            </div>
                        </div>
                        <div class="mt-2 flex items-baseline gap-2">
                            <span id="stat-quizzes" class="text-2xl font-bold text-slate-900 font-mono tracking-tight">-</span>
                            <span class="text-[11px] text-slate-400 font-medium">to'plam</span>
                        </div>
                    </div>
                </div>

                <!-- Quick Action Tools Grid -->
                <div>
                    <div class="flex items-center justify-between mb-2.5 px-0.5">
                        <h3 class="text-xs font-semibold text-slate-500 uppercase tracking-wider">Tezkor amallar</h3>
                        <span class="text-[11px] text-brand-600 font-medium">Barchasi</span>
                    </div>

                    <div class="grid grid-cols-2 gap-2.5">
                        <div onclick="window.location.hash='#/files'" class="group bg-white border border-slate-200/80 hover:border-brand-500/60 rounded-xl p-3.5 shadow-sm transition-all duration-200 cursor-pointer hover:-translate-y-0.5">
                            <div class="w-9 h-9 rounded-lg bg-slate-100 group-hover:bg-brand-50 text-slate-600 group-hover:text-brand-600 flex items-center justify-center transition-colors mb-2.5">
                                <i data-lucide="file-up" class="w-5 h-5"></i>
                            </div>
                            <h4 class="text-sm font-semibold text-slate-900">Fayl tahlili</h4>
                            <p class="text-xs text-slate-500 mt-0.5">PDF, Word, Excel konvert</p>
                        </div>

                        <div onclick="window.location.hash='#/ai'" class="group bg-white border border-slate-200/80 hover:border-brand-500/60 rounded-xl p-3.5 shadow-sm transition-all duration-200 cursor-pointer hover:-translate-y-0.5">
                            <div class="w-9 h-9 rounded-lg bg-slate-100 group-hover:bg-brand-50 text-slate-600 group-hover:text-brand-600 flex items-center justify-center transition-colors mb-2.5">
                                <i data-lucide="sparkles" class="w-5 h-5"></i>
                            </div>
                            <h4 class="text-sm font-semibold text-slate-900">AI Yordamchi</h4>
                            <p class="text-xs text-slate-500 mt-0.5">Dars rejasi, xulosalash</p>
                        </div>

                        <div onclick="window.location.hash='#/quiz'" class="group bg-white border border-slate-200/80 hover:border-brand-500/60 rounded-xl p-3.5 shadow-sm transition-all duration-200 cursor-pointer hover:-translate-y-0.5">
                            <div class="w-9 h-9 rounded-lg bg-slate-100 group-hover:bg-brand-50 text-slate-600 group-hover:text-brand-600 flex items-center justify-center transition-colors mb-2.5">
                                <i data-lucide="layers" class="w-5 h-5"></i>
                            </div>
                            <h4 class="text-sm font-semibold text-slate-900">Test yaratish</h4>
                            <p class="text-xs text-slate-500 mt-0.5">A/B/C/D yoki ochiq test</p>
                        </div>

                        <div onclick="window.location.hash='#/settings'" class="group bg-white border border-slate-200/80 hover:border-brand-500/60 rounded-xl p-3.5 shadow-sm transition-all duration-200 cursor-pointer hover:-translate-y-0.5">
                            <div class="w-9 h-9 rounded-lg bg-slate-100 group-hover:bg-brand-50 text-slate-600 group-hover:text-brand-600 flex items-center justify-center transition-colors mb-2.5">
                                <i data-lucide="database" class="w-5 h-5"></i>
                            </div>
                            <h4 class="text-sm font-semibold text-slate-900">Baza holati</h4>
                            <p class="text-xs text-slate-500 mt-0.5">Kanal sinxronizatsiyasi</p>
                        </div>
                    </div>
                </div>
            </div>
        `;
        refreshIcons();

        // Load stats
        try {
            const files = await api.getFiles();
            document.getElementById('stat-files').innerText = files.length;
            const quizzes = await api.getQuizzes();
            document.getElementById('stat-quizzes').innerText = quizzes.length;
        } catch (e) {
            document.getElementById('stat-files').innerText = '0';
            document.getElementById('stat-quizzes').innerText = '0';
        }
    }

    // ─────────────────────────────────────────────────────────────
    // 2. FILES VIEW (Upload, conversion, modern file list)
    // ─────────────────────────────────────────────────────────────
    async function renderFiles() {
        appDiv.innerHTML = `
            <div class="space-y-4 animate-fade-in">
                <!-- Header -->
                <div>
                    <h2 class="text-lg font-bold text-slate-900 tracking-tight">Hujjatlar boshqaruvi</h2>
                    <p class="text-xs text-slate-500">PDF, Word, Excel va PowerPoint fayllari</p>
                </div>

                <!-- Dropzone / Upload Box -->
                <div class="bg-white border-2 border-dashed border-slate-200 rounded-2xl p-6 text-center hover:border-brand-500 transition-colors duration-200">
                    <div class="w-11 h-11 mx-auto rounded-xl bg-brand-50 text-brand-600 flex items-center justify-center mb-3">
                        <i data-lucide="upload-cloud" class="w-6 h-6"></i>
                    </div>
                    <h4 class="text-sm font-semibold text-slate-900">Yangi hujjat yuklang</h4>
                    <p class="text-xs text-slate-500 mt-1 max-w-xs mx-auto">PDF, DOCX, XLSX, PPTX (maksimal 20 MB)</p>
                    
                    <input type="file" id="file-input" class="hidden" accept=".pdf,.docx,.doc,.xlsx,.xls,.pptx,.ppt,.csv">
                    <button onclick="document.getElementById('file-input').click()" class="mt-4 px-4 py-2 rounded-xl bg-brand-600 hover:bg-brand-700 text-white text-xs font-semibold shadow-sm transition-all inline-flex items-center gap-2">
                        <i data-lucide="plus" class="w-3.5 h-3.5"></i> Fayl tanlash
                    </button>
                    <p id="file-selected-name" class="text-xs text-slate-600 mt-2 font-medium hidden"></p>
                    <button id="upload-action-btn" class="mt-2 w-full max-w-xs mx-auto py-2 rounded-xl bg-slate-900 text-white text-xs font-semibold hidden">Yuklashni tasdiqlash</button>
                </div>

                <!-- File List -->
                <div class="bg-white border border-slate-200/80 rounded-2xl shadow-sm overflow-hidden">
                    <div class="px-4 py-3 border-b border-slate-100 flex items-center justify-between">
                        <h3 class="text-xs font-semibold text-slate-700 uppercase tracking-wider">Yuklangan fayllar</h3>
                        <span id="files-badge" class="text-[11px] font-mono bg-slate-100 text-slate-600 px-2 py-0.5 rounded-full">0 ta</span>
                    </div>

                    <div id="file-list-container" class="divide-y divide-slate-100">
                        <div class="p-6 text-center text-xs text-slate-400">Yuklanmoqda...</div>
                    </div>
                </div>
            </div>
        `;
        refreshIcons();

        const fileInput = document.getElementById('file-input');
        const fileNameDisplay = document.getElementById('file-selected-name');
        const uploadActionBtn = document.getElementById('upload-action-btn');

        fileInput.onchange = () => {
            if (fileInput.files.length > 0) {
                fileNameDisplay.innerText = fileInput.files[0].name;
                fileNameDisplay.classList.remove('hidden');
                uploadActionBtn.classList.remove('hidden');
            }
        };

        uploadActionBtn.onclick = async () => {
            if (!fileInput.files.length) return;
            const fd = new FormData();
            fd.append('file', fileInput.files[0]);

            uploadActionBtn.innerText = "Yuklanmoqda...";
            uploadActionBtn.disabled = true;

            try {
                await api.uploadFile(fd);
                TelegramApp.hapticFeedback('medium');
                TelegramApp.showAlert("Fayl muvaffaqiyatli saqlandi!");
                renderFiles();
            } catch (err) {
                TelegramApp.showAlert(`Xatolik: ${err.message}`);
                uploadActionBtn.innerText = "Yuklashni tasdiqlash";
                uploadActionBtn.disabled = false;
            }
        };

        // Load files list
        try {
            const files = await api.getFiles();
            document.getElementById('files-badge').innerText = `${files.length} ta`;
            const container = document.getElementById('file-list-container');

            if (files.length === 0) {
                container.innerHTML = `
                    <div class="py-10 text-center text-slate-400">
                        <i data-lucide="folder-open" class="w-8 h-8 mx-auto stroke-1 text-slate-300 mb-2"></i>
                        <p class="text-xs">Hozircha hech qanday fayl yuklanmagan</p>
                    </div>
                `;
                refreshIcons();
                return;
            }

            container.innerHTML = files.map(f => {
                const isPdf = f.file_type.toLowerCase() === 'pdf';
                const sizeMb = (f.file_size / (1024 * 1024)).toFixed(2);
                return `
                    <div class="p-3.5 flex items-center justify-between hover:bg-slate-50 transition-colors">
                        <div class="flex items-center gap-3 min-w-0 pr-2">
                            <div class="w-9 h-9 shrink-0 rounded-xl bg-slate-100 flex items-center justify-center text-slate-600">
                                <i data-lucide="${isPdf ? 'file-text' : 'file'}" class="w-4 h-4"></i>
                            </div>
                            <div class="truncate">
                                <h4 class="text-xs font-semibold text-slate-900 truncate">${f.file_name}</h4>
                                <p class="text-[11px] text-slate-500 font-mono mt-0.5">${sizeMb} MB • ${f.file_type.toUpperCase()}</p>
                            </div>
                        </div>

                        <div class="flex items-center gap-1.5 shrink-0">
                            ${!isPdf ? `
                                <button onclick="convertFileAction(${f.id}, 'pdf')" class="px-2.5 py-1 rounded-lg border border-slate-200 text-[11px] font-semibold text-slate-700 hover:bg-slate-100 transition-colors inline-flex items-center gap-1">
                                    <i data-lucide="refresh-cw" class="w-3 h-3"></i> PDF
                                </button>
                            ` : `
                                <button onclick="convertFileAction(${f.id}, 'docx')" class="px-2.5 py-1 rounded-lg border border-slate-200 text-[11px] font-semibold text-slate-700 hover:bg-slate-100 transition-colors inline-flex items-center gap-1">
                                    <i data-lucide="refresh-cw" class="w-3 h-3"></i> Word
                                </button>
                            `}
                            <button onclick="deleteFileAction(${f.id})" class="p-1.5 rounded-lg text-slate-400 hover:text-red-600 hover:bg-red-50 transition-colors">
                                <i data-lucide="trash-2" class="w-4 h-4"></i>
                            </button>
                        </div>
                    </div>
                `;
            }).join('');
            refreshIcons();
        } catch (err) {
            document.getElementById('file-list-container').innerHTML = `<div class="p-4 text-center text-xs text-red-500">${err.message}</div>`;
        }
    }

    window.convertFileAction = async (id, format) => {
        TelegramApp.hapticFeedback();
        try {
            TelegramApp.showAlert(`Konvertatsiya qilinmoqda (${format.toUpperCase()})...`);
            await api.convertFile(id, format);
            TelegramApp.showAlert("Fayl muvaffaqiyatli aylantirildi!");
            renderFiles();
        } catch (e) {
            TelegramApp.showAlert(`Xato: ${e.message}`);
        }
    };

    window.deleteFileAction = async (id) => {
        TelegramApp.showConfirm("Ushbu faylni o'chirishga ishonchingiz komilmi?", async (confirmed) => {
            if (confirmed) {
                try {
                    await api.deleteFile(id);
                    TelegramApp.showAlert("Fayl o'chirildi.");
                    renderFiles();
                } catch (e) {
                    TelegramApp.showAlert(`Xato: ${e.message}`);
                }
            }
        });
    };

    // ─────────────────────────────────────────────────────────────
    // 3. AI ASSISTANT VIEW (Segmented tabs, high-contrast prompt)
    // ─────────────────────────────────────────────────────────────
    function renderAI() {
        appDiv.innerHTML = `
            <div class="space-y-4 animate-fade-in">
                <!-- Header -->
                <div>
                    <h2 class="text-lg font-bold text-slate-900 tracking-tight">AI Pedagogik Yordamchi</h2>
                    <p class="text-xs text-slate-500">Google Gemini 2.0 Flash texnologiyasi asosida</p>
                </div>

                <!-- Modern Segmented Pill Bar -->
                <div class="grid grid-cols-4 gap-1.5 bg-slate-200/70 p-1 rounded-xl">
                    <button id="ai-tab-summarize" onclick="switchAITool('summarize')" class="ai-tool-tab py-1.5 px-2 rounded-lg text-xs font-semibold text-slate-900 bg-white shadow-sm transition-all">
                        Xulosa
                    </button>
                    <button id="ai-tab-lesson" onclick="switchAITool('lesson')" class="ai-tool-tab py-1.5 px-2 rounded-lg text-xs font-medium text-slate-600 hover:text-slate-900 transition-all">
                        Dars rejasi
                    </button>
                    <button id="ai-tab-translate" onclick="switchAITool('translate')" class="ai-tool-tab py-1.5 px-2 rounded-lg text-xs font-medium text-slate-600 hover:text-slate-900 transition-all">
                        Tarjima
                    </button>
                    <button id="ai-tab-explain" onclick="switchAITool('explain')" class="ai-tool-tab py-1.5 px-2 rounded-lg text-xs font-medium text-slate-600 hover:text-slate-900 transition-all">
                        Tushuntirish
                    </button>
                </div>

                <!-- Input Card -->
                <div class="bg-white border border-slate-200/80 rounded-2xl p-4 shadow-sm space-y-3">
                    <div class="flex items-center justify-between">
                        <label id="ai-tool-label" class="text-xs font-semibold text-slate-700">Matnni kiriting:</label>
                        <span class="text-[11px] text-slate-400 font-mono">Gemini AI</span>
                    </div>

                    <textarea id="ai-textarea" rows="5" class="w-full rounded-xl border border-slate-200 bg-slate-50/50 p-3 text-xs text-slate-900 placeholder:text-slate-400 focus:outline-none focus:border-brand-600 focus:bg-white transition-all resize-none" placeholder="Matnni shu yerga yozing yoki kiriting..."></textarea>

                    <button id="ai-run-btn" class="w-full py-2.5 rounded-xl bg-brand-600 hover:bg-brand-700 text-white text-xs font-semibold shadow-sm transition-all inline-flex items-center justify-center gap-2">
                        <i data-lucide="sparkles" class="w-3.5 h-3.5"></i> Tahlil qilish
                    </button>
                </div>

                <!-- Result Box -->
                <div id="ai-output-box" class="hidden bg-white border border-slate-200/80 rounded-2xl p-4 shadow-sm space-y-2">
                    <div class="flex items-center justify-between border-b border-slate-100 pb-2">
                        <span class="text-xs font-semibold text-slate-700 inline-flex items-center gap-1.5">
                            <i data-lucide="bot" class="w-3.5 h-3.5 text-brand-600"></i> AI Natijasi
                        </span>
                        <button onclick="navigator.clipboard.writeText(document.getElementById('ai-output-text').innerText); TelegramApp.showAlert('Nusxa olindi!')" class="text-[11px] text-brand-600 font-medium inline-flex items-center gap-1">
                            <i data-lucide="copy" class="w-3 h-3"></i> Nusxalash
                        </button>
                    </div>
                    <div id="ai-output-text" class="text-xs text-slate-700 leading-relaxed whitespace-pre-wrap"></div>
                </div>
            </div>
        `;
        refreshIcons();

        window.currentTool = 'summarize';

        window.switchAITool = (tool) => {
            TelegramApp.hapticFeedback();
            window.currentTool = tool;
            document.querySelectorAll('.ai-tool-tab').forEach(b => {
                b.className = 'ai-tool-tab py-1.5 px-2 rounded-lg text-xs font-medium text-slate-600 hover:text-slate-900 transition-all';
            });
            document.getElementById(`ai-tab-${tool}`).className = 'ai-tool-tab py-1.5 px-2 rounded-lg text-xs font-semibold text-slate-900 bg-white shadow-sm transition-all';

            const lbl = document.getElementById('ai-tool-label');
            const txt = document.getElementById('ai-textarea');
            if (tool === 'summarize') {
                lbl.innerText = "Xulosa qilinadigan matn:";
                txt.placeholder = "Katta matn yoki maqolani kiriting...";
            } else if (tool === 'lesson') {
                lbl.innerText = "Fan va Mavzu:";
                txt.placeholder = "Masalan: Kimyo — Davriy qonun va elementlar sistemasi";
            } else if (tool === 'translate') {
                lbl.innerText = "Tarjima qilinadigan matn:";
                txt.placeholder = "O'zbek, ingliz yoki rus tilidagi matn...";
            } else if (tool === 'explain') {
                lbl.innerText = "Murakkab tushuncha yoki savol:";
                txt.placeholder = "Masalan: Neyron tarmoqlari qanday ishlaydi?";
            }
        };

        document.getElementById('ai-run-btn').onclick = async () => {
            const inputVal = document.getElementById('ai-textarea').value.trim();
            if (!inputVal) {
                TelegramApp.showAlert("Iltimos, matn kiriting!");
                return;
            }

            const btn = document.getElementById('ai-run-btn');
            const box = document.getElementById('ai-output-box');
            const out = document.getElementById('ai-output-text');

            btn.innerText = "AI tahlil qilmoqda...";
            btn.disabled = true;
            box.classList.remove('hidden');
            out.innerText = "⏳ Javob shakllantirilmoqda...";

            try {
                let res;
                if (window.currentTool === 'summarize') res = await api.summarizeText(inputVal);
                else if (window.currentTool === 'lesson') res = await api.lessonPlan(inputVal);
                else if (window.currentTool === 'translate') res = await api.translateText(inputVal);
                else if (window.currentTool === 'explain') res = await api.explainTopic(inputVal);

                out.innerText = res.result;
                TelegramApp.hapticFeedback('medium');
            } catch (e) {
                out.innerText = `Xatolik: ${e.message}`;
            } finally {
                btn.innerHTML = `<i data-lucide="sparkles" class="w-3.5 h-3.5"></i> Tahlil qilish`;
                btn.disabled = false;
                refreshIcons();
            }
        };
    }

    // ─────────────────────────────────────────────────────────────
    // 4. QUIZ VIEW (Generator & Download Cards)
    // ─────────────────────────────────────────────────────────────
    async function renderQuiz() {
        appDiv.innerHTML = `
            <div class="space-y-4 animate-fade-in">
                <!-- Header -->
                <div>
                    <h2 class="text-lg font-bold text-slate-900 tracking-tight">Test savollari generatori</h2>
                    <p class="text-xs text-slate-500">Mavzu asosida A/B/C/D variantli testlar va Word/PDF eksport</p>
                </div>

                <!-- Generator Card -->
                <div class="bg-white border border-slate-200/80 rounded-2xl p-4 shadow-sm space-y-3">
                    <div>
                        <label class="text-xs font-semibold text-slate-700">Test mavzusi yoki asosiy matn:</label>
                        <textarea id="quiz-topic" rows="3" class="mt-1.5 w-full rounded-xl border border-slate-200 bg-slate-50/50 p-3 text-xs text-slate-900 placeholder:text-slate-400 focus:outline-none focus:border-brand-600 focus:bg-white transition-all resize-none" placeholder="Masalan: 8-sinf Fizika, Issiqlik miqdori va uning o'lchov birliklari..."></textarea>
                    </div>

                    <div class="grid grid-cols-2 gap-2">
                        <div>
                            <label class="text-[11px] font-medium text-slate-500">Savollar soni</label>
                            <select id="quiz-count" class="mt-1 w-full rounded-lg border border-slate-200 bg-slate-50 p-2 text-xs font-medium text-slate-900 focus:outline-none focus:border-brand-600">
                                <option value="5">5 ta savol</option>
                                <option value="10" selected>10 ta savol</option>
                                <option value="15">15 ta savol</option>
                            </select>
                        </div>
                        <div>
                            <label class="text-[11px] font-medium text-slate-500">Format</label>
                            <select id="quiz-type" class="mt-1 w-full rounded-lg border border-slate-200 bg-slate-50 p-2 text-xs font-medium text-slate-900 focus:outline-none focus:border-brand-600">
                                <option value="multiple">A/B/C/D Test</option>
                                <option value="open">Ochiq savollar</option>
                            </select>
                        </div>
                    </div>

                    <button id="quiz-gen-btn" class="w-full py-2.5 rounded-xl bg-brand-600 hover:bg-brand-700 text-white text-xs font-semibold shadow-sm transition-all inline-flex items-center justify-center gap-2">
                        <i data-lucide="plus-circle" class="w-3.5 h-3.5"></i> Testni shakllantirish
                    </button>
                </div>

                <!-- Existing Quizzes -->
                <div class="bg-white border border-slate-200/80 rounded-2xl shadow-sm overflow-hidden">
                    <div class="px-4 py-3 border-b border-slate-100 flex items-center justify-between">
                        <h3 class="text-xs font-semibold text-slate-700 uppercase tracking-wider">Tayyorlangan to'plamlar</h3>
                    </div>

                    <div id="quiz-list-container" class="divide-y divide-slate-100">
                        <div class="p-6 text-center text-xs text-slate-400">Yuklanmoqda...</div>
                    </div>
                </div>
            </div>
        `;
        refreshIcons();

        document.getElementById('quiz-gen-btn').onclick = async () => {
            const topic = document.getElementById('quiz-topic').value.trim();
            if (!topic) {
                TelegramApp.showAlert("Iltimos, mavzuni kiriting!");
                return;
            }
            const count = parseInt(document.getElementById('quiz-count').value);
            const type = document.getElementById('quiz-type').value;

            const btn = document.getElementById('quiz-gen-btn');
            btn.innerText = "AI test tuzmoqda (15-20 soniya)...";
            btn.disabled = true;

            try {
                await api.createQuiz(topic, count, type);
                TelegramApp.hapticFeedback('medium');
                TelegramApp.showAlert("Test tayyorlandi!");
                renderQuiz();
            } catch (err) {
                TelegramApp.showAlert(`Xatolik: ${err.message}`);
                btn.innerHTML = `<i data-lucide="plus-circle" class="w-3.5 h-3.5"></i> Testni shakllantirish`;
                btn.disabled = false;
                refreshIcons();
            }
        };

        // Load quizzes
        try {
            const quizzes = await api.getQuizzes();
            const container = document.getElementById('quiz-list-container');

            if (quizzes.length === 0) {
                container.innerHTML = `
                    <div class="py-10 text-center text-slate-400">
                        <i data-lucide="clipboard-x" class="w-8 h-8 mx-auto stroke-1 text-slate-300 mb-2"></i>
                        <p class="text-xs">Hali testlar yaratilmagan</p>
                    </div>
                `;
                refreshIcons();
                return;
            }

            container.innerHTML = quizzes.map(q => `
                <div class="p-3.5 flex items-center justify-between hover:bg-slate-50 transition-colors">
                    <div class="truncate pr-2">
                        <h4 class="text-xs font-semibold text-slate-900 truncate">${q.title}</h4>
                        <p class="text-[11px] text-slate-500 font-mono mt-0.5">${q.questions_count} ta savol • ${new Date(q.created_at).toLocaleDateString()}</p>
                    </div>

                    <div class="flex items-center gap-1.5 shrink-0">
                        <a href="/api/quiz/${q.id}/export/docx" target="_blank" class="px-2.5 py-1 rounded-lg border border-slate-200 text-[11px] font-semibold text-slate-700 hover:bg-slate-100 transition-colors inline-flex items-center gap-1">
                            <i data-lucide="download" class="w-3 h-3"></i> Word
                        </a>
                        <a href="/api/quiz/${q.id}/export/pdf" target="_blank" class="px-2.5 py-1 rounded-lg border border-slate-200 text-[11px] font-semibold text-slate-700 hover:bg-slate-100 transition-colors inline-flex items-center gap-1">
                            <i data-lucide="download" class="w-3 h-3"></i> PDF
                        </a>
                    </div>
                </div>
            `).join('');
            refreshIcons();
        } catch (e) {
            document.getElementById('quiz-list-container').innerHTML = `<div class="p-4 text-center text-xs text-red-500">${e.message}</div>`;
        }
    }

    // ─────────────────────────────────────────────────────────────
    // 5. SETTINGS & PROFILE VIEW
    // ─────────────────────────────────────────────────────────────
    function renderSettings() {
        appDiv.innerHTML = `
            <div class="space-y-4 animate-fade-in">
                <!-- Header -->
                <div>
                    <h2 class="text-lg font-bold text-slate-900 tracking-tight">Tizim va Profil</h2>
                    <p class="text-xs text-slate-500">Bot sozlamalari va bulutli ma'lumotlar bazasi</p>
                </div>

                <!-- User Card -->
                <div class="bg-white border border-slate-200/80 rounded-2xl p-4 shadow-sm flex items-center gap-3">
                    <div class="w-12 h-12 rounded-full bg-brand-50 text-brand-600 flex items-center justify-center font-bold text-base">
                        ${(tgUser.first_name || 'O').charAt(0)}
                    </div>
                    <div>
                        <h3 class="text-sm font-semibold text-slate-900">${tgUser.first_name || "O'qituvchi"}</h3>
                        <p class="text-xs text-slate-500 font-mono mt-0.5">ID: ${tgUser.id || 'N/A'}</p>
                    </div>
                </div>

                <!-- Channel DB Card -->
                <div class="bg-white border border-slate-200/80 rounded-2xl p-4 shadow-sm space-y-3">
                    <div class="flex items-center gap-2 text-slate-900 font-semibold text-xs">
                        <i data-lucide="shield-check" class="w-4 h-4 text-emerald-600"></i>
                        <span>Bulutli Baza (Telegram Channel)</span>
                    </div>
                    <p class="text-xs text-slate-500 leading-relaxed">
                        Barcha foydalanuvchilar, testlar va fayllar <b>-1004294226425</b> kanalida <code>.js</code> formatida avtomatik zaxiralanadi va qayta tiklanadi.
                    </p>
                    <div class="p-2.5 rounded-xl bg-slate-50 border border-slate-200/60 flex items-center justify-between text-xs">
                        <span class="text-slate-600 font-medium">Baza formati:</span>
                        <span class="font-mono text-brand-600 font-semibold">window.EDUBOT_DB (.js)</span>
                    </div>
                </div>

                <!-- About Card -->
                <div class="bg-white border border-slate-200/80 rounded-2xl p-4 shadow-sm">
                    <div class="flex items-center justify-between text-xs">
                        <span class="text-slate-500">Loyiha versiyasi:</span>
                        <span class="font-mono font-semibold text-slate-700">v1.2.0 (SaaS UI)</span>
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
            case '#/files': renderFiles(); break;
            case '#/ai': renderAI(); break;
            case '#/quiz': renderQuiz(); break;
            case '#/settings': renderSettings(); break;
            default: renderDashboard(); break;
        }
    }

    window.addEventListener('hashchange', router);
    router();
});
