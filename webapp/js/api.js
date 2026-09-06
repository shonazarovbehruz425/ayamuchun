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
    
    // Files
    getFiles() { return this.fetchWithAuth('/files'); },
    uploadFile(formData) { return this.fetchWithAuth('/files/upload', { method: 'POST', body: formData }); },
    convertFile(fileId, format) { return this.fetchWithAuth(`/files/${fileId}/convert?format=${format}`, { method: 'POST' }); },
    deleteFile(fileId) { return this.fetchWithAuth(`/files/${fileId}`, { method: 'DELETE' }); },
    
    // AI tools
    summarizeText(text, language = 'uz') { return this.fetchWithAuth('/ai/summarize', { method: 'POST', body: { text, action: 'summarize', language } }); },
    translateText(text, language = 'en') { return this.fetchWithAuth('/ai/translate', { method: 'POST', body: { text, action: 'translate', language } }); },
    lessonPlan(text, language = 'uz') { return this.fetchWithAuth('/ai/lesson-plan', { method: 'POST', body: { text, action: 'lesson-plan', language } }); },
    checkGrammar(text) { return this.fetchWithAuth('/ai/grammar', { method: 'POST', body: { text, action: 'grammar' } }); },
    improveText(text, language = 'uz') { return this.fetchWithAuth('/ai/improve', { method: 'POST', body: { text, action: 'improve', language } }); },
    explainTopic(text, language = 'uz') { return this.fetchWithAuth('/ai/explain', { method: 'POST', body: { text, action: 'explain', language } }); },
    
    // Quiz
    getQuizzes() { return this.fetchWithAuth('/quiz/list'); },
    createQuiz(topic, count, type) { return this.fetchWithAuth('/quiz/create', { method: 'POST', body: { topic, num_questions: count, quiz_type: type } }); },
    getQuiz(quizId) { return this.fetchWithAuth(`/quiz/${quizId}`); }
};
