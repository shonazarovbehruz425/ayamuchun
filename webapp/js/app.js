document.addEventListener('DOMContentLoaded', () => {
    const appDiv = document.getElementById('app');

    // Update active nav link
    function updateNav(hash) {
        document.querySelectorAll('.nav-item').forEach(item => {
            if (item.getAttribute('href') === hash || (hash === '' && item.getAttribute('href') === '#/')) {
                item.classList.add('active');
            } else {
                item.classList.remove('active');
            }
        });
    }

    // --- DASHBOARD ---
    async function renderDashboard() {
        appDiv.innerHTML = `
            <h2>EduBot Dashboard</h2>
            <div class="card">
                <h3>Xush kelibsiz! 👋</h3>
                <p style="color: var(--hint-color); margin: 6px 0 0;">O'qituvchilar uchun qulay hujjatlar va AI yordamchi tizimi.</p>
            </div>
            
            <div class="stat-grid">
                <div class="stat-box">
                    <div class="stat-val" id="file-stat">-</div>
                    <div class="stat-label">Hujjatlar</div>
                </div>
                <div class="stat-box">
                    <div class="stat-val" id="quiz-stat">-</div>
                    <div class="stat-label">Testlar</div>
                </div>
            </div>

            <div class="card">
                <h3>⚡ Tezkor vositalar</h3>
                <div class="tools-grid" style="margin-top: 12px;">
                    <div class="tool-card" onclick="window.location.hash='#/files'">
                        <div class="tool-icon">📁</div>
                        <div class="tool-title">Fayl tahlili</div>
                    </div>
                    <div class="tool-card" onclick="window.location.hash='#/ai'">
                        <div class="tool-icon">🧠</div>
                        <div class="tool-title">AI Yordamchi</div>
                    </div>
                    <div class="tool-card" onclick="window.location.hash='#/quiz'">
                        <div class="tool-icon">📝</div>
                        <div class="tool-title">Test Tuzish</div>
                    </div>
                    <div class="tool-card" onclick="window.location.hash='#/settings'">
                        <div class="tool-icon">⚙️</div>
                        <div class="tool-title">Sozlamalar</div>
                    </div>
                </div>
            </div>
        `;

        try {
            const files = await api.getFiles();
            document.getElementById('file-stat').innerText = files.length || 0;
            const quizzes = await api.getQuizzes();
            document.getElementById('quiz-stat').innerText = quizzes.length || 0;
        } catch (e) {
            document.getElementById('file-stat').innerText = '0';
            document.getElementById('quiz-stat').innerText = '0';
        }
    }

    // --- FILES ---
    async function renderFiles() {
        appDiv.innerHTML = `
            <h2>📁 Hujjatlar bilan ishlash</h2>
            <div class="card">
                <h3>Yangi fayl yuklash</h3>
                <p style="font-size: 13px; color: var(--hint-color);">PDF, DOCX, XLSX, PPTX formatlari qo'llab-quvvatlanadi.</p>
                <input type="file" id="file-upload-input" style="margin: 10px 0;">
                <button class="btn" id="upload-btn">Yuklash</button>
            </div>

            <div class="card">
                <h3>Mening hujjatlarim</h3>
                <div id="files-container"><div class="loader">Hujjatlar yuklanmoqda...</div></div>
            </div>
        `;

        document.getElementById('upload-btn').onclick = async () => {
            const input = document.getElementById('file-upload-input');
            if (!input.files || input.files.length === 0) {
                TelegramApp.showAlert("Iltimos, avval faylni tanlang!");
                return;
            }
            const file = input.files[0];
            const fd = new FormData();
            fd.append('file', file);

            const btn = document.getElementById('upload-btn');
            btn.innerText = "Yuklanmoqda...";
            btn.disabled = true;

            try {
                await api.uploadFile(fd);
                TelegramApp.hapticFeedback('medium');
                TelegramApp.showAlert("Fayl muvaffaqiyatli yuklandi!");
                renderFiles();
            } catch (err) {
                TelegramApp.showAlert(`Xatolik: ${err.message}`);
                btn.innerText = "Yuklash";
                btn.disabled = false;
            }
        };

        const container = document.getElementById('files-container');
        try {
            const files = await api.getFiles();
            if (files.length === 0) {
                container.innerHTML = `<p style="color: var(--hint-color); text-align: center;">Hozircha yuklangan fayllar yo'q.</p>`;
                return;
            }

            container.innerHTML = files.map(f => `
                <div class="file-item">
                    <div class="file-info">
                        <div class="file-name">${f.file_name}</div>
                        <div class="file-meta">${(f.file_size / (1024*1024)).toFixed(2)} MB • ${f.file_type.toUpperCase()}</div>
                    </div>
                    <div class="file-actions">
                        ${f.file_type.toLowerCase() !== 'pdf' ? `<button class="btn btn-sm" onclick="convertFile(${f.id}, 'pdf')">PDF</button>` : ''}
                        ${f.file_type.toLowerCase() === 'pdf' ? `<button class="btn btn-sm" onclick="convertFile(${f.id}, 'docx')">Word</button>` : ''}
                        <button class="btn btn-sm btn-danger" onclick="deleteFileItem(${f.id})">🗑️</button>
                    </div>
                </div>
            `).join('');
        } catch (err) {
            container.innerHTML = `<p style="color: red;">Yuklashda xatolik: ${err.message}</p>`;
        }
    }

    window.convertFile = async (id, format) => {
        TelegramApp.hapticFeedback();
        try {
            TelegramApp.showAlert(`Konvertatsiya qilinmoqda (${format})...`);
            await api.convertFile(id, format);
            TelegramApp.showAlert("Muvaffaqiyatli aylantirildi!");
            renderFiles();
        } catch (e) {
            TelegramApp.showAlert(`Xato: ${e.message}`);
        }
    };

    window.deleteFileItem = async (id) => {
        TelegramApp.showConfirm("Faylni o'chirishga ishonchingiz komilmi?", async (confirmed) => {
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

    // --- AI ASSISTANT ---
    function renderAI() {
        appDiv.innerHTML = `
            <h2>🧠 AI Yordamchi</h2>
            <div class="tools-grid">
                <div class="tool-card active" id="tab-summarize" onclick="selectAITool('summarize')">
                    <div class="tool-icon">📋</div>
                    <div class="tool-title">Xulosa qilish</div>
                </div>
                <div class="tool-card" id="tab-lesson" onclick="selectAITool('lesson')">
                    <div class="tool-icon">📝</div>
                    <div class="tool-title">Dars rejasi</div>
                </div>
                <div class="tool-card" id="tab-translate" onclick="selectAITool('translate')">
                    <div class="tool-icon">🔄</div>
                    <div class="tool-title">Tarjima</div>
                </div>
                <div class="tool-card" id="tab-explain" onclick="selectAITool('explain')">
                    <div class="tool-icon">💡</div>
                    <div class="tool-title">Tushuntirish</div>
                </div>
            </div>

            <div class="card">
                <div class="form-group">
                    <label id="ai-input-label">Xulosa qilinadigan matnni kiriting:</label>
                    <textarea id="ai-input" placeholder="Matnni shu yerga yozing yoki kiriting..."></textarea>
                </div>
                <button class="btn" id="ai-submit-btn">Yuborish va Tahlil qilish</button>
                <div id="ai-result" style="display: none;" class="result-box"></div>
            </div>
        `;

        window.currentAITool = 'summarize';

        window.selectAITool = (tool) => {
            TelegramApp.hapticFeedback();
            window.currentAITool = tool;
            document.querySelectorAll('.tool-card').forEach(c => c.classList.remove('active'));
            const card = document.getElementById(`tab-${tool}`);
            if (card) card.classList.add('active');

            const label = document.getElementById('ai-input-label');
            const input = document.getElementById('ai-input');
            const res = document.getElementById('ai-result');
            res.style.display = 'none';

            if (tool === 'summarize') {
                label.innerText = "Xulosa qilinadigan matnni kiriting:";
                input.placeholder = "Matnni shu yerga kiriting...";
            } else if (tool === 'lesson') {
                label.innerText = "Fan va Dars mavzusini kiriting:";
                input.placeholder = "Masalan: Fizika — Nyuton qonunlari";
            } else if (tool === 'translate') {
                label.innerText = "Tarjima qilinadigan matnni kiriting:";
                input.placeholder = "Tarjima uchun matn...";
            } else if (tool === 'explain') {
                label.innerText = "Tushuntirilishi kerak bo'lgan mavzu yoki tushuncha:";
                input.placeholder = "Masalan: Fotosintez jarayoni nima?";
            }
        };

        document.getElementById('ai-submit-btn').onclick = async () => {
            const input = document.getElementById('ai-input').value.trim();
            if (!input) {
                TelegramApp.showAlert("Iltimos, matn kiriting!");
                return;
            }

            const btn = document.getElementById('ai-submit-btn');
            const res = document.getElementById('ai-result');
            btn.innerText = "AI tahlil qilmoqda...";
            btn.disabled = true;
            res.style.display = 'block';
            res.innerText = "⏳ AI javob tayyorlamoqda...";

            try {
                let response;
                if (window.currentAITool === 'summarize') response = await api.summarizeText(input);
                else if (window.currentAITool === 'lesson') response = await api.lessonPlan(input);
                else if (window.currentAITool === 'translate') response = await api.translateText(input);
                else if (window.currentAITool === 'explain') response = await api.explainTopic(input);

                res.innerText = response.result;
                TelegramApp.hapticFeedback('medium');
            } catch (err) {
                res.innerText = `Xatolik: ${err.message}`;
            } finally {
                btn.innerText = "Yuborish va Tahlil qilish";
                btn.disabled = false;
            }
        };
    }

    // --- QUIZ ---
    async function renderQuiz() {
        appDiv.innerHTML = `
            <h2>📝 Test Yaratish</h2>
            <div class="card">
                <h3>Yangi test generatsiya qilish</h3>
                <div class="form-group">
                    <label>Test mavzusi yoki manba matn:</label>
                    <textarea id="quiz-topic" placeholder="Mavzu: O'zbekiston tarixi 9-sinf..."></textarea>
                </div>
                <div class="form-group">
                    <label>Savollar soni:</label>
                    <select id="quiz-count">
                        <option value="5">5 ta savol</option>
                        <option value="10" selected>10 ta savol</option>
                        <option value="15">15 ta savol</option>
                    </select>
                </div>
                <div class="form-group">
                    <label>Test turi:</label>
                    <select id="quiz-type">
                        <option value="multiple">Ko'p variantli (A/B/C/D)</option>
                        <option value="open">Ochiq savollar</option>
                        <option value="mixed">Aralash</option>
                    </select>
                </div>
                <button class="btn" id="generate-quiz-btn">Test yaratish</button>
            </div>

            <div class="card">
                <h3>Avvalgi testlar</h3>
                <div id="quiz-list"><div class="loader">Yuklanmoqda...</div></div>
            </div>
        `;

        document.getElementById('generate-quiz-btn').onclick = async () => {
            const topic = document.getElementById('quiz-topic').value.trim();
            if (!topic) {
                TelegramApp.showAlert("Iltimos, test mavzusini kiriting!");
                return;
            }
            const count = parseInt(document.getElementById('quiz-count').value);
            const type = document.getElementById('quiz-type').value;

            const btn = document.getElementById('generate-quiz-btn');
            btn.innerText = "AI test yaratmoqda (15-30 soniya)...";
            btn.disabled = true;

            try {
                await api.createQuiz(topic, count, type);
                TelegramApp.hapticFeedback('medium');
                TelegramApp.showAlert("Test muvaffaqiyatli yaratildi!");
                renderQuiz();
            } catch (err) {
                TelegramApp.showAlert(`Xatolik: ${err.message}`);
                btn.innerText = "Test yaratish";
                btn.disabled = false;
            }
        };

        const listCont = document.getElementById('quiz-list');
        try {
            const quizzes = await api.getQuizzes();
            if (quizzes.length === 0) {
                listCont.innerHTML = `<p style="color: var(--hint-color); text-align: center;">Hali testlar yaratilmagan.</p>`;
                return;
            }

            listCont.innerHTML = quizzes.map(q => `
                <div class="file-item">
                    <div class="file-info">
                        <div class="file-name">${q.title}</div>
                        <div class="file-meta">${q.questions_count} ta savol • ${new Date(q.created_at).toLocaleDateString()}</div>
                    </div>
                    <div class="file-actions">
                        <a href="/api/quiz/${q.id}/export/docx" target="_blank" class="btn btn-sm">Word</a>
                        <a href="/api/quiz/${q.id}/export/pdf" target="_blank" class="btn btn-sm">PDF</a>
                    </div>
                </div>
            `).join('');
        } catch (e) {
            listCont.innerHTML = `<p style="color: red;">Xatolik: ${e.message}</p>`;
        }
    }

    // --- SETTINGS ---
    function renderSettings() {
        const user = TelegramApp.getUserData() || { first_name: "O'qituvchi", id: "99999999" };
        appDiv.innerHTML = `
            <h2>⚙️ Sozlamalar</h2>
            <div class="card">
                <h3>Foydalanuvchi ma'lumotlari</h3>
                <p><strong>Ism:</strong> ${user.first_name}</p>
                <p><strong>Telegram ID:</strong> ${user.id}</p>
            </div>
            <div class="card">
                <h3>EduBot haqida</h3>
                <p style="color: var(--hint-color); font-size: 14px;">EduBot — o'qituvchilar va pedagoglar uchun yaratilgan universal yordamchi platforma. PDF, Word, Excel, PowerPoint fayllar tahlili, konvertatsiya va sun'iy intellekt xizmatlarini taqdim etadi.</p>
                <p style="font-size: 12px; color: var(--hint-color);">Versiya 1.0.0</p>
            </div>
        `;
    }

    // Router
    function router() {
        const hash = window.location.hash || '#/';
        TelegramApp.hapticFeedback();
        updateNav(hash);

        switch(hash) {
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
