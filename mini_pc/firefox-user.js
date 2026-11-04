// Karavan kiosk profili
// Sesli uyarılar dokunmadan çalabilsin
user_pref("media.autoplay.default", 0);
user_pref("media.autoplay.blocking_policy", 0);
// Çökme sonrası "oturumu geri yükle" sayfası, karşılama ve varsayılan tarayıcı soruları çıkmasın
user_pref("browser.sessionstore.resume_from_crash", false);
user_pref("browser.shell.checkDefaultBrowser", false);
user_pref("browser.aboutwelcome.enabled", false);
user_pref("startup.homepage_welcome_url", "");
user_pref("startup.homepage_welcome_url.additional", "");
user_pref("browser.startup.homepage_override.mstone", "ignore");
user_pref("datareporting.policy.dataSubmissionEnabled", false);
user_pref("datareporting.healthreport.uploadEnabled", false);
user_pref("toolkit.telemetry.reportingpolicy.firstRun", false);
user_pref("browser.translations.automaticallyPopup", false);
user_pref("browser.tabs.warnOnClose", false);
// 1 GB RAM: tek içerik işlemi
user_pref("dom.ipc.processCount", 1);
user_pref("browser.tabs.unloadOnLowMemory", false);
// Dokunmatik: olaylar açık, yanlışlıkla iki parmak yakınlaştırma kapalı
user_pref("dom.w3c_touch_events.enabled", 1);
user_pref("apz.allow_zooming", false);
// Dokunmatikte sürüklenebilir kaydırma çubuğu
user_pref("widget.gtk.overlay-scrollbars.enabled", false);
// --- Yavaş işlemci (Atom Z510, tek çekirdek) için hafifletme ---
user_pref("fission.autostart", false);
user_pref("dom.ipc.processPrelaunch.enabled", false);
user_pref("extensions.webextensions.remote", false);
user_pref("accessibility.force_disabled", 1);
user_pref("browser.newtab.preload", false);
user_pref("browser.newtabpage.enabled", false);
user_pref("browser.safebrowsing.malware.enabled", false);
user_pref("browser.safebrowsing.phishing.enabled", false);
user_pref("browser.safebrowsing.downloads.enabled", false);
user_pref("browser.safebrowsing.update.enabled", false);
user_pref("app.normandy.enabled", false);
user_pref("extensions.pocket.enabled", false);
user_pref("extensions.update.enabled", false);
user_pref("browser.search.update", false);
user_pref("browser.discovery.enabled", false);
user_pref("toolkit.telemetry.enabled", false);
user_pref("toolkit.telemetry.unified", false);
user_pref("network.prefetch-next", false);
user_pref("network.dns.disablePrefetch", true);
user_pref("browser.cache.disk.enable", false);
user_pref("browser.sessionstore.interval", 600000);
user_pref("ui.prefersReducedMotion", 1);
user_pref("layout.frame_rate", 30);
