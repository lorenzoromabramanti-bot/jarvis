/**
 * iptv_player.ts — J.A.R.V.I.S IPTV & Video Player v2
 * ====================================================
 * Corrections v2 :
 *   - Drag clamp correct (getBoundingClientRect) → plus d'orange à droite
 *   - Audio MKV via serveur HTTP Python + ffmpeg (AAC transcode)
 *   - Sélection de piste audio (multi-track)
 *   - Contrôles fullscreen auto-hide au mouvement souris
 */

// ── Types ─────────────────────────────────────────────────────────────────────
interface IPTVChannel {
  name: string;
  url: string;
  logo: string;
  group: string;
}
interface AudioTrack {
  index: number;
  label: string;
  codec: string;
  lang: string;
  channels: number;
}

// ── State ─────────────────────────────────────────────────────────────────────
let _ws: WebSocket | null = null;
let _hlsInstance: any = null;
let _hlsLoaded = false;
let _hlsLoading = false;
let _channels: IPTVChannel[] = [];
let _currentChannelIdx = -1;
let _isDragging = false;
let _isResizing = false;
let _dragOffX = 0;
let _dragOffY = 0;
let _resizeDir = "";
let _resizeStartX = 0;
let _resizeStartY = 0;
let _resizeStartW = 0;
let _resizeStartH = 0;
let _resizeStartL = 0;
let _resizeStartT = 0;
let _isMinimized = false;
let _currentStreamUrl = "";
let _currentStreamType = "";
let _currentLocalPath = "";
let _audioTracks: AudioTrack[] = [];
let _currentAudioTrack = 0;
let _fsHideTimer: ReturnType<typeof setTimeout> | null = null;

// ── DOM References ─────────────────────────────────────────────────────────
let panel: HTMLDivElement;
let videoEl: HTMLVideoElement;
let playlistDrawer: HTMLDivElement;
let channelsList: HTMLDivElement;
let urlInput: HTMLInputElement;
let fileInput: HTMLInputElement;
let progressBar: HTMLInputElement;
let volumeBar: HTMLInputElement;
let timeDisplay: HTMLSpanElement;
let durationDisplay: HTMLSpanElement;
let playBtn: HTMLButtonElement;
let loadingOverlay: HTMLDivElement;
let errorOverlay: HTMLDivElement;
let groupFilter: HTMLSelectElement;
let audioTrackSelect: HTMLSelectElement;

// ── HLS.js Dynamic Loader ─────────────────────────────────────────────────
function loadHLS(): Promise<void> {
  return new Promise((resolve, reject) => {
    if (_hlsLoaded) { resolve(); return; }
    if (_hlsLoading) {
      const check = setInterval(() => {
        if (_hlsLoaded) { clearInterval(check); resolve(); }
      }, 100);
      return;
    }
    _hlsLoading = true;
    const script = document.createElement("script");
    script.src = "https://cdn.jsdelivr.net/npm/hls.js@latest/dist/hls.min.js";
    script.onload = () => { _hlsLoaded = true; _hlsLoading = false; resolve(); };
    script.onerror = () => { _hlsLoading = false; reject(new Error("HLS.js non chargeable")); };
    document.head.appendChild(script);
  });
}

// ── Panel HTML Template ───────────────────────────────────────────────────
function buildPanelHTML(): string {
  return `
    <div class="iptv-scanlines"></div>
    <div class="iptv-corner iptv-tl"></div>
    <div class="iptv-corner iptv-tr"></div>
    <div class="iptv-corner iptv-bl"></div>
    <div class="iptv-corner iptv-br"></div>

    <!-- Resize handles -->
    <div class="iptv-resize-handle iptv-rh-n"  data-dir="n"></div>
    <div class="iptv-resize-handle iptv-rh-s"  data-dir="s"></div>
    <div class="iptv-resize-handle iptv-rh-e"  data-dir="e"></div>
    <div class="iptv-resize-handle iptv-rh-w"  data-dir="w"></div>
    <div class="iptv-resize-handle iptv-rh-nw" data-dir="nw"></div>
    <div class="iptv-resize-handle iptv-rh-ne" data-dir="ne"></div>
    <div class="iptv-resize-handle iptv-rh-sw" data-dir="sw"></div>
    <div class="iptv-resize-handle iptv-rh-se" data-dir="se"></div>

    <!-- Header / drag bar -->
    <div class="iptv-header" id="iptv-header">
      <div class="iptv-header-drag">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="16" height="16">
          <path d="M5 9h14M5 15h14"/>
        </svg>
      </div>
      <div class="iptv-title-area">
        <span class="iptv-label-tag">◈ JARVIS // MEDIA_PLAYER</span>
        <span class="iptv-current-title" id="iptv-current-title">AUCUN MÉDIA CHARGÉ</span>
      </div>
      <div class="iptv-header-actions">
        <button class="iptv-hbtn" id="iptv-minimize-btn" title="Réduire">⊟</button>
        <button class="iptv-hbtn" id="iptv-fullscreen-btn" title="Plein écran panneau">⛶</button>
        <button class="iptv-hbtn iptv-close-btn" id="iptv-close-btn" title="Fermer">✕</button>
      </div>
    </div>

    <!-- Toolbar -->
    <div class="iptv-toolbar" id="iptv-toolbar">
      <div class="iptv-toolbar-left">
        <button class="iptv-tool-btn" id="iptv-open-file-btn" title="Ouvrir fichier vidéo ou playlist">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="14" height="14">
            <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/>
          </svg>
          OUVRIR
        </button>
        <button class="iptv-tool-btn" id="iptv-playlist-btn" title="Afficher/masquer la playlist">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="14" height="14">
            <path d="M9 18V5l12-2v13M6 21a3 3 0 1 0 0-6 3 3 0 0 0 0 6zM18 19a3 3 0 1 0 0-6 3 3 0 0 0 0 6z"/>
          </svg>
          PLAYLIST
        </button>
      </div>
      <div class="iptv-url-zone">
        <input type="text" id="iptv-url-input" class="iptv-url-input" placeholder="URL stream / lien M3U / IPTV direct..."/>
        <button class="iptv-tool-btn iptv-load-btn" id="iptv-load-url-btn">⏩ CHARGER</button>
      </div>
      <!-- Sélecteur piste audio (visible seulement si multi-pistes) -->
      <div class="iptv-audio-zone hidden" id="iptv-audio-zone">
        <svg viewBox="0 0 24 24" fill="currentColor" width="12" height="12" style="opacity:0.6;flex-shrink:0">
          <path d="M12 3v10.55A4 4 0 1 0 14 17V7h4V3z"/>
        </svg>
        <select id="iptv-audio-select" class="iptv-audio-select" title="Piste audio"></select>
      </div>
      <input type="file" id="iptv-file-input" accept=".mp4,.mkv,.avi,.mov,.wmv,.flv,.webm,.m4v,.ts,.m3u,.m3u8,.xspf,.pls" style="display:none"/>
    </div>

    <!-- Main content area -->
    <div class="iptv-body" id="iptv-body">
      <!-- Playlist drawer -->
      <div class="iptv-playlist-drawer hidden" id="iptv-playlist-drawer">
        <div class="iptv-playlist-header">
          <span>📡 CHAÎNES IPTV</span>
          <select id="iptv-group-filter" class="iptv-group-select">
            <option value="">Tous les groupes</option>
          </select>
        </div>
        <div class="iptv-channels-list" id="iptv-channels-list"></div>
      </div>

      <!-- Video area -->
      <div class="iptv-video-area" id="iptv-video-area">
        <!-- Drop zone -->
        <div class="iptv-drop-zone" id="iptv-drop-zone">
          <div class="iptv-drop-content">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" width="56" height="56">
              <circle cx="12" cy="12" r="10"/>
              <polygon points="10,8 16,12 10,16" fill="currentColor" stroke="none"/>
            </svg>
            <p>GLISSER UN FICHIER VIDÉO / M3U</p>
            <p class="iptv-drop-hint">MP4 · MKV · AVI · M3U · M3U8 · XSPF</p>
          </div>
        </div>

        <!-- Loading -->
        <div class="iptv-loading-overlay hidden" id="iptv-loading-overlay">
          <div class="iptv-loading-spinner"></div>
          <span>CHARGEMENT DU FLUX...</span>
        </div>

        <!-- Error -->
        <div class="iptv-error-overlay hidden" id="iptv-error-overlay">
          <svg viewBox="0 0 24 24" fill="none" stroke="#ff3b30" stroke-width="2" width="36" height="36">
            <circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/>
          </svg>
          <span id="iptv-error-msg">ERREUR DE CHARGEMENT</span>
          <button class="iptv-tool-btn" id="iptv-retry-btn">⟳ RÉESSAYER</button>
        </div>

        <!-- Video -->
        <video id="iptv-video" class="iptv-video" preload="auto"></video>

        <!-- Click-to-play overlay (visible uniquement en pause) -->
        <div class="iptv-play-overlay iptv-paused" id="iptv-play-overlay">
          <div class="iptv-play-icon">▶</div>
        </div>

        <!-- ════ FULLSCREEN CONTROLS OVERLAY ════ -->
        <div class="iptv-fs-overlay hidden" id="iptv-fs-overlay">
          <!-- Top bar -->
          <div class="iptv-fs-topbar">
            <div class="iptv-fs-logo">◈ JARVIS // MEDIA</div>
            <span class="iptv-fs-title-text" id="iptv-fs-title-text">—</span>
          </div>
          <!-- Bottom bar -->
          <div class="iptv-fs-bottombar">
            <div class="iptv-fs-progress-row">
              <span class="iptv-fs-time" id="iptv-fs-time-cur">0:00</span>
              <input type="range" id="iptv-fs-progress" class="iptv-fs-progress-bar" min="0" max="100" value="0" step="0.1"/>
              <span class="iptv-fs-time" id="iptv-fs-time-dur">--:--</span>
            </div>
            <div class="iptv-fs-controls-row">
              <button class="iptv-fs-btn iptv-fs-play-btn" id="iptv-fs-play-btn">▶</button>
              <button class="iptv-fs-btn" id="iptv-fs-mute-btn">🔊</button>
              <input type="range" id="iptv-fs-volume" class="iptv-fs-vol-bar" min="0" max="100" value="80"/>
              <div class="iptv-fs-badge" id="iptv-fs-badge">DIRECT</div>
              <div style="flex:1"></div>
              <button class="iptv-fs-btn iptv-fs-exit-btn" id="iptv-fs-exit-btn">⛶ QUITTER PLEIN ÉCRAN</button>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Controls bar -->
    <div class="iptv-controls" id="iptv-controls">
      <div class="iptv-progress-row">
        <span class="iptv-time" id="iptv-time-current">0:00</span>
        <input type="range" id="iptv-progress" class="iptv-progress-bar" min="0" max="100" value="0" step="0.1"/>
        <span class="iptv-time" id="iptv-time-duration">--:--</span>
      </div>
      <div class="iptv-controls-row">
        <div class="iptv-ctrl-left">
          <button class="iptv-ctrl-btn" id="iptv-prev-btn" title="Précédent">⏮</button>
          <button class="iptv-ctrl-btn iptv-play-pause" id="iptv-play-btn" title="Lecture / Pause">▶</button>
          <button class="iptv-ctrl-btn" id="iptv-next-btn" title="Suivant">⏭</button>
          <button class="iptv-ctrl-btn" id="iptv-stop-btn" title="Arrêter">⏹</button>
        </div>
        <div class="iptv-ctrl-center">
          <div class="iptv-stream-badge" id="iptv-stream-badge">STANDBY</div>
        </div>
        <div class="iptv-ctrl-right">
          <svg viewBox="0 0 24 24" fill="currentColor" width="13" height="13" style="opacity:0.5">
            <path d="M11 5L6 9H2v6h4l5 4V5zM19.07 4.93a10 10 0 0 1 0 14.14M15.54 8.46a5 5 0 0 1 0 7.07"/>
          </svg>
          <input type="range" id="iptv-volume" class="iptv-volume-bar" min="0" max="100" value="80"/>
          <button class="iptv-ctrl-btn" id="iptv-mute-btn" title="Muet">🔊</button>
          <button class="iptv-ctrl-btn" id="iptv-fs-video-btn" title="Plein écran vidéo">⛶</button>
        </div>
      </div>
    </div>

    <!-- Footer -->
    <div class="iptv-footer">
      <span>JARVIS_HUD_MEDIA_V2.0</span>
      <span id="iptv-footer-info">◈ EN ATTENTE</span>
    </div>
  `;
}

