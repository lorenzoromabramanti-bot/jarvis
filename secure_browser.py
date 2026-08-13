# -*- coding: utf-8 -*-
import webview
import ctypes
import threading
import time
import urllib.parse
import re
import os

# --- CONTEXTE ET CONSTANTES WINDOWS ---
GWL_STYLE = -16
WS_CHILD = 0x40000000
WS_POPUP = 0x80000000
WS_VISIBLE = 0x10000000
WS_CAPTION = 0x00C00000
WS_THICKFRAME = 0x00040000
WS_SYSMENU = 0x00080000
WS_MINIMIZEBOX = 0x00020000
WS_MAXIMIZEBOX = 0x00010000
WS_OVERLAPPEDWINDOW = 0x00CF0000

SWP_NOZORDER = 0x0004
SWP_NOACTIVATE = 0x0010
SWP_FRAMECHANGED = 0x0020
SWP_SHOWWINDOW = 0x0040

class RECT(ctypes.Structure):
    _fields_ = [
        ("left", ctypes.c_long),
        ("top", ctypes.c_long),
        ("right", ctypes.c_long),
        ("bottom", ctypes.c_long)
    ]

# Globals
_browser_window = None
_main_hwnd = None
_browser_hwnd = None
_is_docked = False
_default_url = "https://www.techenclair.fr"
_main_webview_window = None  # Reference to main JARVIS pywebview window

# --- CODE D'INJECTION JS (ADBLOCK + TOOLBAR) ---

ADBLOCK_JS = """
(function() {
    function cleanPageAds() {
        // Sélecteurs de bannières pub courants
        const adSelectors = [
            '.adsbygoogle', 'iframe[id^="google_ads"]', '.ad-banner', 
            '.ads-container', '#ad-slot', '.ad-box', '.ytp-ad-overlay-container',
            'ytd-ad-slot-renderer', 'ytd-companion-ad-renderer',
            'ytd-promoted-sparkles-web-renderer', 'ytd-promoted-video-renderer',
            '.ytd-ad-slot-renderer', '.video-ads', '.ytp-ad-module', 'div[id^="ad-text:"]'
        ];
        adSelectors.forEach(selector => {
            document.querySelectorAll(selector).forEach(el => {
                if (el && el.id !== 'jarvis-browser-toolbar') {
                    el.style.display = 'none';
                }
            });
        });

        // Bloqueur / Accélérateur de pub YouTube
        const video = document.querySelector('video');
        const isAdShowing = document.querySelector('.ad-showing, .ytp-ad-player-overlay, .ytp-ad-image-overlay');
        
        if (video && isAdShowing) {
            video.playbackRate = 16.0;
            video.muted = true;
            if (video.duration && video.currentTime < video.duration) {
                // Avancer directement à la fin de la pub
                video.currentTime = video.duration - 0.1;
            }
        }

        // Clic automatique sur "Passer l'annonce"
        const skipButtons = [
            '.ytp-ad-skip-button', 
            '.ytp-ad-skip-button-modern', 
            '.ytp-ad-skip-button-slot .ytp-ad-skip-button',
            '[class*="skip-button"]',
            '.ytp-ad-skip-button-text'
        ];
        skipButtons.forEach(selector => {
            const btn = document.querySelector(selector);
            if (btn && btn.style.display !== 'none') {
                btn.click();
            }
        });
    }

    // Exécuter immédiatement puis toutes les 250ms
    cleanPageAds();
    if (!window._jarvisAdBlockInterval) {
        window._jarvisAdBlockInterval = setInterval(cleanPageAds, 250);
    }
})();
"""

