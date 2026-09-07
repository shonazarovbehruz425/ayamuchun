const BASE_URL = '/api';

const api = {
    async fetchWithAuth(url, options = {}) {
        const initData = TelegramApp.getInitData() || '';
        const headers = {
            'Authorization': `Bearer ${initData}`,
            ...options.headers
        };
        
        if (options.body && !(options.body instanceof FormData)) {
            headers['Content-Type'] = 'application/json';
            options.body = JSON.stringify(options.body);
        }
        
        const response = await fetch(`${BASE_URL}${url}`, { ...options, headers });
        if (!response.ok) {
            const errData = await response.json().catch(() => ({}));
            throw new Error(errData.detail || `Server xatosi: ${response.status}`);
        }
        return response.json();
    },
    
    // Files & Documents
    getFiles() { return this.fetchWithAuth('/files'); },
    uploadFile(formData) { return this.fetchWithAuth('/files/upload', { method: 'POST', body: formData }); },
    convertFile(fileId, format) { return this.fetchWithAuth(`/files/${fileId}/convert?format=${format}`, { method: 'POST' }); },
    deleteFile(fileId) { return this.fetchWithAuth(`/files/${fileId}`, { method: 'DELETE' }); },
    clearAllFiles() { return this.fetchWithAuth('/files/clear-all', { method: 'DELETE' }); },
    getFileContent(fileId) { return this.fetchWithAuth(`/files/${fileId}/content`); },
    saveFileContent(fileId, content) { return this.fetchWithAuth(`/files/${fileId}/save-content`, { method: 'POST', body: { content } }); },
    getFileHtml(fileId) { return this.fetchWithAuth(`/files/${fileId}/html`); },
    saveFileHtml(fileId, html, format = 'both') { return this.fetchWithAuth(`/files/${fileId}/save-html`, { method: 'POST', body: { html, format } }); },
    imagesToPdf(formData) { return this.fetchWithAuth('/files/images-to-pdf', { method: 'POST', body: formData }); },
    extractImages(fileId) { return this.fetchWithAuth(`/files/${fileId}/extract-images`, { method: 'POST' }); },
    mergePdfs(formData) { return this.fetchWithAuth('/files/merge-pdfs', { method: 'POST', body: formData }); },
    splitPdf(formData) { return this.fetchWithAuth('/files/split-pdf', { method: 'POST', body: formData }); },
    compressPdf(formData) { return this.fetchWithAuth('/files/compress-pdf', { method: 'POST', body: formData }); },
    watermarkPdf(formData) { return this.fetchWithAuth('/files/watermark-pdf', { method: 'POST', body: formData }); },
    generatePhoto3x4(formData) { return this.fetchWithAuth('/files/photo-3x4', { method: 'POST', body: formData }); },
    sendFileToTelegram(fileId) { return this.fetchWithAuth(`/files/${fileId}/send-to-telegram`, { method: 'POST' }); },
    
    // AI tools
    summarizeText(text, language = 'uz') { return this.fetchWithAuth('/ai/summarize', { method: 'POST', body: { text, action: 'summarize', language } }); },
    translateText(text, language = 'en') { return this.fetchWithAuth('/ai/translate', { method: 'POST', body: { text, action: 'translate', language } }); },
    lessonPlan(text, language = 'uz') { return this.fetchWithAuth('/ai/lesson-plan', { method: 'POST', body: { text, action: 'lesson-plan', language } }); },
    checkGrammar(text) { return this.fetchWithAuth('/ai/grammar', { method: 'POST', body: { text, action: 'grammar' } }); },
    improveText(text, language = 'uz') { return this.fetchWithAuth('/ai/improve', { method: 'POST', body: { text, action: 'improve', language } }); },
    explainTopic(text, language = 'uz') { return this.fetchWithAuth('/ai/explain', { method: 'POST', body: { text, action: 'explain', language } }); },
    createQuizAI(text, language = 'uz') { return this.fetchWithAuth('/ai/quiz', { method: 'POST', body: { text, action: 'quiz', language } }); },
    exportAIDocx(title, text) { return this.fetchWithAuth('/ai/export-docx', { method: 'POST', body: { title, text } }); },
    sendAIToTelegram(title, text, actionType = 'text') { return this.fetchWithAuth('/ai/send-to-telegram', { method: 'POST', body: { title, text, action_type: actionType } }); },
    getAiConfig() { return this.fetchWithAuth('/ai/config'); },
    
    // Auth & Profile
    getMe() { return this.fetchWithAuth('/auth/me'); },
    updatePhone(phoneNumber) { return this.fetchWithAuth('/auth/update-phone', { method: 'POST', body: { phone_number: phoneNumber } }); },

    // Quiz
    getQuizzes() { return this.fetchWithAuth('/quiz/list'); },
    createQuiz(topic, count, type) { return this.fetchWithAuth('/quiz/create', { method: 'POST', body: { topic, num_questions: count, quiz_type: type } }); },
    getQuiz(quizId) { return this.fetchWithAuth(`/quiz/${quizId}`); }
};