// ── CSS Injection ──────────────────────────────────────────────────────────
function injectIPTVStyles(): void {
  if (document.getElementById("iptv-styles")) return;
  const style = document.createElement("style");
  style.id = "iptv-styles";
  style.textContent = `
    /* ════════════════════════════════════════════════════════════
       JARVIS IPTV PLAYER — Iron Man HUD v2
    ════════════════════════════════════════════════════════════ */

    .iptv-panel {
      position: fixed;
      top: 60px; left: 50%;
      transform: translateX(-50%);
      width: 900px; min-width: 340px; min-height: 280px;
      background: rgba(5, 5, 8, 0.97);
      border: 1px solid rgba(255, 138, 26, 0.45);
      box-shadow: 0 0 40px rgba(255, 138, 26, 0.2), 0 0 60px rgba(255, 138, 26, 0.08);
      border-radius: 4px; z-index: 500;
      display: flex; flex-direction: column;
      overflow: hidden;
      font-family: 'Courier New', monospace; user-select: none;
    }
    .iptv-panel:not(.hidden) { display: flex; }
    .iptv-panel.hidden { display: none !important; }
    .iptv-panel.iptv-minimized .iptv-toolbar,
    .iptv-panel.iptv-minimized .iptv-body,
    .iptv-panel.iptv-minimized .iptv-controls,
    .iptv-panel.iptv-minimized .iptv-footer { display: none !important; }

    .iptv-scanlines {
      position: absolute; inset: 0; pointer-events: none; z-index: 1;
      background: repeating-linear-gradient(0deg, transparent, transparent 2px, rgba(255,138,26,0.012) 2px, rgba(255,138,26,0.012) 4px);
    }

    .iptv-corner { position: absolute; width: 12px; height: 12px; z-index: 2; pointer-events: none; }
    .iptv-tl { top:0; left:0;    border-top: 2px solid rgba(255,138,26,0.7); border-left: 2px solid rgba(255,138,26,0.7); }
    .iptv-tr { top:0; right:0;   border-top: 2px solid rgba(255,138,26,0.7); border-right: 2px solid rgba(255,138,26,0.7); }
    .iptv-bl { bottom:0; left:0; border-bottom: 2px solid rgba(255,138,26,0.7); border-left: 2px solid rgba(255,138,26,0.7); }
    .iptv-br { bottom:0; right:0;border-bottom: 2px solid rgba(255,138,26,0.7); border-right: 2px solid rgba(255,138,26,0.7); }

    .iptv-resize-handle { position: absolute; z-index: 10; }
    .iptv-rh-n  { top:-3px; left:12px; right:12px; height:6px; cursor:n-resize; }
    .iptv-rh-s  { bottom:-3px; left:12px; right:12px; height:6px; cursor:s-resize; }
    .iptv-rh-e  { top:12px; bottom:12px; right:-3px; width:6px; cursor:e-resize; }
    .iptv-rh-w  { top:12px; bottom:12px; left:-3px; width:6px; cursor:w-resize; }
    .iptv-rh-nw { top:-3px; left:-3px; width:12px; height:12px; cursor:nw-resize; }
    .iptv-rh-ne { top:-3px; right:-3px; width:12px; height:12px; cursor:ne-resize; }
    .iptv-rh-sw { bottom:-3px; left:-3px; width:12px; height:12px; cursor:sw-resize; }
    .iptv-rh-se { bottom:-3px; right:-3px; width:12px; height:12px; cursor:se-resize; }

    .iptv-header {
      display:flex; align-items:center; gap:10px; padding:8px 12px;
      background: rgba(255,138,26,0.07);
      border-bottom: 1px solid rgba(255,138,26,0.25);
      cursor: grab; flex-shrink:0; position:relative; z-index:3;
    }
    .iptv-header:active { cursor: grabbing; }
    .iptv-header-drag { color: rgba(255,138,26,0.5); flex-shrink:0; }
    .iptv-title-area { flex:1; min-width:0; display:flex; flex-direction:column; gap:1px; }
    .iptv-label-tag { font-size:8px; letter-spacing:3px; color:rgba(255,138,26,0.6); text-transform:uppercase; }
    .iptv-current-title {
      font-size:11px; font-weight:bold; color:#ff8a1a;
      letter-spacing:1px; text-transform:uppercase;
      white-space:nowrap; overflow:hidden; text-overflow:ellipsis;
    }
    .iptv-header-actions { display:flex; gap:4px; flex-shrink:0; }
    .iptv-hbtn {
      background:none; border:1px solid rgba(255,138,26,0.3); color:rgba(255,138,26,0.7);
      padding:3px 7px; border-radius:2px; cursor:pointer; font-size:11px;
      transition:all 0.15s ease; line-height:1;
    }
    .iptv-hbtn:hover { background:rgba(255,138,26,0.15); color:#ff8a1a; border-color:#ff8a1a; }
    .iptv-close-btn:hover { background:rgba(255,59,48,0.15); color:#ff3b30; border-color:#ff3b30; }

    .iptv-toolbar {
      display:flex; align-items:center; gap:8px; padding:6px 10px;
      border-bottom:1px solid rgba(255,138,26,0.15);
      background:rgba(255,138,26,0.03); flex-shrink:0; flex-wrap:wrap;
    }
    .iptv-toolbar-left { display:flex; gap:6px; flex-shrink:0; }
    .iptv-url-zone { display:flex; gap:6px; flex:1; min-width:200px; }
    .iptv-url-input {
      flex:1; background:rgba(255,138,26,0.05); border:1px solid rgba(255,138,26,0.25);
      color:rgba(255,138,26,0.9); padding:5px 10px; font-family:'Courier New',monospace;
      font-size:10px; border-radius:2px; outline:none;
      transition:border-color 0.2s ease;
    }
    .iptv-url-input::placeholder { color:rgba(255,138,26,0.3); }
    .iptv-url-input:focus { border-color:#ff8a1a; box-shadow:0 0 8px rgba(255,138,26,0.2); }
    .iptv-tool-btn {
      background:rgba(255,138,26,0.08); border:1px solid rgba(255,138,26,0.3);
      color:#ff8a1a; padding:5px 10px; font-family:'Courier New',monospace;
      font-size:9px; letter-spacing:1px; border-radius:2px; cursor:pointer;
      transition:all 0.15s ease; white-space:nowrap; display:flex; align-items:center; gap:4px;
    }
    .iptv-tool-btn:hover { background:rgba(255,138,26,0.2); box-shadow:0 0 10px rgba(255,138,26,0.2); }
    .iptv-load-btn { font-weight:bold; }

    /* Audio track selector */
    .iptv-audio-zone {
      display:flex; align-items:center; gap:6px; flex-shrink:0;
    }
    .iptv-audio-zone.hidden { display:none !important; }
    .iptv-audio-select {
      background:rgba(255,138,26,0.05); border:1px solid rgba(255,138,26,0.3);
      color:#ff8a1a; font-family:'Courier New',monospace; font-size:9px;
      padding:4px 6px; border-radius:2px; outline:none; cursor:pointer;
      max-width:180px;
    }
    .iptv-audio-select option { background:#0a0a10; }

    .iptv-body { display:flex; flex:1; overflow:hidden; position:relative; min-height:0; }

    .iptv-playlist-drawer {
      width:220px; min-width:180px; max-width:300px; flex-shrink:0;
      background:rgba(0,0,0,0.5); border-right:1px solid rgba(255,138,26,0.2);
      display:flex; flex-direction:column; overflow:hidden;
    }
    .iptv-playlist-drawer.hidden { display:none; }
    .iptv-playlist-header {
      padding:8px; font-size:9px; color:rgba(255,138,26,0.7); letter-spacing:2px;
      border-bottom:1px solid rgba(255,138,26,0.15); flex-shrink:0;
      display:flex; flex-direction:column; gap:6px;
    }
    .iptv-group-select {
      background:rgba(255,138,26,0.05); border:1px solid rgba(255,138,26,0.2);
      color:rgba(255,138,26,0.8); font-family:'Courier New',monospace;
      font-size:9px; padding:3px 5px; border-radius:2px; outline:none;
    }
    .iptv-channels-list {
      flex:1; overflow-y:auto; padding:4px;
      scrollbar-width:thin; scrollbar-color:rgba(255,138,26,0.3) transparent;
    }
    .iptv-channel-item {
      display:flex; align-items:center; gap:8px; padding:6px 8px;
      border-radius:2px; cursor:pointer; transition:all 0.15s ease;
      border:1px solid transparent; margin-bottom:2px;
    }
    .iptv-channel-item:hover { background:rgba(255,138,26,0.1); border-color:rgba(255,138,26,0.2); }
    .iptv-channel-item.active {
      background:rgba(255,138,26,0.2); border-color:rgba(255,138,26,0.5);
      box-shadow:0 0 8px rgba(255,138,26,0.15);
    }
    .iptv-channel-logo {
      width:28px; height:28px; border-radius:2px; object-fit:contain;
      background:rgba(255,138,26,0.05); flex-shrink:0;
    }
    .iptv-channel-name {
      font-size:9px; color:rgba(255,138,26,0.85); letter-spacing:0.5px;
      white-space:nowrap; overflow:hidden; text-overflow:ellipsis; flex:1;
    }
    .iptv-channel-group { font-size:7px; color:rgba(255,138,26,0.4); text-transform:uppercase; }

    .iptv-video-area {
      flex:1; position:relative; background:#000; overflow:hidden;
      display:flex; align-items:center; justify-content:center; min-width:0;
    }
    .iptv-video { width:100%; height:100%; object-fit:contain; display:block; }

    .iptv-drop-zone {
      position:absolute; inset:0; z-index:5;
      display:flex; align-items:center; justify-content:center;
      background:rgba(5,5,8,0.95); border:2px dashed rgba(255,138,26,0.3);
      transition:all 0.2s ease;
    }
    .iptv-drop-zone.drag-over {
      border-color:#ff8a1a; background:rgba(255,138,26,0.05);
      box-shadow:inset 0 0 40px rgba(255,138,26,0.1);
    }
    .iptv-video-loaded .iptv-drop-zone { display:none; }
    .iptv-drop-content {
      text-align:center; color:rgba(255,138,26,0.5);
      display:flex; flex-direction:column; align-items:center; gap:15px;
    }
    .iptv-drop-content p { font-size:11px; letter-spacing:2px; margin:0; }
    .iptv-drop-hint { font-size:9px !important; color:rgba(255,138,26,0.3) !important; }

    .iptv-loading-overlay {
      position:absolute; inset:0; z-index:8;
      display:flex; flex-direction:column; align-items:center; justify-content:center; gap:15px;
      background:rgba(5,5,8,0.85); color:rgba(255,138,26,0.8);
      font-size:10px; letter-spacing:3px;
    }
    .iptv-loading-overlay.hidden { display:none !important; }
    .iptv-loading-spinner {
      width:40px; height:40px; border:2px solid rgba(255,138,26,0.2);
      border-top-color:#ff8a1a; border-radius:50%;
      animation:iptv-spin 0.8s linear infinite;
    }
    @keyframes iptv-spin { to { transform:rotate(360deg); } }

    .iptv-error-overlay {
      position:absolute; inset:0; z-index:8;
      display:flex; flex-direction:column; align-items:center; justify-content:center; gap:12px;
      background:rgba(5,5,8,0.85); color:#ff3b30;
      font-size:10px; letter-spacing:2px;
    }
    .iptv-error-overlay.hidden { display:none !important; }
    #iptv-error-msg { max-width:320px; text-align:center; line-height:1.5; }

    /* ── Play overlay (uniquement en mode PAUSE) ── */
    .iptv-play-overlay {
      position:absolute; inset:0; z-index:6;
      display:flex; align-items:center; justify-content:center;
      cursor:pointer; opacity:0; transition:opacity 0.25s ease;
      pointer-events:none;
    }
    .iptv-video-area:hover .iptv-play-overlay.iptv-paused {
      opacity:1; pointer-events:auto;
    }
    /* En plein écran standard/webkit */
    :fullscreen .iptv-play-overlay { display:none !important; }
    :-webkit-full-screen .iptv-play-overlay { display:none !important; }

    .iptv-play-icon {
      font-size:56px; color:rgba(255,138,26,0.85);
      text-shadow:0 0 30px rgba(255,138,26,0.6), 0 0 60px rgba(255,138,26,0.3);
      transition:transform 0.15s ease;
    }
    .iptv-play-overlay:hover .iptv-play-icon { transform:scale(1.15); color:#ff8a1a; }

    /* ════ FULLSCREEN OVERLAY CONTROLS ════ */
    .iptv-fs-overlay {
      position:absolute; inset:0; z-index:20;
      display:flex; flex-direction:column; justify-content:space-between;
      pointer-events:none;
      opacity:0; transition:opacity 0.3s ease;
    }
    .iptv-fs-overlay.iptv-fs-visible {
      opacity:1; pointer-events:auto;
    }
    .iptv-fs-overlay.hidden { display:none !important; }

    /* Dégradés pour la lisibilité du texte */
    .iptv-fs-topbar {
      background:linear-gradient(to bottom, rgba(0,0,0,0.75) 0%, transparent 100%);
      padding:16px 20px 40px; display:flex; align-items:center; gap:12px;
    }
    .iptv-fs-bottombar {
      background:linear-gradient(to top, rgba(0,0,0,0.85) 0%, transparent 100%);
      padding:40px 20px 16px;
    }
    .iptv-fs-logo {
      font-size:9px; letter-spacing:3px; color:rgba(255,138,26,0.7); flex-shrink:0;
    }
    .iptv-fs-title-text {
      flex:1; font-size:13px; font-weight:bold; color:#ff8a1a;
      letter-spacing:1px; text-transform:uppercase;
      white-space:nowrap; overflow:hidden; text-overflow:ellipsis;
    }
    .iptv-fs-btn {
      background:rgba(255,138,26,0.12); border:1px solid rgba(255,138,26,0.4);
      color:#ff8a1a; padding:6px 14px; font-family:'Courier New',monospace;
      font-size:10px; letter-spacing:1px; border-radius:3px; cursor:pointer;
      transition:all 0.15s ease; white-space:nowrap; flex-shrink:0;
    }
    .iptv-fs-btn:hover { background:rgba(255,138,26,0.3); box-shadow:0 0 12px rgba(255,138,26,0.3); }
    .iptv-fs-play-btn { font-size:18px; padding:6px 16px; }
    .iptv-fs-exit-btn { border-color:rgba(255,59,48,0.4); color:#ff6b60; }
    .iptv-fs-exit-btn:hover { background:rgba(255,59,48,0.2); box-shadow:0 0 12px rgba(255,59,48,0.3); }

    .iptv-fs-progress-row {
      display:flex; align-items:center; gap:10px; margin-bottom:10px;
    }
    .iptv-fs-controls-row {
      display:flex; align-items:center; gap:10px;
    }
    .iptv-fs-time { font-size:11px; color:rgba(255,138,26,0.8); white-space:nowrap; min-width:40px; }
    .iptv-fs-progress-bar {
      -webkit-appearance:none; appearance:none; flex:1;
      height:4px; border-radius:2px; background:rgba(255,138,26,0.25); cursor:pointer; outline:none;
    }
    .iptv-fs-vol-bar {
      -webkit-appearance:none; appearance:none;
      height:4px; width:90px; border-radius:2px; background:rgba(255,138,26,0.25); cursor:pointer; outline:none;
    }
    .iptv-fs-progress-bar::-webkit-slider-thumb,
    .iptv-fs-vol-bar::-webkit-slider-thumb {
      -webkit-appearance:none; width:14px; height:14px;
      border-radius:50%; background:#ff8a1a;
      box-shadow:0 0 8px rgba(255,138,26,0.7); cursor:pointer;
    }
    .iptv-fs-badge {
      font-size:9px; letter-spacing:2px; color:rgba(255,138,26,0.6);
      background:rgba(255,138,26,0.08); border:1px solid rgba(255,138,26,0.2);
      padding:4px 10px; border-radius:2px;
    }

    /* Fullscreen : masquer le curseur souris après inactivité */
    :fullscreen.iptv-video-area, :fullscreen .iptv-video-area,
    :-webkit-full-screen.iptv-video-area, :-webkit-full-screen .iptv-video-area {
      cursor: none !important;
    }
    :fullscreen.iptv-video-area.iptv-fs-active, :fullscreen .iptv-video-area.iptv-fs-active,
    :-webkit-full-screen.iptv-video-area.iptv-fs-active, :-webkit-full-screen .iptv-video-area.iptv-fs-active {
      cursor: default !important;
    }

    /* Assurer que la zone vidéo prend tout l'écran et garde sa disposition relative en fullscreen */
    #iptv-video-area:fullscreen, #iptv-video-area:-webkit-full-screen {
      width: 100vw !important;
      height: 100vh !important;
      background: #000 !important;
      display: flex !important;
      align-items: center !important;
      justify-content: center !important;
      position: relative !important;
    }
    :fullscreen #iptv-video-area, :-webkit-full-screen #iptv-video-area {
      flex: 1 !important;
      width: 100% !important;
      height: 100% !important;
      position: relative !important;
    }

    /* ── Main controls ── */
    .iptv-controls {
      padding:6px 10px; background:rgba(0,0,0,0.6);
      border-top:1px solid rgba(255,138,26,0.2); flex-shrink:0;
    }
    .iptv-progress-row { display:flex; align-items:center; gap:8px; margin-bottom:6px; }
    .iptv-time { font-size:9px; color:rgba(255,138,26,0.7); white-space:nowrap; min-width:32px; }
    .iptv-progress-bar, .iptv-volume-bar {
      -webkit-appearance:none; appearance:none;
      height:3px; border-radius:2px; cursor:pointer; outline:none;
      background:rgba(255,138,26,0.2);
    }
    .iptv-progress-bar { flex:1; }
    .iptv-volume-bar { width:70px; }
    .iptv-progress-bar::-webkit-slider-thumb,
    .iptv-volume-bar::-webkit-slider-thumb {
      -webkit-appearance:none; width:10px; height:10px;
      border-radius:50%; background:#ff8a1a;
      box-shadow:0 0 6px rgba(255,138,26,0.6); cursor:pointer;
    }
    .iptv-controls-row { display:flex; align-items:center; justify-content:space-between; gap:10px; }
    .iptv-ctrl-left, .iptv-ctrl-right, .iptv-ctrl-center { display:flex; align-items:center; gap:6px; }
    .iptv-ctrl-btn {
      background:none; border:1px solid rgba(255,138,26,0.25); color:rgba(255,138,26,0.8);
      padding:4px 8px; border-radius:2px; cursor:pointer; font-size:12px;
      transition:all 0.15s ease; line-height:1;
    }
    .iptv-ctrl-btn:hover { background:rgba(255,138,26,0.15); color:#ff8a1a; border-color:#ff8a1a; }
    .iptv-play-pause { font-size:14px; padding:4px 10px; }
    .iptv-stream-badge {
      font-size:8px; letter-spacing:2px; color:rgba(255,138,26,0.5);
      background:rgba(255,138,26,0.05); border:1px solid rgba(255,138,26,0.15);
      padding:3px 8px; border-radius:2px;
    }
    .iptv-stream-badge.live {
      color:#ff3b30; border-color:rgba(255,59,48,0.4);
      background:rgba(255,59,48,0.08);
      animation:iptv-live-pulse 1.5s ease-in-out infinite;
    }
    @keyframes iptv-live-pulse {
      0%,100% { box-shadow:0 0 4px rgba(255,59,48,0.3); }
      50%      { box-shadow:0 0 12px rgba(255,59,48,0.6); }
    }
    .iptv-footer {
      display:flex; justify-content:space-between; padding:4px 12px;
      font-size:8px; color:rgba(255,138,26,0.35); letter-spacing:2px;
      border-top:1px solid rgba(255,138,26,0.1); flex-shrink:0;
    }
  `;
  document.head.appendChild(style);
}