TOOLBAR_JS = """
(function() {
    const stopMedia = () => {
        try {
            const findMedia = (root) => {
                let list = Array.from(root.querySelectorAll('video, audio'));
                root.querySelectorAll('*').forEach(el => {
                    try {
                        if (el.shadowRoot) {
                            list = list.concat(findMedia(el.shadowRoot));
                        }
                    } catch(e){}
                });
                return list;
            };
            findMedia(document).forEach(el => {
                try {
                    el.pause();
                    el.src = '';
                    el.load();
                } catch(e){}
            });
        } catch(e){}
    };

    function ensureToolbar() {
        // Détecter les changements d'URL côté client (SPA)
        if (!window._jarvisLastUrl) {
            window._jarvisLastUrl = window.location.href;
        }
        if (window.location.href !== window._jarvisLastUrl) {
            const wasWatch = window._jarvisLastUrl.includes('/watch');
            const isWatch = window.location.href.includes('/watch');
            if (wasWatch && !isWatch) {
                stopMedia();
            }
            window._jarvisLastUrl = window.location.href;
        }

        let tb = document.getElementById('jarvis-browser-toolbar');
        if (tb) {
            // Mettre à jour l'adresse si elle a changé
            const input = document.getElementById('jarvis-browser-toolbar-input');
            if (input && input !== document.activeElement && input.value !== window.location.href) {
                input.value = window.location.href;
            }
            // S'assurer que le décalage du body est appliqué
            if (document.body && document.body.style.transform !== 'translateY(40px)') {
                document.body.style.setProperty('transform', 'translateY(40px)', 'important');
                document.body.style.setProperty('height', 'calc(100% - 40px)', 'important');
                document.body.style.setProperty('box-sizing', 'border-box', 'important');
            }
            return;
        }

        if (!document.body || !document.documentElement) return;

        // Décalage du body pour ne pas masquer le haut avec les éléments fixed de la page
        document.body.style.setProperty('transform', 'translateY(40px)', 'important');
        document.body.style.setProperty('height', 'calc(100% - 40px)', 'important');
        document.body.style.setProperty('box-sizing', 'border-box', 'important');

        // Création de la barre
        tb = document.createElement('div');
        tb.id = 'jarvis-browser-toolbar';
        tb.style.position = 'fixed';
        tb.style.top = '0';
        tb.style.left = '0';
        tb.style.width = '100%';
        tb.style.height = '40px';
        tb.style.backgroundColor = 'rgba(10, 10, 20, 0.95)';
        tb.style.borderBottom = '1px solid rgba(0, 229, 255, 0.3)';
        tb.style.boxShadow = '0 3px 15px rgba(0,0,0,0.6)';
        tb.style.display = 'flex';
        tb.style.alignItems = 'center';
        tb.style.justifyContent = 'space-between';
        tb.style.padding = '0 15px';
        tb.style.zIndex = '999999999';
        tb.style.fontFamily = 'Segoe UI, Arial, sans-serif';
        tb.style.color = '#fff';
        tb.style.boxSizing = 'border-box';
        tb.style.userSelect = 'none';

        // Groupe boutons navigation
        const navGroup = document.createElement('div');
        navGroup.style.display = 'flex';
        navGroup.style.gap = '8px';
        navGroup.style.alignItems = 'center';

        const createBtn = (icon, title, action) => {
            const btn = document.createElement('button');
            btn.textContent = icon;
            btn.title = title;
            btn.style.cssText = 'background:rgba(0,229,255,0.05); border:1px solid rgba(0,229,255,0.2); border-radius:4px; color:#00e5ff; cursor:pointer; font-size:14px; width:28px; height:28px; display:flex; align-items:center; justify-content:center; transition: all 0.2s;';
            btn.onmouseover = () => { btn.style.background = 'rgba(0,229,255,0.2)'; btn.style.borderColor = '#00e5ff'; };
            btn.onmouseout = () => { btn.style.background = 'rgba(0,229,255,0.05)'; btn.style.borderColor = 'rgba(0,229,255,0.2)'; };
            btn.onclick = action;
            return btn;
        };

        const btnBack = createBtn('◀', 'Retour', () => { stopMedia(); window.history.back(); });
        const btnForward = createBtn('▶', 'Suivant', () => { stopMedia(); window.history.forward(); });
        const btnReload = createBtn('🔄', 'Actualiser', () => { stopMedia(); window.location.reload(); });
        const btnGoogle = createBtn('🔍', 'Google', () => { stopMedia(); window.location.href = 'https://www.google.com'; });
        const btnYouTube = createBtn('📺', 'YouTube', () => { stopMedia(); window.location.href = 'https://www.youtube.com'; });

        navGroup.appendChild(btnBack);
        navGroup.appendChild(btnForward);
        navGroup.appendChild(btnReload);
        navGroup.appendChild(btnGoogle);
        navGroup.appendChild(btnYouTube);

        // Groupe barre d'adresse
        const addressGroup = document.createElement('div');
        addressGroup.style.flex = '1';
        addressGroup.style.margin = '0 15px';
        addressGroup.style.maxWidth = '700px';

        const input = document.createElement('input');
        input.id = 'jarvis-browser-toolbar-input';
        input.type = 'text';
        input.placeholder = 'Entrez une URL ou effectuez une recherche Google...';
        input.value = window.location.href;
        input.style.cssText = 'width:100%; height:28px; border-radius:14px; border:1px solid rgba(0, 229, 255, 0.3); background:rgba(15,15,25,0.9); color:#fff; padding:0 15px; font-size:12px; outline:none; box-sizing:border-box; transition: border-color 0.2s;';
        input.onfocus = () => { input.style.borderColor = '#00e5ff'; input.select(); };
        input.onblur = () => { input.style.borderColor = 'rgba(0, 229, 255, 0.3)'; };
        input.onkeydown = (e) => {
            if (e.key === 'Enter') {
                if (window.pywebview && window.pywebview.api) {
                    stopMedia();
                    window.pywebview.api.navigate_to(input.value);
                }
            }
        };
        addressGroup.appendChild(input);

        // Groupe boutons système
        const sysGroup = document.createElement('div');
        sysGroup.style.display = 'flex';
        sysGroup.style.gap = '10px';
        sysGroup.style.alignItems = 'center';

        const btnDock = document.createElement('button');
        btnDock.id = 'jarvis-btn-dock';
        btnDock.textContent = window._isBrowserDocked ? '⚡ DETACHER' : '🔗 ANCRER';
        btnDock.title = 'Ancrer ou Détacher la fenêtre';
        btnDock.style.cssText = 'background:rgba(0, 229, 255, 0.1); border:1px solid #00e5ff; border-radius:4px; color:#00e5ff; cursor:pointer; font-size:11px; font-weight:bold; height:28px; padding:0 12px; transition: all 0.2s;';
        btnDock.onmouseover = () => { btnDock.style.background = '#00e5ff'; btnDock.style.color = '#000'; };
        btnDock.onmouseout = () => { btnDock.style.background = 'rgba(0, 229, 255, 0.1)'; btnDock.style.color = '#00e5ff'; };
        btnDock.onclick = () => {
            if (window.pywebview && window.pywebview.api) {
                window.pywebview.api.toggle_dock();
            }
        };

        const btnClose = document.createElement('button');
        btnClose.textContent = '❌';
        btnClose.title = 'Fermer le navigateur';
        btnClose.style.cssText = 'background:rgba(255,59,48,0.1); border:1px solid #ff3b30; border-radius:4px; color:#ff3b30; cursor:pointer; font-size:12px; width:28px; height:28px; display:flex; align-items:center; justify-content:center; transition: all 0.2s;';
        btnClose.onmouseover = () => { btnClose.style.background = '#ff3b30'; btnClose.style.color = '#fff'; };
        btnClose.onmouseout = () => { btnClose.style.background = 'rgba(255,59,48,0.1)'; btnClose.style.color = '#ff3b30'; };
        btnClose.onclick = () => {
            if (window.pywebview && window.pywebview.api) {
                window.pywebview.api.close_browser();
            }
        };

        sysGroup.appendChild(btnDock);
        sysGroup.appendChild(btnClose);

        tb.appendChild(navGroup);
        tb.appendChild(addressGroup);
        tb.appendChild(sysGroup);
        
        // Injecter dans documentElement pour éviter d'être écrasé par Polymer/SPA ou affecté par les translations du body
        document.documentElement.appendChild(tb);
    }

    // Exécuter et surveiller toutes les 500ms
    try {
        ensureToolbar();
    } catch(e) {
        console.error("Jarvis Toolbar init error:", e);
    }
    if (!window._jarvisToolbarInterval) {
        window._jarvisToolbarInterval = setInterval(() => {
            try {
                ensureToolbar();
            } catch(e) {
                console.error("Jarvis Toolbar interval error:", e);
            }
        }, 500);
    }
})();
"""

