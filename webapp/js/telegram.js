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

    botUsername: (function() {
        try {
            return localStorage.getItem('edubot_bot_username') || "AyamUchunBot";
        } catch (e) {
            return "AyamUchunBot";
        }
    })(),

    setBotUsername(username) {
        if (!username) return;
        this.botUsername = String(username).replace(/^@/, '').trim();
        try {
            localStorage.setItem('edubot_bot_username', this.botUsername);
        } catch (e) {}
    },

    openTelegramLink(url) {
        this.hapticFeedback('light');
        if (tg && typeof tg.openTelegramLink === 'function') {
            try {
                tg.openTelegramLink(url);
                return true;
            } catch (e) {
                console.warn("tg.openTelegramLink error:", e);
            }
        }
        if (tg && typeof tg.openLink === 'function') {
            try {
                tg.openLink(url);
                return true;
            } catch (e) {
                console.warn("tg.openLink error:", e);
            }
        }
        window.open(url, '_blank');
        return false;
    },

    openChat(botUsername = null) {
        this.hapticFeedback('medium');
        const username = botUsername || this.botUsername || "AyamUchunBot";
        const cleanUsername = String(username).replace(/^@/, '').trim();
        const tgUrl = `https://t.me/${cleanUsername}`;

        if (tg) {
            // Mini App yopilmasdan (sessiya va holat saqlangan holda) bot chatiga o'tish
            try {
                if (typeof tg.exitFullscreen === 'function' && tg.isFullscreen) {
                    tg.exitFullscreen();
                }
                if (typeof tg.enableVerticalSwipes === 'function') {
                    tg.enableVerticalSwipes();
                }
            } catch (e) {}

            try {
                if (typeof tg.openTelegramLink === 'function') {
                    tg.openTelegramLink(tgUrl, { force_request: true });
                    return true;
                }
            } catch (e) {
                console.warn("tg.openTelegramLink error:", e);
            }

            try {
                if (typeof tg.openLink === 'function') {
                    tg.openLink(tgUrl);
                    return true;
                }
            } catch (e) {}
        }

        // Fallback for regular web browsers
        try {
            window.location.href = tgUrl;
        } catch (e) {
            window.open(tgUrl, '_blank');
        }
        return false;
    },

    closeApp() {
        this.hapticFeedback('medium');
        try {
            if (tg) {
                if (tg.disableClosingConfirmation) {
                    tg.disableClosingConfirmation();
                }
                if (tg.close) {
                    tg.close();
                    return;
                }
            }
        } catch (e) {
            console.warn("closeApp error:", e);
        }
        window.close();
    },

    closeToChat() {
        // Safe navigation to chat without destroying/closing the web app
        this.openChat();
    },

    downloadFile(url, fileName = "") {
        this.hapticFeedback('medium');

        let fullUrl = url.startsWith('http') ? url : (window.location.origin + url);
        const initData = this.getInitData();
        if (initData && !fullUrl.includes('auth=') && !fullUrl.includes('token=')) {
            fullUrl += (fullUrl.includes('?') ? '&' : '?') + 'auth=' + encodeURIComponent(initData);
        }

        const safeFileName = fileName || "document";

        // 1. Modern Telegram WebApp 8.0+ downloadFile API
        if (tg && typeof tg.downloadFile === 'function') {
            try {
                tg.downloadFile({ url: fullUrl, file_name: safeFileName }, (accepted) => {
                    if (accepted) {
                        this.showAlert("Yuklab olish boshlandi!");
                    } else {
                        this._triggerBrowserDownload(fullUrl, safeFileName);
                    }
                });
                return;
            } catch (tgDlErr) {
                console.warn("tg.downloadFile error:", tgDlErr);
            }
        }

        // 2. Direct browser & WebApp download
        this._triggerBrowserDownload(fullUrl, safeFileName);
    },

    async _triggerBrowserDownload(fullUrl, fileName = "") {
        try {
            // First attempt: fetch as blob with auth header (most reliable for all webviews & safari)
            const initData = this.getInitData();
            const res = await fetch(fullUrl, {
                headers: initData ? { 'Authorization': `Bearer ${initData}` } : {}
            });
            if (res.ok) {
                const blob = await res.blob();
                const blobUrl = window.URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = blobUrl;
                if (fileName) a.download = fileName;
                a.style.display = 'none';
                document.body.appendChild(a);
                a.click();
                setTimeout(() => {
                    window.URL.revokeObjectURL(blobUrl);
                    if (document.body.contains(a)) document.body.removeChild(a);
                }, 2000);
                return;
            }
        } catch (fetchErr) {
            console.warn("Blob download fallback failed:", fetchErr);
        }

        // Fallback standard anchor
        try {
            const a = document.createElement('a');
            a.href = fullUrl;
            if (fileName) a.download = fileName;
            a.target = '_blank';
            a.style.display = 'none';
            document.body.appendChild(a);
            a.click();
            setTimeout(() => {
                if (document.body.contains(a)) document.body.removeChild(a);
            }, 500);
        } catch (e) {
            console.warn("Direct download fallback error:", e);
            if (tg && tg.openLink) {
                tg.openLink(fullUrl);
            } else {
                window.open(fullUrl, '_blank');
            }
        }
    }
};

TelegramApp.init();