// ── Time Formatter ─────────────────────────────────────────────────────────
function formatTime(s: number): string {
  if (!isFinite(s) || isNaN(s)) return "--:--";
  const h = Math.floor(s / 3600), m = Math.floor((s % 3600) / 60), sec = Math.floor(s % 60);
  if (h > 0) return `${h}:${String(m).padStart(2,"0")}:${String(sec).padStart(2,"0")}`;
  return `${m}:${String(sec).padStart(2,"0")}`;
}

// ── HLS Attach ─────────────────────────────────────────────────────────────
async function attachHLS(url: string): Promise<void> {
  try {
    await loadHLS();
    const Hls = (window as any).Hls;
    if (!Hls) throw new Error("HLS.js indisponible");
    if (_hlsInstance) { _hlsInstance.destroy(); _hlsInstance = null; }
    if (Hls.isSupported()) {
      _hlsInstance = new Hls({ enableWorker: true, lowLatencyMode: true });
      _hlsInstance.loadSource(url);
      _hlsInstance.attachMedia(videoEl);
      _hlsInstance.on(Hls.Events.MANIFEST_PARSED, () => {
        videoEl.play().catch(() => {});
        hideLoading(); showVideoArea(); updateStreamBadge("HLS LIVE", true);
      });
      _hlsInstance.on(Hls.Events.ERROR, (_: any, d: any) => {
        if (d.fatal) showErrorOverlay("Erreur HLS : " + (d.details || "inconnu"));
      });
    } else if (videoEl.canPlayType("application/vnd.apple.mpegurl")) {
      videoEl.src = url;
      videoEl.play().catch(() => {});
      hideLoading(); showVideoArea();
    }
  } catch (err) {
    showErrorOverlay("Impossible de charger HLS.js");
  }
}