# --- PYWEBVIEW INTERFACE JAVASCRIPT API ---
class BrowserAPI:
    def navigate_to(self, query):
        url = format_url_or_search(query)
        global _browser_window
        if _browser_window:
            try:
                _browser_window.evaluate_js(
                    """
                    (function() {
                        const findMedia = (root) => {
                            let list = Array.from(root.querySelectorAll('video, audio'));
                            root.querySelectorAll('*').forEach(el => {
                                try {
                                    if (el.shadowRoot) {
                                        list = list.concat(findMedia(el.shadowRoot));
                                    }
                                } catch(e){}
                            });
                            return list;
                        };
                        findMedia(document).forEach(el => {
                            try {
                                el.pause();
                                el.src = '';
                                el.load();
                            } catch(e){}
                        });
                    })();
                    """
                )
            except Exception:
                pass
            _browser_window.load_url(url)
            
    def toggle_dock(self):
        global _is_docked
        if _is_docked:
            undock_browser()
        else:
            dock_browser()
            
    def close_browser(self):
        close_browser_window()

# --- UTILS & FORMATEUR D'URL ---
def format_url_or_search(query):
    query = query.strip()
    if not query:
        return _default_url
        
    # Vérifier si c'est une adresse IP locale ou distante
    ip_pattern = re.compile(r'^https?://\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}(:\d+)?')
    if ip_pattern.match(query) or query.startswith("localhost") or query.startswith("http://localhost"):
        if not query.startswith("http"):
            return "http://" + query
        return query
        
    # URL classique
    url_pattern = re.compile(
        r'^(https?:\/\/)?' # http:// ou https://
        r'([\w\d\-_]+\.)+[\w\d\-_]+' # domaine
        r'(:\d+)?(\/[^\s]*)?$', re.IGNORECASE
    )
    if url_pattern.match(query):
        if not (query.startswith("http://") or query.startswith("https://")):
            return "https://" + query
        return query
    else:
        # Recherche Google
        return "https://www.google.com/search?q=" + urllib.parse.quote(query)

