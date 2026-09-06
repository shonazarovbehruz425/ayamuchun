const tg = window.Telegram.WebApp;

const TelegramApp = {
    init() {
        tg.ready();
        tg.expand();
    },
    
    getUserData() {
        return tg.initDataUnsafe?.user;
    },
    
    getInitData() {
        return tg.initData;
    },
    
    showAlert(message) {
        tg.showAlert(message);
    },
    
    showConfirm(message, callback) {
        tg.showConfirm(message, callback);
    },
    
    hapticFeedback(style = 'light') {
        tg.HapticFeedback.impactOccurred(style);
    }
};

TelegramApp.init();