// ── Video Area State ───────────────────────────────────────────────────────
function showVideoArea(): void {
  document.getElementById("iptv-video-area")?.classList.add("iptv-video-loaded");
  hideLoading(); hideError();
}
function showLoading(): void { loadingOverlay?.classList.remove("hidden"); hideError(); }
function hideLoading(): void { loadingOverlay?.classList.add("hidden"); }
function showErrorOverlay(msg: string): void {
  hideLoading(); errorOverlay?.classList.remove("hidden");
  const el = document.getElementById("iptv-error-msg");
  if (el) el.textContent = msg;
}
function hideError(): void { errorOverlay?.classList.add("hidden"); }

function updateStreamBadge(text: string, live = false): void {
  const b = document.getElementById("iptv-stream-badge");
  if (b) { b.textContent = text; b.classList.toggle("live", live); }
  const fb = document.getElementById("iptv-fs-badge");
  if (fb) { fb.textContent = text; fb.classList.toggle("live", live); }
}

function updateTitle(name: string): void {
  const el = document.getElementById("iptv-current-title");
  if (el) el.textContent = name.toUpperCase();
  const fi = document.getElementById("iptv-footer-info");
  if (fi) fi.textContent = "◈ " + name.toUpperCase();
  const ft = document.getElementById("iptv-fs-title-text");
  if (ft) ft.textContent = name.toUpperCase();
}