# --- LOGIQUE D'ANCRAGE & DÉTACHEMENT ---

def trigger_browser(url_or_search=None, main_window_ref=None):
    """Fonction principale de déclenchement du navigateur vocale/manuelle."""
    global _browser_window, _browser_hwnd, _main_webview_window, _is_docked
    
    if main_window_ref:
        _main_webview_window = main_window_ref
        
    target_url = _default_url
    if url_or_search:
        target_url = format_url_or_search(url_or_search)
        
    if _browser_window is not None:
        # Déjà ouvert, on recharge ou remet au premier plan
        print(f"[BROWSER] Navigateur deja ouvert. Navigation vers : {target_url}")
        _browser_window.load_url(target_url)
        if _browser_hwnd:
            ctypes.windll.user32.SetForegroundWindow(_browser_hwnd)
        return
        
    print(f"[BROWSER] Lancement du navigateur securise sur : {target_url}")
    _is_docked = False  # Flottant par défaut au démarrage
    
    # Création de la fenêtre pywebview (avec cadres/bordures standards au démarrage)
    _browser_window = webview.create_window(
        title="Navigateur Securise J.A.R.V.I.S",
        url=target_url,
        width=1024,
        height=768,
        frameless=False,
        background_color="#0a0a0f",
        js_api=BrowserAPI()
    )
    
    # Événements pywebview
    _browser_window.events.loaded += _on_browser_loaded
    _browser_window.events.closed += _on_browser_closed
    
    # Lancement de la recherche d'HWND et du centrage/owner
    threading.Thread(target=_find_hwnd_and_dock_loop, daemon=True).start()

def _find_hwnd_and_dock_loop():
    global _browser_hwnd, _main_hwnd
    
    # Trouver la fenêtre principale J.A.R.V.I.S
    _main_hwnd = ctypes.windll.user32.FindWindowW(None, "J.A.R.V.I.S")
    if not _main_hwnd:
        print("[BROWSER] Fenetre principale J.A.R.V.I.S introuvable !")
        
    # Recherche de la nouvelle fenêtre pendant 5 secondes max
    for _ in range(50):
        hwnd = ctypes.windll.user32.FindWindowW(None, "Navigateur Securise J.A.R.V.I.S")
        if hwnd:
            _browser_hwnd = hwnd
            print(f"[BROWSER] HWND du navigateur trouve : {_browser_hwnd}")
            # Centrer la fenêtre et l'associer en tant que fenêtre possédée (owned)
            center_and_own_browser()
            break
        time.sleep(0.1)

