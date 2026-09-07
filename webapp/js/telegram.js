const tg = window.Telegram?.WebApp;

const TelegramApp = {
    init() {
        if (!tg) return;
        try {
            const triggerExpandAndFullscreen = () => {
                try {
                    tg.ready();
                    tg.expand();
                    if (tg.requestFullscreen && !tg.isFullscreen) {
                        tg.requestFullscreen();
                    }
                    if (tg.disableVerticalSwipes) {
                        tg.disableVerticalSwipes();
                    }
                } catch (e) {}
            };

            triggerExpandAndFullscreen();
            setTimeout(triggerExpandAndFullscreen, 50);
            setTimeout(triggerExpandAndFullscreen, 150);
            setTimeout(triggerExpandAndFullscreen, 400);

            // Synchronize Telegram Safe Area Insets and dynamically position header below overlay buttons
            const syncSafeArea = () => {
                const top = tg.contentSafeAreaInset?.top ?? tg.safeAreaInset?.top ?? 0;
                const bottom = tg.contentSafeAreaInset?.bottom ?? tg.safeAreaInset?.bottom ?? 0;
                if (top > 0) {
                    document.documentElement.style.setProperty('--tg-safe-area-inset-top', `${top}px`);
                    document.documentElement.style.setProperty('--tg-content-safe-area-inset-top', `${top}px`);
                }
                if (bottom > 0) {
                    document.documentElement.style.setProperty('--tg-safe-area-inset-bottom', `${bottom}px`);
                    document.documentElement.style.setProperty('--tg-content-safe-area-inset-bottom', `${bottom}px`);
                }

                // Explicitly enforce header clearance so Close and Menu buttons never overlap
                const headerPadding = Math.max(72, top + 56);
                document.querySelectorAll('header.liquid-glass-header, .doc-editor-header').forEach(h => {
                    h.style.setProperty('padding-top', `${headerPadding}px`, 'important');
                });
            };
            syncSafeArea();
            tg.onEvent?.('safeAreaChanged', syncSafeArea);
            tg.onEvent?.('contentSafeAreaChanged', syncSafeArea);
            tg.onEvent?.('fullscreenChanged', () => {
                syncSafeArea();
            });
            tg.onEvent?.('fullscreenFailed', () => {
                tg.expand();
            });

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

            // Fallback: on first interaction, ensure full screen if webview restricted auto-fullscreen
            const onFirstTouch = () => {
                triggerExpandAndFullscreen();
                window.removeEventListener('touchstart', onFirstTouch);
                window.removeEventListener('click', onFirstTouch);
            };
            window.addEventListener('touchstart', onFirstTouch, { passive: true, once: true });
            window.addEventListener('click', onFirstTouch, { passive: true, once: true });
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

    requestContact(callback) {
        if (tg?.requestContact) {
            try {
                tg.requestContact((sent, event) => {
                    if (callback) callback(sent, event);
                });
                return true;
            } catch (e) {
                console.warn("requestContact warning:", e);
            }
        }
        if (callback) callback(false, null);
        return false;
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

    closeApp() {
        if (tg?.close) {
            tg.close();
        }
    },

    downloadFile(url, fileName = "") {
        // 1. Notify user clearly in Telegram Mini App that document is ready and sent to Telegram
        this.hapticFeedback('medium');
        this.showAlert(
            "📬 Hujjatingiz to'g'ridan-to'g'ri Telegram botingizga yuborildi!\n\n" +
            "Siz uni pastdagi 'Yopish' tugmasini bosib, bot chatidan yuklab olishingiz mumkin."
        );

        // 2. Also trigger direct device download in background without forcing navigation
        try {
            const fullUrl = url.startsWith('http') ? url : (window.location.origin + url);
            const a = document.createElement('a');
            a.href = fullUrl;
            if (fileName) a.download = fileName;
            a.target = '_self';
            a.style.display = 'none';
            document.body.appendChild(a);
            a.click();
            setTimeout(() => {
                if (document.body.contains(a)) document.body.removeChild(a);
            }, 500);
        } catch (e) {
            console.warn("Direct download fallback error:", e);
        }
    }
};

TelegramApp.init();