// ── Stream Loader ──────────────────────────────────────────────────────────
async function loadStream(url: string, type: string, name: string): Promise<void> {
  if (!videoEl) return;
  _currentStreamUrl = url;
  _currentStreamType = type;
  showLoading(); updateTitle(name);

  if (_hlsInstance) { _hlsInstance.destroy(); _hlsInstance = null; }
  videoEl.pause();
  videoEl.removeAttribute("src");
  videoEl.load();

  if (type === "hls" || url.includes(".m3u8")) {
    await attachHLS(url); return;
  }

  videoEl.src = url;
  videoEl.load();
  showVideoArea();
  try {
    await videoEl.play();
    updateStreamBadge(type.toUpperCase() || "DIRECT");
  } catch {
    updateStreamBadge("EN ATTENTE");
  }
}

// ── Audio Track UI ─────────────────────────────────────────────────────────
function updateAudioTracks(tracks: AudioTrack[]): void {
  _audioTracks = tracks;
  const zone = document.getElementById("iptv-audio-zone");
  const sel  = document.getElementById("iptv-audio-select") as HTMLSelectElement;
  if (!zone || !sel) return;

  if (tracks.length <= 1) {
    zone.classList.add("hidden"); return;
  }
  zone.classList.remove("hidden");
  sel.innerHTML = "";
  tracks.forEach(t => {
    const opt = document.createElement("option");
    opt.value = String(t.index);
    opt.textContent = `🎵 ${t.label}`;
    sel.appendChild(opt);
  });
  sel.value = String(_currentAudioTrack);
}

// ── Playlist Rendering ─────────────────────────────────────────────────────
function renderPlaylist(channels: IPTVChannel[]): void {
  _channels = channels;
  if (!channelsList) return;
  const groups = Array.from(new Set(channels.map(c => c.group).filter(Boolean)));
  if (groupFilter) {
    groupFilter.innerHTML = '<option value="">Tous les groupes</option>';
    groups.forEach(g => { const o = document.createElement("option"); o.value = g; o.textContent = g; groupFilter.appendChild(o); });
  }
  renderFilteredPlaylist(channels);
  playlistDrawer?.classList.remove("hidden");
}

function renderFilteredPlaylist(channels: IPTVChannel[]): void {
  if (!channelsList) return;
  channelsList.innerHTML = "";
  channels.forEach(ch => {
    const globalIdx = _channels.indexOf(ch);
    const item = document.createElement("div");
    item.className = "iptv-channel-item" + (globalIdx === _currentChannelIdx ? " active" : "");
    item.dataset.idx = String(globalIdx);
    item.innerHTML = `
      <img class="iptv-channel-logo" src="${ch.logo||""}" alt="" onerror="this.style.display='none'"/>
      <div style="flex:1;min-width:0;">
        <div class="iptv-channel-name">${ch.name}</div>
        ${ch.group ? `<div class="iptv-channel-group">${ch.group}</div>` : ""}
      </div>`;
    item.addEventListener("click", () => {
      _currentChannelIdx = globalIdx;
      loadStream(ch.url, detectStreamType(ch.url), ch.name);
      document.querySelectorAll(".iptv-channel-item").forEach(e => e.classList.remove("active"));
      item.classList.add("active");
    });
    channelsList.appendChild(item);
  });
}

function detectStreamType(url: string): string {
  const u = url.toLowerCase().split("?")[0];
  if (u.endsWith(".m3u8")) return "hls";
  if (u.endsWith(".mpd"))  return "dash";
  if (u.match(/\.(mp4|mkv|avi|mov|webm|m4v)$/)) return "mp4";
  return "direct";
}

// ── Drag Logic (FIX: getBoundingClientRect pour clamp précis) ──────────────
function initDrag(): void {
  document.getElementById("iptv-header")!.addEventListener("mousedown", (e: MouseEvent) => {
    if ((e.target as HTMLElement).closest(".iptv-header-actions")) return;
    _isDragging = true;
    const rect = panel.getBoundingClientRect();
    _dragOffX = e.clientX - rect.left;
    _dragOffY = e.clientY - rect.top;
    panel.style.transform = "none";
    panel.style.left = rect.left + "px";
    panel.style.top  = rect.top  + "px";
    e.preventDefault();
  });
}

// ── Resize Logic ───────────────────────────────────────────────────────────
function initResize(): void {
  document.querySelectorAll(".iptv-resize-handle").forEach(h => {
    (h as HTMLElement).addEventListener("mousedown", (e: MouseEvent) => {
      _isResizing = true;
      _resizeDir  = (h as HTMLElement).dataset.dir || "";
      _resizeStartX = e.clientX; _resizeStartY = e.clientY;
      const r = panel.getBoundingClientRect();
      _resizeStartW = r.width; _resizeStartH = r.height;
      _resizeStartL = r.left;  _resizeStartT = r.top;
      panel.style.transform = "none";
      panel.style.left = r.left + "px"; panel.style.top = r.top + "px";
      e.preventDefault(); e.stopPropagation();
    });
  });
}