def dock_browser():
    """Ancre le navigateur à droite de l'interface principale."""
    global _is_docked, _browser_hwnd, _main_hwnd, _browser_window
    if not _browser_hwnd or not _main_hwnd:
        return
        
    _is_docked = True
    print("[BROWSER] Ancrage du navigateur dans l'application principale.")
    
    # 1. Attacher à la fenêtre parente J.A.R.V.I.S
    ctypes.windll.user32.SetParent(_browser_hwnd, _main_hwnd)
    
    # 2. Retirer les bordures, menus système, etc., pour en faire une fenêtre enfant (WS_CHILD)
    style = ctypes.windll.user32.GetWindowLongW(_browser_hwnd, GWL_STYLE)
    style = (style & ~WS_POPUP & ~WS_OVERLAPPEDWINDOW) | WS_CHILD
    ctypes.windll.user32.SetWindowLongW(_browser_hwnd, GWL_STYLE, style)
    
    # 3. Mettre à jour la taille et position de l'ancrage
    resize_docked_window()
    
    # 4. Synchroniser l'état avec l'HUD principal
    try:
        from main2 import send_web_broadcast_sync
        send_web_broadcast_sync({"action": "browser_state", "state": "docked"})
    except Exception as e:
        print(f"[BROWSER] Error broadcasting state: {e}")
        
    if _main_webview_window:
        _main_webview_window.evaluate_js("if(window.updateBrowserUIState) { window.updateBrowserUIState('docked'); } else { document.body.classList.add('browser-open'); }")
        
    # 5. Mettre à jour l'étiquette du bouton de détachement dans la barre flottante
    if _browser_window:
        _browser_window.evaluate_js("window._isBrowserDocked = true; if(document.getElementById('jarvis-btn-dock')) document.getElementById('jarvis-btn-dock').innerText = '⚡ DETACHER';")

def center_and_own_browser():
    """Centre le navigateur par rapport à la fenêtre principale et définit JARVIS comme propriétaire (owner)."""
    global _browser_hwnd, _main_hwnd, _browser_window, _is_docked
    if not _browser_hwnd:
        return
        
    _is_docked = False
    print("[BROWSER] Centrage du navigateur et liaison de propriété (owner).")
    
    # 1. Obtenir les dimensions de la fenêtre principale
    rect = RECT()
    if _main_hwnd:
        ctypes.windll.user32.GetWindowRect(_main_hwnd, ctypes.byref(rect))
        main_w = rect.right - rect.left
        main_h = rect.bottom - rect.top
        
        browser_w = 1024
        browser_h = 768
        
        if main_w < browser_w:
            browser_w = int(main_w * 0.9)
        if main_h < browser_h:
            browser_h = int(main_h * 0.9)
            
        x = rect.left + (main_w - browser_w) // 2
        y = rect.top + (main_h - browser_h) // 2
    else:
        x, y, browser_w, browser_h = 150, 150, 1024, 768
        
    # 2. Définir JARVIS comme propriétaire (owner) de la fenêtre du navigateur (GWL_HWNDPARENT = -8)
    if _main_hwnd:
        ctypes.windll.user32.SetWindowLongW(_browser_hwnd, -8, _main_hwnd)
        
    # 3. Positionner au centre de la fenêtre principale
    ctypes.windll.user32.SetWindowPos(
        _browser_hwnd, 0, x, y, browser_w, browser_h,
        SWP_NOZORDER | SWP_FRAMECHANGED | SWP_SHOWWINDOW
    )
    
    # 4. Synchroniser l'état avec l'HUD principal
    try:
        from main2 import send_web_broadcast_sync
        send_web_broadcast_sync({"action": "browser_state", "state": "undocked"})
    except Exception as e:
        print(f"[BROWSER] Error broadcasting state: {e}")
        
    if _main_webview_window:
        _main_webview_window.evaluate_js("if(window.updateBrowserUIState) { window.updateBrowserUIState('undocked'); } else { document.body.classList.remove('browser-open'); }")
        
    # 5. Mettre à jour l'étiquette du bouton de détachement dans la barre flottante
    if _browser_window:
        _browser_window.evaluate_js("window._isBrowserDocked = false; if(document.getElementById('jarvis-btn-dock')) document.getElementById('jarvis-btn-dock').innerText = '🔗 ANCRER';")

