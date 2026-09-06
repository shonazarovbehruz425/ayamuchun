const tg = window.Telegram?.WebApp;

const TelegramApp = {
    init() {
        if (!tg) return;
        try {
            tg.ready();
            // Request full screen & expand immediately
            if (tg.requestFullscreen) {
                tg.requestFullscreen();
            }
            tg.expand();

            // Set app headers and backgrounds
            if (tg.setHeaderColor) {
                tg.setHeaderColor('secondary_bg_color');
            }
            if (tg.setBackgroundColor) {
                tg.setBackgroundColor('secondary_bg_color');
            }
            if (tg.enableClosingConfirmation) {
                tg.enableClosingConfirmation();
            }

            // Disable vertical swipes to prevent accidental minimize/close
            if (tg.disableVerticalSwipes) {
                tg.disableVerticalSwipes();
            }
        } catch (e) {
            console.warn("Telegram WebApp init warning:", e);
        }
    },
    
    getUserData() {
        return tg?.initDataUnsafe?.user;
    },
    
    getInitData() {
        return tg?.initData || "";
    },

    getPlatform() {
        return tg?.platform || "web";
    },
    
    showAlert(message) {
        if (tg?.showAlert) {
            tg.showAlert(message);
        } else {
            alert(message);
        }
    },
    
    showConfirm(message, callback) {
        if (tg?.showConfirm) {
            tg.showConfirm(message, callback);
        } else {
            callback(confirm(message));
        }
    },
    
    hapticFeedback(style = 'light') {
        if (tg?.HapticFeedback?.impactOccurred) {
            tg.HapticFeedback.impactOccurred(style);
        }
    },

    openLink(url) {
        if (tg?.openLink) {
            tg.openLink(url);
        } else {
            window.open(url, '_blank');
        }
    },

    downloadFile(url) {
        const fullUrl = url.startsWith('http') ? url : (window.location.origin + url);
        if (tg?.openLink) {
            tg.openLink(fullUrl);
        } else {
            const a = document.createElement('a');
            a.href = fullUrl;
            a.download = '';
            a.target = '_blank';
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
        }
    }
};

TelegramApp.init();