function onMouseMove(e: MouseEvent): void {
  if (_isDragging) {
    let newLeft = e.clientX - _dragOffX;
    let newTop  = e.clientY - _dragOffY;
    // FIX: Utiliser getBoundingClientRect pour la largeur réelle du panneau
    // Évite que l'ombre orange déborde sur le bord droit de l'écran
    const rect = panel.getBoundingClientRect();
    const maxLeft = Math.max(0, window.innerWidth  - rect.width);
    const maxTop  = Math.max(0, window.innerHeight - 40);
    newLeft = Math.max(0, Math.min(maxLeft, newLeft));
    newTop  = Math.max(0, Math.min(maxTop,  newTop));
    panel.style.left = newLeft + "px";
    panel.style.top  = newTop  + "px";
  }
  if (_isResizing) {
    const dx = e.clientX - _resizeStartX;
    const dy = e.clientY - _resizeStartY;
    const MIN_W = 340, MIN_H = 200;
    let w = _resizeStartW, h = _resizeStartH, l = _resizeStartL, t = _resizeStartT;
    if (_resizeDir.includes("e"))  w = Math.max(MIN_W, _resizeStartW + dx);
    if (_resizeDir.includes("s"))  h = Math.max(MIN_H, _resizeStartH + dy);
    if (_resizeDir.includes("w")) { w = Math.max(MIN_W, _resizeStartW - dx); l = _resizeStartL + (_resizeStartW - w); }
    if (_resizeDir.includes("n")) { h = Math.max(MIN_H, _resizeStartH - dy); t = _resizeStartT + (_resizeStartH - h); }
    panel.style.width  = w + "px"; panel.style.height = h + "px";
    panel.style.left   = l + "px"; panel.style.top    = t + "px";
  }
}

function onMouseUp(): void { _isDragging = false; _isResizing = false; }

// ── updatePlayPauseBtn (sync overlay play/pause + FS controls) ─────────────
function updatePlayPauseBtn(): void {
  if (!playBtn || !videoEl) return;
  const paused = videoEl.paused;
  playBtn.textContent = paused ? "▶" : "⏸";

  // Overlay click-to-play : visible uniquement en pause
  document.getElementById("iptv-play-overlay")?.classList.toggle("iptv-paused", paused);

  // Bouton FS play
  const fsPlay = document.getElementById("iptv-fs-play-btn") as HTMLButtonElement;
  if (fsPlay) fsPlay.textContent = paused ? "▶" : "⏸";
}

function isFullscreenActive(): boolean {
  return !!(
    document.fullscreenElement ||
    (document as any).webkitFullscreenElement ||
    (document as any).mozFullScreenElement ||
    (document as any).msFullscreenElement
  );
}

function exitFullscreenAll(): void {
  if (document.exitFullscreen) {
    document.exitFullscreen().catch(() => {});
  } else if ((document as any).webkitExitFullscreen) {
    (document as any).webkitExitFullscreen();
  } else if ((document as any).mozCancelFullScreen) {
    (document as any).mozCancelFullScreen();
  } else if ((document as any).msExitFullscreen) {
    (document as any).msExitFullscreen();
  }
}

// ── Fullscreen Controls (auto-hide) ────────────────────────────────────────
function initFullscreenControls(): void {
  const videoArea = document.getElementById("iptv-video-area")!;
  const fsOverlay = document.getElementById("iptv-fs-overlay")!;
  if (!fsOverlay || !videoArea) return;

  const showFSControls = () => {
    if (!isFullscreenActive()) return;

    // Retirer hidden pour rendre l'overlay visible
    fsOverlay.classList.remove("hidden");
    fsOverlay.classList.add("iptv-fs-visible");
    videoArea.classList.add("iptv-fs-active"); // curseur visible

    // Reset du timer d'auto-hide (3 secondes d'inactivité → masquer)
    if (_fsHideTimer) clearTimeout(_fsHideTimer);
    _fsHideTimer = setTimeout(() => {
      fsOverlay.classList.remove("iptv-fs-visible");
      videoArea.classList.remove("iptv-fs-active");
    }, 3000);
  };

  // Mouvements de souris sur le document entier pour afficher les contrôles en plein écran
  document.addEventListener("mousemove", () => {
    if (isFullscreenActive()) {
      showFSControls();
    }
  });

  // Mouvements également sur la zone vidéo et l'overlay spécifiquement
  videoArea.addEventListener("mousemove", showFSControls);
  fsOverlay.addEventListener("mousemove", showFSControls);

  // Quitter fullscreen via boutons FS
  document.getElementById("iptv-fs-exit-top")?.addEventListener("click", exitFullscreenAll);
  document.getElementById("iptv-fs-exit-btn")?.addEventListener("click", exitFullscreenAll);

  // Play/Pause FS
  document.getElementById("iptv-fs-play-btn")?.addEventListener("click", () => {
    if (!videoEl) return;
    if (videoEl.paused) videoEl.play().catch(() => {}); else videoEl.pause();
  });

  // Mute FS
  document.getElementById("iptv-fs-mute-btn")?.addEventListener("click", () => {
    if (!videoEl) return;
    videoEl.muted = !videoEl.muted;
    (document.getElementById("iptv-fs-mute-btn") as HTMLButtonElement).textContent = videoEl.muted ? "🔇" : "🔊";
    (document.getElementById("iptv-mute-btn") as HTMLButtonElement | null)!.textContent = videoEl.muted ? "🔇" : "🔊";
  });

  // Volume FS
  const fsVol = document.getElementById("iptv-fs-volume") as HTMLInputElement;
  fsVol?.addEventListener("input", () => {
    if (!videoEl) return;
    videoEl.volume = parseFloat(fsVol.value) / 100;
    if (volumeBar) volumeBar.value = fsVol.value;
  });

  // Progress FS (seek)
  const fsProg = document.getElementById("iptv-fs-progress") as HTMLInputElement;
  fsProg?.addEventListener("input", () => {
    if (!videoEl || !videoEl.duration) return;
    videoEl.currentTime = (parseFloat(fsProg.value) / 100) * videoEl.duration;
  });

  // Gestionnaire de changement fullscreen unifié
  const handleFSChange = () => {
    if (isFullscreenActive()) {
      fsOverlay.classList.remove("hidden");
      // Afficher les contrôles immédiatement lors de l'entrée
      showFSControls();
    } else {
      fsOverlay.classList.remove("iptv-fs-visible");
      fsOverlay.classList.add("hidden");
      videoArea.classList.remove("iptv-fs-active");
      if (_fsHideTimer) { clearTimeout(_fsHideTimer); _fsHideTimer = null; }
    }
  };

  document.addEventListener("fullscreenchange", handleFSChange);
  document.addEventListener("webkitfullscreenchange", handleFSChange);
  document.addEventListener("mozfullscreenchange", handleFSChange);
  document.addEventListener("MSFullscreenChange", handleFSChange);
}