def undock_browser():
    """Détache le navigateur dans une fenêtre indépendante avec ses bordures."""
    global _is_docked, _browser_hwnd
    if not _browser_hwnd:
        return
        
    print("[BROWSER] Detachement du navigateur.")
    
    # 1. Retirer la fenêtre parente (SetParent à 0 pour la remettre au niveau du Bureau Windows)
    ctypes.windll.user32.SetParent(_browser_hwnd, 0)
    
    # 2. Restaurer les bordures standards, barre de titre, boutons agrandir/réduire (WS_OVERLAPPEDWINDOW)
    style = ctypes.windll.user32.GetWindowLongW(_browser_hwnd, GWL_STYLE)
    style = (style & ~WS_CHILD) | WS_POPUP | WS_OVERLAPPEDWINDOW | WS_VISIBLE
    ctypes.windll.user32.SetWindowLongW(_browser_hwnd, GWL_STYLE, style)
    
    # 3. Centrer et associer le propriétaire (owner)
    center_and_own_browser()

def resize_docked_window():
    """Recalcule la position et la taille de la fenêtre ancrée à droite."""
    global _is_docked, _browser_hwnd, _main_hwnd
    if not _is_docked or not _browser_hwnd or not _main_hwnd:
        return
        
    rect = RECT()
    ctypes.windll.user32.GetClientRect(_main_hwnd, ctypes.byref(rect))
    main_w = rect.right - rect.left
    main_h = rect.bottom - rect.top
    
    # Le navigateur occupe 45% de la largeur totale à droite
    width = int(main_w * 0.45)
    height = main_h
    x = main_w - width
    y = 0
    
    ctypes.windll.user32.SetWindowPos(
        _browser_hwnd, 0, x, y, width, height,
        SWP_NOZORDER | SWP_NOACTIVATE | SWP_FRAMECHANGED | SWP_SHOWWINDOW
    )

def close_browser_window():
    """Ferme proprement le navigateur et restaure l'interface."""
    global _browser_window
    if _browser_window:
        try:
            _browser_window.evaluate_js(
                """
                (function() {
                    const findMedia = (root) => {
                        let list = Array.from(root.querySelectorAll('video, audio'));
                        root.querySelectorAll('*').forEach(el => {
                            try {
                                if (el.shadowRoot) {
                                    list = list.concat(findMedia(el.shadowRoot));
                                }
                            } catch(e){}
                        });
                        return list;
                    };
                    findMedia(document).forEach(el => {
                        try {
                            el.pause();
                            el.src = '';
                            el.load();
                        } catch(e){}
                    });
                })();
                """
            )
        except Exception:
            pass
        try:
            _browser_window.destroy()
        except Exception:
            pass

def _on_browser_loaded():
    """Injection automatique des scripts à chaque chargement de page."""
    global _browser_window
    if _browser_window:
        print("[BROWSER] Tentative d'injection des scripts...")
        try:
            _browser_window.evaluate_js(ADBLOCK_JS)
            print("[BROWSER] Adblocker injecte.")
        except Exception as e:
            print(f"[BROWSER] Erreur d'injection Adblocker : {e}")
            
        try:
            _browser_window.evaluate_js(TOOLBAR_JS)
            print("[BROWSER] Barre de navigation injectee.")
        except Exception as e:
            print(f"[BROWSER] Erreur d'injection Barre de navigation : {e}")

def _on_browser_closed():
    """Callback de fermeture de la fenêtre du navigateur."""
    global _browser_window, _browser_hwnd, _is_docked
    print("[BROWSER] Fenetre fermee.")
    _browser_window = None
    _browser_hwnd = None
    _is_docked = False
    
    # Synchroniser l'état avec l'HUD principal
    try:
        from main2 import send_web_broadcast_sync
        send_web_broadcast_sync({"action": "browser_state", "state": "closed"})
    except Exception as e:
        print(f"[BROWSER] Error broadcasting state: {e}")
        
    if _main_webview_window:
        _main_webview_window.evaluate_js("if(window.updateBrowserUIState) { window.updateBrowserUIState('closed'); } else { document.body.classList.remove('browser-open'); }")