// ── Main Controls ──────────────────────────────────────────────────────────
function initControls(): void {
  playBtn = document.getElementById("iptv-play-btn") as HTMLButtonElement;
  playBtn?.addEventListener("click", () => {
    if (!videoEl) return;
    if (videoEl.paused) videoEl.play().catch(() => {}); else videoEl.pause();
  });

  document.getElementById("iptv-play-overlay")?.addEventListener("click", () => {
    if (!videoEl) return;
    if (videoEl.paused) videoEl.play().catch(() => {}); else videoEl.pause();
  });

  document.getElementById("iptv-stop-btn")?.addEventListener("click", () => {
    if (!videoEl) return;
    videoEl.pause(); videoEl.currentTime = 0; updatePlayPauseBtn();
  });

  document.getElementById("iptv-prev-btn")?.addEventListener("click", () => {
    if (!_channels.length) return;
    _currentChannelIdx = (_currentChannelIdx - 1 + _channels.length) % _channels.length;
    const ch = _channels[_currentChannelIdx];
    loadStream(ch.url, detectStreamType(ch.url), ch.name); updateChannelActive();
  });

  document.getElementById("iptv-next-btn")?.addEventListener("click", () => {
    if (!_channels.length) return;
    _currentChannelIdx = (_currentChannelIdx + 1) % _channels.length;
    const ch = _channels[_currentChannelIdx];
    loadStream(ch.url, detectStreamType(ch.url), ch.name); updateChannelActive();
  });

  progressBar = document.getElementById("iptv-progress") as HTMLInputElement;
  progressBar?.addEventListener("input", () => {
    if (!videoEl || !videoEl.duration) return;
    videoEl.currentTime = (parseFloat(progressBar.value) / 100) * videoEl.duration;
  });

  volumeBar = document.getElementById("iptv-volume") as HTMLInputElement;
  volumeBar?.addEventListener("input", () => {
    if (!videoEl) return;
    videoEl.volume = parseFloat(volumeBar.value) / 100;
    const fsVol = document.getElementById("iptv-fs-volume") as HTMLInputElement;
    if (fsVol) fsVol.value = volumeBar.value;
  });

  document.getElementById("iptv-mute-btn")?.addEventListener("click", () => {
    if (!videoEl) return;
    videoEl.muted = !videoEl.muted;
    (document.getElementById("iptv-mute-btn") as HTMLButtonElement).textContent = videoEl.muted ? "🔇" : "🔊";
    (document.getElementById("iptv-fs-mute-btn") as HTMLButtonElement | null)!.textContent = videoEl.muted ? "🔇" : "🔊";
  });

  // Fullscreen vidéo uniquement
  document.getElementById("iptv-fs-video-btn")?.addEventListener("click", () => {
    const area = document.getElementById("iptv-video-area");
    if (!area) return;
    if (!isFullscreenActive()) {
      if (area.requestFullscreen) {
        area.requestFullscreen().catch(() => {});
      } else if ((area as any).webkitRequestFullscreen) {
        (area as any).webkitRequestFullscreen();
      } else if ((area as any).mozRequestFullScreen) {
        (area as any).mozRequestFullScreen();
      } else if ((area as any).msRequestFullscreen) {
        (area as any).msRequestFullscreen();
      }
    } else {
      exitFullscreenAll();
    }
  });

  // Fullscreen panneau entier
  document.getElementById("iptv-fullscreen-btn")?.addEventListener("click", () => {
    if (!isFullscreenActive()) {
      if (panel.requestFullscreen) {
        panel.requestFullscreen().catch(() => {});
      } else if ((panel as any).webkitRequestFullscreen) {
        (panel as any).webkitRequestFullscreen();
      } else if ((panel as any).mozRequestFullScreen) {
        (panel as any).mozRequestFullScreen();
      } else if ((panel as any).msRequestFullscreen) {
        (panel as any).msRequestFullscreen();
      }
    } else {
      exitFullscreenAll();
    }
  });

  document.getElementById("iptv-minimize-btn")?.addEventListener("click", () => {
    _isMinimized = !_isMinimized;
    panel.classList.toggle("iptv-minimized", _isMinimized);
  });

  document.getElementById("iptv-close-btn")?.addEventListener("click", closePanel);

  document.getElementById("iptv-playlist-btn")?.addEventListener("click", () => {
    playlistDrawer?.classList.toggle("hidden");
  });

  document.getElementById("iptv-retry-btn")?.addEventListener("click", () => {
    if (_currentStreamUrl) loadStream(_currentStreamUrl, _currentStreamType, "Stream");
  });

  // Audio track selector
  audioTrackSelect = document.getElementById("iptv-audio-select") as HTMLSelectElement;
  audioTrackSelect?.addEventListener("change", () => {
    const trackIdx = parseInt(audioTrackSelect.value);
    _currentAudioTrack = trackIdx;
    if (_currentLocalPath && _ws?.readyState === WebSocket.OPEN) {
      // Demander au backend de streamer avec la nouvelle piste audio
      _ws.send(JSON.stringify({
        type: "iptv_set_audio_track",
        path: _currentLocalPath,
        audio_track: trackIdx
      }));
    }
  });
}

function updateChannelActive(): void {
  document.querySelectorAll(".iptv-channel-item").forEach(el => {
    const idx = parseInt((el as HTMLElement).dataset.idx || "-1");
    el.classList.toggle("active", idx === _currentChannelIdx);
  });
}

// ── Video Event Listeners ──────────────────────────────────────────────────
function bindVideoEvents(): void {
  timeDisplay   = document.getElementById("iptv-time-current")  as HTMLSpanElement;
  durationDisplay = document.getElementById("iptv-time-duration") as HTMLSpanElement;
  progressBar   = document.getElementById("iptv-progress")      as HTMLInputElement;
  loadingOverlay = document.getElementById("iptv-loading-overlay") as HTMLDivElement;
  errorOverlay  = document.getElementById("iptv-error-overlay") as HTMLDivElement;

  const fsProg    = () => document.getElementById("iptv-fs-progress")  as HTMLInputElement;
  const fsTimeCur = () => document.getElementById("iptv-fs-time-cur")  as HTMLSpanElement;
  const fsTimeDur = () => document.getElementById("iptv-fs-time-dur")  as HTMLSpanElement;

  videoEl.addEventListener("timeupdate", () => {
    const cur = formatTime(videoEl.currentTime);
    timeDisplay.textContent = cur;
    if (fsTimeCur()) fsTimeCur().textContent = cur;

    if (videoEl.duration && isFinite(videoEl.duration)) {
      const pct = String((videoEl.currentTime / videoEl.duration) * 100);
      progressBar.value = pct;
      if (fsProg()) fsProg().value = pct;
    }
  });

  videoEl.addEventListener("durationchange", () => {
    const dur = isFinite(videoEl.duration) ? formatTime(videoEl.duration) : "∞ LIVE";
    durationDisplay.textContent = dur;
    if (fsTimeDur()) fsTimeDur().textContent = dur;
  });

  videoEl.addEventListener("play",    updatePlayPauseBtn);
  videoEl.addEventListener("pause",   updatePlayPauseBtn);
  videoEl.addEventListener("playing", updatePlayPauseBtn);
  videoEl.addEventListener("error",   () => {
    showErrorOverlay("Impossible de lire ce média");
    updateStreamBadge("ERREUR");
    updatePlayPauseBtn();
  });
  videoEl.addEventListener("loadstart", () => { showLoading(); updatePlayPauseBtn(); });
  videoEl.addEventListener("canplay",   () => { hideLoading(); showVideoArea(); });
  videoEl.addEventListener("waiting",   showLoading);

  // État initial
  document.getElementById("iptv-play-overlay")?.classList.add("iptv-paused");
}

// ── Open / Close Panel ─────────────────────────────────────────────────────
function openPanel(): void { panel.classList.remove("hidden"); }
function closePanel(): void {
  panel.classList.add("hidden");
  if (videoEl && !videoEl.paused) videoEl.pause();
}

// ── File & URL Handlers ────────────────────────────────────────────────────
function initFileHandlers(): void {
  document.getElementById("iptv-open-file-btn")?.addEventListener("click", () => fileInput?.click());

  fileInput = document.getElementById("iptv-file-input") as HTMLInputElement;
  fileInput?.addEventListener("change", () => {
    const file = fileInput.files?.[0];
    if (!file) return;
    const ext = file.name.substring(file.name.lastIndexOf(".")).toLowerCase();
    const playlistExts = [".m3u", ".m3u8", ".xspf", ".pls"];
    if (playlistExts.includes(ext)) {
      const reader = new FileReader();
      reader.onload = ev => {
        const content = ev.target?.result as string;
        if (ext === ".m3u" || ext === ".m3u8") {
          renderPlaylist(parseM3ULocal(content)); updateTitle(file.name); updateStreamBadge("IPTV");
        } else if (_ws?.readyState === WebSocket.OPEN) {
          _ws.send(JSON.stringify({ type: "iptv_parse_m3u", path: file.name }));
        }
      };
      reader.readAsText(file);
    } else {
      // Pour les vidéos : envoyer le chemin au backend pour streaming HTTP avec transcoding
      // On utilise l'API File pour récupérer le chemin réel si possible (Electron/CEF),
      // sinon on utilise un blob URL (sans transcoding ffmpeg)
      const filePath: string = (file as any).path || "";
      if (filePath && _ws?.readyState === WebSocket.OPEN) {
        // Backend disponible → streaming HTTP avec ffmpeg
        showLoading();
        _currentLocalPath = filePath;
        updateTitle(file.name);
        _ws.send(JSON.stringify({ type: "iptv_open_file", path: filePath }));
      } else {
        // Fallback : blob URL (sans transcoding, pas de son pour les codecs non supportés)
        const url = URL.createObjectURL(file);
        loadStream(url, detectStreamType(file.name), file.name);
        updateStreamBadge(ext.toUpperCase().replace(".", ""));
        updateAudioTracks([]); // Pas de multi-piste en mode blob
      }
    }
  });

  document.getElementById("iptv-load-url-btn")?.addEventListener("click", () => {
    const url = urlInput?.value.trim();
    if (url) handleURLLoad(url);
  });
  urlInput?.addEventListener("keydown", (e: KeyboardEvent) => {
    if (e.key === "Enter" && urlInput.value.trim()) handleURLLoad(urlInput.value.trim());
  });

  groupFilter = document.getElementById("iptv-group-filter") as HTMLSelectElement;
  groupFilter?.addEventListener("change", () => {
    const f = groupFilter.value;
    renderFilteredPlaylist(f ? _channels.filter(c => c.group === f) : _channels);
  });

  // Drop zone
  const dropZone = document.getElementById("iptv-drop-zone")!;
  dropZone.addEventListener("dragover", e => { e.preventDefault(); dropZone.classList.add("drag-over"); });
  dropZone.addEventListener("dragleave", () => dropZone.classList.remove("drag-over"));
  dropZone.addEventListener("drop", e => {
    e.preventDefault(); dropZone.classList.remove("drag-over");
    const file = e.dataTransfer?.files[0];
    if (file) handleDroppedFile(file);
  });
  panel.addEventListener("dragover", e => e.preventDefault());
  panel.addEventListener("drop", e => {
    e.preventDefault();
    const file = e.dataTransfer?.files[0];
    if (file) handleDroppedFile(file);
  });
}

function handleDroppedFile(file: File): void {
  const ext = file.name.substring(file.name.lastIndexOf(".")).toLowerCase();
  if ([".m3u", ".m3u8", ".xspf", ".pls"].includes(ext)) {
    const reader = new FileReader();
    reader.onload = ev => {
      if (ext === ".m3u" || ext === ".m3u8") {
        renderPlaylist(parseM3ULocal(ev.target?.result as string));
        updateTitle(file.name);
      }
    };
    reader.readAsText(file);
  } else {
    const filePath: string = (file as any).path || "";
    if (filePath && _ws?.readyState === WebSocket.OPEN) {
      showLoading(); _currentLocalPath = filePath;
      updateTitle(file.name);
      _ws.send(JSON.stringify({ type: "iptv_open_file", path: filePath }));
    } else {
      loadStream(URL.createObjectURL(file), detectStreamType(file.name), file.name);
    }
  }
}

function handleURLLoad(url: string): void {
  const ext = url.toLowerCase().split("?")[0];
  const isPlaylist = [".m3u", ".m3u8", ".xspf", ".pls"].some(e => ext.endsWith(e));
  if (isPlaylist && _ws?.readyState === WebSocket.OPEN) {
    showLoading(); updateTitle("Chargement playlist...");
    _ws.send(JSON.stringify({ type: "iptv_parse_url", url }));
  } else {
    _currentLocalPath = "";
    loadStream(url, detectStreamType(url), url.split("/").pop()?.split("?")[0] || "Stream");
  }
}

// ── Local M3U Parser ───────────────────────────────────────────────────────
function parseM3ULocal(content: string): IPTVChannel[] {
  const channels: IPTVChannel[] = [];
  const lines = content.split(/\r?\n/);
  let i = 0;
  while (i < lines.length) {
    const line = lines[i].trim();
    if (line.startsWith("#EXTINF")) {
      const meta = line.substring(line.indexOf(":") + 1);
      let name = "", logo = "", group = "";
      if (meta.includes(",")) {
        const [attrs, ...rest] = meta.split(",");
        name = rest.join(",").trim();
        const lm = attrs.match(/tvg-logo="([^"]*)"/);
        const gm = attrs.match(/group-title="([^"]*)"/);
        if (lm) logo = lm[1]; if (gm) group = gm[1];
      }
      i++;
      while (i < lines.length && (!lines[i].trim() || lines[i].trim().startsWith("#"))) i++;
      if (i < lines.length) {
        const url = lines[i].trim();
        if (url) channels.push({ name: name || url, url, logo, group });
      }
    }
    i++;
  }
  return channels;
}

// ── WebSocket Incoming Message Handler ────────────────────────────────────
export function handleIPTVMessage(data: any): boolean {
  if (data.type === "iptv_open") { openPanel(); return true; }

  if (data.type === "iptv_stream_ready") {
    // Fichier local streamé via le serveur HTTP Python + ffmpeg
    hideLoading();
    _currentLocalPath = data.local_path || _currentLocalPath;
    _currentAudioTrack = data.audio_track ?? 0;
    loadStream(data.url, data.stream_type || "mp4", data.name || "Vidéo");

    const hasFfmpeg = data.ffmpeg_available !== false;
    const codec = data.video_codec || "";
    updateStreamBadge(hasFfmpeg ? `${codec.toUpperCase()} → AAC` : codec.toUpperCase());

    // Afficher les pistes audio si disponibles
    if (data.audio_tracks && !data.audio_track_changed) {
      updateAudioTracks(data.audio_tracks as AudioTrack[]);
      if (audioTrackSelect) audioTrackSelect.value = "0";
    }
    return true;
  }

  if (data.type === "iptv_playlist") {
    hideLoading();
    if (data.success && data.channels?.length > 0) {
      renderPlaylist(data.channels);
      updateTitle(data.source_name || "Playlist IPTV");
      updateStreamBadge(`IPTV — ${data.channels.length} CH.`);
    } else {
      showErrorOverlay(data.error || "Aucune chaîne trouvée");
    }
    return true;
  }

  if (data.type === "iptv_direct_stream") {
    loadStream(data.url, data.stream_type || "direct", data.name || "Stream");
    return true;
  }

  if (data.type === "iptv_playlist_error") {
    hideLoading(); showErrorOverlay(data.error || "Erreur playlist");
    return true;
  }

  return false;
}

// ── Public Init Function ──────────────────────────────────────────────────
export function initIPTVPlayer(ws: WebSocket | null): void {
  _ws = ws;
  injectIPTVStyles();

  panel = document.getElementById("iptv-panel") as HTMLDivElement;
  if (!panel) { console.error("[IPTV] Panel introuvable"); return; }

  panel.innerHTML = buildPanelHTML();

  videoEl        = document.getElementById("iptv-video")         as HTMLVideoElement;
  playlistDrawer = document.getElementById("iptv-playlist-drawer") as HTMLDivElement;
  channelsList   = document.getElementById("iptv-channels-list") as HTMLDivElement;
  urlInput       = document.getElementById("iptv-url-input")     as HTMLInputElement;
  volumeBar      = document.getElementById("iptv-volume")        as HTMLInputElement;
  playBtn        = document.getElementById("iptv-play-btn")      as HTMLButtonElement;
  groupFilter    = document.getElementById("iptv-group-filter")  as HTMLSelectElement;

  if (videoEl) videoEl.volume = 0.8;

  bindVideoEvents();
  initDrag();
  initResize();
  initControls();
  initFileHandlers();
  initFullscreenControls();

  document.addEventListener("mousemove", onMouseMove);
  document.addEventListener("mouseup",   onMouseUp);

  console.log("[IPTV] Lecteur JARVIS v2 initialisé ✔ (serveur HTTP sur port 8766)");
}

// ── Update WS reference ───────────────────────────────────────────────────
export function updateIPTVWS(ws: WebSocket | null): void { _ws = ws; }
