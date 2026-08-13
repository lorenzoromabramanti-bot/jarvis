/**
 * J.A.R.V.I.S — Interface Web avec Orbe Three.js
 *
 * Se connecte au backend Python via WebSocket (ws://localhost:8765),
 * recoit les changements d'etat et pilote l'orbe en consequence.
 *
 * Etats: "idle" | "listening" | "thinking" | "speaking"
 */

import { createOrb, type OrbState } from "./orb";
import { injectVisionButton, captureFrame } from "./screen_capture";
import { initJarvisGlobe } from "./globe";
import { activerHolo, desactiverHolo } from "./hologramme";
import { initIPTVPlayer, handleIPTVMessage, updateIPTVWS } from "./iptv_player";
import { initHADashboard, handleHAMessage, updateHAWS } from "./ha_dashboard";
import { initOsAppStore, handleOsAppInstallProgress } from "./os_appstore";
import "./style.css";
import "./theme_neon.css";
import "./theme_aurum.css";

declare var Hands: any;

// ── Thème visuel (Néon terminal ⇄ Classique) ────────────────────────────────
// Défaut : néon (choisi par l'utilisateur). Réversible + persistant.
(function initTheme() {
  const stored = localStorage.getItem("jarvisTheme");
  const theme = stored || "neon";
  document.documentElement.setAttribute("data-theme", theme);
})();
// Cycle des thèmes : néon → aurum → classique → néon …
const THEME_CYCLE = ["neon", "aurum", "classic"] as const;
const THEME_LABEL: Record<string, string> = {
  neon: '<span class="btn-icon">🖥️</span> THÈME : NÉON',
  aurum: '<span class="btn-icon">🜚</span> THÈME : AURUM',
  classic: '<span class="btn-icon">🎨</span> THÈME : CLASSIQUE',
};
// Le thème visuel pilote la couleur de l'orbe : classique=bleu, néon=vert, aurum=or.
const THEME_ORB: Record<string, string> = {
  classic: "default",
  neon: "neon",
  aurum: "aurum",
};
// Applique la couleur d'orbe correspondant au thème courant (appelé après création de l'orbe).
function applyThemeOrb() {
  const cur = document.documentElement.getAttribute("data-theme") || "neon";
  try { orb.setTheme(THEME_ORB[cur] ?? "default"); } catch { /* orbe pas encore prête */ }
}
function toggleTheme() {
  const current = document.documentElement.getAttribute("data-theme") || "neon";
  const idx = THEME_CYCLE.indexOf(current as any);
  const next = THEME_CYCLE[(idx + 1) % THEME_CYCLE.length];
  document.documentElement.setAttribute("data-theme", next);
  localStorage.setItem("jarvisTheme", next);
  const btn = document.getElementById("theme-toggle-btn");
  if (btn) btn.innerHTML = THEME_LABEL[next] ?? THEME_LABEL.neon;
  orb.setTheme(THEME_ORB[next] ?? "default");
}

// ── Config ────────────────────────────────────────────────────────────────────
const WS_URL = `ws://${window.location.hostname}:8765`;
const RECONNECT_INTERVAL_MS = 2_000;

// ── Boot sequence state ───────────────────────────────────────────────────────
let bootConnectedCallback: (() => void) | null = null;
let wsConnectedBeforeBoot = false;

// ── DOM refs ──────────────────────────────────────────────────────────────────
const canvas = document.getElementById("orb-canvas") as HTMLCanvasElement;
const statusEl = document.getElementById("status-text") as HTMLDivElement;
const errorEl = document.getElementById("error-text") as HTMLDivElement;
const badgeEl = document.getElementById("connection-badge") as HTMLDivElement;
const badgeLabelEl = document.getElementById(
  "connection-label"
) as HTMLSpanElement;
const muteButtonEl = document.getElementById("mute-button") as HTMLButtonElement;
const gpuButtonEl = document.getElementById("gpu-button") as HTMLButtonElement;
const helpOverlayEl = document.getElementById("help-overlay") as HTMLDivElement;
const timerHudEl = document.getElementById("timer-hud") as HTMLDivElement;
const timerDisplayEl = document.getElementById("timer-display") as HTMLDivElement;
const timerProgressEl = document.getElementById("timer-progress") as HTMLDivElement;
const subtitleToggleButtonEl = document.getElementById("subtitle-toggle") as HTMLButtonElement;
const keyboardToggleButtonEl = document.getElementById("keyboard-toggle") as HTMLButtonElement;
const keyboardHudEl = document.getElementById("keyboard-hud") as HTMLDivElement;
const keyboardInputEl = document.getElementById("keyboard-input") as HTMLInputElement;
const keyboardCloseEl = document.getElementById("keyboard-close") as HTMLSpanElement;

const userSpeechHudEl = document.getElementById("user-speech-hud") as HTMLDivElement;
const userSpeechTextEl = document.getElementById("user-speech-text") as HTMLDivElement;

const settingsButtonEl = document.getElementById("settings-button") as HTMLButtonElement;
const commandsBtnEl = document.getElementById("commands-btn") as HTMLButtonElement;
const holoButtonEl = document.getElementById("holo-button") as HTMLButtonElement;
const micBtnEl = document.getElementById("mic-btn") as HTMLButtonElement;
const settingsModalEl = document.getElementById("settings-modal") as HTMLDivElement;
const settingsCloseBtn = document.getElementById("settings-close-btn") as HTMLSpanElement;
const apiKeysButtonEl = document.getElementById("api-keys-button") as HTMLButtonElement;
const apiKeysModalEl = document.getElementById("api-keys-modal") as HTMLDivElement;
const apiKeysCloseBtn = document.getElementById("api-keys-close-btn") as HTMLSpanElement;
const apiKeysSaveBtn = document.getElementById("api-keys-save-btn") as HTMLButtonElement;
const agentModeleBtnEl = document.getElementById("agent-modele-btn") as HTMLButtonElement;
const agentModelModalEl = document.getElementById("agent-model-modal") as HTMLDivElement;
const agentModelCloseBtn = document.getElementById("agent-model-close-btn") as HTMLSpanElement;
const agentModelSaveBtn = document.getElementById("agent-model-save-btn") as HTMLButtonElement;
const agentModelsContainerEl = document.getElementById("agent-models-container") as HTMLDivElement;
const settingsNameEl = document.getElementById("settings-name") as HTMLInputElement;
const settingsAgeEl = document.getElementById("settings-age") as HTMLInputElement;
const settingsCityEl = document.getElementById("settings-city") as HTMLInputElement;
const settingsImgEngineEl = document.getElementById("settings-img-engine") as HTMLSelectElement;
const settingsAppsListEl = document.getElementById("settings-apps-list") as HTMLDivElement;
const appAddNameEl = document.getElementById("app-add-name") as HTMLInputElement;
const appAddPathEl = document.getElementById("app-add-path") as HTMLInputElement;
const appAddBtn = document.getElementById("app-add-btn") as HTMLButtonElement;
const appDetectBtn = document.getElementById("app-detect-btn") as HTMLButtonElement;
const appDetectSelect = document.getElementById("app-detect-select") as HTMLSelectElement;
const settingsSaveBtn = document.getElementById("settings-save-btn") as HTMLButtonElement;
const settingsMicEl = document.getElementById("settings-mic") as HTMLSelectElement;
const settingsOrbStyleEl = document.getElementById("settings-orb-style") as HTMLSelectElement;
const settingsShowClockHudEl = document.getElementById("settings-show-clock-hud") as HTMLInputElement;
const orbClockHudEl = document.getElementById("orb-clock-hud") as HTMLDivElement;
const settingsCameraEl = document.getElementById("settings-camera") as HTMLSelectElement;
const settingsPreferredBrainEl = document.getElementById("settings-preferred-brain") as HTMLSelectElement;
const settingsMusiqueLienEl = document.getElementById("settings-musique-lien") as HTMLInputElement;
const haEntitiesListEl = document.getElementById("ha-entities-list") as HTMLDivElement;
const haAddNomEl = document.getElementById("ha-add-nom") as HTMLInputElement;
const haAddEntityEl = document.getElementById("ha-add-entity") as HTMLInputElement;
const haAddBtn = document.getElementById("ha-add-btn") as HTMLButtonElement;

// Micro sensitivity
const settingsMicDynamicEl = document.getElementById("settings-mic-dynamic") as HTMLInputElement;
const settingsMicSensEl = document.getElementById("settings-mic-sens") as HTMLInputElement;
const settingsMicSensValEl = document.getElementById("settings-mic-sens-val") as HTMLSpanElement;
const settingsMicSensContainer = document.getElementById("settings-mic-sens-container") as HTMLDivElement;
const settingsMicWarningNotDetectedEl = document.getElementById("mic-not-detected-warning") as HTMLDivElement;
const settingsAvLiveEl = document.getElementById("settings-av-live") as HTMLInputElement;

// ── New DOM Refs ─────────────────────────────────────────────────────────────
const jarvisMenuBtn = document.getElementById("jarvis-menu-btn") as HTMLButtonElement;
const jarvisMenuDropdown = document.getElementById("jarvis-menu-dropdown") as HTMLDivElement;
const shoppingPanel = document.getElementById("shopping-panel") as HTMLDivElement;
const shoppingCloseBtn = document.getElementById("shopping-panel-close-btn") as HTMLButtonElement;
const shoppingListContainer = document.getElementById("shopping-list-container") as HTMLDivElement;
const shoppingAddInput = document.getElementById("shopping-add-input") as HTMLInputElement;
const shoppingAddBtn = document.getElementById("shopping-add-btn") as HTMLButtonElement;
const shoppingClearBtn = document.getElementById("shopping-clear-btn") as HTMLButtonElement;
const shoppingHeader = document.getElementById("shopping-panel-header") as HTMLDivElement;
const shoppingToggleBtn = document.getElementById("shopping-toggle-btn") as HTMLButtonElement;
const nemotronToggleBtn = document.getElementById("nemotron-asr-toggle") as HTMLButtonElement;
const nemotronToastEl = document.getElementById("nemotron-toast") as HTMLDivElement;
const nemotronModal = document.getElementById("nemotron-modal") as HTMLDivElement;
const nemotronModalClose = document.getElementById("nemotron-modal-close") as HTMLSpanElement;
const nemotronModalGpuNotice = document.getElementById("nemotron-modal-gpu-notice") as HTMLParagraphElement;
const nemotronInstallBtn = document.getElementById("nemotron-install-btn") as HTMLButtonElement;
const nemotronCancelBtn = document.getElementById("nemotron-cancel-btn") as HTMLButtonElement;
const nemotronProgressSection = document.getElementById("nemotron-install-progress-section") as HTMLDivElement;
const nemotronProgressStage = document.getElementById("nemotron-progress-stage") as HTMLDivElement;
const nemotronProgressBar = document.getElementById("nemotron-progress-bar") as HTMLDivElement;
const nemotronInstallLogs = document.getElementById("nemotron-install-logs") as HTMLDivElement;
const nemotronModalActions = document.getElementById("nemotron-modal-actions") as HTMLDivElement;
const settingsNemotronBtn = document.getElementById("settings-nemotron-btn") as HTMLButtonElement;
const nemotronUninstallBtn = document.getElementById("nemotron-uninstall-btn") as HTMLButtonElement;

const restaurantPanel = document.getElementById("restaurant-panel") as HTMLDivElement;
const restaurantCloseBtn = document.getElementById("restaurant-panel-close-btn") as HTMLButtonElement;
const restaurantItemsList = document.getElementById("restaurant-items-list") as HTMLDivElement;
const restaurantRadarBlips = document.getElementById("restaurant-radar-blips") as HTMLDivElement;
const restaurantLocationTitle = document.getElementById("restaurant-location-title") as HTMLDivElement;
const restaurantHeader = document.getElementById("restaurant-panel-header") as HTMLDivElement;

const reminderAddTextEl = document.getElementById("reminder-add-text") as HTMLInputElement;
const reminderAddTimeEl = document.getElementById("reminder-add-time") as HTMLInputElement;
const reminderAddBtn = document.getElementById("reminder-add-btn") as HTMLButtonElement;

const reminderAlertOverlay = document.getElementById("reminder-alert-overlay") as HTMLDivElement;
const reminderAlertTime = document.getElementById("reminder-alert-time") as HTMLSpanElement;
const reminderAlertText = document.getElementById("reminder-alert-text") as HTMLDivElement;
const reminderAlertAckBtn = document.getElementById("reminder-alert-ack-btn") as HTMLButtonElement;

// ── Obsidian DOM Refs ────────────────────────────────────────────────────────
const obsidianPanel = document.getElementById("obsidian-panel") as HTMLDivElement;
const obsidianCloseBtn = document.getElementById("obsidian-panel-close-btn") as HTMLButtonElement;
const obsidianHeader = document.getElementById("obsidian-panel-header") as HTMLDivElement;
const obsidianSearch = document.getElementById("obsidian-search") as HTMLInputElement;
const obsidianAddBtn = document.getElementById("obsidian-add-btn") as HTMLButtonElement;
const obsidianNotesList = document.getElementById("obsidian-notes-list") as HTMLDivElement;
const obsidianNoteTitle = document.getElementById("obsidian-note-title") as HTMLInputElement;
const obsidianNoteContent = document.getElementById("obsidian-note-content") as HTMLTextAreaElement;
const obsidianNoteSaveBtn = document.getElementById("obsidian-note-save-btn") as HTMLButtonElement;
const obsidianNoteDeleteBtn = document.getElementById("obsidian-note-delete-btn") as HTMLButtonElement;
const settingsObsidianPathEl = document.getElementById("settings-obsidian-path") as HTMLInputElement;
const settingsWakeWordEl = document.getElementById("settings-wakeword") as HTMLInputElement;
const settingsVoiceEl = document.getElementById("settings-voice") as HTMLSelectElement;
const settingsLaunchStartupEl = document.getElementById("settings-launch-startup") as HTMLInputElement;

// ── Uninstaller DOM Refs ───────────────────────────────────────────────────
const uninstallerPanel = document.getElementById("uninstaller-panel") as HTMLDivElement;
const uninstallerToggleBtn = document.getElementById("uninstaller-toggle-btn") as HTMLButtonElement;
const uninstallerCloseBtn = document.getElementById("uninstaller-panel-close-btn") as HTMLButtonElement;
const uninstallerHeader = document.getElementById("uninstaller-panel-header") as HTMLDivElement;
const uninstallerSearchInput = document.getElementById("uninstaller-search-input") as HTMLInputElement;
const uninstallerAppsList = document.getElementById("uninstaller-apps-list") as HTMLDivElement;
const uninstallerListView = document.getElementById("uninstaller-list-view") as HTMLDivElement;
const uninstallerActionView = document.getElementById("uninstaller-action-view") as HTMLDivElement;
const uninstallerStatusMsg = document.getElementById("uninstaller-status-msg") as HTMLDivElement;
const uninstallerRadarContainer = document.getElementById("uninstaller-radar-container") as HTMLDivElement;
const uninstallerLeftoversContainer = document.getElementById("uninstaller-leftovers-container") as HTMLDivElement;
const uninstallerLeftoversList = document.getElementById("uninstaller-leftovers-list") as HTMLDivElement;
const uninstallerSelectAll = document.getElementById("uninstaller-select-all") as HTMLInputElement;
const uninstallerCleanBtn = document.getElementById("uninstaller-clean-btn") as HTMLButtonElement;
const uninstallerSkipBtn = document.getElementById("uninstaller-skip-btn") as HTMLButtonElement;

// ── Winget Upgrade DOM Refs ────────────────────────────────────────────────
const wingetPanel = document.getElementById("winget-panel") as HTMLDivElement;
const wingetToggleBtn = document.getElementById("winget-toggle-btn") as HTMLButtonElement;
const wingetCloseBtn = document.getElementById("winget-panel-close-btn") as HTMLButtonElement;
const wingetHeader = document.getElementById("winget-panel-header") as HTMLDivElement;
const wingetSearchInput = document.getElementById("winget-search-input") as HTMLInputElement;
const wingetList = document.getElementById("winget-upgrades-list") as HTMLDivElement;
const wingetSelectAll = document.getElementById("winget-select-all") as HTMLInputElement;
const wingetRefreshBtn = document.getElementById("winget-refresh-btn") as HTMLButtonElement;
const wingetUpgradeSelectedBtn = document.getElementById("winget-upgrade-selected-btn") as HTMLButtonElement;
const wingetUpgradeAllBtn = document.getElementById("winget-upgrade-all-btn") as HTMLButtonElement;
const wingetLogsContainer = document.getElementById("winget-logs-container") as HTMLDivElement;
const wingetConsole = document.getElementById("winget-console") as HTMLPreElement;
const wingetCloseLogsBtn = document.getElementById("winget-close-logs-btn") as HTMLButtonElement;
const wingetCountBadge = document.getElementById("winget-count-badge") as HTMLSpanElement;

// ── Jarvis OS DOM Refs ─────────────────────────────────────────────────────
const jarvisOsToggleBtn = document.getElementById("jarvis-os-toggle-btn") as HTMLButtonElement;
const jarvisOsWizard = document.getElementById("jarvis-os-wizard") as HTMLDivElement;
const jarvisOsWizardCloseBtn = document.getElementById("jarvis-os-wizard-close-btn") as HTMLButtonElement;
const osStep1 = document.getElementById("os-step-1") as HTMLDivElement;
const osStep2 = document.getElementById("os-step-2") as HTMLDivElement;
const osStep3 = document.getElementById("os-step-3") as HTMLDivElement;
const osBtnNext1 = document.getElementById("os-btn-next-1") as HTMLButtonElement;
const osBtnNext2 = document.getElementById("os-btn-next-2") as HTMLButtonElement;
const osBtnPrev2 = document.getElementById("os-btn-prev-2") as HTMLButtonElement;
const osBtnPrev3 = document.getElementById("os-btn-prev-3") as HTMLButtonElement;
const osBtnBrowse = document.getElementById("os-btn-browse") as HTMLButtonElement;
const osBtnInstall = document.getElementById("os-btn-install") as HTMLButtonElement;
const osFolderInput = document.getElementById("os-folder-input") as HTMLInputElement;
const osProgressContainer = document.getElementById("os-progress-container") as HTMLDivElement;
const osProgressStatus = document.getElementById("os-progress-status") as HTMLSpanElement;
const osProgressPct = document.getElementById("os-progress-pct") as HTMLSpanElement;
const osProgressBar = document.getElementById("os-progress-bar") as HTMLDivElement;
const osInstallLogs = document.getElementById("os-install-logs") as HTMLPreElement;

const jarvisOsPanel = document.getElementById("jarvis-os-panel") as HTMLDivElement;
const jarvisOsCloseBtn = document.getElementById("jarvis-os-close-btn") as HTMLButtonElement;
const jarvisOsIframe = document.getElementById("jarvis-os-iframe") as HTMLIFrameElement;
const osToolbarShared = document.getElementById("os-toolbar-shared") as HTMLButtonElement;
const osToolbarRestart = document.getElementById("os-toolbar-restart") as HTMLButtonElement;
const osToolbarStop = document.getElementById("os-toolbar-stop") as HTMLButtonElement;
const osToolbarUninstall = document.getElementById("os-toolbar-uninstall") as HTMLButtonElement;
const osStatusText = document.getElementById("os-status-text") as HTMLSpanElement;
const osLoadingOverlay = document.getElementById("os-loading-overlay") as HTMLDivElement;

const jarvisOsHeader = document.getElementById("jarvis-os-header") as HTMLDivElement;
const jarvisOsFullscreenBtn = document.getElementById("jarvis-os-fullscreen-btn") as HTMLButtonElement;
const osToolbarAppStore = document.getElementById("os-toolbar-appstore") as HTMLButtonElement;
const osAppStorePanel = document.getElementById("os-appstore-panel") as HTMLDivElement;
const osAppStoreCloseBtn = document.getElementById("os-appstore-close-btn") as HTMLButtonElement;
const osAppStoreSearch = document.getElementById("os-appstore-search") as HTMLInputElement;
const osAppStoreGrid = document.getElementById("os-appstore-grid") as HTMLDivElement;
const osAppStoreLog = document.getElementById("os-appstore-log") as HTMLDivElement;
const osAppStoreCustomInstall = document.getElementById("os-appstore-custom-install") as HTMLButtonElement;

let jarvisOsPath = "";

interface WingetUpgradeItem {
  name: string;
  id: string;
  version: string;
  available: string;
  source: string;
}
let allWingetUpgrades: WingetUpgradeItem[] = [];

let allInstalledPrograms: Array<{
  name: string;
  subkey: string;
  publisher: string;
  version: string;
  uninstall_string: string;
  install_location: string;
  icon_path: string;
  hive: string;
}> = [];
let currentLeftovers: Array<{
  type: string;
  path: string;
  desc: string;
  hive?: string;
}> = [];

let allObsidianNotes: Array<{titre: string, mtime: number, taille: number}> = [];
let activeObsidianNoteTitle: string = "";

let currentReminders: Array<{id: string, text: string, time: string, date: string, triggered: boolean}> = [];
let currentShoppingList: string[] = [];
let initialShoppingListLoaded = false;
let currentCustomApps: { id: string, label: string, exe_path: string }[] = [];

type HaEntry = { nom: string; entity_id: string };
type HaTab = "lumieres" | "prises" | "capteurs";
let currentHaEntities: Record<HaTab, HaEntry[]> = { lumieres: [], prises: [], capteurs: [] };
let currentHaTab: HaTab = "lumieres";

let subtitlesEnabled = true;
let keyboardEnabled = false;
let nemotronAsrEnabled = false;
let nemotronAsrLoading = false;
let nemotronAsrAvailable = false;
let gpuAvailable = false;

let timerInterval: number | null = null;
let timerSeconds = 0;
let timerTotalSeconds = 0;

let userSpeechTimer: number | null = null;
let userSpeechTypeInterval: number | null = null;

const HELP_COMMANDS = [
  // ── Navigation & Général ────────────────────────────────────────────────
  "Affiche la terre",
  "Où se trouve Tokyo ?",
  "Trace l'itinéraire Paris à Lyon",
  "Quelle heure est-il ?",
  "Prends une capture d'écran",
  "Ferme le globe",
  "Quelle est la météo ?",
  "Quel temps fait-il à New York ?",
  "Quelles sont les dernières news ?",
  "Cherche sur Wikipédia l'intelligence artificielle",
  "Lance une recherche sur YouTube",
  "Rappelle-moi de faire les courses",
  "Vérifie mes e-mails",
  "Raconte-moi une blague",
  "Lance le mode protocole",
  "Vérifie l'état du système",
  "Analyse les fichiers récents",
  "Active la vision",
  "Ouvre mon dossier Bureau",
  "Mets le volume à 50%",
  "Lance le téléchargement",
  "Convertis ce fichier en PDF",
  "Ouvre mon TikTok",
  "Montre-moi les photos de vacances",

  // ── Musique & Streaming ─────────────────────────────────────────────────
  "Ouvre Spotify",
  "Mets de la musique",
  "Mets de la musique sur YouTube",
  "Lance ma playlist",
  "Mets en pause la lecture",
  "Stop la musique",
  "Chanson suivante",
  "Chanson précédente",
  "Augmente le volume",
  "Baisse le son",
  "Joue du jazz",
  "Joue de la house",
  "Mets du rap",

  // ── Création musicale IA ────────────────────────────────────────────────
  "Crée une musique sur la liberté",
  "Chante-moi une chanson",
  "Rappe-moi quelque chose sur la nuit",
  "Fais-moi un rap sur la technologie",
  "Balance un rap sur Paris",
  "Pose un couplet sur l'amour",
  "Compose-moi une chanson sur l'été",
  "Fais-moi une chanson sur la mer",
  "Écris une chanson sur la nostalgie",
  "Fais-moi un slam sur la société",
  "Compose un slam sur le temps",
  "Écris un poème sur la vie",
  "Fais-moi un reggae sur la paix",
  "Compose un reggae sur la liberté",
  "Fais-moi du metal sur la guerre",
  "Fais-moi du hard rock sur la nuit",
  "Compose une chanson pop sur l'amour",
  "Fais du pop sur les rêves",
  "Fais-moi du blues sur la solitude",
  "Compose du blues sur le train du soir",
  "Fais-moi du rock sur la route",
  "Balance du rock sur la révolte",
  "Fais-moi un track sur la danse",
  "Balance un track sur le futur",
];

// ── Orb ───────────────────────────────────────────────────────────────────────
const orb = createOrb(canvas);
// L'orbe prend d'emblée la couleur du thème visuel (bleu / vert / or).
applyThemeOrb();

// ── State labels (French) ────────────────────────────────────────────────────
const STATE_LABELS: Record<OrbState, string> = {
  idle: "",
  listening: "ecoute...",
  thinking: "reflexion...",
  speaking: "",
  searching: "recherche radar...",
};

function applyState(state: OrbState): void {
  orb.setState(state);
  statusEl.textContent = STATE_LABELS[state];
  if (state === "listening" || (state as string) === "active") {
    micBtnEl.classList.add("mic-active");
  } else {
    micBtnEl.classList.remove("mic-active");
  }
}

function setMuted(muted: boolean): void {
  muteButtonEl.classList.toggle("is-muted", muted);
  muteButtonEl.setAttribute("aria-pressed", String(muted));
}

// ── Error toast ───────────────────────────────────────────────────────────────
let errorTimer: ReturnType<typeof setTimeout> | null = null;

function showError(msg: string): void {
  errorEl.textContent = msg;
  errorEl.style.opacity = "1";
  if (errorTimer) clearTimeout(errorTimer);
  errorTimer = setTimeout(() => {
    errorEl.style.opacity = "0";
  }, 4_000);
}

// ── Connection badge ──────────────────────────────────────────────────────────
function setConnected(ok: boolean): void {
  badgeEl.classList.toggle("connected", ok);
  badgeEl.classList.toggle("disconnected", !ok);
  badgeLabelEl.textContent = ok ? "connecte" : "reconnexion";
  muteButtonEl.disabled = !ok;
}

// ── WebSocket with auto-reconnect ─────────────────────────────────────────────
let ws: WebSocket | null = null;
let reconnectTimer: ReturnType<typeof setTimeout> | null = null;

function connect(): void {
  if (reconnectTimer) {
    clearTimeout(reconnectTimer);
    reconnectTimer = null;
  }

  ws = new WebSocket(WS_URL);
  (window as any).ws = ws;
  (window as unknown as Record<string, unknown>)._jarvisWs = ws;
  updateIPTVWS(ws);
  updateHAWS(ws);

  ws.addEventListener("open", () => {
    setConnected(true);

    // Authentification — DOIT être le tout premier message, sinon le serveur
    // ferme la connexion. Le frontend PC est servi par Vite sur une autre
    // origine que le serveur mobile : il ne reçoit donc pas le cookie et lit
    // le jeton dans localStorage. Le renseigner une fois avec :
    //   localStorage.setItem("jarvisToken", "<jeton de .env>")
    const jeton = localStorage.getItem("jarvisToken");
    if (jeton && ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ type: "auth", token: jeton }));
    }

    // Notifie la séquence de boot que le serveur est prêt
    if (bootConnectedCallback) {
      bootConnectedCallback();
      bootConnectedCallback = null;
    } else {
      wsConnectedBeforeBoot = true;
    }

    // Demander la liste de courses courante et les paramètres
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ type: "get_shopping_list" }));
      ws.send(JSON.stringify({ type: "get_settings" }));
      ws.send(JSON.stringify({ type: "ha_get_states" }));
    }

    // Envoyer la position GPS si disponible
    if (navigator.geolocation) {
      navigator.geolocation.getCurrentPosition(
        (position) => {
          const lat = position.coords.latitude;
          const lng = position.coords.longitude;
          if (ws && ws.readyState === WebSocket.OPEN) {
            ws.send(JSON.stringify({
              type: "location_update",
              lat,
              lng
            }));
          }
        },
        (error) => {
          console.warn("[GEOLOCATION] Geolocation error or blocked:", error.message);
        }
      );
    }
  });

  ws.addEventListener("message", async (event: MessageEvent) => {
    try {
      const data = JSON.parse(event.data as string) as {
        state?: string;
        action?: string;
        muted?: boolean;
        volume?: number;
        id?: string;
        duration?: number;
        text?: string;
        type?: string;
        version?: string;
        url?: string;
        cpu?: number;
        ram?: number;
        data?: Record<string, unknown>;
      };

      if (data.action === "request_screen_capture") {
        const frame = await captureFrame();
        if (frame && ws && ws.readyState === WebSocket.OPEN) {
          ws.send(JSON.stringify({
            type: "screen_frame",
            id: data.id,
            data: frame,
          }));
        } else if (ws && ws.readyState === WebSocket.OPEN) {
          ws.send(JSON.stringify({
            type: "screen_frame",
            id: data.id,
            error: "no_stream",
          }));
        }
        return;
      }

      if (data.action === "browser_state" && data.state) {
        if ((window as any).updateBrowserUIState) {
          (window as any).updateBrowserUIState(data.state);
        }
        return;
      }

      if (data.type === "detected_apps" && (data as any).apps) {
        if (appDetectSelect && appDetectBtn) {
          appDetectSelect.innerHTML = '<option value="">-- Sélectionner une application détectée --</option>';
          const appsList = (data as any).apps as {nom: string, chemin: string}[];
          appsList.forEach(app => {
            const opt = document.createElement("option");
            opt.value = app.chemin;
            opt.textContent = app.nom;
            appDetectSelect.appendChild(opt);
          });
          appDetectBtn.textContent = `🔍 APPS (${appsList.length})`;
        }
        return;
      }

      if (data.type === "media_playing") {
        const hud = document.getElementById("pc-lyrics-hud");
        const titleEl = document.getElementById("pc-lyrics-title");
        const textEl = document.getElementById("pc-lyrics-text");
        if (hud && titleEl && textEl) {
          hud.style.display = "block";
          titleEl.textContent = (data as any).title || "Lecture en cours";
          textEl.textContent = (data as any).lyrics || "Recherche des paroles...";
          
          // Auto hide after 2 minutes
          if ((window as any).pcLyricsTimer) clearTimeout((window as any).pcLyricsTimer);
          (window as any).pcLyricsTimer = setTimeout(() => {
            hud.style.display = "none";
          }, 120000);
        }
        return;
      }

      if (data.type === "mic_state") {
        if (data.muted) {
          micBtnEl.classList.add("mic-muted");
          micBtnEl.classList.remove("mic-active");
        } else {
          micBtnEl.classList.remove("mic-muted");
        }
        return;
      }

      if (data.type === "settings_data" && data.data) {
        const settings = data.data as any;
        settingsNameEl.value = settings.user_name || "";
        settingsAgeEl.value = settings.user_age || "";
        settingsCityEl.value = settings.user_city || "";
        if (settings.image_search_engine) settingsImgEngineEl.value = settings.image_search_engine;
        {
          const _sky = document.getElementById("settings-sky-watch") as HTMLInputElement | null;
          if (_sky) _sky.checked = !!settings.sky_watch;
          const _rocket = document.getElementById("settings-rocket-watch") as HTMLInputElement | null;
          if (_rocket) _rocket.checked = !!settings.rocket_watch;
          const _lat = document.getElementById("settings-user-lat") as HTMLInputElement | null;
          if (_lat) _lat.value = settings.user_lat != null ? String(settings.user_lat) : "";
          const _lon = document.getElementById("settings-user-lon") as HTMLInputElement | null;
          if (_lon) _lon.value = settings.user_lon != null ? String(settings.user_lon) : "";
        }

        // Populate microphone list
        applyMicSettings(settings);
        // Appliquer l'orbe
        applyOrbSettings(settings);

        if (settings.reminders) {
          currentReminders = settings.reminders;
          renderReminders();
        } else {
          currentReminders = [];
          renderReminders();
        }
        if (settings.custom_apps) {
          currentCustomApps = settings.custom_apps;
          renderCustomApps();
        }
        if (settings.ha_custom_entities) {
          currentHaEntities = {
            lumieres: settings.ha_custom_entities.lumieres || [],
            prises:   settings.ha_custom_entities.prises   || [],
            capteurs: settings.ha_custom_entities.capteurs || [],
          };
        } else {
          currentHaEntities = { lumieres: [], prises: [], capteurs: [] };
        }
        renderHaEntities();
        settingsMusiqueLienEl.value = settings.musique_lien || "";
        if (settings.obsidian_vault_path !== undefined) {
          settingsObsidianPathEl.value = settings.obsidian_vault_path || "";
        }
        if (settings.wake_word !== undefined) {
          settingsWakeWordEl.value = settings.wake_word || "jarvis";
        }
        if (settings.voice !== undefined) {
          settingsVoiceEl.value = settings.voice || "male";
        }
        if (settings.show_clock_hud !== undefined) {
          settingsShowClockHudEl.checked = settings.show_clock_hud;
          if (orbClockHudEl) {
            orbClockHudEl.style.display = settings.show_clock_hud ? "" : "none";
          }
        } else {
          settingsShowClockHudEl.checked = true;
          if (orbClockHudEl) {
            orbClockHudEl.style.display = "";
          }
        }
        if (settings.launch_on_startup !== undefined) {
          if (settingsLaunchStartupEl) {
            settingsLaunchStartupEl.checked = settings.launch_on_startup;
          }
        }
        if (settings.camera_device_label !== undefined) {
          if (settingsCameraEl) {
            settingsCameraEl.dataset.pendingLabel = settings.camera_device_label || "";
          }
        }
        if (settings.camera_device_id !== undefined) {
          (window as any).JARVIS_CAMERA_DEVICE_ID = settings.camera_device_id || "";
          if (settingsCameraEl) {
            settingsCameraEl.dataset.pendingValue = settings.camera_device_id || "";
            settingsCameraEl.value = settings.camera_device_id || "";
          }
        } else {
          (window as any).JARVIS_CAMERA_DEVICE_ID = "";
          if (settingsCameraEl) {
            settingsCameraEl.dataset.pendingValue = "";
            settingsCameraEl.value = "";
          }
        }
        updateCameraList();
        if (settings.preferred_brain !== undefined) {
          if (settingsPreferredBrainEl) {
            settingsPreferredBrainEl.value = settings.preferred_brain || "auto";
          }
        } else {
          if (settingsPreferredBrainEl) {
            settingsPreferredBrainEl.value = "auto";
          }
        }

        // Initialisation de la sensibilité micro
        if (settings.mic_dynamic_sensitivity !== undefined) {
          settingsMicDynamicEl.checked = settings.mic_dynamic_sensitivity;
        } else {
          settingsMicDynamicEl.checked = true;
        }
          if (settings.mic_sensitivity !== undefined) {
          settingsMicSensEl.value = String(settings.mic_sensitivity);
          settingsMicSensValEl.textContent = String(settings.mic_sensitivity);
        } else {
          settingsMicSensEl.value = "300";
          settingsMicSensValEl.textContent = "300";
        }

        if (settingsMicDynamicEl.checked) {
          settingsMicSensContainer.style.opacity = "0.35";
          settingsMicSensContainer.style.pointerEvents = "none";
          settingsMicSensEl.disabled = true;
        } else {
          settingsMicSensContainer.style.opacity = "1";
          settingsMicSensContainer.style.pointerEvents = "auto";
          settingsMicSensEl.disabled = false;
        }

        // ── Restauration des clés API et de leur état activé/désactivé ──
        if (settings.api_keys) {
          const geminiKeyEl = document.getElementById("settings-api-gemini-key") as HTMLInputElement;
          const groqKeyEl = document.getElementById("settings-api-groq-key") as HTMLInputElement;
          const youtubeKeyEl = document.getElementById("settings-api-youtube-key") as HTMLInputElement;
          const grokKeyEl = document.getElementById("settings-api-grok-key") as HTMLInputElement;
          const serpapiKeyEl = document.getElementById("settings-api-serpapi-key") as HTMLInputElement;
          const anthropicKeyEl = document.getElementById("settings-api-anthropic-key") as HTMLInputElement;
          const mistralKeyEl = document.getElementById("settings-api-mistral-key") as HTMLInputElement;
          const openaiKeyEl = document.getElementById("settings-api-openai-key") as HTMLInputElement;

          if (geminiKeyEl) geminiKeyEl.value = settings.api_keys.GEMINI_API_KEY || "";
          if (groqKeyEl) groqKeyEl.value = settings.api_keys.GROQ_API_KEY || "";
          if (youtubeKeyEl) youtubeKeyEl.value = settings.api_keys.YOUTUBE_API_KEY || "";
          if (grokKeyEl) grokKeyEl.value = settings.api_keys.XAI_API_KEY || "";
          if (serpapiKeyEl) serpapiKeyEl.value = settings.api_keys.SERPAPI_API_KEY || "";
          if (anthropicKeyEl) anthropicKeyEl.value = settings.api_keys.ANTHROPIC_API_KEY || "";
          if (mistralKeyEl) mistralKeyEl.value = settings.api_keys.MISTRAL_API_KEY || "";
          if (openaiKeyEl) openaiKeyEl.value = settings.api_keys.OPENAI_API_KEY || "";
        }

        const geminiEnabledEl = document.getElementById("settings-api-gemini-enabled") as HTMLInputElement;
        const groqEnabledEl = document.getElementById("settings-api-groq-enabled") as HTMLInputElement;
        const youtubeEnabledEl = document.getElementById("settings-api-youtube-enabled") as HTMLInputElement;
        const grokEnabledEl = document.getElementById("settings-api-grok-enabled") as HTMLInputElement;
        const serpapiEnabledEl = document.getElementById("settings-api-serpapi-enabled") as HTMLInputElement;
        const anthropicEnabledEl = document.getElementById("settings-api-anthropic-enabled") as HTMLInputElement;
        const mistralEnabledEl = document.getElementById("settings-api-mistral-enabled") as HTMLInputElement;
        const openaiEnabledEl = document.getElementById("settings-api-openai-enabled") as HTMLInputElement;

        if (geminiEnabledEl) geminiEnabledEl.checked = settings.api_gemini_enabled !== false;
        if (groqEnabledEl) groqEnabledEl.checked = settings.api_groq_enabled !== false;
        if (youtubeEnabledEl) youtubeEnabledEl.checked = settings.api_youtube_enabled !== false;
        if (grokEnabledEl) grokEnabledEl.checked = settings.api_grok_enabled !== false;
        if (serpapiEnabledEl) serpapiEnabledEl.checked = settings.api_serpapi_enabled !== false;
        if (anthropicEnabledEl) anthropicEnabledEl.checked = settings.api_anthropic_enabled !== false;
        if (mistralEnabledEl) mistralEnabledEl.checked = settings.api_mistral_enabled !== false;
        if (openaiEnabledEl) openaiEnabledEl.checked = settings.api_openai_enabled !== false;

        // ── Restauration état de la protection antivirus en temps réel ──
        if (settingsAvLiveEl) {
          settingsAvLiveEl.checked = settings.av_live_protection === true;
        }
        const menuAvLiveBtn = document.getElementById("menu-av-live-btn");
        if (menuAvLiveBtn) {
          const enabled = settings.av_live_protection === true;
          menuAvLiveBtn.setAttribute("aria-pressed", String(enabled));
          menuAvLiveBtn.innerHTML = enabled
            ? `<span class="btn-icon">🛡️</span> PROT. TEMPS RÉEL : ON`
            : `<span class="btn-icon">🛡️</span> PROT. TEMPS RÉEL : OFF`;
          if (enabled) {
            menuAvLiveBtn.classList.add("active");
            menuAvLiveBtn.style.color = "#00ffcc";
            menuAvLiveBtn.style.borderColor = "#00ffcc";
          } else {
            menuAvLiveBtn.classList.remove("active");
            menuAvLiveBtn.style.color = "";
            menuAvLiveBtn.style.borderColor = "";
          }
        }

        // ── Nemotron ASR state restoration ──
        nemotronAsrAvailable = settings.nemotron_asr_available || false;
        gpuAvailable = settings.gpu_available || false;
        updateNemotronUI();
        if (settings.nemotron_asr_enabled) {
          nemotronAsrEnabled = true;
          nemotronToggleBtn.setAttribute("aria-pressed", "true");
        } else {
          nemotronAsrEnabled = false;
          nemotronToggleBtn.setAttribute("aria-pressed", "false");
        }
        orb.setNemotronActive(nemotronAsrEnabled);
        return;
      }

      if (data.type === "agent_models_info") {
        const info = data.data as { available_models: Record<string, string[]>, current_models: Record<string, string> };
        agentModelsContainerEl.innerHTML = "";
        
        for (const [agent, models] of Object.entries(info.available_models)) {
          const wrapper = document.createElement("div");
          wrapper.style.marginBottom = "15px";
          
          const label = document.createElement("label");
          label.style.display = "block";
          label.style.marginBottom = "5px";
          label.style.fontSize = "12px";
          label.style.letterSpacing = "2px";
          label.style.color = "rgba(0, 229, 255, 0.7)";
          label.textContent = `MODÈLE ${agent.toUpperCase()}`;
          
          const select = document.createElement("select");
          select.className = "agent-model-select";
          select.dataset.agent = agent;
          select.style.width = "100%";
          select.style.padding = "10px";
          select.style.background = "rgba(0, 229, 255, 0.05)";
          select.style.border = "1px solid rgba(0, 229, 255, 0.3)";
          select.style.color = "#00e5ff";
          select.style.fontFamily = "'Courier New', monospace";
          select.style.fontSize = "14px";
          select.style.outline = "none";
          
          const currentModel = info.current_models[agent] || "";
          
          for (const model of models) {
            const option = document.createElement("option");
            option.value = model;
            option.textContent = model;
            if (model === currentModel) {
              option.selected = true;
            }
            select.appendChild(option);
          }
          
          wrapper.appendChild(label);
          wrapper.appendChild(select);
          agentModelsContainerEl.appendChild(wrapper);
        }
        return;
      }

      if (data.action === "help") {
        showHelpHUD();
        return;
      }
      if (data.action === "timer_start") {
        startTimer(data.duration || 0);
        return;
      }
      if (data.action === "timer_stop") {
        stopTimer();
        return;
      }
      if (data.action === "timer_add") {
        addTimer(data.duration || 60);
        return;
      }
      if (data.action === "timer_remove") {
        removeTimer(data.duration || 60);
        return;
      }
      if (data.action === "demo") {
        orb.triggerDemo();
        return;
      }
      // ── Globe 3D Navigation ─────────────────────────────────────────
      if (data.action === "jarvis_globe") {
        if (typeof (window as any).jarvisGlobe === "function") {
          (window as any).jarvisGlobe(data);
        }
        return;
      }
      if (data.action === "set_volume" && typeof data.volume === "number") {
        orb.setVolume(data.volume);
        return;
      }
      if (data.action === "jarvis_text" && typeof data.text === "string") {
        showSubtitles(data.text);
        return;
      }
      if (data.action === "user_speech" && typeof data.text === "string") {
        showUserSpeech(data.text);
        return;
      }
      if (data.action === "user_listening") {
        showUserSpeechListening();
        return;
      }
      if (data.type === "update_available") {
        const banner = document.getElementById("update-banner");
        if (banner) {
          banner.style.display = "block";
          banner.textContent = `SYSTEM_UPDATE_AVAILABLE_V${data.version}`;
          banner.onclick = () => {
            window.open(data.url, "_blank");
          };
        }
        return;
      }

      if (data.type === "cache_cleared") {
        // Feedback visuel apres nettoyage du cache
        const cacheData = data as any;
        const banner = document.getElementById("update-banner");
        if (banner) {
          banner.style.display = "block";
          banner.style.cursor = "default";
          if (cacheData.success) {
            banner.textContent = "✓ CACHE VIDÉ — RECHARGEMENT EN COURS...";
            banner.style.background = "linear-gradient(90deg, rgba(0,100,60,0.95), rgba(0,180,100,0.85))";
            setTimeout(() => {
              window.location.href = window.location.origin + window.location.pathname + "?v=" + Math.random();
            }, 1500);
          } else {
            banner.textContent = "✗ ERREUR NETTOYAGE CACHE — Relancez JARVIS manuellement.";
            banner.style.background = "linear-gradient(90deg, rgba(100,0,0,0.95), rgba(180,50,0,0.85))";
            setTimeout(() => { banner.style.display = "none"; }, 5000);
          }
        }
        return;
      }




      if (data.action === "system_stats") {
        const cpuVal = document.getElementById("cpu-value");
        const ramVal = document.getElementById("ram-value");
        const cpuHud = document.getElementById("cpu-hud");
        const ramHud = document.getElementById("ram-hud");

        if (cpuVal && typeof data.cpu === "number") {
          cpuVal.textContent = `${Math.round(data.cpu)}%`;
          cpuHud?.classList.toggle("stat-critical", data.cpu > 90);
        }
        if (ramVal && typeof data.ram === "number") {
          ramVal.textContent = `${Math.round(data.ram)}%`;
          ramHud?.classList.toggle("stat-critical", data.ram > 90);
        }
        return;
      }


      if (data.action === "temp_panel" && data.data) {
        showTempPanel(data.data as Parameters<typeof showTempPanel>[0]);
      }

      if (data.action === "weather_panel" && data.data) {
        showWeatherPanel(data.data as Parameters<typeof showWeatherPanel>[0]);
      }

      if (data.type === "show_recipe") {
        const modal = document.getElementById("recipe-modal");
        const titleEl = document.getElementById("recipe-title");
        const ingListEl = document.getElementById("recipe-ingredients-list");
        const instListEl = document.getElementById("recipe-instructions-list");

        if (modal && titleEl && ingListEl && instListEl) {
          titleEl.textContent = (data as any).titre || "RECETTE J.A.R.V.I.S";

          ingListEl.innerHTML = "";
          const ingredients = (data as any).ingredients || [];
          ingredients.forEach((ing: string) => {
            const li = document.createElement("li");
            li.textContent = ing;
            ingListEl.appendChild(li);
          });

          instListEl.innerHTML = "";
          const instructions = (data as any).instructions || [];
          instructions.forEach((inst: string) => {
            const li = document.createElement("li");
            li.textContent = inst;
            instListEl.appendChild(li);
          });

          modal.classList.remove("hidden");
        }
        return;
      }

      if (data.type === "show_images") {
        showImagePanel((data as any).query || "IMAGE_SCAN", (data as any).images || []);
        return;
      }

      if (data.type === "show_generated_image") {
        hideGenerationLoading();
        showAuroraImagePanel(
          (data as any).prompt_fr || "Image générée",
          (data as any).prompt_en || "",
          (data as any).url || "",
          (data as any).path || ""
        );
        return;
      }

      if (data.type === "ask_image_model") {
        showImageModelSelector((data as any).prompt || "");
        return;
      }
      if (data.type === "ask_website_model") {
        showWebsiteModelSelector((data as any).prompt || "", (data as any).available_models || []);
        return;
      }
      if (data.type === "show_generated_prompt") {
        showGeneratedPrompt((data as any).prompt || "");
        return;
      }
      
      if (data.type === "coding_started") {
        const overlay = document.getElementById("coding-matrix-overlay");
        const container = document.getElementById("matrix-code-container");
        if (overlay && container) {
          overlay.style.display = "block";
          container.innerHTML = "";
          // Start the matrix animation
          if ((window as any).codingMatrixInterval) clearInterval((window as any).codingMatrixInterval);
          (window as any).codingMatrixInterval = setInterval(() => {
            const lines = [
              "Parsing user request...",
              "Initializing DOM tree...",
              "Compiling SCSS to CSS...",
              "Generating responsive layout...",
              "Injecting AI generated assets...",
              "Optimizing performance...",
              "return document.getElementById('root');",
              "function createVirtualDOM() { ... }",
              "await fetch('/api/v1/generate');",
              "import { render } from 'engine';",
              "const app = buildWeb(container);"
            ];
            const line = document.createElement("div");
            line.textContent = "> " + lines[Math.floor(Math.random() * lines.length)] + " " + Math.random().toString(36).substring(7);
            container.prepend(line);
            if (container.children.length > 50) {
              container.lastChild?.remove();
            }
          }, 100);
        }
        return;
      }

      if (data.type === "coding_finished") {
        const overlay = document.getElementById("coding-matrix-overlay");
        if (overlay) {
          overlay.style.display = "none";
        }
        if ((window as any).codingMatrixInterval) {
          clearInterval((window as any).codingMatrixInterval);
        }
        return;
      }

      if (data.type === "close_image_model_selector") {
        const oldPanel = document.getElementById("model-selector-panel");
        if (oldPanel) oldPanel.remove();
        return;
      }
      if (data.type === "close_website_model_selector") {
        const oldPanel = document.getElementById("website-model-selector-panel");
        if (oldPanel) oldPanel.remove();
        return;
      }

      if (data.type === "show_generated_video") {
        hideGenerationLoading();
        showAuroraVideoPanel(
          (data as any).prompt_fr || "Vidéo générée",
          (data as any).prompt_en || "",
          (data as any).url || "",
          (data as any).source || "xAI",
          (data as any).path || ""
        );
        return;
      }

      if (data.type === "generation_loading") {
        showGenerationLoading((data as any).media_type || "media");
        return;
      }
      if (data.type === "hide_generation_loading") {
        hideGenerationLoading();
        return;
      }
      if (data.type === "shopping_list" && (data as any).items) {
        currentShoppingList = (data as any).items;
        renderShoppingList();
        if (initialShoppingListLoaded) {
          if (shoppingPanel) {
            shoppingPanel.classList.remove("hidden");
            shoppingPanel.classList.add("visible");
            shoppingToggleBtn?.setAttribute("aria-pressed", "true");
          }
        } else {
          initialShoppingListLoaded = true;
        }
        return;
      }

      if (data.type === "show_restaurants" && (data as any).restaurants) {
        applyState("idle");
        renderRestaurants((data as any).location || "à proximité", (data as any).restaurants);
        return;
      }

      if (data.type === "reminder_trigger") {
        if (reminderAlertOverlay && reminderAlertTime && reminderAlertText) {
          reminderAlertTime.textContent = (data as any).time || "00:00";
          reminderAlertText.textContent = (data as any).text || "";
          reminderAlertOverlay.style.display = "flex";
        }
        return;
      }

      if (data.type === "av_open") {
        openAntivirusPanel();
        return;
      }

      if (data.type === "av_start" || data.type === "av_progress" || data.type === "av_threat_detected" || data.type === "av_complete" || data.type === "av_cancel") {
        handleAntivirusWSMessage(data);
        return;
      }

      // ── Winget WS Messages ──
      if (data.action === "winget_open" || data.type === "winget_open") {
        openWingetPanel();
        return;
      }

      if (data.type === "winget_upgrades" && (data as any).upgrades) {
        allWingetUpgrades = (data as any).upgrades;
        renderWingetUpgrades(allWingetUpgrades);
        return;
      }

      if (data.type === "winget_upgrade_progress") {
        if (wingetConsole) {
          const progressData = data as any;
          if (progressData.status === "running" && progressData.log) {
            wingetConsole.textContent += progressData.log;
            wingetConsole.scrollTop = wingetConsole.scrollHeight;
          } else if (progressData.status === "complete") {
            wingetConsole.textContent += `\n[JARVIS] Processus de mise à jour terminé (Code: ${progressData.returncode}).\n`;
            wingetConsole.scrollTop = wingetConsole.scrollHeight;
          }
        }
        return;
      }

      // ── Uninstaller WS Messages ──
      if (data.action === "uninstaller_open" || data.type === "uninstaller_open") {
        openUninstallerPanel();
        return;
      }

      if (data.type === "installed_programs" && (data as any).programs) {
        allInstalledPrograms = (data as any).programs;
        renderInstalledPrograms(allInstalledPrograms);
        return;
      }

      if (data.type === "uninstall_progress") {
        updateUninstallProgress(data);
        return;
      }

      if (data.type === "uninstall_complete") {
        showUninstallComplete(data);
        return;
      }

      if (data.type === "clean_complete") {
        showCleanComplete(data);
        return;
      }

      // ── VPN WS Messages ──
      const vpnData = data as any;
      if (vpnData.type === "vpn_countries" && Array.isArray(vpnData.countries)) {
        const select = document.getElementById("vpn-country-select") as HTMLSelectElement;
        if (select) {
          select.innerHTML = '<option value="">-- Sélectionner un pays --</option>';
          vpnData.countries.forEach((c: any) => {
            const opt = document.createElement("option");
            opt.value = c.code;
            opt.textContent = `${c.name} (${c.count} serveurs)`;
            select.appendChild(opt);
          });
        }
        return;
      }

      if (vpnData.type === "vpn_status") {
        updateVpnUI(vpnData.status, vpnData.ip_info);
        return;
      }

      if (vpnData.type === "vpn_connect_result") {
        const result = vpnData.result;
        const dot = document.getElementById("vpn-status-dot");
        const text = document.getElementById("vpn-status-text");
        const connectBtn = document.getElementById("vpn-connect-btn") as HTMLButtonElement;
        const disconnectBtn = document.getElementById("vpn-disconnect-btn") as HTMLButtonElement;
        
        if (result.success) {
          if (dot) { dot.className = "vpn-dot-connected"; }
          if (text) { text.textContent = "CONNECTÉ"; }
          if (connectBtn) { connectBtn.disabled = true; connectBtn.textContent = "SE CONNECTER"; }
          if (disconnectBtn) { disconnectBtn.disabled = false; }
          
          const ipInfoEl = document.getElementById("vpn-ip-info");
          if (ipInfoEl && result.new_ip_info) {
            const info = result.new_ip_info;
            ipInfoEl.innerHTML = `
              <strong>Nouvelle IP :</strong> ${info.ip}<br>
              <strong>Pays :</strong> ${info.country} (${info.city || 'Ville inconnue'})<br>
              <strong>Fournisseur :</strong> ${info.org || 'Inconnu'}
            `;
          }
          const footer = document.getElementById("vpn-footer-server");
          if (footer) { footer.textContent = `SERVEUR : ${result.server_ip}`; }
        } else {
          if (dot) { dot.className = "vpn-dot-disconnected"; }
          if (text) { text.textContent = "ÉCHEC DE CONNEXION"; }
          if (connectBtn) { connectBtn.disabled = false; connectBtn.textContent = "SE CONNECTER"; }
          if (disconnectBtn) { disconnectBtn.disabled = true; }
          alert("Erreur VPN : " + result.error);
        }
        return;
      }

      if (vpnData.type === "vpn_disconnect_result") {
        const dot = document.getElementById("vpn-status-dot");
        const text = document.getElementById("vpn-status-text");
        const connectBtn = document.getElementById("vpn-connect-btn") as HTMLButtonElement;
        const disconnectBtn = document.getElementById("vpn-disconnect-btn") as HTMLButtonElement;
        const ipInfoEl = document.getElementById("vpn-ip-info");
        const footer = document.getElementById("vpn-footer-server");
        
        if (dot) { dot.className = "vpn-dot-disconnected"; }
        if (text) { text.textContent = "DÉCONNECTÉ"; }
        if (connectBtn) { connectBtn.disabled = false; connectBtn.textContent = "SE CONNECTER"; }
        if (disconnectBtn) { disconnectBtn.disabled = true; }
        if (ipInfoEl) { ipInfoEl.innerHTML = "IP : Déconnecté"; }
        if (footer) { footer.textContent = "SERVEUR : AUCUN"; }
        return;
      }

      if (vpnData.type === "vpn_cancel_result") {
        const dot = document.getElementById("vpn-status-dot");
        const text = document.getElementById("vpn-status-text");
        const connectBtn = document.getElementById("vpn-connect-btn") as HTMLButtonElement;
        const disconnectBtn = document.getElementById("vpn-disconnect-btn") as HTMLButtonElement;
        const ipInfoEl = document.getElementById("vpn-ip-info");
        const footer = document.getElementById("vpn-footer-server");
        
        if (dot) { dot.className = "vpn-dot-disconnected"; }
        if (text) { text.textContent = "DÉCONNECTÉ (ANNULÉ)"; }
        if (connectBtn) { connectBtn.disabled = false; connectBtn.textContent = "SE CONNECTER"; }
        if (disconnectBtn) { disconnectBtn.disabled = true; }
        if (ipInfoEl) { ipInfoEl.innerHTML = "IP : Déconnecté"; }
        if (footer) { footer.textContent = "SERVEUR : AUCUN"; }
        return;
      }

      // ── Webcam / Camera WS Messages ──
      if (vpnData.type === "open_webcam") {
        const isFullscreen = !!vpnData.fullscreen;
        activeWebcam(isFullscreen);
        return;
      }
      if (vpnData.type === "close_webcam") {
        desactiveWebcam();
        return;
      }
      if (vpnData.type === "request_camera_capture") {
        captureCameraFrame(vpnData.id);
        return;
      }

      // ── Nemotron Installation Progress ──
      if (data.type === "nemotron_install_progress") {
        const installData = data as any;
        if (installData.status === "started") {
          nemotronModal.style.display = "flex";
          nemotronModalActions.style.display = "none";
          nemotronProgressSection.style.display = "block";
          nemotronProgressStage.textContent = installData.stage;
          nemotronProgressBar.style.width = installData.progress + "%";
          nemotronInstallLogs.innerHTML = "";
          if (installData.log) {
            nemotronInstallLogs.innerHTML += `<div>${installData.log}</div>`;
          }
        } else if (installData.status === "installing") {
          nemotronProgressStage.textContent = installData.stage;
          nemotronProgressBar.style.width = installData.progress + "%";
          if (installData.log) {
            const isAtBottom = nemotronInstallLogs.scrollHeight - nemotronInstallLogs.clientHeight <= nemotronInstallLogs.scrollTop + 10;
            nemotronInstallLogs.innerHTML += `<div>${installData.log}</div>`;
            if (isAtBottom) {
              nemotronInstallLogs.scrollTop = nemotronInstallLogs.scrollHeight;
            }
          }
        } else if (installData.status === "success") {
          nemotronProgressStage.textContent = installData.stage;
          nemotronProgressBar.style.width = "100%";
          nemotronAsrAvailable = true;
          updateNemotronUI();
          if (installData.log) {
            nemotronInstallLogs.innerHTML += `<div style="color: #76b900;">${installData.log}</div>`;
          }
          showNemotronToast("✔ Installation de Nemotron ASR réussie !", "success", 5000);
          setTimeout(() => {
            nemotronModal.style.display = "none";
          }, 3000);
        } else if (installData.status === "error") {
          nemotronProgressStage.textContent = installData.stage;
          nemotronProgressBar.style.width = "0%";
          if (installData.log) {
            nemotronInstallLogs.innerHTML += `<div style="color: #ff3333;">${installData.log}</div>`;
          }
          nemotronModalActions.style.display = "flex";
          showNemotronToast("✖ L'installation a échoué.", "error", 5000);
        }
        return;
      }

      // ── Nemotron Uninstallation Progress ──
      if (data.type === "nemotron_uninstall_progress") {
        const uninstallData = data as any;
        if (uninstallData.status === "started") {
          nemotronModal.style.display = "flex";
          nemotronModalActions.style.display = "none";
          nemotronProgressSection.style.display = "block";
          nemotronProgressStage.textContent = uninstallData.stage;
          nemotronProgressBar.style.width = uninstallData.progress + "%";
          nemotronInstallLogs.innerHTML = "";
          if (uninstallData.log) {
            nemotronInstallLogs.innerHTML += `<div>${uninstallData.log}</div>`;
          }
        } else if (uninstallData.status === "uninstalling") {
          nemotronProgressStage.textContent = uninstallData.stage;
          nemotronProgressBar.style.width = uninstallData.progress + "%";
          if (uninstallData.log) {
            const isAtBottom = nemotronInstallLogs.scrollHeight - nemotronInstallLogs.clientHeight <= nemotronInstallLogs.scrollTop + 10;
            nemotronInstallLogs.innerHTML += `<div>${uninstallData.log}</div>`;
            if (isAtBottom) {
              nemotronInstallLogs.scrollTop = nemotronInstallLogs.scrollHeight;
            }
          }
        } else if (uninstallData.status === "success") {
          nemotronProgressStage.textContent = uninstallData.stage;
          nemotronProgressBar.style.width = "100%";
          nemotronAsrAvailable = false;
          updateNemotronUI();
          if (uninstallData.log) {
            nemotronInstallLogs.innerHTML += `<div style="color: #76b900;">${uninstallData.log}</div>`;
          }
          showNemotronToast("✔ Désinstallation de Nemotron ASR réussie !", "success", 5000);
          setTimeout(() => {
            nemotronModal.style.display = "none";
          }, 3000);
        } else if (uninstallData.status === "error") {
          nemotronProgressStage.textContent = uninstallData.stage;
          nemotronProgressBar.style.width = "0%";
          if (uninstallData.log) {
            nemotronInstallLogs.innerHTML += `<div style="color: #ff3333;">${uninstallData.log}</div>`;
          }
          nemotronModalActions.style.display = "flex";
          showNemotronToast("✖ La désinstallation a échoué.", "error", 5000);
        }
        return;
      }

      // ── Nemotron ASR state update ──
      if (data.type === "nemotron_asr_state") {
        nemotronAsrLoading = false;
        nemotronToggleBtn.classList.remove("asr-loading");
        nemotronToggleBtn.classList.remove("asr-error");

        const asrData = data as any;
        nemotronAsrEnabled = asrData.enabled;
        nemotronToggleBtn.setAttribute("aria-pressed", nemotronAsrEnabled.toString());

        // Show warnings
        if (asrData.warnings && asrData.warnings.length > 0) {
          showNemotronToast("⚠ " + asrData.warnings.join(" | "), "warning", 8000);
        }

        // Show error
        if (asrData.error) {
          nemotronToggleBtn.classList.add("asr-error");
          showNemotronToast("✖ " + asrData.error, "error", 10000);
          setTimeout(() => nemotronToggleBtn.classList.remove("asr-error"), 5000);
        } else if (nemotronAsrEnabled) {
          const deviceLabel = asrData.gpu_available ? "GPU NVIDIA" : "CPU (mode lent)";
          showNemotronToast(`✔ NEMOTRON ASR ACTIVÉ — ${deviceLabel}`, "success", 4000);
        } else {
          showNemotronToast("NEMOTRON ASR DÉSACTIVÉ — Google SR rétabli", "success", 3000);
        }
        orb.setNemotronActive(nemotronAsrEnabled);
        return;
      }

      // ── IPTV Player WS Messages ──
      if (data.type === "iptv_open" || data.type === "iptv_playlist" || data.type === "iptv_direct_stream" || data.type === "iptv_playlist_error") {
        handleIPTVMessage(data);
        return;
      }

      // ── Home Assistant WS Messages ──
      if (data.type === "ha_states" || data.type === "ha_state_changed" || data.type === "ha_service_result") {
        handleHAMessage(data);
        return;
      }

      if (data.type === "obsidian_open") {
        if (obsidianPanel) {
          obsidianPanel.classList.remove("hidden");
          obsidianPanel.classList.add("visible");
        }
        return;
      }

      if (data.type === "obsidian_notes" && (data as any).notes) {
        allObsidianNotes = (data as any).notes;
        renderObsidianNotes(allObsidianNotes);
        return;
      }

      if (data.type === "obsidian_note_content") {
        const titre = (data as any).titre || "";
        const content = (data as any).content || "";
        activeObsidianNoteTitle = titre;
        if (obsidianNoteTitle) obsidianNoteTitle.value = titre;
        if (obsidianNoteContent) obsidianNoteContent.value = content;
        renderObsidianNotes(allObsidianNotes);
        return;
      }

      if (data.type === "obsidian_search_results" && (data as any).results) {
        const results = (data as any).results as Array<{titre: string, snippet: string}>;
        const matchedTitles = results.map(r => r.titre.toLowerCase());
        const filtered = allObsidianNotes.filter(n => matchedTitles.includes(n.titre.toLowerCase()));
        renderObsidianNotes(filtered);
        return;
      }

      if (data.action === "show_word") {
        const wordData = data as any;
        if (wordData.word) {
          const w = wordData.word.trim();
          const wordCount = w.split(/\s+/).filter(Boolean).length;
          // N'affiche le mot en 3D que si c'est un mot unique (pas d'espaces dans le mot) et pas trop long (max 25 caractères)
          // pour éviter de déformer la sphère en un grand cylindre illisible lors des commandes ou réponses longues.
          if (wordCount === 1 && w.length <= 25) {
            orb.showWord(w, wordData.duration || 7000);
          }
        }
        return;
      }

      // ── JARVIS OS ────────────────────────────────────────────────────────
      if (data.type === "jarvis_os_status_reply") {
        const payload = data as any;
        if (payload.installed) {
          // Open main panel
          jarvisOsPanel.classList.remove("hidden");
          jarvisOsPanel.classList.add("visible");
          jarvisOsIframe.src = `http://localhost:${payload.port || 3000}`;
          osStatusText.textContent = "ÉTAT: EN LIGNE";
          osStatusText.style.color = "#00ff88";
        } else {
          // Open Wizard
          jarvisOsWizard.classList.remove("hidden");
          jarvisOsWizard.classList.add("visible");
          osStep1.style.display = "block";
          osStep2.style.display = "none";
          osStep3.style.display = "none";
        }
        return;
      }

      if (data.type === "jarvis_os_folder_picked") {
        const payload = data as any;
        if (payload.path) {
          if (osFolderInput) osFolderInput.value = payload.path;
          if (osBtnNext2) osBtnNext2.disabled = false;
        }
        return;
      }

      if (data.type === "jarvis_os_install_progress") {
        const payload = data as any;
        osProgressStatus.textContent = payload.status || "Installation...";
        if (payload.progress !== undefined) {
          osProgressPct.textContent = `${payload.progress}%`;
          osProgressBar.style.width = `${payload.progress}%`;
        }
        if (payload.log) {
          osInstallLogs.textContent += payload.log + "\n";
          osInstallLogs.scrollTop = osInstallLogs.scrollHeight;
        }
        if (payload.done) {
          osProgressStatus.textContent = "Installation terminée !";
          osProgressPct.textContent = "100%";
          osProgressBar.style.width = "100%";
          setTimeout(() => {
            jarvisOsWizard.classList.add("hidden");
            jarvisOsPanel.classList.remove("hidden");
            jarvisOsIframe.src = `http://localhost:${payload.port || 3000}`;
            osStatusText.textContent = "ÉTAT: EN LIGNE";
            osStatusText.style.color = "#00ff88";
            // Réinitialiser le wizard
            osBtnInstall.disabled = false;
            osBtnPrev3.disabled = false;
            osProgressContainer.classList.add("hidden");
          }, 1500);
        }
        return;
      }

      if (data.type === "jarvis_os_stopped") {
        osStatusText.textContent = "ÉTAT: HORS LIGNE";
        osStatusText.style.color = "#ff3366";
        return;
      }

      if (data.type === "jarvis_os_app_install_progress") {
        handleOsAppInstallProgress(data as Record<string, unknown>);
        return;
      }

      if (data.state) {
        applyState(data.state as OrbState);
      }
      if (typeof data.volume === "number") {
        orb.setVolume(data.volume);
      }
      if (typeof data.muted === "boolean") {
        setMuted(data.muted);
      }
    } catch {
      // ignore malformed messages
    }
  });

  ws.addEventListener("close", () => {
    setConnected(false);
    applyState("idle");
    scheduleReconnect();
  });

  ws.addEventListener("error", () => {
    setConnected(false);
  });
}

// ── Subtitles HUD Logic ──────────────────────────────────────────────────────
let subtitleTimer: number | null = null;
let subtitleTypeInterval: number | null = null;

function hideSubtitles() {
  const container = document.getElementById("subtitle-hud");
  if (container) {
    container.style.display = "none";
  }
  if (subtitleTimer) {
    clearTimeout(subtitleTimer);
    subtitleTimer = null;
  }
  if (subtitleTypeInterval) {
    clearInterval(subtitleTypeInterval);
    subtitleTypeInterval = null;
  }
}

// Bind click event to hide subtitles instantly
document.getElementById("subtitle-hud")?.addEventListener("click", () => {
  hideSubtitles();
});

// Bind click event to hide user speech instantly
document.getElementById("user-speech-hud")?.addEventListener("click", () => {
  hideUserSpeech();
});

function hideUserSpeech() {
  if (userSpeechTimer) {
    clearTimeout(userSpeechTimer);
    userSpeechTimer = null;
  }
  if (userSpeechTypeInterval) {
    clearInterval(userSpeechTypeInterval);
    userSpeechTypeInterval = null;
  }
  if (userSpeechHudEl) {
    userSpeechHudEl.style.display = "none";
  }
}

function showUserSpeechListening() {
  hideUserSpeech();
  hideSubtitles();
  if (!subtitlesEnabled) return;
  userSpeechHudEl.style.display = "block";
  userSpeechTextEl.textContent = "ÉCOUTE ACTIVE...";
}

function showUserSpeech(text: string) {
  // Clear any existing user speech animation and timer
  hideUserSpeech();
  
  // Hide Jarvis's subtitles to prevent overlapping
  hideSubtitles();

  if (!subtitlesEnabled) {
    return;
  }

  userSpeechHudEl.style.display = "block";
  userSpeechTextEl.textContent = "";

  let i = 0;
  const speed = 20;

  userSpeechTypeInterval = window.setInterval(() => {
    if (i < text.length) {
      userSpeechTextEl.textContent += text.charAt(i);
      i++;
    } else {
      if (userSpeechTypeInterval) clearInterval(userSpeechTypeInterval);
      userSpeechTypeInterval = null;

      // Hide after 5 seconds
      userSpeechTimer = window.setTimeout(() => {
        userSpeechHudEl.style.display = "none";
        userSpeechTimer = null;
      }, 5000);
    }
  }, speed);
}

function showSubtitles(text: string) {
  const container = document.getElementById("subtitle-hud")!;
  const textEl = document.getElementById("subtitle-text")!;
  const metaEl = document.getElementById("subtitle-meta")!;

  // Si c'est un message du HUD de compilation (Iron Man Matrix)
  if (text.startsWith("[HUD]")) {
    if (subtitleTypeInterval) {
      clearInterval(subtitleTypeInterval);
      subtitleTypeInterval = null;
    }
    if (subtitleTimer) {
      clearTimeout(subtitleTimer);
      subtitleTimer = null;
    }
    container.style.display = "block";
    metaEl.textContent = "COMPILING_SKILL_MATRIX...";
    metaEl.style.color = "#ffaa00"; // Orange néon
    
    const cleanText = text.replace("[HUD] ", "").replace("[HUD]", "");
    textEl.textContent = cleanText;
    return;
  }

  // Clear any existing animation and hide Jarvis subtitles
  hideSubtitles();

  if (!subtitlesEnabled) {
    return;
  }

  container.style.display = "block";
  textEl.textContent = "";
  metaEl.textContent = "DECRYPTING_RESPONSE...";
  metaEl.style.color = "rgba(0, 229, 255, 0.4)";

  let i = 0;
  // Faster for long text (news), slower for short phrases
  const speed = text.length > 100 ? 15 : 25;

  subtitleTypeInterval = window.setInterval(() => {
    if (i < text.length) {
      // Add a bit of "glitch" feel by sometimes adding random chars before the real one
      textEl.textContent += text.charAt(i);
      i++;

      // Auto-scroll if it's long? (The box is fixed width/max-width)
    } else {
      if (subtitleTypeInterval) clearInterval(subtitleTypeInterval);
      subtitleTypeInterval = null;
      metaEl.textContent = "DECRYPTION_COMPLETE [STABLE]";
      metaEl.style.color = "#22c55e";

      // Hide after a delay proportional to text length
      const delay = Math.max(3000, text.length * 50);
      subtitleTimer = window.setTimeout(() => {
        container.style.display = "none";
        subtitleTimer = null;
      }, delay);
    }
  }, speed);
}

function scheduleReconnect(): void {
  if (reconnectTimer) return;
  reconnectTimer = setTimeout(() => {
    reconnectTimer = null;
    connect();
  }, RECONNECT_INTERVAL_MS);
}

// ── Events ──────────────────────────────────────────────────────────────────
muteButtonEl.addEventListener("click", () => {
  if (!ws || ws.readyState !== WebSocket.OPEN) return;

  // Envoi du signal stop au backend
  ws.send(JSON.stringify({ type: "stop_audio" }));

  // Feedback immédiat sur l'orbe
  applyState("idle");

  // Masquer les sous-titres immédiatement
  hideSubtitles();
  
  // Masquer les paroles
  const hud = document.getElementById("pc-lyrics-hud");
  if (hud) hud.style.display = "none";
});

// ── Unified Menu Event Listeners ─────────────────────────────────────────────
jarvisMenuBtn.addEventListener("click", (e) => {
  e.stopPropagation();
  const isOpen = !jarvisMenuDropdown.classList.contains("hidden");
  if (isOpen) {
    jarvisMenuDropdown.classList.add("hidden");
    jarvisMenuBtn.classList.remove("active");
  } else {
    jarvisMenuDropdown.classList.remove("hidden");
    jarvisMenuBtn.classList.add("active");
  }
});

// Close menu when clicking outside of it
document.addEventListener("click", (e) => {
  const target = e.target as HTMLElement;
  if (!jarvisMenuDropdown.classList.contains("hidden")) {
    if (!jarvisMenuDropdown.contains(target) && target !== jarvisMenuBtn) {
      jarvisMenuDropdown.classList.add("hidden");
      jarvisMenuBtn.classList.remove("active");
    }
  }
});

// Close menu when panel-opening buttons are clicked
jarvisMenuDropdown.querySelectorAll(".menu-action-btn").forEach((btn) => {
  btn.addEventListener("click", () => {
    const id = btn.id;
    if (id === "settings-button" || id === "agent-modele-btn" || id === "api-keys-button" || id === "shopping-toggle-btn" || id === "uninstaller-toggle-btn" || id === "winget-toggle-btn" || id === "holo-button" || id === "iptv-toggle-btn" || id === "ha-toggle-btn" || id === "browser-btn" || id === "jarvis-os-toggle-btn" || id === "shadowbroker-btn") {
      jarvisMenuDropdown.classList.add("hidden");
      jarvisMenuBtn.classList.remove("active");
    }
  });
});

gpuButtonEl.addEventListener("click", () => {
  const isPressed = gpuButtonEl.getAttribute("aria-pressed") === "true";
  const newState = !isPressed;
  gpuButtonEl.setAttribute("aria-pressed", newState.toString());

  if (newState) {
    orb.setQuality("high");
    // Feedback visuel / textuel
    console.log("GPU Acceleration Enabled");
  } else {
    orb.setQuality("low");
    console.log("GPU Acceleration Disabled");
  }
});

subtitleToggleButtonEl.addEventListener("click", () => {
  subtitlesEnabled = !subtitlesEnabled;
  subtitleToggleButtonEl.setAttribute("aria-pressed", subtitlesEnabled.toString());
  subtitleToggleButtonEl.textContent = subtitlesEnabled ? "HUD TEXT" : "TEXT OFF";

  if (!subtitlesEnabled) {
    document.getElementById("subtitle-hud")!.style.display = "none";
  }
});

keyboardToggleButtonEl.addEventListener("click", () => {
  keyboardEnabled = !keyboardEnabled;
  keyboardToggleButtonEl.setAttribute("aria-pressed", keyboardEnabled.toString());
  keyboardHudEl.style.display = keyboardEnabled ? "block" : "none";

  if (keyboardEnabled) {
    setTimeout(() => keyboardInputEl.focus(), 100);
  }
});

function closeKeyboard() {
  keyboardEnabled = false;
  keyboardToggleButtonEl.setAttribute("aria-pressed", "false");
  keyboardHudEl.style.display = "none";
}

if (keyboardCloseEl) {
  keyboardCloseEl.addEventListener("click", closeKeyboard);
}

// ── PANNEAU LISTE DES COMMANDES ───────────────────────────────
const commandsPanelEl = document.getElementById("commands-panel") as HTMLDivElement;
const commandsCloseEl = document.getElementById("commands-close") as HTMLSpanElement;
const commandsOverlayEl = document.getElementById("commands-overlay") as HTMLDivElement;
const commandsSearchEl = document.getElementById("commands-search") as HTMLInputElement;

function openCommandsPanel() {
  commandsPanelEl.style.display = "block";
  // Ferme le menu dropdown
  const dropdown = document.querySelector(".dropdown-menu") as HTMLElement;
  if (dropdown) dropdown.style.display = "none";
  setTimeout(() => commandsSearchEl.focus(), 150);
}

function closeCommandsPanel() {
  commandsPanelEl.style.display = "none";
  commandsSearchEl.value = "";
  // Ré-affiche tous les items
  document.querySelectorAll(".cmd-item").forEach(el => el.classList.remove("cmd-hidden"));
  document.querySelectorAll(".cmd-category").forEach(el => (el as HTMLElement).style.display = "");
}

if (commandsBtnEl) {
  commandsBtnEl.addEventListener("click", openCommandsPanel);
}

// ── OUTILS RAPIDES : handler délégué unique sur le dropdown ──
// Un clic sur tout bouton [data-cmd] envoie la commande à Jarvis via
// EXACTEMENT le même canal WebSocket que la délégation .cmd-item.
jarvisMenuDropdown.addEventListener("click", (e) => {
  const btn = (e.target as HTMLElement).closest("[data-cmd]") as HTMLElement | null;
  if (!btn) return;
  const cmd = btn.getAttribute("data-cmd")?.trim();
  if (!cmd) return;

  // Ferme le menu déroulant (classe .hidden réellement utilisée)
  jarvisMenuDropdown.classList.add("hidden");
  jarvisMenuBtn.classList.remove("active");

  const hasPlaceholder = /\[.+?\]/.test(cmd);
  if (!hasPlaceholder && ws && ws.readyState === WebSocket.OPEN) {
    ws.send(JSON.stringify({ type: "user_input", text: cmd }));
    // Feedback visuel HUD sur le bouton cliqué
    const prev = btn.style.background;
    btn.style.background = "rgba(0, 229, 255, 0.18)";
    setTimeout(() => { btn.style.background = prev; }, 600);
  } else {
    // WebSocket indisponible ou commande à compléter → fallback sûr
    openCommandsPanel();
  }
});

// ── Bouton passerelle "TOUS LES OUTILS & CALCULS" → panneau + scroll cat.18 ──
const menuAllToolsBtn = document.getElementById("menu-all-tools-btn") as HTMLButtonElement | null;
if (menuAllToolsBtn) {
  menuAllToolsBtn.addEventListener("click", (e) => {
    e.stopPropagation(); // pas de data-cmd : évite le handler délégué ci-dessus
    jarvisMenuDropdown.classList.add("hidden");
    jarvisMenuBtn.classList.remove("active");
    openCommandsPanel();
    setTimeout(() => {
      const titles = commandsPanelEl.querySelectorAll(".cmd-cat-title");
      const target = Array.prototype.find.call(titles, (t: Element) =>
        (t.textContent || "").toUpperCase().includes("CALCULS")) as HTMLElement | undefined;
      if (target) {
        target.scrollIntoView({ behavior: "smooth", block: "start" });
        target.style.transition = "background .35s";
        target.style.background = "rgba(0,229,255,0.18)";
        setTimeout(() => { target.style.background = ""; }, 1400);
      }
    }, 260); // laisse passer le focus différé (150ms) de openCommandsPanel
  });
}

// ── Barre de recherche du MENU (filtre live des .menu-action-btn) ──
const menuSearchEl = document.getElementById("menu-search") as HTMLInputElement | null;
if (menuSearchEl) {
  menuSearchEl.addEventListener("input", () => {
    const q = menuSearchEl.value.toLowerCase().trim();
    jarvisMenuDropdown.querySelectorAll(".dropdown-section").forEach((section) => {
      let visible = 0;
      section.querySelectorAll(".menu-action-btn").forEach((b) => {
        const txt = (b.textContent || "").toLowerCase();
        const match = !q || txt.includes(q);
        (b as HTMLElement).style.display = match ? "" : "none";
        if (match) visible++;
      });
      (section as HTMLElement).style.display = visible === 0 ? "none" : "";
    });
  });
}

// ── Repli / dépliage de la section OUTILS RAPIDES (persisté) ──
const toolsCollapseBtn = document.getElementById("tools-collapse-btn") as HTMLButtonElement | null;
const toolsQuickButtons = document.getElementById("tools-quick-buttons") as HTMLElement | null;
if (toolsCollapseBtn && toolsQuickButtons) {
  const applyToolsState = (collapsed: boolean) => {
    toolsQuickButtons.style.display = collapsed ? "none" : "";
    toolsCollapseBtn.textContent = collapsed ? "▶" : "▼";
  };
  applyToolsState(localStorage.getItem("jarvisToolsCollapsed") === "1");
  toolsCollapseBtn.addEventListener("click", (e) => {
    e.stopPropagation();
    const collapsed = toolsQuickButtons.style.display !== "none";
    applyToolsState(collapsed);
    localStorage.setItem("jarvisToolsCollapsed", collapsed ? "1" : "0");
  });
}

// ── Bouton MESSAGERIE : ouvre l'app mail (même hôte que JARVIS) ──
const messagerieBtn = document.getElementById("messagerie-btn");
if (messagerieBtn) {
  messagerieBtn.addEventListener("click", () => {
    jarvisMenuDropdown.classList.add("hidden");
    jarvisMenuBtn.classList.remove("active");
    const host = location.hostname || "localhost";
    window.open(`http://${host}:8090`, "_blank");
  });
}

// ── Bouton de bascule du THÈME visuel ──
const themeToggleBtn = document.getElementById("theme-toggle-btn");
if (themeToggleBtn) {
  const cur = document.documentElement.getAttribute("data-theme") || "neon";
  themeToggleBtn.innerHTML = THEME_LABEL[cur] ?? THEME_LABEL.neon;
  themeToggleBtn.addEventListener("click", (e) => {
    e.stopPropagation();
    toggleTheme();
  });
}

// --- NAVIGATEUR SECURISE CONTROLES & EVENEMENTS ---
(window as any).updateBrowserUIState = (state: string) => {
  const browserControls = document.getElementById("hud-browser-controls");
  const dockBtn = document.getElementById("hud-browser-dock-btn");
  if (state === "docked") {
    document.body.classList.add("browser-open");
    if (browserControls) browserControls.classList.remove("hidden");
    if (dockBtn) dockBtn.innerText = "⚡ DÉTACHER";
  } else if (state === "undocked") {
    document.body.classList.remove("browser-open");
    if (browserControls) browserControls.classList.remove("hidden");
    if (dockBtn) dockBtn.innerText = "🔗 ANCRER";
  } else if (state === "closed") {
    document.body.classList.remove("browser-open");
    if (browserControls) browserControls.classList.add("hidden");
  }
};

// ── JARVIS OS UI LOGIC ───────────────────────────────────────────────

if (jarvisOsToggleBtn) {
  jarvisOsToggleBtn.addEventListener("click", () => {
    // Demande le status au backend
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ type: "check_jarvis_os_status" }));
    } else {
      showError("WS déconnecté. Impossible de vérifier JARVIS OS.");
    }
  });
}

if (jarvisOsWizardCloseBtn) {
  jarvisOsWizardCloseBtn.addEventListener("click", () => {
    jarvisOsWizard.classList.add("hidden");
    jarvisOsWizard.classList.remove("visible");
  });
}

if (jarvisOsCloseBtn) {
  jarvisOsCloseBtn.addEventListener("click", () => {
    jarvisOsPanel.classList.add("hidden");
    jarvisOsPanel.classList.remove("visible");
    jarvisOsIframe.src = "";
    if (osLoadingOverlay) osLoadingOverlay.style.display = "flex";
  });
}
    
if (jarvisOsFullscreenBtn && jarvisOsPanel) {
  jarvisOsFullscreenBtn.addEventListener("click", () => {
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ type: "toggle_fullscreen" }));
    }
    
    if (jarvisOsPanel.classList.contains("fullscreen-mode")) {
      jarvisOsPanel.classList.remove("fullscreen-mode");
      jarvisOsPanel.style.width = "90vw";
      jarvisOsPanel.style.height = "85vh";
      jarvisOsPanel.style.top = "";
      jarvisOsPanel.style.left = "";
      jarvisOsPanel.style.transform = "";
      jarvisOsPanel.style.maxWidth = "1600px";
      jarvisOsFullscreenBtn.textContent = "[ ]";
    } else {
      jarvisOsPanel.classList.add("fullscreen-mode");
      jarvisOsPanel.style.width = "100vw";
      jarvisOsPanel.style.height = "100vh";
      jarvisOsPanel.style.top = "0";
      jarvisOsPanel.style.left = "0";
      jarvisOsPanel.style.transform = "none";
      jarvisOsPanel.style.maxWidth = "100%";
      jarvisOsFullscreenBtn.textContent = "><";
    }
  });
}
if (jarvisOsIframe && osLoadingOverlay) {
  jarvisOsIframe.addEventListener("load", () => {
    if (jarvisOsIframe.src && jarvisOsIframe.src.includes("localhost:30")) {
      osLoadingOverlay.style.display = "none";
    }
  });
}

// Wizard steps
if (osBtnNext1) {
  osBtnNext1.addEventListener("click", () => {
    osStep1.style.display = "none";
    osStep2.style.display = "block";
  });
}

if (osBtnPrev2) {
  osBtnPrev2.addEventListener("click", () => {
    osStep2.style.display = "none";
    osStep1.style.display = "block";
  });
}

if (osBtnBrowse) {
  osBtnBrowse.addEventListener("click", () => {
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ type: "jarvis_os_pick_folder" }));
    }
  });
}

if (osBtnNext2) {
  osBtnNext2.addEventListener("click", () => {
    osStep2.style.display = "none";
    osStep3.style.display = "block";
  });
}

if (osBtnPrev3) {
  osBtnPrev3.addEventListener("click", () => {
    osStep3.style.display = "none";
    osStep2.style.display = "block";
  });
}

if (osBtnInstall) {
  osBtnInstall.addEventListener("click", () => {
    const path = osFolderInput.value;
    if (!path) return;
    
    osBtnInstall.disabled = true;
    osBtnPrev3.disabled = true;
    osProgressContainer.classList.remove("hidden");
    osInstallLogs.textContent = "";
    
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ 
        type: "jarvis_os_install", 
        path: path 
      }));
    }
  });
}

// Toolbar controls
if (osToolbarShared) {
  osToolbarShared.addEventListener("click", () => {
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ type: "jarvis_os_open_shared" }));
    }
  });
}

if (osToolbarRestart) {
  osToolbarRestart.addEventListener("click", () => {
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ type: "jarvis_os_restart" }));
    }
    // Reload iframe after delay
    setTimeout(() => {
      jarvisOsIframe.src = jarvisOsIframe.src;
    }, 5000);
  });
}

if (osToolbarStop) {
  osToolbarStop.addEventListener("click", () => {
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ type: "jarvis_os_stop" }));
    }
    jarvisOsPanel.classList.add("hidden");
    jarvisOsIframe.src = "";
  });
}

if (osToolbarUninstall) {
  osToolbarUninstall.addEventListener("click", () => {
    if (confirm("Voulez-vous vraiment désinstaller JARVIS OS ? Toutes les données dans le dossier sélectionné seront définitivement supprimées.")) {
      if (ws && ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ type: "jarvis_os_uninstall" }));
      }
      jarvisOsPanel.classList.add("hidden");
      jarvisOsIframe.src = "";
    }
  });
}

const browserBtnEl = document.getElementById("browser-btn") as HTMLButtonElement;
if (browserBtnEl) {
  browserBtnEl.addEventListener("click", () => {
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ type: "open_browser" }));
    }
  });
}

const hudBrowserDockBtn = document.getElementById("hud-browser-dock-btn") as HTMLButtonElement;
const hudBrowserCloseBtn = document.getElementById("hud-browser-close-btn") as HTMLButtonElement;

if (hudBrowserDockBtn) {
  hudBrowserDockBtn.addEventListener("click", () => {
    if (ws && ws.readyState === WebSocket.OPEN) {
      if (document.body.classList.contains("browser-open")) {
        ws.send(JSON.stringify({ type: "undock_browser" }));
      } else {
        ws.send(JSON.stringify({ type: "dock_browser" }));
      }
    }
  });
}

if (hudBrowserCloseBtn) {
  hudBrowserCloseBtn.addEventListener("click", () => {
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ type: "close_browser" }));
    }
  });
}
if (commandsCloseEl) {
  commandsCloseEl.addEventListener("click", closeCommandsPanel);
}
if (commandsOverlayEl) {
  commandsOverlayEl.addEventListener("click", closeCommandsPanel);
}

// Fermer avec Escape
document.addEventListener("keydown", (e) => {
  if (e.key === "Escape") {
    if (commandsPanelEl.style.display === "block") {
      closeCommandsPanel();
    }
    if (keyboardEnabled) {
      closeKeyboard();
    }
  }
});

// Recherche en temps réel
if (commandsSearchEl) {
  commandsSearchEl.addEventListener("input", () => {
    const query = commandsSearchEl.value.toLowerCase().trim();
    const categories = document.querySelectorAll(".cmd-category");
    categories.forEach(cat => {
      const items = cat.querySelectorAll(".cmd-item");
      let visibleCount = 0;
      items.forEach(item => {
        const text = item.textContent?.toLowerCase() || "";
        if (!query || text.includes(query)) {
          item.classList.remove("cmd-hidden");
          visibleCount++;
        } else {
          item.classList.add("cmd-hidden");
        }
      });
      (cat as HTMLElement).style.display = visibleCount === 0 ? "none" : "";
    });
  });
}

// ── CLIC SUR UNE COMMANDE → EXÉCUTION ─────────────────────────
// Délégation sur le body du panneau (couvre tous les .cmd-item)
const commandsBodyEl = document.getElementById("commands-body") as HTMLDivElement;
if (commandsBodyEl) {
  commandsBodyEl.addEventListener("click", (e) => {
    const item = (e.target as HTMLElement).closest(".cmd-item") as HTMLElement | null;
    if (!item) return;

    // Extraire le texte de la commande (contenu de .cmd-text, sans les guillemets)
    const cmdTextEl = item.querySelector(".cmd-text");
    if (!cmdTextEl) return;
    let rawCmd = cmdTextEl.textContent?.trim() ?? "";

    // Retirer les guillemets de début/fin
    rawCmd = rawCmd.replace(/^["\u00ab\u2018\u2019\u201c\u201d]|["\u00bb\u2018\u2019\u201c\u201d]$/g, "").trim();

    // Ignorer les items sans vraie commande (ex: "Via le bouton...")
    if (rawCmd.startsWith("Via le")) return;

    const hasPlaceholder = /\[.+?\]/.test(rawCmd);

    if (!hasPlaceholder) {
      // ✅ Commande sans placeholder → envoi direct à Jarvis
      if (ws && ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ type: "user_input", text: rawCmd }));
        closeCommandsPanel();

        // Feedback visuel sur l'item cliqué
        item.style.background = "rgba(0, 229, 255, 0.18)";
        item.style.borderColor = "#00e5ff";
        setTimeout(() => {
          item.style.background = "";
          item.style.borderColor = "";
        }, 600);
      } else {
        // WebSocket non dispo → afficher dans le clavier visuel quand même
        openKeyboardWithCommand(rawCmd);
      }
    } else {
      // ✏️ Commande avec placeholder → ouvre le clavier visuel pré-rempli
      openKeyboardWithCommand(rawCmd);
    }
  });
}

function openKeyboardWithCommand(cmd: string) {
  closeCommandsPanel();
  // Ouvre le clavier visuel
  keyboardEnabled = true;
  keyboardToggleButtonEl.setAttribute("aria-pressed", "true");
  keyboardHudEl.style.display = "block";
  keyboardInputEl.value = cmd;
  setTimeout(() => {
    keyboardInputEl.focus();
    // Positionne le curseur à la fin
    keyboardInputEl.setSelectionRange(keyboardInputEl.value.length, keyboardInputEl.value.length);
  }, 100);
}

keyboardInputEl.addEventListener("keydown", (e) => {
  if (e.key === "Enter") {
    const val = keyboardInputEl.value.trim();
    if (val && ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ type: "user_input", text: val }));
      keyboardInputEl.value = "";
    }
  }
});

// ── Mic button (toggle mute) ──────────────────────────────────────────────────
micBtnEl.addEventListener("click", () => {
  if (!ws || ws.readyState !== WebSocket.OPEN) return;
  ws.send(JSON.stringify({ type: "toggle_mic" }));
});

// ── Fullscreen (pywebview) ───────────────────────────────────────────────────
const fullscreenBtn = document.getElementById("fullscreen-btn") as HTMLButtonElement;
let _isFullscreen = false;

function updateFsIcon() {
  if (!fullscreenBtn) return;
  fullscreenBtn.innerHTML = _isFullscreen ? "&#x2715;" : "&#x26F6;";
  fullscreenBtn.title     = _isFullscreen ? "Quitter le plein écran" : "Plein écran";
}

fullscreenBtn?.addEventListener("click", () => {
  if (!ws || ws.readyState !== WebSocket.OPEN) return;
  ws.send(JSON.stringify({ type: "toggle_fullscreen" }));
  _isFullscreen = !_isFullscreen;
  updateFsIcon();
});

async function updateCameraList() {
  if (!settingsCameraEl) return;
  try {
    let devices = await navigator.mediaDevices.enumerateDevices();
    let videoDevices = devices.filter(d => d.kind === 'videoinput');
    
    const hasLabels = videoDevices.some(d => !!d.label);
    if (!hasLabels && videoDevices.length > 0) {
      try {
        const stream = await navigator.mediaDevices.getUserMedia({ video: true });
        stream.getTracks().forEach(track => track.stop());
        devices = await navigator.mediaDevices.enumerateDevices();
        videoDevices = devices.filter(d => d.kind === 'videoinput');
      } catch (e) {
        console.warn("Accès caméra non accordé pour les labels :", e);
      }
    }

    const pendingLabel = settingsCameraEl.dataset.pendingLabel;
    let matchedDeviceId = "";
    if (pendingLabel) {
      const match = videoDevices.find(d => d.label === pendingLabel);
      if (match) {
        matchedDeviceId = match.deviceId;
      }
    }

    const currentVal = settingsCameraEl.value;
    settingsCameraEl.innerHTML = '<option value="">-- Détection automatique --</option>';
    videoDevices.forEach(device => {
      const opt = document.createElement("option");
      opt.value = device.deviceId;
      opt.textContent = device.label || `Caméra (${device.deviceId.substring(0, 5)}...)`;
      settingsCameraEl.appendChild(opt);
    });
    
    if (matchedDeviceId) {
      settingsCameraEl.value = matchedDeviceId;
      (window as any).JARVIS_CAMERA_DEVICE_ID = matchedDeviceId;
      settingsCameraEl.dataset.pendingLabel = "";
      settingsCameraEl.dataset.pendingValue = "";
    } else {
      const pendingVal = settingsCameraEl.dataset.pendingValue;
      if (pendingVal) {
        settingsCameraEl.value = pendingVal;
        settingsCameraEl.dataset.pendingValue = "";
      } else if (currentVal) {
        settingsCameraEl.value = currentVal;
      }
    }
  } catch (err) {
    console.warn("Erreur lors de l'énumération des caméras :", err);
  }
}

// ── Settings UI Logic ────────────────────────────────────────────────────────
settingsButtonEl.addEventListener("click", () => {
  settingsModalEl.classList.add("visible");
  updateCameraList();
  if (ws && ws.readyState === WebSocket.OPEN) {
    ws.send(JSON.stringify({ type: "get_settings" }));
  }
});

settingsCloseBtn.addEventListener("click", () => {
  settingsModalEl.classList.remove("visible");
});

// Bouton menu ShadowBroker (OSINT) → ouvre le dashboard OSINT dans le navigateur
document.getElementById("shadowbroker-btn")?.addEventListener("click", () => {
  if (ws && ws.readyState === WebSocket.OPEN) {
    ws.send(JSON.stringify({ type: "open_shadowbroker" }));
  }
});

apiKeysButtonEl.addEventListener("click", () => {
  apiKeysModalEl.style.display = "flex";
  if (ws && ws.readyState === WebSocket.OPEN) {
    ws.send(JSON.stringify({ type: "get_settings" }));
  }
});

apiKeysCloseBtn.addEventListener("click", () => {
  apiKeysModalEl.style.display = "none";
});

agentModeleBtnEl?.addEventListener("click", () => {
  agentModelModalEl.style.display = "flex";
  if (ws && ws.readyState === WebSocket.OPEN) {
    ws.send(JSON.stringify({ type: "get_agent_models" }));
  }
});

agentModelCloseBtn?.addEventListener("click", () => {
  agentModelModalEl.style.display = "none";
});

agentModelSaveBtn?.addEventListener("click", () => {
  saveAllSettings();
  if (ws && ws.readyState === WebSocket.OPEN) {
    const selects = agentModelsContainerEl.querySelectorAll(".agent-model-select") as NodeListOf<HTMLSelectElement>;
    const models: Record<string, string> = {};
    selects.forEach(select => {
      const agent = select.dataset.agent;
      if (agent) {
        models[agent] = select.value;
      }
    });
    ws.send(JSON.stringify({ type: "set_agent_models", models: models }));
  }
  agentModelModalEl.style.display = "none";
});


// ── Hologramme mode toggle ────────────────────────────────────────────────────
let _holoActive = false;
const _holoOverlay = document.getElementById("holo-overlay") as HTMLDivElement;

function _openHolo() {
  _holoActive = true;
  _holoOverlay.style.display = "block";
  holoButtonEl.setAttribute("aria-pressed", "true");
  activerHolo();
}

function _closeHolo() {
  _holoActive = false;
  desactiverHolo();
  _holoOverlay.style.display = "none";
  holoButtonEl.setAttribute("aria-pressed", "false");
}

holoButtonEl?.addEventListener("click", () => {
  if (_holoActive) _closeHolo(); else _openHolo();
});

document.getElementById("holo-close-btn")?.addEventListener("click", _closeHolo);

// Record hologramme — persisté en localStorage, affiché visuellement dans le jeu

function saveAllSettings() {
  const micVal = settingsMicEl.value;
  const orbStyleVal = settingsOrbStyleEl.value;
  const showClockHudVal = settingsShowClockHudEl.checked;
  const selectedIndex = settingsCameraEl ? settingsCameraEl.selectedIndex : 0;
  const cameraDeviceIndex = selectedIndex > 0 ? (selectedIndex - 1) : null;
  const cameraDeviceId = settingsCameraEl ? settingsCameraEl.value : "";

  const settings = {
    user_name: settingsNameEl.value.trim(),
    user_age: settingsAgeEl.value.trim(),
    user_city: settingsCityEl.value.trim(),
    mic_device_index: micVal !== "" ? parseInt(micVal, 10) : null,
    mic_dynamic_sensitivity: settingsMicDynamicEl.checked,
    mic_sensitivity: parseInt(settingsMicSensEl.value, 10),
    custom_apps: currentCustomApps,
    ha_custom_entities: currentHaEntities,
    musique_lien: settingsMusiqueLienEl.value.trim(),
    image_search_engine: settingsImgEngineEl.value,
    reminders: currentReminders,
    obsidian_vault_path: settingsObsidianPathEl ? settingsObsidianPathEl.value.trim() : "",
    wake_word: settingsWakeWordEl ? settingsWakeWordEl.value.trim() : "jarvis",
    voice: settingsVoiceEl ? settingsVoiceEl.value : "male",
    launch_on_startup: settingsLaunchStartupEl ? settingsLaunchStartupEl.checked : false,
    orb_style: orbStyleVal,
    show_clock_hud: showClockHudVal,
    camera_device_index: cameraDeviceIndex,
    camera_device_id: cameraDeviceId,
    camera_device_label: (settingsCameraEl && selectedIndex > 0) ? settingsCameraEl.options[selectedIndex].text : "",
    preferred_brain: settingsPreferredBrainEl ? settingsPreferredBrainEl.value : "auto",
    av_live_protection: settingsAvLiveEl ? settingsAvLiveEl.checked : false,
    sky_watch: (document.getElementById("settings-sky-watch") as HTMLInputElement)?.checked || false,
    rocket_watch: (document.getElementById("settings-rocket-watch") as HTMLInputElement)?.checked || false,
    user_lat: ((): number | null => { const v = (document.getElementById("settings-user-lat") as HTMLInputElement)?.value; return v && v.trim() !== "" ? parseFloat(v) : null; })(),
    user_lon: ((): number | null => { const v = (document.getElementById("settings-user-lon") as HTMLInputElement)?.value; return v && v.trim() !== "" ? parseFloat(v) : null; })(),
    api_keys: {
      ANTHROPIC_API_KEY: (document.getElementById("settings-api-anthropic-key") as HTMLInputElement)?.value || "",
      MISTRAL_API_KEY: (document.getElementById("settings-api-mistral-key") as HTMLInputElement)?.value || "",
      OPENAI_API_KEY: (document.getElementById("settings-api-openai-key") as HTMLInputElement)?.value || ""
    }
  };

  if (ws && ws.readyState === WebSocket.OPEN) {
    ws.send(JSON.stringify({ type: "update_settings", settings }));
  }

  orb.setTheme(orbStyleVal);
  if (orbClockHudEl) {
    orbClockHudEl.style.display = showClockHudVal ? "" : "none";
  }
  (window as any).JARVIS_CAMERA_DEVICE_ID = cameraDeviceId;
}

function renderCustomApps(triggerSave: boolean = false) {
  settingsAppsListEl.innerHTML = "";
  currentCustomApps.forEach((app, index) => {
    const div = document.createElement("div");
    div.className = "settings-app-item";
    div.innerHTML = `
      <div style="flex: 1;">
        <input type="text" class="settings-app-rename-input" data-index="${index}" value="${app.label}" style="background: transparent; border: none; border-bottom: 1px dashed rgba(0, 229, 255, 0.4); color: #00e5ff; font-family: inherit; font-size: 14px; font-weight: bold; width: 90%; outline: none; margin-bottom: 4px;" title="Cliquez pour renommer le mot-clé vocal">
        <br>
        <span style="font-size:10px;color:rgba(0,229,255,0.5)">${app.exe_path.replace(/\\/g, '\\\\')}</span>
      </div>
      <div class="settings-app-remove" data-index="${index}">[ X ]</div>
    `;
    settingsAppsListEl.appendChild(div);
  });

  document.querySelectorAll(".settings-app-remove").forEach(btn => {
    btn.addEventListener("click", (e) => {
      const idx = parseInt((e.target as HTMLElement).getAttribute("data-index") || "0", 10);
      currentCustomApps.splice(idx, 1);
      renderCustomApps(true);
    });
  });

  document.querySelectorAll(".settings-app-rename-input").forEach(input => {
    input.addEventListener("change", (e) => {
      const target = e.target as HTMLInputElement;
      const idx = parseInt(target.getAttribute("data-index") || "0", 10);
      const newLabel = target.value.trim();
      if (newLabel && idx < currentCustomApps.length) {
        currentCustomApps[idx].label = newLabel;
        currentCustomApps[idx].id = newLabel.toLowerCase().replace(/[^a-z0-9]/g, "_");
        saveAllSettings();
      } else {
        target.value = currentCustomApps[idx].label;
      }
    });
  });

  if (triggerSave) {
    saveAllSettings();
  }
}
// ═══════════════════════════════════════════════════
// Fonctions d'application des paramètres (anti-treeshaking)
// ═══════════════════════════════════════════════════
function applyMicSettings(settings: any): void {
  const micEl = document.getElementById("settings-mic") as HTMLSelectElement;
  const notDetectedWarn = document.getElementById("mic-not-detected-warning") as HTMLDivElement;
  const pyaudioWarn = document.getElementById("mic-pyaudio-warning") as HTMLDivElement;
  if (!micEl) return;
  if (settings.pyaudio_available === false) {
    micEl.innerHTML = '<option value="" disabled>⚠ PyAudio non installé — micro désactivé</option>';
    micEl.disabled = true;
    if (pyaudioWarn) pyaudioWarn.style.display = "block";
    return;
  }
  micEl.disabled = false;
  micEl.innerHTML = '<option value="">-- Détection automatique --</option>';
  if (pyaudioWarn) pyaudioWarn.style.display = "none";
  const list = settings.mic_list;
  if (list && Array.isArray(list) && list.length > 0) {
    list.forEach((m: {index: number, name: string}) => {
      const opt = document.createElement("option");
      opt.value = String(m.index);
      opt.textContent = `[${m.index}] ${m.name}`;
      if (m.index === settings.mic_device_index) opt.selected = true;
      micEl.appendChild(opt);
    });
    if (notDetectedWarn) notDetectedWarn.style.display = "none";
  } else {
    if (notDetectedWarn) notDetectedWarn.style.display = "block";
  }
}

function applyOrbSettings(settings: any): void {
  const orbEl = document.getElementById("settings-orb-style") as HTMLSelectElement;
  const style = (settings.orb_style && typeof settings.orb_style === "string") ? settings.orb_style : "default";
  if (orbEl) orbEl.value = style;
  // Le thème visuel pilote la couleur de l'orbe. On ne laisse un style d'orbe
  // explicite gagner que s'il est différent du défaut ; sinon le thème prime.
  if (style && style !== "default") orb.setTheme(style);
  else applyThemeOrb();
}

appAddBtn.addEventListener("click", () => {
  const name = appAddNameEl.value.trim();
  const path = appAddPathEl.value.trim();
  if (name && path) {
    const id = name.toLowerCase().replace(/[^a-z0-9]/g, "_");
    currentCustomApps.push({ id, label: name, exe_path: path });
    appAddNameEl.value = "";
    appAddPathEl.value = "";
    renderCustomApps(true);
  }
});

if (appDetectBtn) {
  appDetectBtn.addEventListener("click", () => {
    appDetectBtn.textContent = "🔍 SCAN...";
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ type: "detect_apps" }));
    }
  });
}

if (appDetectSelect) {
  appDetectSelect.addEventListener("change", () => {
    const selectedPath = appDetectSelect.value;
    const selectedText = appDetectSelect.options[appDetectSelect.selectedIndex].text;
    if (selectedPath && selectedText) {
      const alreadyExists = currentCustomApps.some(app => app.exe_path === selectedPath);
      if (!alreadyExists) {
        const id = selectedText.toLowerCase().replace(/[^a-z0-9]/g, "_");
        currentCustomApps.push({ id, label: selectedText, exe_path: selectedPath });
        renderCustomApps(true);
      }
      appDetectSelect.value = "";
    }
  });
}

settingsSaveBtn.addEventListener("click", () => {
  saveAllSettings();
  settingsModalEl.classList.remove("visible");
});

// Événements pour le réglage en direct de la sensibilité micro
if (settingsMicSensEl && settingsMicSensValEl) {
  settingsMicSensEl.addEventListener("input", () => {
    settingsMicSensValEl.textContent = settingsMicSensEl.value;
  });
}

if (settingsMicDynamicEl && settingsMicSensEl && settingsMicSensContainer) {
  settingsMicDynamicEl.addEventListener("change", () => {
    const isDynamic = settingsMicDynamicEl.checked;
    if (isDynamic) {
      settingsMicSensContainer.style.opacity = "0.35";
      settingsMicSensContainer.style.pointerEvents = "none";
      settingsMicSensEl.disabled = true;
    } else {
      settingsMicSensContainer.style.opacity = "1";
      settingsMicSensContainer.style.pointerEvents = "auto";
      settingsMicSensEl.disabled = false;
    }
  });
}

apiKeysSaveBtn.addEventListener("click", () => {
  const geminiEnabledEl = document.getElementById("settings-api-gemini-enabled") as HTMLInputElement;
  const groqEnabledEl = document.getElementById("settings-api-groq-enabled") as HTMLInputElement;
  const youtubeEnabledEl = document.getElementById("settings-api-youtube-enabled") as HTMLInputElement;
  const grokEnabledEl = document.getElementById("settings-api-grok-enabled") as HTMLInputElement;
  const serpapiEnabledEl = document.getElementById("settings-api-serpapi-enabled") as HTMLInputElement;
  const anthropicEnabledEl = document.getElementById("settings-api-anthropic-enabled") as HTMLInputElement;
  const mistralEnabledEl = document.getElementById("settings-api-mistral-enabled") as HTMLInputElement;
  const openaiEnabledEl = document.getElementById("settings-api-openai-enabled") as HTMLInputElement;

  const geminiKeyEl = document.getElementById("settings-api-gemini-key") as HTMLInputElement;
  const groqKeyEl = document.getElementById("settings-api-groq-key") as HTMLInputElement;
  const youtubeKeyEl = document.getElementById("settings-api-youtube-key") as HTMLInputElement;
  const grokKeyEl = document.getElementById("settings-api-grok-key") as HTMLInputElement;
  const serpapiKeyEl = document.getElementById("settings-api-serpapi-key") as HTMLInputElement;
  const anthropicKeyEl = document.getElementById("settings-api-anthropic-key") as HTMLInputElement;
  const mistralKeyEl = document.getElementById("settings-api-mistral-key") as HTMLInputElement;
  const openaiKeyEl = document.getElementById("settings-api-openai-key") as HTMLInputElement;

  const settings = {
    // Toggles API
    api_gemini_enabled: geminiEnabledEl ? geminiEnabledEl.checked : true,
    api_groq_enabled: groqEnabledEl ? groqEnabledEl.checked : true,
    api_youtube_enabled: youtubeEnabledEl ? youtubeEnabledEl.checked : true,
    api_grok_enabled: grokEnabledEl ? grokEnabledEl.checked : true,
    api_serpapi_enabled: serpapiEnabledEl ? serpapiEnabledEl.checked : true,
    api_anthropic_enabled: anthropicEnabledEl ? anthropicEnabledEl.checked : true,
    api_mistral_enabled: mistralEnabledEl ? mistralEnabledEl.checked : true,
    api_openai_enabled: openaiEnabledEl ? openaiEnabledEl.checked : true,
    
    // Clés API pour le .env
    api_keys: {
      GEMINI_API_KEY: geminiKeyEl ? geminiKeyEl.value.trim() : "",
      GROQ_API_KEY: groqKeyEl ? groqKeyEl.value.trim() : "",
      YOUTUBE_API_KEY: youtubeKeyEl ? youtubeKeyEl.value.trim() : "",
      XAI_API_KEY: grokKeyEl ? grokKeyEl.value.trim() : "",
      SERPAPI_API_KEY: serpapiKeyEl ? serpapiKeyEl.value.trim() : "",
      ANTHROPIC_API_KEY: anthropicKeyEl ? anthropicKeyEl.value.trim() : "",
      MISTRAL_API_KEY: mistralKeyEl ? mistralKeyEl.value.trim() : "",
      OPENAI_API_KEY: openaiKeyEl ? openaiKeyEl.value.trim() : ""
    }
  };

  if (ws && ws.readyState === WebSocket.OPEN) {
    ws.send(JSON.stringify({ type: "update_settings", settings }));
  }

  apiKeysModalEl.style.display = "none";
});

// Toggle visibilité des mots de passe (oeil)
document.querySelectorAll(".toggle-password-eye").forEach(eye => {
  eye.addEventListener("click", () => {
    const targetId = eye.getAttribute("data-target");
    if (targetId) {
      const input = document.getElementById(targetId) as HTMLInputElement;
      if (input) {
        if (input.type === "password") {
          input.type = "text";
          eye.textContent = "🙈";
        } else {
          input.type = "password";
          eye.textContent = "👁️";
        }
      }
    }
  });
});

// ── HA Entities UI ────────────────────────────────────────────────────────────
function renderHaEntities() {
  haEntitiesListEl.innerHTML = "";
  const entries = currentHaEntities[currentHaTab];
  if (entries.length === 0) {
    const empty = document.createElement("div");
    empty.style.cssText = "padding:10px;font-size:11px;color:rgba(0,229,255,0.3);text-align:center;";
    empty.textContent = "Aucun appareil — ajoutez-en un ci-dessous";
    haEntitiesListEl.appendChild(empty);
    return;
  }
  entries.forEach((entry, index) => {
    const div = document.createElement("div");
    div.className = "settings-app-item";
    div.innerHTML = `
      <div>
        <strong style="text-transform:capitalize">${entry.nom}</strong>
        <br><span style="font-size:10px;color:rgba(0,229,255,0.45)">${entry.entity_id}</span>
      </div>
      <div class="settings-app-remove ha-remove" data-index="${index}">[ X ]</div>
    `;
    haEntitiesListEl.appendChild(div);
  });
  document.querySelectorAll(".ha-remove").forEach(btn => {
    btn.addEventListener("click", (e) => {
      const idx = parseInt((e.target as HTMLElement).getAttribute("data-index") || "0", 10);
      currentHaEntities[currentHaTab].splice(idx, 1);
      renderHaEntities();
    });
  });
}

document.querySelectorAll(".ha-tab-btn").forEach(btn => {
  btn.addEventListener("click", () => {
    document.querySelectorAll(".ha-tab-btn").forEach(b => b.classList.remove("active"));
    btn.classList.add("active");
    currentHaTab = (btn as HTMLElement).dataset.tab as HaTab;
    renderHaEntities();
  });
});

haAddBtn.addEventListener("click", () => {
  const nom = haAddNomEl.value.trim();
  const entity_id = haAddEntityEl.value.trim();
  if (nom && entity_id) {
    currentHaEntities[currentHaTab].push({ nom, entity_id });
    haAddNomEl.value = "";
    haAddEntityEl.value = "";
    renderHaEntities();
  }
});

// ── Boot Sequence ─────────────────────────────────────────────────────────────
function runBootSequence(): void {
  const overlay    = document.getElementById("boot-overlay") as HTMLDivElement;
  const modulesEl  = document.getElementById("boot-modules") as HTMLDivElement;
  const progressBar = document.getElementById("boot-progress-bar") as HTMLDivElement;
  const progressLbl = document.getElementById("boot-progress-label") as HTMLDivElement;
  const statusText  = document.getElementById("boot-status-text") as HTMLDivElement;
  const finalText   = document.getElementById("boot-final-text") as HTMLDivElement;
  const buildYear   = document.getElementById("boot-build-year") as HTMLSpanElement;

  if (!overlay) return;
  if (buildYear) buildYear.textContent = new Date().getFullYear().toString();

  const MODULES = [
    "NEURAL_NETWORK_CORE",
    "SPEECH_RECOGNITION",
    "KNOWLEDGE_DATABASE",
    "VISION_SYSTEM",
    "AUDIO_SYNTHESIS_TTS",
    "HOME_AUTOMATION_LINK",
    "COMM_PROTOCOLS",
  ];

  const TOTAL = MODULES.length + 1; // +1 pour la connexion serveur
  let done = 0;

  function setProgress(n: number) {
    const pct = Math.round((n / TOTAL) * 100);
    progressBar.style.width = `${pct}%`;
    progressLbl.textContent = `CHARGEMENT... ${pct}%`;
  }

  function addLine(name: string): HTMLDivElement {
    const div = document.createElement("div");
    div.className = "boot-module-line";
    div.innerHTML = `
      <span class="boot-module-name">${name}</span>
      <span class="boot-module-dots"></span>
      <span class="boot-module-status pending">INITIALISATION</span>
    `;
    modulesEl.appendChild(div);
    return div;
  }

  function setLineOnline(line: HTMLDivElement, mode: "ok" | "wait" = "ok") {
    const s = line.querySelector(".boot-module-status") as HTMLSpanElement;
    s.classList.remove("pending");
    if (mode === "ok") {
      s.textContent = "[ ONLINE ]";
      s.classList.add("online");
      done++;
      setProgress(done);
    } else {
      s.textContent = "[ EN ATTENTE ]";
      s.classList.add("waiting");
    }
  }

  function finishBoot() {
    setProgress(TOTAL);
    progressLbl.textContent = "CHARGEMENT... 100%";
    statusText.textContent = "SYSTÈMES OPÉRATIONNELS — BONNE JOURNÉE";
    finalText.style.opacity = "1";
    finalText.style.transform = "scale(1)";

    setTimeout(() => {
      overlay.style.opacity = "0";
      setTimeout(() => { 
        overlay.style.display = "none"; 

        // --- FIRST LAUNCH CHECK ---
        const firstLaunchModal = document.getElementById("first-launch-modal");
        if (firstLaunchModal && !localStorage.getItem("jarvis_first_launch_done_v9")) {
          firstLaunchModal.classList.remove("hidden");
          firstLaunchModal.style.display = "flex";
          
          const btnSite = document.getElementById("first-launch-btn-site");
          const btnClose = document.getElementById("first-launch-btn-close");
          
          const closeFirstLaunch = () => {
            localStorage.setItem("jarvis_first_launch_done_v9", "true");
            firstLaunchModal.classList.add("hidden");
            firstLaunchModal.style.display = "none";
          };
          
          if (btnSite) {
            btnSite.onclick = () => {
              window.open("https://www.techenclair.fr", "_blank");
              closeFirstLaunch();
            };
          }
          if (btnClose) {
            btnClose.onclick = closeFirstLaunch;
          }
        }
        // --------------------------

      }, 900);
    }, 1600);
  }

  // Défilement des modules locaux (~280 ms entre chaque)
  MODULES.forEach((name, i) => {
    const delay = 250 + i * 280;
    setTimeout(() => {
      const line = addLine(name);
      setTimeout(() => setLineOnline(line, "ok"), 200);
    }, delay);
  });

  // Module serveur — attend la connexion WebSocket
  const serverDelay = 250 + MODULES.length * 280;
  setTimeout(() => {
    const line = addLine("SERVER_CONNECTION");
    statusText.textContent = "CONNEXION AU SERVEUR EN COURS...";

    if (wsConnectedBeforeBoot) {
      // WS déjà connecté avant cette étape
      setTimeout(() => { setLineOnline(line, "ok"); setTimeout(finishBoot, 350); }, 250);
    } else {
      setLineOnline(line, "wait");
      bootConnectedCallback = () => {
        const s = line.querySelector(".boot-module-status") as HTMLSpanElement;
        s.classList.remove("waiting");
        s.textContent = "[ ONLINE ]";
        s.classList.add("online");
        done++;
        setTimeout(finishBoot, 350);
      };
      // Sécurité : ferme le boot après 25 s si le serveur ne répond pas
      setTimeout(() => {
        if (bootConnectedCallback) {
          bootConnectedCallback = null;
          overlay.style.opacity = "0";
          setTimeout(() => { overlay.style.display = "none"; }, 900);
        }
      }, 25_000);
    }
  }, serverDelay);
}

// ── Boot ──────────────────────────────────────────────────────────────────────
setConnected(false);
applyState("idle");
setMuted(false);
injectVisionButton();
initJarvisGlobe();
initIPTVPlayer(ws);
initHADashboard(ws);
initOsAppStore();
(window as unknown as Record<string, unknown>)._jarvisWs = ws;
runBootSequence();


// Masquer le message d'aide après 10 secondes
setTimeout(() => {
  const tip = document.getElementById("user-tip");
  if (tip) {
    tip.style.opacity = "0";
    setTimeout(() => { tip.style.display = "none"; }, 1000);
  }
}, 10000);
// ── Help HUD Logic ───────────────────────────────────────────────────────────
function showHelpHUD() {
  helpOverlayEl.style.display = "block";
  helpOverlayEl.innerHTML = "";

  // Select 16 random commands
  const shuffled = [...HELP_COMMANDS].sort(() => 0.5 - Math.random());
  const selected = shuffled.slice(0, 16);

  selected.forEach((cmd, i) => {
    const isRight = i % 2 === 1;
    const widget = document.createElement("div");
    widget.className = `help-widget ${isRight ? 'right' : ''}`;

    // Grid-like positioning with random offsets (starting lower to avoid the tip)
    const row = Math.floor(i / 2);
    const top = 160 + (row * 95) + (Math.random() * 15);
    widget.style.top = `${top}px`;

    // Position them more towards the center to "fill around"
    const sideOffset = 30 + (Math.random() * 40);
    if (isRight) widget.style.right = `${sideOffset}px`;
    else widget.style.left = `${sideOffset}px`;

    // Faster reveal and varied animations
    widget.style.animation = `float ${2 + Math.random() * 2}s ease-in-out infinite`;
    widget.style.animationDelay = `${Math.random() * 1}s`;

    widget.innerHTML = `
      <div class="help-widget-title" style="display:flex; justify-content: space-between;">
        <span>CAPACITÉ ${Math.floor(Math.random() * 999)}</span>
        <span style="opacity:0.3">[SYNC]</span>
      </div>
      <div class="help-widget-cmd">"${cmd}"</div>
    `;

    helpOverlayEl.appendChild(widget);

    // Cinematic reveal synchronized with speech (one widget every 800ms)
    setTimeout(() => widget.classList.add("visible"), i * 800);
  });

  // Auto-hide after 20 seconds
  setTimeout(() => {
    const widgets = document.querySelectorAll(".help-widget");
    widgets.forEach((w, i) => {
      setTimeout(() => w.classList.remove("visible"), i * 100);
    });
    setTimeout(() => helpOverlayEl.style.display = "none", 2000);
  }, 20000);
}

// ── Timer Logic ─────────────────────────────────────────────────────────────
function startTimer(duration: number) {
  stopTimer();
  timerSeconds = duration;
  timerTotalSeconds = duration;
  timerHudEl.style.display = "block";
  updateTimerDisplay();

  timerInterval = window.setInterval(() => {
    timerSeconds--;
    updateTimerDisplay();
    if (timerSeconds <= 0) {
      timerDisplayEl.textContent = "FINISH";
      timerDisplayEl.style.color = "#ff3d00";
      setTimeout(() => stopTimer(), 3000);
    }
  }, 1000);
}

function stopTimer() {
  if (timerInterval) {
    clearInterval(timerInterval);
    timerInterval = null;
  }
  timerHudEl.style.display = "none";
}

function addTimer(extraSeconds: number) {
  timerSeconds += extraSeconds;
  timerTotalSeconds += extraSeconds;
  updateTimerDisplay();
}

function removeTimer(lessSeconds: number) {
  timerSeconds = Math.max(0, timerSeconds - lessSeconds);
  updateTimerDisplay();
}

function updateTimerDisplay() {
  const mins = Math.floor(timerSeconds / 60);
  const secs = timerSeconds % 60;
  timerDisplayEl.textContent = `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;

  const progress = ((timerTotalSeconds - timerSeconds) / timerTotalSeconds) * 100;
  timerProgressEl.style.width = `${progress}%`;

  // Flash effect if near end
  if (timerSeconds <= 10) {
    timerDisplayEl.style.color = (timerSeconds % 2 === 0) ? "#ff3d00" : "#00e5ff";
  } else {
    timerDisplayEl.style.color = "#00e5ff";
  }
}

connect();

// ── Clock Logic ─────────────────────────────────────────────────────────────
function updateClock() {
  const now = new Date();
  const timeStr = now.toLocaleTimeString('fr-FR', { hour12: false });

  // Globe overlay clock (existing)
  const clockEl = document.getElementById("globe-clock");
  if (clockEl) clockEl.textContent = timeStr;

  // Orb HUD clock (top of screen, always visible)
  const orbTime = document.getElementById("orb-time-display");
  if (orbTime) orbTime.textContent = timeStr;

  const orbDate = document.getElementById("orb-date-display");
  if (orbDate) {
    orbDate.textContent = now.toLocaleDateString('fr-FR', {
      day: '2-digit', month: '2-digit', year: 'numeric'
    });
  }
}
setInterval(updateClock, 1000);
updateClock();

// Silence unused-import warning for showError
void showError;

// ── Temp Panel (left side — Home Assistant interior) ────────────────────────

// Comfort scale: 10°C → 30°C maps to 0% → 100%
function tempToPercent(t: number): number {
  return Math.min(100, Math.max(0, ((t - 10) / 20) * 100));
}

function showTempPanel(d: {
  piece: string; temperature: string; humidite?: string | null;
}) {
  const panel = document.getElementById("temp-panel");
  if (!panel) return;

  const temp = parseFloat(d.temperature) || 0;
  (document.getElementById("tp-piece") as HTMLElement).textContent = d.piece.toUpperCase();
  (document.getElementById("tp-temp") as HTMLElement).textContent = String(Math.round(temp));

  const humRow = document.getElementById("tp-hum-row") as HTMLElement;
  if (d.humidite) {
    (document.getElementById("tp-hum") as HTMLElement).textContent = d.humidite;
    humRow.style.display = "flex";
  } else {
    humRow.style.display = "none";
  }

  const pct = tempToPercent(temp);
  (document.getElementById("tp-marker") as HTMLElement).style.left = `${pct}%`;

  panel.classList.add("tp-visible");
}

function hideTempPanel() {
  const panel = document.getElementById("temp-panel");
  if (!panel) return;
  panel.classList.remove("tp-visible");
  panel.style.left = "";
  panel.style.top = "";
  panel.style.transform = "";
}

document.getElementById("tp-close-btn")?.addEventListener("click", hideTempPanel);

// ── Weather Panel ────────────────────────────────────────────────────────────

const WEATHER_ICONS: Record<number, string> = {
  0: "☀️", 1: "🌤", 2: "⛅", 3: "☁️",
  45: "🌫", 48: "🌫",
  51: "🌦", 53: "🌦", 55: "🌧",
  61: "🌧", 63: "🌧", 65: "🌧",
  71: "🌨", 73: "🌨", 75: "❄️", 77: "🌨",
  80: "🌦", 81: "🌦", 82: "⛈",
  85: "🌨", 86: "❄️",
  95: "⛈", 96: "⛈", 99: "⛈",
};

function showWeatherPanel(d: {
  ville: string; temperature: number; ressenti: number;
  humidite: number; vent: number; code: number; description: string;
}) {
  const panel = document.getElementById("weather-panel");
  if (!panel) return;

  (document.getElementById("wp-city") as HTMLElement).textContent = d.ville.toUpperCase();
  (document.getElementById("wp-temp") as HTMLElement).textContent = String(d.temperature);
  (document.getElementById("wp-desc") as HTMLElement).textContent = d.description.toUpperCase();
  (document.getElementById("wp-feels") as HTMLElement).textContent = String(d.ressenti);
  (document.getElementById("wp-humidity") as HTMLElement).textContent = String(d.humidite);
  (document.getElementById("wp-wind") as HTMLElement).textContent = String(d.vent);
  (document.getElementById("wp-icon") as HTMLElement).textContent = WEATHER_ICONS[d.code] ?? "🌡";

  panel.classList.add("wp-visible");
}

function hideWeatherPanel() {
  const panel = document.getElementById("weather-panel");
  if (!panel) return;
  panel.classList.remove("wp-visible");
  panel.style.left = "";
  panel.style.right = "";
  panel.style.top = "";
  panel.style.transform = "";
}

document.getElementById("wp-close-btn")?.addEventListener("click", hideWeatherPanel);

// ── Drag & Drop — Temp Panel & Weather Panel ─────────────────────────────────
function makePanelDraggable(panel: HTMLElement, header: HTMLElement) {
  let isDragging = false;
  let offsetX = 0;
  let offsetY = 0;

  header.style.cursor = "grab";

  header.addEventListener("mousedown", (e) => {
    isDragging = true;
    const rect = panel.getBoundingClientRect();
    panel.style.left      = `${rect.left}px`;
    panel.style.top       = `${rect.top}px`;
    panel.style.right     = "auto";
    panel.style.bottom    = "auto";
    panel.style.transform = "none";
    offsetX = e.clientX - rect.left;
    offsetY = e.clientY - rect.top;
    header.style.cursor = "grabbing";
    e.preventDefault();
  });

  document.addEventListener("mousemove", (e) => {
    if (!isDragging) return;
    const newX = Math.max(0, Math.min(e.clientX - offsetX, window.innerWidth  - panel.offsetWidth));
    const newY = Math.max(0, Math.min(e.clientY - offsetY, window.innerHeight - panel.offsetHeight));
    panel.style.left = `${newX}px`;
    panel.style.top  = `${newY}px`;
  });

  document.addEventListener("mouseup", () => {
    if (isDragging) { isDragging = false; header.style.cursor = "grab"; }
  });
}

const _tpPanel  = document.getElementById("temp-panel");
const _tpHeader = _tpPanel?.querySelector(".tp-header") as HTMLElement | null;
if (_tpPanel && _tpHeader) makePanelDraggable(_tpPanel, _tpHeader);

const _wpPanel  = document.getElementById("weather-panel");
const _wpHeader = _wpPanel?.querySelector(".wp-header") as HTMLElement | null;
if (_wpPanel && _wpHeader) makePanelDraggable(_wpPanel, _wpHeader);

if (orbClockHudEl) makePanelDraggable(orbClockHudEl, orbClockHudEl);

// ── Recipe Modal Logic ───────────────────────────────────────────────────────

const recipeModal = document.getElementById("recipe-modal");
const closeRecipeBtn = document.getElementById("close-recipe");
const recipeHeader = document.getElementById("recipe-header");

if (closeRecipeBtn && recipeModal) {
  closeRecipeBtn.addEventListener("click", () => {
    recipeModal.classList.add("hidden");
  });
}

// Drag & Drop for Recipe Modal
if (recipeModal && recipeHeader) {
  let isDragging = false;
  let offsetX = 0;
  let offsetY = 0;

  recipeHeader.addEventListener("mousedown", (e) => {
    isDragging = true;
    const rect = recipeModal.getBoundingClientRect();
    offsetX = e.clientX - rect.left;
    offsetY = e.clientY - rect.top;
    recipeModal.style.cursor = "grabbing";
  });

  document.addEventListener("mousemove", (e) => {
    if (!isDragging) return;
    
    // Prevent dragging outside the window
    let newX = e.clientX - offsetX;
    let newY = e.clientY - offsetY;
    
    // Boundaries
    const maxX = window.innerWidth - recipeModal.offsetWidth;
    const maxY = window.innerHeight - recipeModal.offsetHeight;
    
    newX = Math.max(0, Math.min(newX, maxX));
    newY = Math.max(0, Math.min(newY, maxY));

    recipeModal.style.left = `${newX}px`;
    recipeModal.style.top = `${newY}px`;
    recipeModal.style.transform = "none"; // disable original translation for dragging
  });

  document.addEventListener("mouseup", () => {
    if (isDragging) {
      isDragging = false;
      recipeModal.style.cursor = "default";
    }
  });
}

// ── Image Panels Logic (Iron Man style floating panels) ──────────────────────
let imgPanelCount = 0;
let maxZIndex = 600;

function showImagePanel(query: string, images: string[]) {
  const container = document.getElementById("image-panels-container");
  if (!container) return;

  const panel = document.createElement("div");
  panel.className = "img-panel";
  
  // Bring to front on mousedown
  panel.addEventListener("mousedown", () => {
    maxZIndex++;
    panel.style.zIndex = maxZIndex.toString();
  });

  // Calculate dynamic position with cascade offset
  const offset = (imgPanelCount % 6) * 30;
  const left = Math.max(20, (window.innerWidth - 420) / 2 + offset);
  const top = Math.max(20, (window.innerHeight - 380) / 2 + offset);
  panel.style.left = `${left}px`;
  panel.style.top = `${top}px`;
  imgPanelCount++;

  // Add scanlines, corners & structure
  panel.innerHTML = `
    <div class="img-panel-scanlines"></div>
    <div class="img-panel-corner-tr"></div>
    <div class="img-panel-corner-bl"></div>
    <div class="img-panel-header">
      <div class="img-panel-drag-icon">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M5 9l7-7 7 7M5 15l7 7 7-7" />
        </svg>
      </div>
      <div class="img-panel-title">IMAGE_SCAN // ${query.toUpperCase()}</div>
      <button class="img-panel-close">&times;</button>
    </div>
    <div class="img-panel-status">
      <span>GRID STATUS: ACTIVE</span>
      <span class="img-panel-meta">FOUND: ${images.length} SECURE_NODES</span>
    </div>
    <div class="img-panel-grid"></div>
    <div class="img-panel-footer">
      <span>SYS.LOC: LOCAL_HUD</span>
      <span>JARVIS_V2.6</span>
    </div>
  `;

  // Populate grid
  const grid = panel.querySelector(".img-panel-grid") as HTMLElement;
  if (images.length === 0) {
    const empty = document.createElement("div");
    empty.style.gridColumn = "span 3";
    empty.style.padding = "20px";
    empty.style.textAlign = "center";
    empty.style.fontSize = "10px";
    empty.style.color = "rgba(0, 229, 255, 0.4)";
    empty.textContent = "NO SECURE NODE RESOLVED";
    grid.appendChild(empty);
  } else {
    images.forEach((url, index) => {
      const item = document.createElement("div");
      item.className = "img-panel-item";
      // Stagger animation delay
      item.style.animationDelay = `${index * 0.08}s`;
      
      const img = document.createElement("img");
      img.src = url;
      img.alt = query;
      img.loading = "lazy";
      
      // Handle image load error
      img.onerror = () => {
        img.src = "data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='100' height='100' viewBox='0 0 100 100'><rect width='100' height='100' fill='rgba(0,8,20,0.8)'/><text x='50%' y='50%' dominant-baseline='middle' text-anchor='middle' font-family='Courier, monospace' font-size='10' fill='%23ff3366'>LOAD_ERR</text></svg>";
      };

      item.appendChild(img);
      
      // Click for fullscreen zoom
      item.addEventListener("click", () => {
        showFullscreenImage(url, query);
      });

      grid.appendChild(item);
    });
  }

  // Setup close button
  const closeBtn = panel.querySelector(".img-panel-close") as HTMLElement;
  closeBtn.addEventListener("click", () => {
    panel.classList.remove("visible");
    setTimeout(() => {
      panel.remove();
    }, 400);
  });

  // Setup Drag & Drop
  const header = panel.querySelector(".img-panel-header") as HTMLElement;
  makePanelDraggable(panel, header);

  // Append & animate in
  container.appendChild(panel);
  
  // Trigger Reflow to animate opacity/scale
  void panel.offsetWidth;
  panel.classList.add("visible");
}

function showFullscreenImage(url: string, query: string) {
  const overlay = document.createElement("div");
  overlay.className = "img-zoom-overlay";

  overlay.innerHTML = `
    <button class="img-zoom-close">CLOSE [ESC]</button>
    <img src="${url}" alt="${query}" />
    <div class="img-zoom-label">RESOLVED NODE // ${query.toUpperCase()}</div>
  `;

  const closeOverlay = () => {
    overlay.remove();
    document.removeEventListener("keydown", handleEsc);
  };

  const handleEsc = (e: KeyboardEvent) => {
    if (e.key === "Escape") {
      closeOverlay();
    }
  };

  overlay.addEventListener("click", (e) => {
    if (e.target === overlay || (e.target as HTMLElement).classList.contains("img-zoom-close")) {
      closeOverlay();
    }
  });

  document.addEventListener("keydown", handleEsc);
  document.body.appendChild(overlay);
}

// ── Antivirus HUD Logic ──────────────────────────────────────────────────────
const avPanelEl       = document.getElementById("av-panel") as HTMLDivElement;
const avHeaderEl      = document.getElementById("av-panel-header") as HTMLDivElement;
const avCloseBtn      = document.getElementById("av-panel-close-btn") as HTMLButtonElement;
const avCancelBtn     = document.getElementById("av-cancel-btn") as HTMLButtonElement;
const avProgressFill  = document.getElementById("av-progress-bar-fill") as HTMLDivElement;
const avProgressPct   = document.getElementById("av-progress-percent") as HTMLDivElement;
const avStatusLabel   = document.getElementById("av-status-label") as HTMLSpanElement;
const avThreatsCount  = document.getElementById("av-threats-count") as HTMLSpanElement;
const avCurrentFile   = document.getElementById("av-current-file") as HTMLDivElement;
const avConsole       = document.getElementById("av-console") as HTMLDivElement;

let avScanInProgress = false;
let avThreatsList: any[] = [];
let avResolvedThreatsCount = 0;

// Setup Drag & Drop
if (avPanelEl && avHeaderEl) {
  makePanelDraggable(avPanelEl, avHeaderEl);
}

function openAntivirusPanel() {
  if (!avPanelEl) return;

  // Initial positioning
  const left = Math.max(20, (window.innerWidth - 460) / 2);
  const top = Math.max(20, (window.innerHeight - 420) / 2);
  avPanelEl.style.left = `${left}px`;
  avPanelEl.style.top = `${top}px`;
  avPanelEl.style.right = "auto";
  avPanelEl.style.bottom = "auto";
  avPanelEl.style.transform = "none";

  // Reset UI elements
  avPanelEl.classList.remove("threat-detected");
  avPanelEl.classList.remove("hidden");
  void avPanelEl.offsetWidth; // Reflow
  avPanelEl.classList.add("visible");

  avStatusLabel.textContent = "SYS_STATUS: INITIALISATION";
  avThreatsCount.textContent = "MENACES DÉTECTÉES: 0";
  avProgressFill.style.width = "0%";
  avProgressPct.textContent = "0%";
  avCurrentFile.textContent = "CONNEXION AU NOYAU DE SÉCURITÉ...";
  avConsole.innerHTML = '<div class="av-console-line info">[INFO] Initialisation du système de sécurité JARVIS v2.6...</div>';
  
  // Clean active threats state
  avThreatsList = [];
  avResolvedThreatsCount = 0;
  const listContainer = document.getElementById("av-threats-list");
  if (listContainer) {
    listContainer.innerHTML = "";
    listContainer.classList.add("hidden");
  }
  
  // Show radar and progress controls
  const radarCont = avPanelEl.querySelector(".av-radar-container") as HTMLElement;
  const progressCont = avPanelEl.querySelector(".av-progress-bar-container") as HTMLElement;
  const currentFileCont = document.getElementById("av-current-file") as HTMLElement;
  if (radarCont) radarCont.style.display = "";
  if (progressCont) progressCont.style.display = "";
  if (currentFileCont) currentFileCont.style.display = "";

  avCancelBtn.textContent = "ANNULER";
  avCancelBtn.disabled = false;
  avScanInProgress = true;

  // Send start scan to backend
  if (ws && ws.readyState === WebSocket.OPEN) {
    ws.send(JSON.stringify({ type: "av_scan_start" }));
  }
}

function closeAntivirusPanel() {
  if (!avPanelEl) return;
  
  if (avScanInProgress) {
    cancelAvScan();
  }

  avPanelEl.classList.remove("visible");
  setTimeout(() => {
    avPanelEl.classList.add("hidden");
  }, 400);
}

function cancelAvScan() {
  avScanInProgress = false;
  if (ws && ws.readyState === WebSocket.OPEN) {
    ws.send(JSON.stringify({ type: "av_scan_cancel" }));
  }
  avCancelBtn.textContent = "FERMER";
}

if (avCloseBtn) {
  avCloseBtn.addEventListener("click", closeAntivirusPanel);
}

if (avCancelBtn) {
  avCancelBtn.addEventListener("click", () => {
    if (avScanInProgress) {
      cancelAvScan();
    } else {
      closeAntivirusPanel();
    }
  });
}

function handleAntivirusWSMessage(data: any) {
  if (!avConsole) return;

  if (data.type === "av_start") {
    const line = document.createElement("div");
    line.className = "av-console-line info";
    line.textContent = `[NOYAU] ${data.message || 'Moteur antivirus démarré.'}`;
    avConsole.appendChild(line);
    avConsole.scrollTop = avConsole.scrollHeight;
  }
  
  else if (data.type === "av_progress") {
    // Update progress bar
    if (data.percent !== undefined) {
      avProgressFill.style.width = `${data.percent}%`;
      avProgressPct.textContent = `${data.percent}%`;
    }
    
    if (data.step) {
      avStatusLabel.textContent = `SYS_STATUS: ${data.step.toUpperCase()}_SCAN`;
    }
    
    if (data.threats_found !== undefined) {
      avThreatsCount.textContent = `MENACES DÉTECTÉES: ${data.threats_found}`;
    }
    
    if (data.message) {
      avCurrentFile.textContent = data.message;
      
      const line = document.createElement("div");
      line.className = "av-console-line";
      
      if (data.step === "registry") {
        line.textContent = `[REGISTRE] ${data.message}`;
      } else if (data.step === "processes") {
        line.textContent = `[PROCESSUS] ${data.message}`;
      } else {
        line.textContent = `[FICHIER] ${data.message}`;
      }
      
      avConsole.appendChild(line);
      avConsole.scrollTop = avConsole.scrollHeight;
    }
  }
  
  else if (data.type === "av_threat_detected" && data.threat) {
    avThreatsList.push(data.threat);
    avPanelEl.classList.add("threat-detected");
    
    const line = document.createElement("div");
    line.className = "av-console-line threat";
    line.textContent = `[DANGER] Menace détectée : ${data.threat.class} -> ${data.threat.name} (${data.threat.desc})`;
    avConsole.appendChild(line);
    avConsole.scrollTop = avConsole.scrollHeight;
  }
  
  else if (data.type === "av_complete") {
    avScanInProgress = false;
    avCancelBtn.textContent = "FERMER";
    avProgressFill.style.width = "100%";
    avProgressPct.textContent = "100%";
    
    const line = document.createElement("div");
    if (data.status === "infected") {
      avPanelEl.classList.add("threat-detected");
      avStatusLabel.textContent = "SYS_STATUS: VULNÉRABLE";
      line.className = "av-console-line threat";
      line.textContent = `[TERMINE] Analyse terminée. Menaces détectées : ${data.threats ? data.threats.length : avThreatsList.length}. Système vulnérable.`;
      
      // Store threats list
      avThreatsList = data.threats || avThreatsList;
      avResolvedThreatsCount = 0;
      
      // Render the threat controls
      renderThreatsList();
    } else if (data.status === "error") {
      avStatusLabel.textContent = "SYS_STATUS: ERREUR";
      line.className = "av-console-line threat";
      line.textContent = `[ERREUR] ${data.message || 'Une erreur système est survenue pendant le scan.'}`;
    } else {
      avStatusLabel.textContent = "SYS_STATUS: SAIN";
      line.className = "av-console-line success";
      line.textContent = `[TERMINE] Analyse terminée. Aucune menace détectée. Système entièrement sécurisé.`;
    }
    avConsole.appendChild(line);
    avConsole.scrollTop = avConsole.scrollHeight;
  }
  
  else if (data.type === "av_cancel") {
    avScanInProgress = false;
    avCancelBtn.textContent = "FERMER";
    avStatusLabel.textContent = "SYS_STATUS: INTERROMPU";
    
    const line = document.createElement("div");
    line.className = "av-console-line info";
    line.textContent = `[INTERROMPU] ${data.message || "L'analyse antivirus a été annulée."}`;
    avConsole.appendChild(line);
    avConsole.scrollTop = avConsole.scrollHeight;
  }

  else if (data.type === "av_live_threat_intercepted" && data.threat) {
    const line = document.createElement("div");
    line.className = "av-console-line threat";
    line.textContent = `[INTERCEPTION LIVE] Menace neutralisée : ${data.threat.class} -> ${data.threat.name} (${data.threat.desc})`;
    if (avConsole) {
      avConsole.appendChild(line);
      avConsole.scrollTop = avConsole.scrollHeight;
    }
    
    const toast = document.createElement("div");
    toast.className = "security-toast";
    toast.innerHTML = `
      <div class="security-toast-header">
        <span>🛡️ INTERCEPTION SÉCURITÉ LIVE</span>
        <button class="security-toast-close">&times;</button>
      </div>
      <div class="security-toast-body">
        <strong>Menace :</strong> ${data.threat.class}<br>
        <strong>Objet :</strong> ${data.threat.name}<br>
        <strong>Statut :</strong> Neutralisé & sécurisé<br>
        <span class="security-toast-target">${data.threat.target}</span>
      </div>
    `;
    document.body.appendChild(toast);
    
    const closeBtn = toast.querySelector(".security-toast-close");
    if (closeBtn) {
      closeBtn.addEventListener("click", () => {
        toast.remove();
      });
    }
    
    setTimeout(() => {
      if (toast.parentNode) {
        toast.remove();
      }
    }, 15000);
  }

  else if (data.type === "av_action_result") {
    const idx = avThreatsList.findIndex(t => t.target === data.threat_target);
    const line = document.createElement("div");
    if (data.success) {
      line.className = "av-console-line success";
      line.textContent = `[RÉSOLU] Action '${data.action.toUpperCase()}' : ${data.message}`;
      
      if (idx !== -1) {
        const itemEl = document.getElementById(`av-threat-${idx}`);
        if (itemEl && !itemEl.classList.contains("resolved")) {
          itemEl.classList.add("resolved");
          const buttons = itemEl.querySelectorAll(".av-action-btn") as NodeListOf<HTMLButtonElement>;
          buttons.forEach(btn => btn.disabled = true);
          
          const badge = document.createElement("div");
          badge.className = "av-threat-status-badge";
          let actStr = "RÉSOLU";
          if (data.action === "delete") actStr = "SUPPRIMÉ";
          else if (data.action === "clean") actStr = "NETTOYÉ";
          else if (data.action === "quarantine") actStr = "MIS EN QUARANTAINE";
          else if (data.action === "allow") actStr = "AUTORISÉ";
          badge.textContent = `◈ STATUT: ${actStr}`;
          itemEl.appendChild(badge);
          
          avResolvedThreatsCount++;
          avThreatsCount.textContent = `MENACES DÉTECTÉES: ${avThreatsList.length - avResolvedThreatsCount}`;
          
          if (avResolvedThreatsCount === avThreatsList.length) {
            avPanelEl.classList.remove("threat-detected");
            avStatusLabel.textContent = "SYS_STATUS: SAIN";
            const sLine = document.createElement("div");
            sLine.className = "av-console-line success";
            sLine.textContent = "[SYSTEME] Résolution complète. Toutes les menaces ont été traitées.";
            avConsole.appendChild(sLine);
            
            // Verbal feedback
            if (ws && ws.readyState === WebSocket.OPEN) {
              ws.send(JSON.stringify({
                type: "av_speak",
                text: "Toutes les menaces détectées ont été résolues. Votre système est entièrement sécurisé."
              }));
            }
          }
        }
      }
    } else {
      line.className = "av-console-line threat";
      line.textContent = `[ÉCHEC] Action '${data.action.toUpperCase()}' sur la cible ${data.threat_target} : ${data.message}`;
      
      // Re-enable buttons
      if (idx !== -1) {
        const itemEl = document.getElementById(`av-threat-${idx}`);
        if (itemEl) {
          const buttons = itemEl.querySelectorAll(".av-action-btn") as NodeListOf<HTMLButtonElement>;
          buttons.forEach(btn => btn.disabled = false);
        }
      }
    }
    avConsole.appendChild(line);
    avConsole.scrollTop = avConsole.scrollHeight;
  }
}

function renderThreatsList() {
  const listContainer = document.getElementById("av-threats-list");
  if (!listContainer) return;
  
  listContainer.innerHTML = "";
  listContainer.classList.remove("hidden");
  
  // Hide scanning visuals
  const radarCont = avPanelEl.querySelector(".av-radar-container") as HTMLElement;
  const progressCont = avPanelEl.querySelector(".av-progress-bar-container") as HTMLElement;
  const currentFileCont = document.getElementById("av-current-file") as HTMLElement;
  if (radarCont) radarCont.style.display = "none";
  if (progressCont) progressCont.style.display = "none";
  if (currentFileCont) currentFileCont.style.display = "none";
  
  if (avThreatsList.length === 0) {
    listContainer.innerHTML = '<div style="text-align:center;font-size:10px;color:#22c55e;padding:10px;">AUCUNE MENACE ACTIVE</div>';
    return;
  }
  
  avThreatsList.forEach((threat, idx) => {
    const item = document.createElement("div");
    item.className = "av-threat-item";
    item.id = `av-threat-${idx}`;
    
    item.innerHTML = `
      <div class="av-threat-meta">
        <span class="av-threat-class">${threat.class}</span>
        <span class="av-threat-type">${threat.type.toUpperCase()}</span>
      </div>
      <div class="av-threat-details">
        <span class="av-threat-name">${threat.name}</span>
        <span class="av-threat-target">${threat.target}</span>
        <span class="av-threat-desc">${threat.desc || ''}</span>
      </div>
      <div class="av-threat-actions">
        <button class="av-action-btn delete" data-index="${idx}" data-action="delete">SUPPRIMER</button>
        <button class="av-action-btn clean" data-index="${idx}" data-action="clean">NETTOYER</button>
        <button class="av-action-btn quarantine" data-index="${idx}" data-action="quarantine">QUARANTAINE</button>
        <button class="av-action-btn allow" data-index="${idx}" data-action="allow">AUTORISER</button>
      </div>
    `;
    listContainer.appendChild(item);
  });
  
  // Attach event listeners to buttons
  listContainer.querySelectorAll(".av-action-btn").forEach(button => {
    button.addEventListener("click", (e) => {
      const targetBtn = e.target as HTMLButtonElement;
      const idxStr = targetBtn.getAttribute("data-index");
      const action = targetBtn.getAttribute("data-action");
      if (idxStr !== null && action !== null) {
        const idx = parseInt(idxStr);
        triggerAvThreatAction(action, idx);
      }
    });
  });
}

function triggerAvThreatAction(action: string, idx: number) {
  const threat = avThreatsList[idx];
  if (!threat) return;
  
  // Disable all buttons in this threat item
  const itemEl = document.getElementById(`av-threat-${idx}`);
  if (itemEl) {
    const buttons = itemEl.querySelectorAll(".av-action-btn") as NodeListOf<HTMLButtonElement>;
    buttons.forEach(btn => btn.disabled = true);
  }
  
  // Send action to backend
  if (ws && ws.readyState === WebSocket.OPEN) {
    ws.send(JSON.stringify({
      type: "av_threat_action",
      action: action,
      threat: threat
    }));
  }
}

// Lancement manuel du scan antivirus depuis le menu des paramètres
const settingsAvScanBtn = document.getElementById("settings-av-scan-btn") as HTMLButtonElement;
if (settingsAvScanBtn) {
  settingsAvScanBtn.addEventListener("click", () => {
    // Fermer le modal des paramètres
    if (settingsModalEl) {
      settingsModalEl.classList.remove("visible");
    }
    // Ouvrir le panneau antivirus et démarrer le scan
    openAntivirusPanel();
  });
}

// Raccourci ANTIVIRUS dans le menu principal
const menuAvScanBtn = document.getElementById("menu-av-scan-btn") as HTMLButtonElement;
if (menuAvScanBtn) {
  menuAvScanBtn.addEventListener("click", () => {
    // Fermer le menu déroulant
    jarvisMenuDropdown.classList.add("hidden");
    jarvisMenuBtn.classList.remove("active");
    // Ouvrir le panneau antivirus
    openAntivirusPanel();
  });
}

// Raccourci PROTECTION LIVE dans le menu principal
const menuAvLiveBtn = document.getElementById("menu-av-live-btn") as HTMLButtonElement;
if (menuAvLiveBtn) {
  menuAvLiveBtn.addEventListener("click", () => {
    // Fermer le menu déroulant
    jarvisMenuDropdown.classList.add("hidden");
    jarvisMenuBtn.classList.remove("active");
    
    const wasActive = menuAvLiveBtn.getAttribute("aria-pressed") === "true";
    const nextActive = !wasActive;
    
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({
        type: "update_settings",
        settings: {
          av_live_protection: nextActive
        }
      }));
    }
  });
}

// ── Bouton Vider Cache / Recharger ───────────────────────────────────────────
const clearCacheBtn = document.getElementById("clear-cache-btn") as HTMLButtonElement;
if (clearCacheBtn) {
  clearCacheBtn.addEventListener("click", () => {
    // Fermer le menu déroulant
    jarvisMenuDropdown.classList.add("hidden");
    jarvisMenuBtn.classList.remove("active");
    // Feedback visuel immédiat
    clearCacheBtn.disabled = true;
    clearCacheBtn.innerHTML = '<span class="btn-icon">⏳</span> NETTOYAGE EN COURS...';
    // Afficher le banner de statut
    const banner = document.getElementById("update-banner");
    if (banner) {
      banner.style.display = "block";
      banner.style.cursor = "default";
      banner.textContent = "⏳ NETTOYAGE DU CACHE EN COURS...";
      banner.style.background = "linear-gradient(90deg, rgba(0,30,80,0.95), rgba(0,100,180,0.85))";
    }
    // Envoyer la demande au backend
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ type: "clear_cache" }));
    } else {
      // Pas de WS : recharger quand même la page après un délai
      setTimeout(() => location.reload(), 1500);
    }
  });
}

// Plus d'info sur l'antivirus
const settingsAvInfoBtn = document.getElementById("settings-av-info-btn") as HTMLAnchorElement;
const avInfoModal = document.getElementById("av-info-modal") as HTMLDivElement;
const avInfoModalClose = document.getElementById("av-info-modal-close") as HTMLSpanElement;
const avInfoModalOk = document.getElementById("av-info-modal-ok") as HTMLButtonElement;

if (settingsAvInfoBtn && avInfoModal) {
  settingsAvInfoBtn.addEventListener("click", (e) => {
    e.preventDefault();
    avInfoModal.style.display = "flex";
  });
}

if (avInfoModalClose && avInfoModal) {
  avInfoModalClose.addEventListener("click", () => {
    avInfoModal.style.display = "none";
  });
}

if (avInfoModalOk && avInfoModal) {
  avInfoModalOk.addEventListener("click", () => {
    avInfoModal.style.display = "none";
  });
}

// ── Reminders & Shopping & Restaurant Helpers ─────────────────────────────────

function renderReminders() {
  const container = document.getElementById("settings-reminders-list");
  if (!container) return;
  container.innerHTML = "";
  if (currentReminders.length === 0) {
    const empty = document.createElement("div");
    empty.style.cssText = "padding:10px;font-size:11px;color:rgba(0,229,255,0.3);text-align:center;";
    empty.textContent = "Aucun rappel enregistré";
    container.appendChild(empty);
    return;
  }
  currentReminders.forEach((r) => {
    const item = document.createElement("div");
    item.className = "settings-app-item";
    item.style.cssText = "display:flex;justify-content:space-between;align-items:center;padding:8px;border-bottom:1px solid rgba(0,229,255,0.15);font-size:11px;color:#00e5ff;";
    
    const info = document.createElement("span");
    const triggeredBadge = r.triggered ? ' <span style="color:#ff3366;font-size:9px;">[DÉCLENCHÉ]</span>' : "";
    info.innerHTML = `<strong>${r.time}</strong> - ${r.text}${triggeredBadge}`;
    item.appendChild(info);
    
    const delBtn = document.createElement("button");
    delBtn.className = "settings-app-del-btn";
    delBtn.innerHTML = "&times;";
    delBtn.style.cssText = "background:none;border:none;color:#ff3366;cursor:pointer;font-size:14px;padding:0 5px;";
    delBtn.onclick = () => {
      currentReminders = currentReminders.filter(rem => rem.id !== r.id);
      renderReminders();
      saveRemindersToBackend();
    };
    item.appendChild(delBtn);
    container.appendChild(item);
  });
}

function saveRemindersToBackend() {
  const settings = {
    reminders: currentReminders
  };
  if (ws && ws.readyState === WebSocket.OPEN) {
    ws.send(JSON.stringify({ type: "update_settings", settings }));
  }
}

reminderAddBtn?.addEventListener("click", () => {
  const text = reminderAddTextEl.value.trim();
  const time = reminderAddTimeEl.value.trim();
  if (text && time) {
    const id = Math.random().toString(36).substring(2, 10);
    const date = new Date().toISOString().split('T')[0];
    currentReminders.push({
      id,
      text,
      time,
      date,
      triggered: false
    });
    reminderAddTextEl.value = "";
    reminderAddTimeEl.value = "";
    renderReminders();
    saveRemindersToBackend();
  }
});

reminderAlertAckBtn?.addEventListener("click", () => {
  if (reminderAlertOverlay) {
    reminderAlertOverlay.style.display = "none";
  }
});

// Dragging support for Shopping and Restaurant Panels
if (shoppingPanel && shoppingHeader) {
  makePanelDraggable(shoppingPanel, shoppingHeader);
}
if (restaurantPanel && restaurantHeader) {
  makePanelDraggable(restaurantPanel, restaurantHeader);
}
if (obsidianPanel && obsidianHeader) {
  makePanelDraggable(obsidianPanel, obsidianHeader);
}
if (uninstallerPanel && uninstallerHeader) {
  makePanelDraggable(uninstallerPanel, uninstallerHeader);
}

uninstallerCloseBtn?.addEventListener("click", () => {
  closeUninstallerPanel();
});

uninstallerToggleBtn?.addEventListener("click", () => {
  const isHidden = uninstallerPanel.classList.contains("hidden");
  if (isHidden) {
    openUninstallerPanel();
  } else {
    closeUninstallerPanel();
  }
});

// ── Winget Upgrade Panel Toggle Button ──
if (wingetPanel && wingetHeader) {
  makePanelDraggable(wingetPanel, wingetHeader);
}

if (jarvisOsPanel && jarvisOsHeader) {
  makePanelDraggable(jarvisOsPanel, jarvisOsHeader);
}

wingetCloseBtn?.addEventListener("click", () => {
  closeWingetPanel();
});

wingetToggleBtn?.addEventListener("click", () => {
  const isHidden = wingetPanel.classList.contains("hidden");
  if (isHidden) {
    openWingetPanel();
  } else {
    closeWingetPanel();
  }
});

// ── IPTV Player Toggle Button ──
document.getElementById("iptv-toggle-btn")?.addEventListener("click", () => {
  const panel = document.getElementById("iptv-panel");
  if (!panel) return;
  if (panel.classList.contains("hidden")) {
    panel.classList.remove("hidden");
    document.getElementById("iptv-toggle-btn")?.setAttribute("aria-pressed", "true");
  } else {
    panel.classList.add("hidden");
    document.getElementById("iptv-toggle-btn")?.setAttribute("aria-pressed", "false");
  }
  jarvisMenuDropdown.classList.add("hidden");
  jarvisMenuBtn.classList.remove("active");
});

// ── Home Assistant Toggle Button ──
document.getElementById("ha-toggle-btn")?.addEventListener("click", () => {
  const panel = document.getElementById("ha-panel");
  const btn = document.getElementById("ha-toggle-btn");
  if (!panel) return;
  if (panel.classList.contains("hidden")) {
    panel.classList.remove("hidden");
    btn?.setAttribute("aria-pressed", "true");
    btn?.classList.add("active");
    // Fetch fresh states when opening the panel
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ type: "ha_get_states" }));
    }
  } else {
    panel.classList.add("hidden");
    btn?.setAttribute("aria-pressed", "false");
    btn?.classList.remove("active");
  }
  jarvisMenuDropdown.classList.add("hidden");
  jarvisMenuBtn.classList.remove("active");
});



obsidianCloseBtn?.addEventListener("click", () => {
  obsidianPanel.classList.add("hidden");
  obsidianPanel.classList.remove("visible");
});

shoppingCloseBtn?.addEventListener("click", () => {
  shoppingPanel.classList.add("hidden");
  shoppingPanel.classList.remove("visible");
  shoppingToggleBtn?.setAttribute("aria-pressed", "false");
});

shoppingToggleBtn?.addEventListener("click", () => {
  const isHidden = shoppingPanel.classList.contains("hidden");
  if (isHidden) {
    shoppingPanel.classList.remove("hidden");
    shoppingPanel.classList.add("visible");
    shoppingToggleBtn.setAttribute("aria-pressed", "true");
  } else {
    shoppingPanel.classList.add("hidden");
    shoppingPanel.classList.remove("visible");
    shoppingToggleBtn.setAttribute("aria-pressed", "false");
  }
});

shoppingClearBtn?.addEventListener("click", () => {
  currentShoppingList = [];
  sendShoppingListToBackend();
});

function renderShoppingList() {
  if (!shoppingListContainer) return;
  shoppingListContainer.innerHTML = "";
  if (currentShoppingList.length === 0) {
    const empty = document.createElement("div");
    empty.style.cssText = "padding:20px;font-size:11px;color:rgba(0,229,255,0.3);text-align:center;";
    empty.textContent = "Aucun article dans la liste";
    shoppingListContainer.appendChild(empty);
    return;
  }
  currentShoppingList.forEach((itemText) => {
    const isChecked = itemText.startsWith("[x] ");
    const cleanText = isChecked ? itemText.substring(4) : itemText;

    const div = document.createElement("div");
    div.className = `shopping-item${isChecked ? " checked" : ""}`;

    const cb = document.createElement("div");
    cb.className = "shopping-checkbox";
    cb.onclick = () => {
      const idx = currentShoppingList.indexOf(itemText);
      if (idx !== -1) {
        if (isChecked) {
          currentShoppingList[idx] = cleanText;
        } else {
          currentShoppingList[idx] = `[x] ${cleanText}`;
        }
        sendShoppingListToBackend();
      }
    };

    const textSpan = document.createElement("span");
    textSpan.className = "shopping-item-text";
    textSpan.textContent = cleanText;

    const del = document.createElement("button");
    del.className = "shopping-item-delete";
    del.innerHTML = "&times;";
    del.onclick = () => {
      currentShoppingList = currentShoppingList.filter(i => i !== itemText);
      sendShoppingListToBackend();
    };

    div.appendChild(cb);
    div.appendChild(textSpan);
    div.appendChild(del);
    shoppingListContainer.appendChild(div);
  });
}

function sendShoppingListToBackend() {
  if (ws && ws.readyState === WebSocket.OPEN) {
    ws.send(JSON.stringify({
      type: "update_shopping_list",
      items: currentShoppingList
    }));
  }
}

function addShoppingItem() {
  if (!shoppingAddInput) return;
  const val = shoppingAddInput.value.trim();
  if (val) {
    currentShoppingList.push(val);
    shoppingAddInput.value = "";
    sendShoppingListToBackend();
  }
}
shoppingAddBtn?.addEventListener("click", addShoppingItem);
shoppingAddInput?.addEventListener("keydown", (e) => {
  if (e.key === "Enter") addShoppingItem();
});

interface Restaurant {
  nom: string;
  cuisine: string;
  adresse: string;
  note: number;
  telephone?: string;
  site_web?: string;
  horaires?: string;
  coordonnees?: string;
  details_speciaux?: string;
  distance_estimee: string;
  angle_radar: number;
  distance_radar: number;
}

const restaurantDetailsOverlay = document.getElementById("restaurant-details-overlay") as HTMLDivElement;
const restaurantDetailsCloseBtn = document.getElementById("restaurant-details-close-btn") as HTMLButtonElement;
const restDetailName = document.getElementById("rest-detail-name") as HTMLSpanElement;
const restDetailRating = document.getElementById("rest-detail-rating") as HTMLSpanElement;
const restDetailCuisine = document.getElementById("rest-detail-cuisine") as HTMLSpanElement;
const restDetailAdresse = document.getElementById("rest-detail-adresse") as HTMLSpanElement;
const restDetailCoords = document.getElementById("rest-detail-coords") as HTMLSpanElement;
const restDetailTel = document.getElementById("rest-detail-tel") as HTMLSpanElement;
const restDetailHoraires = document.getElementById("rest-detail-horaires") as HTMLSpanElement;
const restDetailWeb = document.getElementById("rest-detail-web") as HTMLAnchorElement;
const restDetailDesc = document.getElementById("rest-detail-desc") as HTMLSpanElement;

let currentRestaurants: Restaurant[] = [];

function showRestaurantDetails(rest: Restaurant) {
  if (restaurantDetailsOverlay) {
    if (restDetailName) restDetailName.textContent = rest.nom;
    if (restDetailRating) restDetailRating.textContent = `★ ${rest.note}`;
    if (restDetailCuisine) restDetailCuisine.textContent = rest.cuisine;
    if (restDetailAdresse) restDetailAdresse.textContent = rest.adresse;
    if (restDetailCoords) restDetailCoords.textContent = rest.coordonnees || "Inconnu";
    if (restDetailTel) restDetailTel.textContent = rest.telephone || "Inconnu";
    if (restDetailHoraires) restDetailHoraires.textContent = rest.horaires || "Inconnu";
    
    if (restDetailWeb) {
      if (rest.site_web && rest.site_web !== "Inconnu" && rest.site_web.startsWith("http")) {
        restDetailWeb.href = rest.site_web;
        restDetailWeb.textContent = "Visiter le site internet";
        restDetailWeb.style.display = "inline-block";
      } else {
        restDetailWeb.style.display = "none";
      }
    }
    
    if (restDetailDesc) {
      restDetailDesc.textContent = rest.details_speciaux && rest.details_speciaux !== "Inconnu" ? rest.details_speciaux : "Aucune description supplémentaire.";
    }
    
    restaurantDetailsOverlay.classList.remove("hidden");
  }
}

restaurantDetailsCloseBtn?.addEventListener("click", () => {
  restaurantDetailsOverlay?.classList.add("hidden");
});

restaurantCloseBtn?.addEventListener("click", () => {
  restaurantPanel.classList.add("hidden");
  restaurantDetailsOverlay?.classList.add("hidden");
});

function renderRestaurants(location: string, restaurants: Restaurant[]) {
  currentRestaurants = restaurants;
  
  if (restaurantLocationTitle) {
    restaurantLocationTitle.textContent = `PROXIMITÉ // ${location.toUpperCase()}`;
  }
  
  if (restaurantItemsList) {
    restaurantItemsList.innerHTML = "";
  }
  
  if (restaurantRadarBlips) {
    restaurantRadarBlips.innerHTML = "";
  }
  
  if (restaurantPanel) {
    // Position sécurisée par défaut
    let leftPx: number | string = "auto";
    let topPx: number | string = "150px";
    let rightPx: number | string = "50px";
    
    // Si la fenêtre est assez grande, on positionne aléatoirement de façon 100% visible
    if (window.innerWidth >= 880 && window.innerHeight >= 590) {
      leftPx = Math.floor(Math.random() * (window.innerWidth - 880)) + 50;
      topPx = Math.floor(Math.random() * (window.innerHeight - 590)) + 120;
      rightPx = "auto";
      
      restaurantPanel.style.left = `${leftPx}px`;
      restaurantPanel.style.top = `${topPx}px`;
      restaurantPanel.style.right = rightPx;
    } else {
      // Fallback
      restaurantPanel.style.left = "auto";
      restaurantPanel.style.right = "50px";
      restaurantPanel.style.top = "150px";
    }
    
    restaurantPanel.classList.remove("hidden");
    restaurantPanel.classList.add("visible");
  }
  
  restaurants.forEach((rest, idx) => {
    const card = document.createElement("div");
    card.className = "restaurant-item-card";
    card.id = `rest-card-${idx}`;
    card.innerHTML = `
      <div class="restaurant-item-card-header">
        <span class="restaurant-card-name">${rest.nom || "Inconnu"}</span>
        <span class="restaurant-card-rating">★ ${rest.note !== undefined ? rest.note : "?"}</span>
      </div>
      <div class="restaurant-item-card-cuisine">${rest.cuisine || "Inconnu"}</div>
      <div class="restaurant-item-card-footer">
        <span class="restaurant-card-address" title="${rest.adresse || "Inconnu"}">${rest.adresse || "Inconnu"}</span>
        <span class="restaurant-card-dist">${rest.distance_estimee || ""}</span>
      </div>
    `;
    
    const blip = document.createElement("div");
    blip.className = "radar-blip";
    blip.id = `rest-blip-${idx}`;
    
    const radius = 140; 
    const angleRadar = typeof rest.angle_radar === "number" ? rest.angle_radar : parseFloat(rest.angle_radar as any) || Math.random() * 360;
    const distanceRadar = typeof rest.distance_radar === "number" ? rest.distance_radar : parseFloat(rest.distance_radar as any) || 20 + Math.random() * 70;
    
    const angleRad = (angleRadar - 90) * (Math.PI / 180);
    const distPx = (distanceRadar / 100) * radius;
    
    const x = radius + distPx * Math.cos(angleRad);
    const y = radius + distPx * Math.sin(angleRad);
    
    blip.style.left = `${x}px`;
    blip.style.top = `${y}px`;
    blip.title = `${rest.nom} (${rest.cuisine})`;
    
    card.addEventListener("click", () => {
      showRestaurantDetails(rest);
    });
    
    card.addEventListener("mouseenter", () => {
      card.classList.add("active");
      blip.classList.add("active");
    });
    
    card.addEventListener("mouseleave", () => {
      card.classList.remove("active");
      blip.classList.remove("active");
    });
    
    blip.addEventListener("mouseenter", () => {
      card.classList.add("active");
      blip.classList.add("active");
      card.scrollIntoView({ behavior: "smooth", block: "nearest" });
    });
    
    blip.addEventListener("mouseleave", () => {
      card.classList.remove("active");
      blip.classList.remove("active");
    });
    
    blip.addEventListener("click", (e) => {
      e.stopPropagation(); // prevent triggering other overlay actions
      card.scrollIntoView({ behavior: "smooth", block: "nearest" });
      showRestaurantDetails(rest);
    });
    
    restaurantItemsList?.appendChild(card);
    restaurantRadarBlips?.appendChild(blip);
  });
}

// ── Obsidian UI Event Listeners & Functions ──────────────────────────────────
obsidianAddBtn?.addEventListener("click", () => {
  activeObsidianNoteTitle = "";
  if (obsidianNoteTitle) obsidianNoteTitle.value = "";
  if (obsidianNoteContent) obsidianNoteContent.value = "";
  document.querySelectorAll(".obsidian-note-item").forEach(item => item.classList.remove("active"));
});

obsidianNoteSaveBtn?.addEventListener("click", () => {
  const titre = obsidianNoteTitle?.value.trim() || "";
  const content = obsidianNoteContent?.value || "";
  if (!titre) {
    alert("Veuillez saisir un titre pour la note.");
    return;
  }
  if (ws && ws.readyState === WebSocket.OPEN) {
    ws.send(JSON.stringify({
      type: "save_obsidian_note",
      titre,
      content
    }));
  }
});

obsidianNoteDeleteBtn?.addEventListener("click", () => {
  const titre = obsidianNoteTitle?.value.trim() || activeObsidianNoteTitle;
  if (!titre) {
    alert("Aucune note sélectionnée pour la suppression.");
    return;
  }
  if (confirm(`Voulez-vous vraiment supprimer la note '${titre}' ?`)) {
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({
        type: "delete_obsidian_note",
        titre
      }));
    }
    activeObsidianNoteTitle = "";
    if (obsidianNoteTitle) obsidianNoteTitle.value = "";
    if (obsidianNoteContent) obsidianNoteContent.value = "";
  }
});

obsidianSearch?.addEventListener("input", () => {
  const query = obsidianSearch.value.trim().toLowerCase();
  if (!query) {
    renderObsidianNotes(allObsidianNotes);
  } else {
    const filtered = allObsidianNotes.filter(n => n.titre.toLowerCase().includes(query));
    renderObsidianNotes(filtered);
  }
});

function renderObsidianNotes(notes: Array<{titre: string, mtime?: number, taille?: number}>) {
  if (!obsidianNotesList) return;
  obsidianNotesList.innerHTML = "";
  
  if (notes.length === 0) {
    const empty = document.createElement("div");
    empty.style.cssText = "padding:20px;font-size:11px;color:rgba(163,112,247,0.4);text-align:center;";
    empty.textContent = "Aucune note";
    obsidianNotesList.appendChild(empty);
    return;
  }

  notes.forEach(note => {
    const card = document.createElement("div");
    card.className = "obsidian-note-item";
    if (note.titre === activeObsidianNoteTitle) {
      card.classList.add("active");
    }
    
    let dateStr = "Date inconnue";
    if (note.mtime) {
      const d = new Date(note.mtime * 1000);
      dateStr = d.toLocaleDateString("fr-FR") + " " + d.toLocaleTimeString("fr-FR", {hour: '2-digit', minute:'2-digit'});
    }
    
    let sizeStr = "0 B";
    if (note.taille !== undefined) {
      if (note.taille < 1024) {
        sizeStr = `${note.taille} B`;
      } else {
        sizeStr = `${(note.taille / 1024).toFixed(1)} KB`;
      }
    }

    card.innerHTML = `
      <div class="obsidian-note-item-title">${note.titre}</div>
      <div class="obsidian-note-item-meta">
        <span>MODIFIÉ : ${dateStr}</span>
        <span>TAILLE : ${sizeStr}</span>
      </div>
    `;

    card.addEventListener("click", () => {
      if (ws && ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({
          type: "read_obsidian_note",
          titre: note.titre
        }));
      }
      document.querySelectorAll(".obsidian-note-item").forEach(item => item.classList.remove("active"));
      card.classList.add("active");
      activeObsidianNoteTitle = note.titre;
    });

    obsidianNotesList.appendChild(card);
  });
}

// ══════════════════════════════════════════════════════════════════════════════
//  NVIDIA NEMOTRON ASR — Toggle + Toast
// ══════════════════════════════════════════════════════════════════════════════

nemotronToggleBtn.addEventListener("click", () => {
  if (!ws || ws.readyState !== WebSocket.OPEN) return;
  if (nemotronAsrLoading) return; // Ignore clicks during loading

  if (!nemotronAsrAvailable) {
    nemotronModal.style.display = "flex";
    nemotronModalActions.style.display = "flex";
    nemotronProgressSection.style.display = "none";
    if (gpuAvailable) {
      nemotronModalGpuNotice.textContent = "✔ GPU NVIDIA compatible CUDA détecté. L'installation exploitera CUDA pour une vitesse maximale.";
      nemotronModalGpuNotice.style.color = "#76b900";
    } else {
      nemotronModalGpuNotice.textContent = "⚠ Aucun GPU NVIDIA détecté (ou pilotes CUDA absents). Le mode CPU lent sera utilisé.";
      nemotronModalGpuNotice.style.color = "#ff8a1a";
    }
    return;
  }

  const newState = !nemotronAsrEnabled;

  if (newState) {
    // Show loading state
    nemotronAsrLoading = true;
    nemotronToggleBtn.classList.add("asr-loading");
    showNemotronToast(
      "⏳ CHARGEMENT DU MODÈLE... En cours de lancement...",
      "warning",
      30000
    );
  }

  ws.send(JSON.stringify({ type: "toggle_nemotron_asr", enabled: newState }));
});

// Handlers pour le modal d'installation de Nemotron
if (nemotronModalClose) {
  nemotronModalClose.addEventListener("click", () => {
    nemotronModal.style.display = "none";
  });
}
if (nemotronCancelBtn) {
  nemotronCancelBtn.addEventListener("click", () => {
    nemotronModal.style.display = "none";
  });
}
if (nemotronInstallBtn) {
  nemotronInstallBtn.addEventListener("click", () => {
    if (!ws || ws.readyState !== WebSocket.OPEN) return;
    nemotronModalActions.style.display = "none";
    nemotronProgressSection.style.display = "block";
    nemotronProgressStage.textContent = "Lancement de la tâche d'installation...";
    nemotronProgressBar.style.width = "0%";
    nemotronInstallLogs.innerHTML = "<div>Demande d'installation envoyée...</div>";
    
    ws.send(JSON.stringify({ type: "install_nemotron_deps" }));
  });
}

let nemotronToastTimer: number | null = null;

function showNemotronToast(message: string, type: "success" | "warning" | "error" = "success", durationMs: number = 4000) {
  if (!nemotronToastEl) return;

  // Clear previous timer
  if (nemotronToastTimer) {
    clearTimeout(nemotronToastTimer);
    nemotronToastTimer = null;
  }

  // Reset classes
  nemotronToastEl.classList.remove("visible", "toast-error", "toast-warning");

  // Set content and type class
  nemotronToastEl.textContent = message;
  if (type === "error") nemotronToastEl.classList.add("toast-error");
  if (type === "warning") nemotronToastEl.classList.add("toast-warning");

  // Show
  requestAnimationFrame(() => {
    nemotronToastEl.classList.add("visible");
  });

  // Auto-hide
  nemotronToastTimer = window.setTimeout(() => {
    nemotronToastEl.classList.remove("visible");
    nemotronToastTimer = null;
  }, durationMs);
}

function updateNemotronUI() {
  if (nemotronAsrAvailable) {
    if (settingsNemotronBtn) {
      settingsNemotronBtn.textContent = "DÉSINSTALLER NVIDIA NEMOTRON ASR (LIBÉRER ~7 GO)";
      settingsNemotronBtn.style.borderColor = "#ff3b30";
      settingsNemotronBtn.style.color = "#ff3b30";
      settingsNemotronBtn.style.background = "rgba(255, 59, 48, 0.05)";
    }
    if (nemotronInstallBtn) nemotronInstallBtn.style.display = "none";
    if (nemotronUninstallBtn) nemotronUninstallBtn.style.display = "block";
  } else {
    if (settingsNemotronBtn) {
      settingsNemotronBtn.textContent = "INSTALLER NVIDIA NEMOTRON ASR (LOCAL)";
      settingsNemotronBtn.style.borderColor = "#76b900";
      settingsNemotronBtn.style.color = "#76b900";
      settingsNemotronBtn.style.background = "rgba(118, 185, 0, 0.05)";
    }
    if (nemotronInstallBtn) nemotronInstallBtn.style.display = "block";
    if (nemotronUninstallBtn) nemotronUninstallBtn.style.display = "none";
  }
}

if (settingsNemotronBtn) {
  settingsNemotronBtn.addEventListener("click", () => {
    // Fermer le modal des paramètres
    const settingsModal = document.getElementById("settings-modal");
    if (settingsModal) settingsModal.style.display = "none";

    // Ouvrir le modal Nemotron
    nemotronModal.style.display = "flex";
    nemotronModalActions.style.display = "flex";
    nemotronProgressSection.style.display = "none";

    if (nemotronAsrAvailable) {
      // Mode confirmation de désinstallation
      nemotronModalGpuNotice.textContent = "⚠ Vous êtes sur le point de désinstaller NeMo, PyTorch, torchaudio et le modèle de 4 Go. Cette action libérera environ 7 Go d'espace disque.";
      nemotronModalGpuNotice.style.color = "#ff3b30";
    } else {
      // Mode installation
      if (gpuAvailable) {
        nemotronModalGpuNotice.textContent = "✔ GPU NVIDIA compatible CUDA détecté. L'installation exploitera CUDA pour une vitesse maximale.";
        nemotronModalGpuNotice.style.color = "#76b900";
      } else {
        nemotronModalGpuNotice.textContent = "⚠ Aucun GPU NVIDIA détecté (ou pilotes CUDA absents). Le mode CPU lent sera utilisé.";
        nemotronModalGpuNotice.style.color = "#ff8a1a";
      }
    }
  });
}

if (nemotronUninstallBtn) {
  nemotronUninstallBtn.addEventListener("click", () => {
    if (!ws || ws.readyState !== WebSocket.OPEN) return;
    nemotronModalActions.style.display = "none";
    nemotronProgressSection.style.display = "block";
    nemotronProgressStage.textContent = "Lancement de la tâche de désinstallation...";
    nemotronProgressBar.style.width = "0%";
    nemotronInstallLogs.innerHTML = "<div>Demande de désinstallation envoyée...</div>";

    ws.send(JSON.stringify({ type: "uninstall_nemotron_deps" }));
  });
}

// ── Uninstaller core functions and listeners ──
function openUninstallerPanel() {
  if (uninstallerPanel) {
    uninstallerPanel.classList.remove("hidden");
    uninstallerPanel.classList.add("visible");
    uninstallerToggleBtn?.setAttribute("aria-pressed", "true");
    
    // Switch to list view initially
    uninstallerListView?.classList.remove("hidden");
    uninstallerActionView?.classList.add("hidden");
    
    // Set loading status
    if (uninstallerAppsList) {
      uninstallerAppsList.innerHTML = '<div class="uninstaller-loading">CHARGEMENT DE LA LISTE DES LOGICIELS...</div>';
    }
    
    // Request installed programs
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ type: "get_installed_programs" }));
    }
  }
}

function closeUninstallerPanel() {
  if (uninstallerPanel) {
    uninstallerPanel.classList.add("hidden");
    uninstallerPanel.classList.remove("visible");
    uninstallerToggleBtn?.setAttribute("aria-pressed", "false");
  }
}

function renderInstalledPrograms(programs: typeof allInstalledPrograms) {
  if (!uninstallerAppsList) return;
  uninstallerAppsList.innerHTML = "";
  
  if (programs.length === 0) {
    const empty = document.createElement("div");
    empty.className = "uninstaller-loading";
    empty.textContent = "AUCUN LOGICIEL TROUVÉ";
    uninstallerAppsList.appendChild(empty);
    return;
  }
  
  programs.forEach(prog => {
    const item = document.createElement("div");
    item.className = "uninstaller-app-item";
    
    item.innerHTML = `
      <div class="uninstaller-app-info">
        <div class="uninstaller-app-name">${prog.name}</div>
        <div class="uninstaller-app-publisher">${prog.publisher || 'Éditeur inconnu'} - v${prog.version || 'Inconnue'} (${prog.hive})</div>
      </div>
      <button class="uninstaller-app-btn">DÉSINSTALLER</button>
    `;
    
    const btn = item.querySelector(".uninstaller-app-btn") as HTMLButtonElement;
    btn.addEventListener("click", () => {
      triggerUninstall(prog);
    });
    
    uninstallerAppsList.appendChild(item);
  });
}

function triggerUninstall(prog: typeof allInstalledPrograms[0]) {
  uninstallerListView?.classList.add("hidden");
  uninstallerActionView?.classList.remove("hidden");
  
  uninstallerRadarContainer?.classList.remove("hidden");
  uninstallerLeftoversContainer?.classList.add("hidden");
  if (uninstallerStatusMsg) {
    uninstallerStatusMsg.textContent = `Lancement de la désinstallation de ${prog.name}...`;
  }
  
  if (ws && ws.readyState === WebSocket.OPEN) {
    ws.send(JSON.stringify({
      type: "uninstall_program",
      name: prog.name,
      publisher: prog.publisher,
      install_location: prog.install_location,
      uninstall_string: prog.uninstall_string
    }));
  }
}

function updateUninstallProgress(data: any) {
  if (uninstallerStatusMsg) {
    uninstallerStatusMsg.textContent = data.message || "En cours...";
  }
}

function showUninstallComplete(data: any) {
  uninstallerRadarContainer?.classList.add("hidden");
  uninstallerLeftoversContainer?.classList.remove("hidden");
  
  currentLeftovers = data.leftovers || [];
  
  // Reset Select All checkbox
  if (uninstallerSelectAll) {
    uninstallerSelectAll.checked = true;
  }
  
  renderLeftovers();
}

function renderLeftovers() {
  if (!uninstallerLeftoversList) return;
  uninstallerLeftoversList.innerHTML = "";
  
  if (currentLeftovers.length === 0) {
    const empty = document.createElement("div");
    empty.className = "uninstaller-leftover-empty";
    empty.textContent = "Aucune trace résiduelle détectée sur le système.";
    uninstallerLeftoversList.appendChild(empty);
    if (uninstallerCleanBtn) uninstallerCleanBtn.disabled = true;
    return;
  }
  
  if (uninstallerCleanBtn) uninstallerCleanBtn.disabled = false;
  
  currentLeftovers.forEach((leftover, idx) => {
    const item = document.createElement("div");
    item.className = "uninstaller-leftover-item";
    
    const icon = leftover.type === 'folder' ? '📁' : '🔑';
    const typeLabel = leftover.type === 'folder' ? 'Dossier' : 'Registre';
    
    item.innerHTML = `
      <label class="uninstaller-leftover-label">
        <input type="checkbox" class="uninstaller-leftover-checkbox" data-idx="${idx}" checked>
        <span class="uninstaller-leftover-icon">${icon}</span>
        <div class="uninstaller-leftover-details">
          <div class="uninstaller-leftover-path" title="${leftover.path}">${leftover.path}</div>
          <div class="uninstaller-leftover-desc">${typeLabel} - ${leftover.desc}</div>
        </div>
      </label>
    `;
    
    uninstallerLeftoversList.appendChild(item);
  });
}

function showCleanComplete(data: any) {
  const cleaned = data.cleaned_count || 0;
  const total = data.total_count || 0;
  alert(`Nettoyage terminé : ${cleaned}/${total} traces supprimées.`);
  
  // Go back to program list
  openUninstallerPanel();
}

// Event Listeners for Uninstaller Controls
uninstallerSearchInput?.addEventListener("input", () => {
  const query = uninstallerSearchInput.value.trim().toLowerCase();
  if (!query) {
    renderInstalledPrograms(allInstalledPrograms);
  } else {
    const filtered = allInstalledPrograms.filter(p => 
      p.name.toLowerCase().includes(query) || 
      (p.publisher && p.publisher.toLowerCase().includes(query))
    );
    renderInstalledPrograms(filtered);
  }
});

uninstallerSelectAll?.addEventListener("change", () => {
  const checked = uninstallerSelectAll.checked;
  const checkboxes = document.querySelectorAll(".uninstaller-leftover-checkbox") as NodeListOf<HTMLInputElement>;
  checkboxes.forEach(cb => {
    cb.checked = checked;
  });
});

uninstallerCleanBtn?.addEventListener("click", () => {
  const selectedItems: any[] = [];
  const checkboxes = document.querySelectorAll(".uninstaller-leftover-checkbox") as NodeListOf<HTMLInputElement>;
  checkboxes.forEach(cb => {
    if (cb.checked) {
      const idx = parseInt(cb.getAttribute("data-idx") || "0");
      selectedItems.push(currentLeftovers[idx]);
    }
  });
  
  if (selectedItems.length === 0) {
    alert("Veuillez sélectionner au moins une trace à nettoyer.");
    return;
  }
  
  if (ws && ws.readyState === WebSocket.OPEN) {
    ws.send(JSON.stringify({
      type: "clean_leftovers",
      items: selectedItems
    }));
  }
});

uninstallerSkipBtn?.addEventListener("click", () => {
  openUninstallerPanel();
});

// ── Winget Upgrade Panel Core Functions ──
function openWingetPanel() {
  if (wingetPanel) {
    wingetPanel.classList.remove("hidden");
    wingetPanel.classList.add("visible");
    wingetToggleBtn?.setAttribute("aria-pressed", "true");
    
    // Hide logs, show list
    wingetLogsContainer?.classList.add("hidden");
    
    // Set loading status
    if (wingetList) {
      wingetList.innerHTML = '<div class="uninstaller-loading">RECHERCHE DES MISES À JOUR DISPONIBLES...</div>';
    }
    
    // Request winget upgrades
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ type: "get_winget_upgrades" }));
    }
  }
}

function closeWingetPanel() {
  if (wingetPanel) {
    wingetPanel.classList.add("hidden");
    wingetPanel.classList.remove("visible");
    wingetToggleBtn?.setAttribute("aria-pressed", "false");
  }
}

function renderWingetUpgrades(upgrades: WingetUpgradeItem[]) {
  if (!wingetList) return;
  wingetList.innerHTML = "";
  
  if (upgrades.length === 0) {
    const empty = document.createElement("div");
    empty.className = "uninstaller-loading";
    empty.style.color = "#00e5ff";
    empty.textContent = "VOTRE SYSTÈME EST À JOUR. AUCUNE MISE À JOUR DISPONIBLE.";
    wingetList.appendChild(empty);
    if (wingetCountBadge) {
      wingetCountBadge.textContent = "";
      wingetCountBadge.classList.add("hidden");
    }
    return;
  }
  
  if (wingetCountBadge) {
    wingetCountBadge.textContent = upgrades.length.toString();
    wingetCountBadge.classList.remove("hidden");
  }
  
  upgrades.forEach((item, idx) => {
    const el = document.createElement("div");
    el.className = "uninstaller-app-item";
    el.innerHTML = `
      <label class="uninstaller-leftover-label" style="flex: 1; display: flex; align-items: center; gap: 10px; cursor: pointer;">
        <input type="checkbox" class="winget-select-checkbox" data-idx="${idx}" checked style="accent-color: #00e5ff;">
        <div class="uninstaller-app-info" style="flex: 1;">
          <div class="uninstaller-app-name" style="color: #00e5ff; font-weight: bold;">${item.name}</div>
          <div class="uninstaller-app-publisher" style="font-size: 11px; opacity: 0.85;">
            ID: ${item.id} | Installée: v${item.version} | Disponible: <span style="color:#00ff88;font-weight:bold;">v${item.available}</span> (${item.source})
          </div>
        </div>
      </label>
      <button class="uninstaller-app-btn winget-upgrade-item-btn" data-id="${item.id}" style="border-color:#00e5ff; color:#00e5ff; background:rgba(0,229,255,0.05);">METTRE À JOUR</button>
    `;
    
    // Wire single upgrade button
    const btn = el.querySelector(".winget-upgrade-item-btn") as HTMLButtonElement;
    btn.addEventListener("click", (e) => {
      e.preventDefault();
      e.stopPropagation();
      runWingetUpgrade([item.id]);
    });
    
    wingetList.appendChild(el);
  });
}

function runWingetUpgrade(ids: string[]) {
  if (ids.length === 0) {
    alert("Veuillez sélectionner au moins un logiciel à mettre à jour.");
    return;
  }
  
  if (wingetLogsContainer && wingetConsole) {
    wingetLogsContainer.classList.remove("hidden");
    wingetConsole.textContent = `[JARVIS] Lancement de la mise à jour pour:\n- ${ids.join("\n- ")}\n\n`;
  }
  
  if (ws && ws.readyState === WebSocket.OPEN) {
    ws.send(JSON.stringify({
      type: "run_winget_upgrade",
      ids: ids
    }));
  }
}

// Event Listeners for Winget controls
wingetSearchInput?.addEventListener("input", () => {
  const query = wingetSearchInput.value.trim().toLowerCase();
  const items = document.querySelectorAll("#winget-upgrades-list .uninstaller-app-item");
  items.forEach(item => {
    const text = item.textContent?.toLowerCase() || "";
    if (text.includes(query)) {
      (item as HTMLElement).style.display = "";
    } else {
      (item as HTMLElement).style.display = "none";
    }
  });
});

wingetSelectAll?.addEventListener("change", () => {
  const checked = wingetSelectAll.checked;
  const checkboxes = document.querySelectorAll(".winget-select-checkbox") as NodeListOf<HTMLInputElement>;
  checkboxes.forEach(cb => {
    cb.checked = checked;
  });
});

wingetRefreshBtn?.addEventListener("click", () => {
  if (wingetList) {
    wingetList.innerHTML = '<div class="uninstaller-loading">RECHERCHE DES MISES À JOUR...</div>';
  }
  if (ws && ws.readyState === WebSocket.OPEN) {
    ws.send(JSON.stringify({ type: "get_winget_upgrades" }));
  }
});

wingetUpgradeSelectedBtn?.addEventListener("click", () => {
  const ids: string[] = [];
  const checkboxes = document.querySelectorAll(".winget-select-checkbox") as NodeListOf<HTMLInputElement>;
  checkboxes.forEach(cb => {
    if (cb.checked) {
      const idx = parseInt(cb.getAttribute("data-idx") || "0");
      ids.push(allWingetUpgrades[idx].id);
    }
  });
  runWingetUpgrade(ids);
});

wingetUpgradeAllBtn?.addEventListener("click", () => {
  if (allWingetUpgrades.length === 0) {
    alert("Aucune mise à jour disponible à installer.");
    return;
  }
  if (wingetLogsContainer && wingetConsole) {
    wingetLogsContainer.classList.remove("hidden");
    wingetConsole.textContent = "[JARVIS] Lancement de la mise à jour globale du système...\n\n";
  }
  if (ws && ws.readyState === WebSocket.OPEN) {
    ws.send(JSON.stringify({
      type: "run_winget_upgrade",
      all: true
    }));
  }
});

wingetCloseLogsBtn?.addEventListener("click", () => {
  wingetLogsContainer?.classList.add("hidden");
  // Trigger update refresh to see what has been updated
  if (ws && ws.readyState === WebSocket.OPEN) {
    ws.send(JSON.stringify({ type: "get_winget_upgrades" }));
  }
});

// ── CLIENT VPN J.A.R.V.I.S ──────────────────────────────────────────────────
const menuVpnBtn = document.getElementById("menu-vpn-btn") as HTMLButtonElement;
const vpnPanel = document.getElementById("vpn-panel") as HTMLDivElement;
const vpnCloseBtn = document.getElementById("vpn-panel-close-btn") as HTMLButtonElement;
const vpnConnectBtn = document.getElementById("vpn-connect-btn") as HTMLButtonElement;
const vpnDisconnectBtn = document.getElementById("vpn-disconnect-btn") as HTMLButtonElement;
const vpnCountrySelect = document.getElementById("vpn-country-select") as HTMLSelectElement;

// Rendre le panel déplaçable
const vpnHeader = document.getElementById("vpn-panel-header");
if (vpnPanel && vpnHeader) {
  makePanelDraggable(vpnPanel, vpnHeader);
}

// Ouvrir/Fermer le panel VPN
if (menuVpnBtn && vpnPanel) {
  menuVpnBtn.addEventListener("click", () => {
    // Fermer le menu principal
    jarvisMenuDropdown.classList.add("hidden");
    jarvisMenuBtn.classList.remove("active");
    
    // Basculer l'affichage du panel
    vpnPanel.classList.toggle("visible");
    vpnPanel.classList.toggle("hidden");
    
    if (vpnPanel.classList.contains("visible")) {
      // Demander l'état et la liste des pays
      if (ws && ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ type: "vpn_get_countries" }));
        ws.send(JSON.stringify({ type: "vpn_get_status" }));
      }
    }
  });
}

if (vpnCloseBtn && vpnPanel) {
  vpnCloseBtn.addEventListener("click", () => {
    vpnPanel.classList.add("hidden");
    vpnPanel.classList.remove("visible");
  });
}

// Actions se connecter / se déconnecter
if (vpnConnectBtn) {
  vpnConnectBtn.addEventListener("click", () => {
    if (vpnConnectBtn.textContent === "ANNULER") {
      // Annuler la connexion en cours
      const dot = document.getElementById("vpn-status-dot");
      const text = document.getElementById("vpn-status-text");
      if (dot) dot.className = "vpn-dot-connecting";
      if (text) text.textContent = "ANNULATION EN COURS...";
      vpnConnectBtn.disabled = true;
      vpnConnectBtn.textContent = "SE CONNECTER";
      
      if (ws && ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ type: "vpn_cancel" }));
      }
      return;
    }

    const country = vpnCountrySelect.value;
    if (!country) {
      alert("Veuillez sélectionner un pays dans la liste.");
      return;
    }
    
    // Mettre à jour l'UI en cours de connexion
    const dot = document.getElementById("vpn-status-dot");
    const text = document.getElementById("vpn-status-text");
    if (dot) dot.className = "vpn-dot-connecting";
    if (text) text.textContent = "CONNEXION EN COURS...";
    
    // Rendre le bouton cliquable pour pouvoir Annuler
    vpnConnectBtn.textContent = "ANNULER";
    vpnDisconnectBtn.disabled = true;
    
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ type: "vpn_connect", country }));
    }
  });
}

if (vpnDisconnectBtn) {
  vpnDisconnectBtn.addEventListener("click", () => {
    // Mettre à jour l'UI en cours de déconnexion
    const dot = document.getElementById("vpn-status-dot");
    const text = document.getElementById("vpn-status-text");
    if (dot) dot.className = "vpn-dot-connecting";
    if (text) text.textContent = "DÉCONNEXION EN COURS...";
    vpnDisconnectBtn.disabled = true;
    
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ type: "vpn_disconnect" }));
    }
  });
}

function updateVpnUI(status: any, ipInfo: any) {
  const dot = document.getElementById("vpn-status-dot");
  const text = document.getElementById("vpn-status-text");
  const connectBtn = document.getElementById("vpn-connect-btn") as HTMLButtonElement;
  const disconnectBtn = document.getElementById("vpn-disconnect-btn") as HTMLButtonElement;
  const ipInfoEl = document.getElementById("vpn-ip-info");
  
  if (status.connected) {
    if (dot) { dot.className = "vpn-dot-connected"; }
    if (text) { text.textContent = "CONNECTÉ"; }
    if (connectBtn) { connectBtn.disabled = true; connectBtn.textContent = "SE CONNECTER"; }
    if (disconnectBtn) { disconnectBtn.disabled = false; }
    if (ipInfoEl && ipInfo) {
      ipInfoEl.innerHTML = `
        <strong>IP :</strong> ${ipInfo.ip}<br>
        <strong>Pays :</strong> ${ipInfo.country} (${ipInfo.city || 'Ville inconnue'})<br>
        <strong>Fournisseur :</strong> ${ipInfo.org || 'Inconnu'}
      `;
    }
  } else {
    if (dot) { dot.className = "vpn-dot-disconnected"; }
    if (text) { text.textContent = status.status || "DÉCONNECTÉ"; }
    if (connectBtn) { connectBtn.disabled = false; connectBtn.textContent = "SE CONNECTER"; }
    if (disconnectBtn) { disconnectBtn.disabled = true; }
    if (ipInfoEl && ipInfo) {
      ipInfoEl.innerHTML = `
        <strong>IP d'origine :</strong> ${ipInfo.ip}<br>
        <strong>Pays :</strong> ${ipInfo.country} (${ipInfo.city || 'Ville inconnue'})
      `;
    } else if (ipInfoEl) {
      ipInfoEl.innerHTML = "IP : Déconnecté";
    }
  }
}

// ── WEBCAM HUD CONTROLS & CAPTURE ──────────────────────────────────────────
const webcamToggleBtn = document.getElementById("webcam-toggle-btn") as HTMLButtonElement;
const webcamPreviewPanel = document.getElementById("webcam-preview-panel") as HTMLDivElement;
const webcamVideo = document.getElementById("webcam-video") as HTMLVideoElement;
const webcamCloseBtn = document.getElementById("webcam-close-btn") as HTMLButtonElement;
const webcamDragHandle = document.getElementById("webcam-drag-handle") as HTMLDivElement;

let webcamStream: MediaStream | null = null;

// Rendre le panel déplaçable
if (webcamPreviewPanel && webcamDragHandle) {
  makePanelDraggable(webcamPreviewPanel, webcamDragHandle);
}

// Activer le flux caméra
async function activeWebcam(fullscreen = false) {
  if (webcamPreviewPanel) {
    if (fullscreen) {
      webcamPreviewPanel.classList.add("fullscreen");
    } else {
      webcamPreviewPanel.classList.remove("fullscreen");
    }
  }

  if (webcamStream) {
    // Already streaming, just updated fullscreen class above
    return;
  }
  
  // Utiliser settingsCameraEl.value (le deviceId) s'il est sélectionné
  const selectedCameraId = settingsCameraEl ? settingsCameraEl.value : "";
  const constraints: MediaStreamConstraints = {
    video: selectedCameraId ? { deviceId: { exact: selectedCameraId } } : true
  };
  
  try {
    webcamStream = await navigator.mediaDevices.getUserMedia(constraints);
    if (webcamVideo) {
      webcamVideo.srcObject = webcamStream;
    }
    if (webcamPreviewPanel) {
      webcamPreviewPanel.classList.remove("hidden");
    }
    if (webcamToggleBtn) {
      webcamToggleBtn.setAttribute("aria-pressed", "true");
    }
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ type: "webcam_state", active: true }));
    }

    // Start Hand Tracking
    initHandTracking();
    isHandTrackingActive = true;
    requestAnimationFrame(handTrackingLoop);
  } catch (err) {
    console.error("Erreur lors de l'activation de la webcam :", err);
    alert("Impossible d'accéder à la caméra sélectionnée. Veuillez vérifier les permissions ou son branchement.");
  }
}

// Désactiver le flux caméra
function desactiveWebcam() {
  if (webcamStream) {
    webcamStream.getTracks().forEach(track => track.stop());
    webcamStream = null;
  }
  if (webcamVideo) {
    webcamVideo.srcObject = null;
  }
  if (webcamPreviewPanel) {
    webcamPreviewPanel.classList.add("hidden");
    webcamPreviewPanel.classList.remove("fullscreen");
  }
  if (webcamToggleBtn) {
    webcamToggleBtn.setAttribute("aria-pressed", "false");
  }
  if (ws && ws.readyState === WebSocket.OPEN) {
    ws.send(JSON.stringify({ type: "webcam_state", active: false }));
  }

  // Stop Hand Tracking
  isHandTrackingActive = false;
  for (let i = 0; i < 2; i++) {
    const cursor = document.getElementById(`hand-gesture-cursor-${i}`);
    if (cursor) {
      cursor.style.display = "none";
    }
  }
  // Reset active deformation on stop
  // @ts-ignore
  if (typeof orb !== "undefined" && orb && orb.setDeformation) {
    orb.setDeformation(1, 1, 0);
  }
}

// Basculer l'affichage de la caméra via le bouton menu
if (webcamToggleBtn) {
  webcamToggleBtn.addEventListener("click", () => {
    // Fermer le menu principal
    jarvisMenuDropdown.classList.add("hidden");
    jarvisMenuBtn.classList.remove("active");
    
    if (webcamStream) {
      desactiveWebcam();
    } else {
      activeWebcam();
    }
  });
}

if (webcamCloseBtn) {
  webcamCloseBtn.addEventListener("click", desactiveWebcam);
}

// Prendre une capture pour le moteur de vision
async function captureCameraFrame(reqId: string) {
  let tempStream: MediaStream | null = null;
  let videoEl = webcamVideo;
  
  // Si le flux vidéo global n'est pas actif, on en ouvre un temporaire en tâche de fond
  if (!webcamStream) {
    const selectedCameraId = settingsCameraEl ? settingsCameraEl.value : "";
    const constraints = {
      video: selectedCameraId ? { deviceId: { exact: selectedCameraId } } : true
    };
    try {
      tempStream = await navigator.mediaDevices.getUserMedia(constraints);
      videoEl = document.createElement("video");
      videoEl.srcObject = tempStream;
      videoEl.autoplay = true;
      videoEl.playsInline = true;
      // Laisser 350ms pour adapter l'exposition de l'objectif
      await new Promise(resolve => setTimeout(resolve, 350));
    } catch (err) {
      console.error("Échec de la capture caméra temporaire :", err);
      if (ws && ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ type: "camera_capture_response", id: reqId, success: false, error: String(err) }));
      }
      return;
    }
  }
  
  try {
    const canvas = document.createElement("canvas");
    canvas.width = videoEl.videoWidth || 640;
    canvas.height = videoEl.videoHeight || 480;
    const ctx = canvas.getContext("2d");
    if (ctx) {
      ctx.drawImage(videoEl, 0, 0, canvas.width, canvas.height);
      const imgB64 = canvas.toDataURL("image/jpeg").split(",")[1];
      if (ws && ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ type: "camera_capture_response", id: reqId, success: true, image: imgB64 }));
      }
    } else {
      throw new Error("Impossible d'obtenir le contexte 2D du Canvas");
    }
  } catch (err) {
    console.error("Erreur de rendu canvas :", err);
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ type: "camera_capture_response", id: reqId, success: false, error: String(err) }));
    }
  } finally {
    if (tempStream) {
      tempStream.getTracks().forEach(track => track.stop());
    }
  }
}

// ── GESTURE AND HAND TRACKING SYSTEM ──────────────────────────────────────────
let globalHands: any = null;
let isHandTrackingActive = false;
let lastFrameTime = 0;

let grabbedElement: HTMLElement | null = null;
let grabOffsetX = 0;
let grabOffsetY = 0;
let isGrabbing = false;

// Variables for Two-Hand Deformation
let initialHandDist = 0;
let initialHandAngle = 0;
let isTwoHandDeforming = false;
let initialCanvasLeft = 0;
let initialCanvasTop = 0;
let initialMidX = 0;
let initialMidY = 0;

// Create the dynamic HUD cursors (one for each hand)
function createGestureCursor() {
  for (let i = 0; i < 2; i++) {
    let cursor = document.getElementById(`hand-gesture-cursor-${i}`);
    if (!cursor) {
      cursor = document.createElement("div");
      cursor.id = `hand-gesture-cursor-${i}`;
      cursor.style.position = "fixed";
      cursor.style.width = "30px";
      cursor.style.height = "30px";
      cursor.style.borderRadius = "50%";
      cursor.style.border = "2px solid #00e5ff";
      cursor.style.boxShadow = "0 0 15px #00e5ff, inset 0 0 10px #00e5ff";
      cursor.style.pointerEvents = "none";
      cursor.style.zIndex = "10000"; // Always on top
      cursor.style.transform = "translate(-50%, -50%) scale(1)";
      cursor.style.transition = "transform 0.1s, border-color 0.2s, box-shadow 0.2s";
      cursor.style.display = "none";

      const dot = document.createElement("div");
      dot.style.position = "absolute";
      dot.style.left = "50%";
      dot.style.top = "50%";
      dot.style.width = "6px";
      dot.style.height = "6px";
      dot.style.backgroundColor = "#00e5ff";
      dot.style.borderRadius = "50%";
      dot.style.transform = "translate(-50%, -50%)";
      cursor.appendChild(dot);

      document.body.appendChild(cursor);
    }
  }
}

// Initialize MediaPipe Hands
function initHandTracking() {
  createGestureCursor();
  if (globalHands) return;

  if (typeof Hands === "undefined") {
    console.warn("[MediaPipe] Hands library not loaded globally.");
    return;
  }

  globalHands = new Hands({
    locateFile: (file: string) => `https://cdn.jsdelivr.net/npm/@mediapipe/hands@0.4.1675469240/${file}`
  });

  globalHands.setOptions({
    maxNumHands: 2, // Track both hands
    modelComplexity: 0,
    minDetectionConfidence: 0.55,
    minTrackingConfidence: 0.5
  });

  globalHands.onResults(handleHandResults);
  console.log("[MediaPipe] Hands initialized successfully.");
}

// Tracking loop
async function handTrackingLoop() {
  if (!webcamStream || !globalHands || !isHandTrackingActive) return;

  if (webcamVideo && !webcamVideo.paused && !webcamVideo.ended) {
    try {
      const now = performance.now();
      // Cap at ~20 fps to save CPU
      if (now - lastFrameTime > 50) {
        lastFrameTime = now;
        await globalHands.send({ image: webcamVideo });
      }
    } catch (e) {
      // Ignore transient frame errors
    }
  }

  requestAnimationFrame(handTrackingLoop);
}

// Helper to list all draggable panels that are visible
function getDraggablePanels(): HTMLElement[] {
  const panelIds = [
    "webcam-preview-panel",
    "vpn-panel",
    "shopping-panel",
    "restaurant-panel",
    "recipe-modal",
    "temp-panel",
    "weather-panel",
    "orb-clock-hud",
    "av-panel",
    "obsidian-panel",
    "uninstaller-panel",
    "winget-panel",
  ];
  const panels: HTMLElement[] = [];
  for (const id of panelIds) {
    const el = document.getElementById(id);
    if (el && !el.classList.contains("hidden") && el.style.display !== "none") {
      // Ignore webcam panel if it is fullscreen background
      if (id === "webcam-preview-panel" && el.classList.contains("fullscreen")) {
        continue;
      }
      panels.push(el);
    }
  }

  const orbCanvas = document.getElementById("orb-canvas");
  if (orbCanvas) {
    panels.push(orbCanvas);
  }

  return panels;
}

// Target detection logic
function findElementAt(x: number, y: number): HTMLElement | null {
  const panels = getDraggablePanels();
  
  // Prioritize panels over the Orb canvas
  for (const el of panels) {
    if (el.id === "orb-canvas") continue;
    const rect = el.getBoundingClientRect();
    if (x >= rect.left && x <= rect.right && y >= rect.top && y <= rect.bottom) {
      return el;
    }
  }

  // Check the Orb canvas
  const orbCanvas = document.getElementById("orb-canvas");
  if (orbCanvas) {
    const rect = orbCanvas.getBoundingClientRect();
    const centerX = rect.left + rect.width / 2;
    const centerY = rect.top + rect.height / 2;
    // Visually target the Orb at the center
    const radius = orbCanvas.classList.contains("minimized") ? 60 : 200;
    if (Math.hypot(x - centerX, y - centerY) < radius) {
      return orbCanvas;
    }
  }

  return null;
}

// Grab, Drag & Release handlers
function startGrab(el: HTMLElement, x: number, y: number) {
  grabbedElement = el;
  isGrabbing = true;

  const rect = el.getBoundingClientRect();

  if (el.id === "orb-canvas") {
    el.style.transition = "none"; // Avoid lag during manual drag
    if (el.style.width === "100%" || !el.style.width || el.style.width === "") {
      el.style.width = `${rect.width}px`;
      el.style.height = `${rect.height}px`;
    }
    el.style.inset = "auto";
    el.style.right = "auto";
    el.style.bottom = "auto";
    el.style.transform = "none";
  } else {
    el.style.right = "auto";
    el.style.bottom = "auto";
    el.style.transform = "none";
  }

  grabOffsetX = x - rect.left;
  grabOffsetY = y - rect.top;
}

function moveGrabbedElement(x: number, y: number) {
  if (!grabbedElement) return;

  const newX = x - grabOffsetX;
  const newY = y - grabOffsetY;

  if (grabbedElement.id === "orb-canvas") {
    // Let the Orb canvas center move anywhere within/around the screen
    const halfW = grabbedElement.offsetWidth / 2;
    const halfH = grabbedElement.offsetHeight / 2;
    const boundedX = Math.max(-halfW, Math.min(newX, window.innerWidth - halfW));
    const boundedY = Math.max(-halfH, Math.min(newY, window.innerHeight - halfH));
    grabbedElement.style.left = `${boundedX}px`;
    grabbedElement.style.top = `${boundedY}px`;
  } else {
    const boundedX = Math.max(0, Math.min(newX, window.innerWidth - grabbedElement.offsetWidth));
    const boundedY = Math.max(0, Math.min(newY, window.innerHeight - grabbedElement.offsetHeight));
    grabbedElement.style.left = `${boundedX}px`;
    grabbedElement.style.top = `${boundedY}px`;
  }
}

function releaseGrab() {
  if (grabbedElement) {
    if (grabbedElement.id === "orb-canvas") {
      grabbedElement.style.transition = "all 0.8s cubic-bezier(0.34, 1.56, 0.64, 1)";
    }
  }
  grabbedElement = null;
  isGrabbing = false;
}

function endTwoHandDeformation() {
  isTwoHandDeforming = false;
  const orbCanvas = document.getElementById("orb-canvas");
  if (orbCanvas) {
    orbCanvas.style.transition = "all 0.8s cubic-bezier(0.34, 1.56, 0.64, 1)";
  }
  // @ts-ignore
  if (typeof orb !== "undefined" && orb && orb.setDeformation) {
    // @ts-ignore
    orb.setDeformation(1, 1, 0);
  }
}

// Update the dynamic cursors state
function updateHandCursor(results: any) {
  const cursor0 = document.getElementById("hand-gesture-cursor-0");
  const cursor1 = document.getElementById("hand-gesture-cursor-1");
  if (!cursor0 || !cursor1) return;

  const numHands = results.multiHandLandmarks ? results.multiHandLandmarks.length : 0;

  if (numHands === 0) {
    cursor0.style.display = "none";
    cursor1.style.display = "none";
    return;
  }

  // Update Hand 0
  cursor0.style.display = "block";
  const hand0 = results.multiHandLandmarks[0];
  const thumb0 = hand0[4];
  const index0 = hand0[8];
  const pinchX0 = (thumb0.x + index0.x) / 2;
  const pinchY0 = (thumb0.y + index0.y) / 2;
  const screenX0 = (1 - pinchX0) * window.innerWidth;
  const screenY0 = pinchY0 * window.innerHeight;

  cursor0.style.left = `${screenX0}px`;
  cursor0.style.top = `${screenY0}px`;

  const dist0 = Math.hypot(thumb0.x - index0.x, thumb0.y - index0.y);
  const pinched0 = dist0 < 0.08;

  if (pinched0) {
    cursor0.style.transform = "translate(-50%, -50%) scale(0.7)";
    cursor0.style.borderColor = "#ff3366";
    cursor0.style.boxShadow = "0 0 15px #ff3366, inset 0 0 10px #ff3366";
    const dot = cursor0.children[0] as HTMLDivElement;
    if (dot) dot.style.backgroundColor = "#ff3366";
  } else {
    cursor0.style.transform = "translate(-50%, -50%) scale(1)";
    cursor0.style.borderColor = "#00e5ff";
    cursor0.style.boxShadow = "0 0 15px #00e5ff, inset 0 0 10px #00e5ff";
    const dot = cursor0.children[0] as HTMLDivElement;
    if (dot) dot.style.backgroundColor = "#00e5ff";
  }

  // Update Hand 1
  if (numHands >= 2) {
    cursor1.style.display = "block";
    const hand1 = results.multiHandLandmarks[1];
    const thumb1 = hand1[4];
    const index1 = hand1[8];
    const pinchX1 = (thumb1.x + index1.x) / 2;
    const pinchY1 = (thumb1.y + index1.y) / 2;
    const screenX1 = (1 - pinchX1) * window.innerWidth;
    const screenY1 = pinchY1 * window.innerHeight;

    cursor1.style.left = `${screenX1}px`;
    cursor1.style.top = `${screenY1}px`;

    const dist1 = Math.hypot(thumb1.x - index1.x, thumb1.y - index1.y);
    const pinched1 = dist1 < 0.08;

    if (pinched1) {
      cursor1.style.transform = "translate(-50%, -50%) scale(0.7)";
      cursor1.style.borderColor = "#ff3366";
      cursor1.style.boxShadow = "0 0 15px #ff3366, inset 0 0 10px #ff3366";
      const dot = cursor1.children[0] as HTMLDivElement;
      if (dot) dot.style.backgroundColor = "#ff3366";
    } else {
      cursor1.style.transform = "translate(-50%, -50%) scale(1)";
      cursor1.style.borderColor = "#00e5ff";
      cursor1.style.boxShadow = "0 0 15px #00e5ff, inset 0 0 10px #00e5ff";
      const dot = cursor1.children[0] as HTMLDivElement;
      if (dot) dot.style.backgroundColor = "#00e5ff";
    }
  } else {
    cursor1.style.display = "none";
  }
}

// Handle MediaPipe hands results
function handleHandResults(results: any) {
  updateHandCursor(results);

  if (!results.multiHandLandmarks || results.multiHandLandmarks.length === 0) {
    if (isGrabbing) releaseGrab();
    if (isTwoHandDeforming) endTwoHandDeformation();
    return;
  }

  const numHands = results.multiHandLandmarks.length;

  if (numHands >= 2) {
    // Two hands: handle stretching/deformation of the Orb
    const hand0 = results.multiHandLandmarks[0];
    const hand1 = results.multiHandLandmarks[1];

    const thumb0 = hand0[4];
    const index0 = hand0[8];
    const thumb1 = hand1[4];
    const index1 = hand1[8];

    const x0 = (1 - (thumb0.x + index0.x) / 2) * window.innerWidth;
    const y0 = ((thumb0.y + index0.y) / 2) * window.innerHeight;
    const x1 = (1 - (thumb1.x + index1.x) / 2) * window.innerWidth;
    const y1 = ((thumb1.y + index1.y) / 2) * window.innerHeight;

    const pinched0 = Math.hypot(thumb0.x - index0.x, thumb0.y - index0.y) < 0.08;
    const pinched1 = Math.hypot(thumb1.x - index1.x, thumb1.y - index1.y) < 0.08;

    if (pinched0 && pinched1) {
      const orbCanvas = document.getElementById("orb-canvas");
      if (orbCanvas) {
        const rect = orbCanvas.getBoundingClientRect();
        const centerX = rect.left + rect.width / 2;
        const centerY = rect.top + rect.height / 2;

        const distToOrb0 = Math.hypot(x0 - centerX, y0 - centerY);
        const distToOrb1 = Math.hypot(x1 - centerX, y1 - centerY);

        // Check if both hands are near the Orb (within 350px)
        if (distToOrb0 < 350 && distToOrb1 < 350) {
          const currentDist = Math.hypot(x0 - x1, y0 - y1);
          const currentAngle = Math.atan2(y1 - y0, x1 - x0);

          if (!isTwoHandDeforming) {
            isTwoHandDeforming = true;
            initialHandDist = currentDist > 0 ? currentDist : 1;
            initialHandAngle = currentAngle;
            initialCanvasLeft = rect.left;
            initialCanvasTop = rect.top;
            initialMidX = (x0 + x1) / 2;
            initialMidY = (y0 + y1) / 2;
            
            orbCanvas.style.transition = "none";
            if (orbCanvas.style.width === "100%" || !orbCanvas.style.width || orbCanvas.style.width === "") {
              orbCanvas.style.width = `${rect.width}px`;
              orbCanvas.style.height = `${rect.height}px`;
            }
            orbCanvas.style.inset = "auto";
            orbCanvas.style.right = "auto";
            orbCanvas.style.bottom = "auto";
            orbCanvas.style.transform = "none";
          } else {
            const scale = currentDist / initialHandDist;
            const deltaAngle = currentAngle - initialHandAngle;
            
            const scaleX = scale;
            const scaleY = 1 / Math.max(0.2, Math.sqrt(scale)); // Elastic volume-preserving scale

            // @ts-ignore
            if (typeof orb !== "undefined" && orb && orb.setDeformation) {
              // @ts-ignore
              orb.setDeformation(scaleX, scaleY, deltaAngle);
            }

            // Move the Orb canvas along with the midpoint of the hands
            const midX = (x0 + x1) / 2;
            const midY = (y0 + y1) / 2;
            const dx = midX - initialMidX;
            const dy = midY - initialMidY;

            const newX = initialCanvasLeft + dx;
            const newY = initialCanvasTop + dy;

            // Bounded limits (allow center to be anywhere on screen)
            const halfW = orbCanvas.offsetWidth / 2;
            const halfH = orbCanvas.offsetHeight / 2;
            const boundedX = Math.max(-halfW, Math.min(newX, window.innerWidth - halfW));
            const boundedY = Math.max(-halfH, Math.min(newY, window.innerHeight - halfH));

            orbCanvas.style.left = `${boundedX}px`;
            orbCanvas.style.top = `${boundedY}px`;
          }
          return;
        }
      }
    }
  }

  if (isTwoHandDeforming) {
    endTwoHandDeformation();
  }

  // One hand logic (drag-and-drop elements)
  const hand = results.multiHandLandmarks[0];
  const thumbTip = hand[4];
  const indexTip = hand[8];

  const pinchX = (thumbTip.x + indexTip.x) / 2;
  const pinchY = (thumbTip.y + indexTip.y) / 2;
  const screenX = (1 - pinchX) * window.innerWidth;
  const screenY = pinchY * window.innerHeight;

  const dist = Math.hypot(thumbTip.x - indexTip.x, thumbTip.y - indexTip.y);
  const pinched = dist < 0.08;

  if (pinched) {
    if (!isGrabbing) {
      const elementToGrab = findElementAt(screenX, screenY);
      if (elementToGrab) {
        startGrab(elementToGrab, screenX, screenY);
      }
    } else {
      moveGrabbedElement(screenX, screenY);
    }
  } else {
    if (isGrabbing) releaseGrab();
  }
}


// ─────────────────────────────────────────────────────────────────────────────
// ─────────────────────────────────────────────────────────────────────────────
// MODEL SELECTOR PANEL
// ─────────────────────────────────────────────────────────────────────────────
export function showImageModelSelector(promptFr: string): void {
  const oldPanel = document.getElementById("model-selector-panel");
  if (oldPanel) oldPanel.remove();

  const panel = document.createElement("div");
  panel.id = "model-selector-panel";
  panel.className = "aurora-panel";
  panel.style.position = "fixed";
  panel.style.zIndex = "999999";
  panel.style.top = "50%";
  panel.style.left = "50%";
  panel.style.transform = "translate(-50%, -50%)";
  panel.style.margin = "0";
  panel.style.display = "flex";
  panel.style.flexDirection = "column";
  panel.style.alignItems = "center";
  panel.style.justifyContent = "center";
  panel.style.padding = "40px";
  panel.style.background = "rgba(5, 0, 20, 0.95)";
  panel.style.border = "1px solid rgba(0, 200, 255, 0.6)";
  panel.style.boxShadow = "0 0 50px rgba(0, 200, 255, 0.3), inset 0 0 20px rgba(0, 200, 255, 0.1)";
  panel.style.backdropFilter = "blur(15px)";
  panel.style.borderRadius = "15px";

  const header = document.createElement("div");
  header.style.textAlign = "center";
  header.style.marginBottom = "30px";

  const title = document.createElement("h2");
  title.innerText = "SÉLECTION DU MODÈLE IA";
  title.style.color = "#00ffff";
  title.style.fontFamily = "'Orbitron', sans-serif";
  title.style.letterSpacing = "2px";
  title.style.margin = "0 0 10px 0";
  title.style.textShadow = "0 0 10px #00ffff";
  header.appendChild(title);

  const sub = document.createElement("p");
  sub.innerText = "Quel cerveau dois-je utiliser pour générer cette image ?";
  sub.style.color = "rgba(255, 255, 255, 0.8)";
  sub.style.fontSize = "14px";
  sub.style.margin = "0";
  header.appendChild(sub);
  
  const promptTxt = document.createElement("p");
  promptTxt.innerText = `"${promptFr}"`;
  promptTxt.style.color = "rgba(255, 255, 255, 0.6)";
  promptTxt.style.fontStyle = "italic";
  promptTxt.style.fontSize = "12px";
  promptTxt.style.marginTop = "10px";
  promptTxt.style.maxWidth = "400px";
  promptTxt.style.textAlign = "center";
  header.appendChild(promptTxt);

  panel.appendChild(header);

  const btnContainer = document.createElement("div");
  btnContainer.style.display = "flex";
  btnContainer.style.gap = "20px";
  btnContainer.style.width = "100%";
  btnContainer.style.justifyContent = "center";

  const createModelBtn = (name: string, modelId: string, color: string) => {
    const btn = document.createElement("button");
    btn.innerHTML = `
      <div style="font-size: 18px; font-weight: bold; margin-bottom: 5px; font-family: 'Orbitron', sans-serif;">${name}</div>
      <div style="font-size: 12px; opacity: 0.7;">Générer l'image</div>
    `;
    btn.style.flex = "1";
    btn.style.padding = "20px";
    btn.style.background = `rgba(${color}, 0.1)`;
    btn.style.border = `1px solid rgba(${color}, 0.5)`;
    btn.style.borderRadius = "10px";
    btn.style.color = "#fff";
    btn.style.cursor = "pointer";
    btn.style.transition = "all 0.3s ease";
    btn.style.fontFamily = "'Jura', sans-serif";

    btn.onmouseenter = () => {
      btn.style.background = `rgba(${color}, 0.3)`;
      btn.style.boxShadow = `0 0 20px rgba(${color}, 0.4)`;
      btn.style.transform = "translateY(-2px)";
    };
    btn.onmouseleave = () => {
      btn.style.background = `rgba(${color}, 0.1)`;
      btn.style.boxShadow = "none";
      btn.style.transform = "translateY(0)";
    };

    btn.onclick = () => {
      panel.remove();
      // Send message to backend
      if (ws && ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({
          type: "generate_image_selected",
          prompt: promptFr,
          model: modelId
        }));
      }
    };
    return btn;
  };

  const geminiImagenBtn = createModelBtn("Gemini Imagen 4", "gemini", "0, 200, 255");
  const geminiFlashBtn = createModelBtn("Gemini 3.1 Flash Lite Image", "gemini_flash_lite", "0, 200, 255");
  const grokBtn = createModelBtn("xAI Grok", "grok", "160, 60, 255");
  const openaiBtn = createModelBtn("gpt-image-2", "openai", "0, 166, 126");

  btnContainer.appendChild(openaiBtn);
  btnContainer.appendChild(geminiImagenBtn);
  btnContainer.appendChild(geminiFlashBtn);
  btnContainer.appendChild(grokBtn);
  panel.appendChild(btnContainer);
  
  const cancelBtn = document.createElement("div");
  cancelBtn.innerText = "ANNULER";
  cancelBtn.style.marginTop = "30px";
  cancelBtn.style.color = "rgba(255,255,255,0.4)";
  cancelBtn.style.cursor = "pointer";
  cancelBtn.style.fontSize = "12px";
  cancelBtn.style.letterSpacing = "2px";
  cancelBtn.style.transition = "color 0.2s";
  cancelBtn.onmouseenter = () => cancelBtn.style.color = "#fff";
  cancelBtn.onmouseleave = () => cancelBtn.style.color = "rgba(255,255,255,0.4)";
  cancelBtn.onclick = () => panel.remove();
  
  panel.appendChild(cancelBtn);

  document.body.appendChild(panel);
}

// ─────────────────────────────────────────────────────────────────────────────
// AURORA IMAGE PANEL — Affichage des images générées par xAI Aurora
// ─────────────────────────────────────────────────────────────────────────────
function showAuroraImagePanel(promptFr: string, promptEn: string, imageUrl: string, imagePath: string = ""): void {
  const container = document.getElementById("image-panels-container");
  if (!container) return;

  const panel = document.createElement("div");
  panel.className = "aurora-panel";

  // Position centrée avec légère cascade si plusieurs panneaux
  const existingPanels = container.querySelectorAll(".aurora-panel").length;
  const offset = existingPanels * 25;
  const left = Math.max(40, (window.innerWidth - 560) / 2 + offset);
  const top  = Math.max(40, (window.innerHeight - 640) / 2 + offset);
  panel.style.left = `${left}px`;
  panel.style.top  = `${top}px`;

  // Z-index
  maxZIndex++;
  panel.style.zIndex = maxZIndex.toString();
  panel.addEventListener("mousedown", () => {
    maxZIndex++;
    panel.style.zIndex = maxZIndex.toString();
  });

  const timestamp = new Date().toLocaleTimeString("fr-FR", { hour: "2-digit", minute: "2-digit" });

  panel.innerHTML = `
    <div class="aurora-scanlines"></div>
    <div class="aurora-corner aurora-corner-tr"></div>
    <div class="aurora-corner aurora-corner-bl"></div>

    <div class="aurora-header">
      <div class="aurora-drag-handle">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="14" height="14">
          <path d="M5 9l7-7 7 7M5 15l7 7 7-7"/>
        </svg>
      </div>
      <div class="aurora-title-block">
        <span class="aurora-badge">⚡ AURORA_GEN</span>
        <span class="aurora-model-tag">xAI • IMAGE_AI</span>
      </div>
      <div class="aurora-header-actions">
        <button class="aurora-close-btn">✕</button>
      </div>
    </div>

    <div class="aurora-status-bar">
      <span class="aurora-status-dot"></span>
      <span>GENERATION_COMPLETE</span>
      <span class="aurora-timestamp">${timestamp}</span>
    </div>

    <div class="aurora-prompt-display">
      <span class="aurora-prompt-label">PROMPT ›</span>
      <span class="aurora-prompt-text">${promptFr}</span>
    </div>

    <div class="aurora-image-wrapper">
      <div class="aurora-image-loading">
        <div class="aurora-spinner"></div>
        <span>RENDERING...</span>
      </div>
      <img class="aurora-image" src="${imageUrl}" alt="${promptFr}" />
    </div>

    <div class="aurora-footer">
      <span>SYS.AI: XAI_AURORA</span>
      <span>JARVIS_V2.6 // NEURAL_GEN</span>
    </div>
  `;

  container.appendChild(panel);

  // Image load handler
  const img = panel.querySelector(".aurora-image") as HTMLImageElement;
  const loader = panel.querySelector(".aurora-image-loading") as HTMLElement;
  img.onload = () => {
    loader.style.display = "none";
    img.style.opacity = "1";
  };
  img.onerror = () => {
    loader.innerHTML = `<span style="color:rgba(255,80,80,0.8)">⚠ Erreur de chargement</span>`;
  };

  // Fermer
  panel.querySelector(".aurora-close-btn")?.addEventListener("click", () => {
    panel.style.animation = "auroraFadeOut 0.25s ease forwards";
    setTimeout(() => panel.remove(), 250);
  });

  // Drag & drop
  const header = panel.querySelector(".aurora-header") as HTMLElement;
  let isDragging = false;
  let dragOffX = 0, dragOffY = 0;
  header.addEventListener("mousedown", (e: MouseEvent) => {
    isDragging = true;
    dragOffX = e.clientX - panel.getBoundingClientRect().left;
    dragOffY = e.clientY - panel.getBoundingClientRect().top;
    e.preventDefault();
  });
  document.addEventListener("mousemove", (e: MouseEvent) => {
    if (!isDragging) return;
    panel.style.left = `${e.clientX - dragOffX}px`;
    panel.style.top  = `${e.clientY - dragOffY}px`;
  });
  document.addEventListener("mouseup", () => { isDragging = false; });
}

// ─────────────────────────────────────────────────────────────────────────────
// GENERATION LOADING OVERLAY (IRON MAN STYLE)
// ─────────────────────────────────────────────────────────────────────────────
let generationLoadingOverlay: HTMLElement | null = null;

function showGenerationLoading(mediaType: string) {
  if (generationLoadingOverlay) {
    document.body.removeChild(generationLoadingOverlay);
  }
  
  const typeText = mediaType === "video" ? "GÉNÉRATION VIDÉO" : "GÉNÉRATION IMAGE";
  const color = mediaType === "video" ? "255, 60, 120" : "160, 60, 255";
  
  generationLoadingOverlay = document.createElement("div");
  generationLoadingOverlay.className = "gen-loading-overlay";
  
  generationLoadingOverlay.innerHTML = `
    <div class="gen-loading-backdrop"></div>
    <div class="gen-loading-content" style="--accent: ${color}">
      <div class="gen-loading-ring"></div>
      <div class="gen-loading-ring gen-loading-ring-inner"></div>
      <div class="gen-loading-core">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
          <!-- Icône Cerveau IA / Hexagone tech au lieu du '$' -->
          <polygon points="12 2 22 8.5 22 15.5 12 22 2 15.5 2 8.5 12 2" />
          <polyline points="2 8.5 12 15.5 22 8.5" />
          <polyline points="12 22 12 15.5" />
          <circle cx="12" cy="15.5" r="1.5" fill="currentColor"/>
          <circle cx="12" cy="2" r="1.5" fill="currentColor"/>
          <circle cx="2" cy="8.5" r="1.5" fill="currentColor"/>
          <circle cx="22" cy="8.5" r="1.5" fill="currentColor"/>
        </svg>
      </div>
      <div class="gen-loading-text">
        <div class="gen-loading-title">SYSTEM.AI_ACTIVE // ${typeText}</div>
        <div class="gen-loading-subtitle">NEURAL NETWORK PROCESSING...</div>
      </div>
    </div>
  `;
  
  document.body.appendChild(generationLoadingOverlay);
}

function hideGenerationLoading() {
  if (generationLoadingOverlay) {
    generationLoadingOverlay.style.animation = "auroraFadeOut 0.4s ease forwards";
    setTimeout(() => {
      if (generationLoadingOverlay && generationLoadingOverlay.parentNode) {
        generationLoadingOverlay.parentNode.removeChild(generationLoadingOverlay);
      }
      generationLoadingOverlay = null;
    }, 400);
  }
}
// ─────────────────────────────────────────────────────────────────────────────
// AURORA VIDEO PANEL — xAI Generated Videos
// ─────────────────────────────────────────────────────────────────────────────
function showAuroraVideoPanel(promptFr: string, promptEn: string, videoUrl: string, source: string, videoPath: string = ""): void {
  const container = document.getElementById("image-panels-container");
  if (!container) return;

  const panel = document.createElement("div");
  panel.className = "aurora-video-panel";

  const existingPanels = container.querySelectorAll(".aurora-video-panel").length;
  const offset = existingPanels * 25;
  const left = Math.max(40, (window.innerWidth - 600) / 2 + offset);
  const top  = Math.max(40, (window.innerHeight - 500) / 2 + offset);
  panel.style.left = `${left}px`;
  panel.style.top  = `${top}px`;

  maxZIndex++;
  panel.style.zIndex = maxZIndex.toString();
  panel.addEventListener("mousedown", () => { maxZIndex++; panel.style.zIndex = maxZIndex.toString(); });

  const timestamp = new Date().toLocaleTimeString("fr-FR", { hour: "2-digit", minute: "2-digit" });
  const isDataUrl = videoUrl.startsWith("data:");

  panel.innerHTML = `
    <div class="aurora-video-scanlines"></div>
    <div class="aurora-corner aurora-video-corner-tr"></div>
    <div class="aurora-corner aurora-video-corner-bl"></div>

    <div class="aurora-video-header">
      <div class="aurora-drag-handle">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="14" height="14">
          <path d="M5 9l7-7 7 7M5 15l7 7 7-7"/>
        </svg>
      </div>
      <div class="aurora-title-block">
        <span class="aurora-video-badge">🎬 VIDEO_GEN</span>
        <span class="aurora-model-tag">${source} • CINEMATIC_AI</span>
      </div>
      <div class="aurora-header-actions">
        <button class="aurora-video-close-btn">✕</button>
      </div>
    </div>

    <div class="aurora-status-bar" style="border-color:rgba(255,60,120,0.15); color:rgba(255,100,150,0.55)">
      <span class="aurora-video-status-dot"></span>
      <span>VIDEO_GENERATION_COMPLETE</span>
      <span class="aurora-timestamp">${timestamp}</span>
    </div>

    <div class="aurora-prompt-display" style="border-color:rgba(255,60,120,0.1)">
      <span class="aurora-prompt-label" style="color:rgba(255,80,130,0.5)">PROMPT ›</span>
      <span class="aurora-prompt-text" style="color:rgba(255,150,180,0.8)">${promptFr}</span>
    </div>

    <div class="aurora-video-wrapper">
      <div class="aurora-image-loading" id="vid-loader-${Date.now()}">
        <div class="aurora-video-spinner"></div>
        <span>LOADING VIDEO...</span>
      </div>
      <video class="aurora-video-player" controls autoplay muted loop>
        <source src="${videoUrl}" type="video/mp4" />
        Votre navigateur ne supporte pas la lecture vidéo.
      </video>
    </div>

    <div class="aurora-footer" style="border-color:rgba(255,60,120,0.15); color:rgba(255,60,120,0.35)">
      <span>SYS.AI: ${source.toUpperCase()}</span>
      <span>JARVIS_V2.6 // NEURAL_VIDEO</span>
    </div>
  `;

  container.appendChild(panel);

  const video = panel.querySelector(".aurora-video-player") as HTMLVideoElement;
  const loader = panel.querySelector(".aurora-image-loading") as HTMLElement;
  video.oncanplay = () => { if (loader) loader.style.display = "none"; };
  video.onerror   = () => { if (loader) loader.innerHTML = `<span style="color:rgba(255,80,80,0.8)">⚠ Erreur vidéo</span>`; };

  panel.querySelector(".aurora-video-close-btn")?.addEventListener("click", () => {
    panel.style.animation = "auroraFadeOut 0.25s ease forwards";
    setTimeout(() => panel.remove(), 250);
  });

  const header = panel.querySelector(".aurora-video-header") as HTMLElement;
  let isDragging = false;
  let dragOffX = 0, dragOffY = 0;
  header.addEventListener("mousedown", (e: MouseEvent) => {
    isDragging = true;
    dragOffX = e.clientX - panel.getBoundingClientRect().left;
    dragOffY = e.clientY - panel.getBoundingClientRect().top;
    e.preventDefault();
  });
  document.addEventListener("mousemove", (e: MouseEvent) => {
    if (!isDragging) return;
    panel.style.left = `${e.clientX - dragOffX}px`;
    panel.style.top  = `${e.clientY - dragOffY}px`;
  });
  document.addEventListener("mouseup", () => { isDragging = false; });
}

export function showGeneratedPrompt(promptText: string): void {
  const oldPanel = document.getElementById("generated-prompt-panel");
  if (oldPanel) oldPanel.remove();

  const panel = document.createElement("div");
  panel.id = "generated-prompt-panel";
  panel.className = "aurora-panel";
  panel.style.position = "fixed";
  panel.style.zIndex = "999999";
  panel.style.top = "50%";
  panel.style.left = "50%";
  panel.style.transform = "translate(-50%, -50%)";
  panel.style.margin = "0";
  panel.style.display = "flex";
  panel.style.flexDirection = "column";
  panel.style.alignItems = "center";
  panel.style.justifyContent = "center";
  panel.style.padding = "40px";
  panel.style.background = "rgba(5, 0, 20, 0.95)";
  panel.style.border = "1px solid rgba(0, 255, 120, 0.6)";
  panel.style.boxShadow = "0 0 50px rgba(0, 255, 120, 0.3), inset 0 0 20px rgba(0, 255, 120, 0.1)";
  panel.style.backdropFilter = "blur(15px)";
  panel.style.borderRadius = "15px";
  panel.style.maxWidth = "800px";
  panel.style.width = "90%";

  const header = document.createElement("div");
  header.style.textAlign = "center";
  header.style.marginBottom = "20px";

  const title = document.createElement("h2");
  title.innerText = "PROMPT GÉNÉRÉ";
  title.style.color = "#00ff78";
  title.style.fontFamily = "'Orbitron', sans-serif";
  title.style.letterSpacing = "2px";
  title.style.margin = "0 0 10px 0";
  title.style.textShadow = "0 0 10px #00ff78";
  header.appendChild(title);

  panel.appendChild(header);

  const textContainer = document.createElement("div");
  textContainer.style.width = "100%";
  textContainer.style.background = "rgba(0, 0, 0, 0.5)";
  textContainer.style.border = "1px solid rgba(0, 255, 120, 0.3)";
  textContainer.style.borderRadius = "8px";
  textContainer.style.padding = "20px";
  textContainer.style.marginBottom = "20px";
  textContainer.style.maxHeight = "400px";
  textContainer.style.overflowY = "auto";
  textContainer.style.color = "rgba(255, 255, 255, 0.9)";
  textContainer.style.fontFamily = "'Courier New', monospace";
  textContainer.style.fontSize = "14px";
  textContainer.style.lineHeight = "1.5";
  textContainer.style.whiteSpace = "pre-wrap";
  textContainer.innerText = promptText;
  panel.appendChild(textContainer);

  const btnContainer = document.createElement("div");
  btnContainer.style.display = "flex";
  btnContainer.style.gap = "20px";
  btnContainer.style.width = "100%";
  btnContainer.style.justifyContent = "center";

  const copyBtn = document.createElement("button");
  copyBtn.innerText = "COPIER LE PROMPT";
  copyBtn.style.padding = "15px 30px";
  copyBtn.style.background = "rgba(0, 255, 120, 0.2)";
  copyBtn.style.border = "1px solid rgba(0, 255, 120, 0.5)";
  copyBtn.style.borderRadius = "10px";
  copyBtn.style.color = "#fff";
  copyBtn.style.cursor = "pointer";
  copyBtn.style.fontFamily = "'Orbitron', sans-serif";
  copyBtn.style.transition = "all 0.3s ease";
  
  copyBtn.onmouseenter = () => {
    copyBtn.style.background = "rgba(0, 255, 120, 0.4)";
    copyBtn.style.boxShadow = "0 0 20px rgba(0, 255, 120, 0.4)";
  };
  copyBtn.onmouseleave = () => {
    copyBtn.style.background = "rgba(0, 255, 120, 0.2)";
    copyBtn.style.boxShadow = "none";
  };
  copyBtn.onclick = () => {
    navigator.clipboard.writeText(promptText).then(() => {
      copyBtn.innerText = "COPIÉ !";
      setTimeout(() => { copyBtn.innerText = "COPIER LE PROMPT"; }, 2000);
    });
  };

  const closeBtn = document.createElement("button");
  closeBtn.innerText = "FERMER";
  closeBtn.style.padding = "15px 30px";
  closeBtn.style.background = "rgba(255, 60, 120, 0.2)";
  closeBtn.style.border = "1px solid rgba(255, 60, 120, 0.5)";
  closeBtn.style.borderRadius = "10px";
  closeBtn.style.color = "#fff";
  closeBtn.style.cursor = "pointer";
  closeBtn.style.fontFamily = "'Orbitron', sans-serif";
  closeBtn.style.transition = "all 0.3s ease";
  
  closeBtn.onmouseenter = () => {
    closeBtn.style.background = "rgba(255, 60, 120, 0.4)";
    closeBtn.style.boxShadow = "0 0 20px rgba(255, 60, 120, 0.4)";
  };
  closeBtn.onmouseleave = () => {
    closeBtn.style.background = "rgba(255, 60, 120, 0.2)";
    closeBtn.style.boxShadow = "none";
  };
  closeBtn.onclick = () => {
    panel.remove();
  };

  btnContainer.appendChild(copyBtn);
  btnContainer.appendChild(closeBtn);
  panel.appendChild(btnContainer);
  document.body.appendChild(panel);
}

export function showWebsiteModelSelector(promptFr: string, availableModels: string[]): void {
  const oldPanel = document.getElementById("website-model-selector-panel");
  if (oldPanel) oldPanel.remove();

  const panel = document.createElement("div");
  panel.id = "website-model-selector-panel";
  panel.className = "aurora-panel";
  panel.style.position = "fixed";
  panel.style.zIndex = "999999";
  panel.style.top = "50%";
  panel.style.left = "50%";
  panel.style.transform = "translate(-50%, -50%)";
  panel.style.margin = "0";
  panel.style.display = "flex";
  panel.style.flexDirection = "column";
  panel.style.alignItems = "center";
  panel.style.justifyContent = "center";
  panel.style.padding = "40px";
  panel.style.background = "rgba(5, 0, 20, 0.95)";
  panel.style.border = "1px solid rgba(0, 200, 255, 0.6)";
  panel.style.boxShadow = "0 0 50px rgba(0, 200, 255, 0.3), inset 0 0 20px rgba(0, 200, 255, 0.1)";
  panel.style.backdropFilter = "blur(15px)";
  panel.style.borderRadius = "15px";
  const header = document.createElement("div");
  header.style.textAlign = "center";
  header.style.marginBottom = "30px";

  const title = document.createElement("h2");
  title.innerText = "CRÉATION DE SITE WEB";
  title.style.color = "#00ffff";
  title.style.fontFamily = "'Orbitron', sans-serif";
  title.style.letterSpacing = "2px";
  title.style.margin = "0 0 10px 0";
  title.style.textShadow = "0 0 10px #00ffff";
  header.appendChild(title);

  const sub = document.createElement("p");
  sub.innerText = "Quel cerveau IA doit générer votre site internet ?";
  sub.style.color = "rgba(255, 255, 255, 0.8)";
  sub.style.fontSize = "14px";
  sub.style.margin = "0";
  header.appendChild(sub);

  
  const promptTxt = document.createElement("p");
  promptTxt.innerText = `"${promptFr}"`;
  promptTxt.style.color = "rgba(255, 255, 255, 0.6)";
  promptTxt.style.fontStyle = "italic";
  promptTxt.style.fontSize = "12px";
  promptTxt.style.marginTop = "10px";
  promptTxt.style.maxWidth = "400px";
  promptTxt.style.textAlign = "center";
  header.appendChild(promptTxt);

  panel.appendChild(header);

  const btnContainer = document.createElement("div");
  btnContainer.style.display = "flex";
  btnContainer.style.gap = "20px";
  btnContainer.style.width = "100%";
  btnContainer.style.justifyContent = "center";
  btnContainer.style.flexWrap = "wrap";

  const modelInfo: Record<string, {name: string, color: string}> = {
    "gemini": { name: "Gemini", color: "0, 200, 255" },
    "claude": { name: "Claude", color: "255, 100, 50" },
    "groq": { name: "Groq", color: "255, 50, 50" },
    "mistral": { name: "Mistral", color: "255, 150, 0" },
    "grok": { name: "Grok", color: "100, 100, 255" },
    "openai": { name: "ChatGPT", color: "0, 166, 126" },
  };

  const createModelBtn = (modelId: string) => {
    const info = modelInfo[modelId] || { name: modelId, color: "200, 200, 200" };
    const btn = document.createElement("button");
    btn.innerHTML = `
      <div style="font-size: 18px; font-weight: bold; margin-bottom: 5px; font-family: 'Orbitron', sans-serif;">${info.name}</div>
      <div style="font-size: 12px; opacity: 0.7;">Créer site</div>
    `;
    btn.style.flex = "1";
    btn.style.minWidth = "120px";
    btn.style.padding = "20px";
    btn.style.background = `rgba(${info.color}, 0.1)`;
    btn.style.border = `1px solid rgba(${info.color}, 0.5)`;
    btn.style.borderRadius = "10px";
    btn.style.color = "#fff";
    btn.style.cursor = "pointer";
    btn.style.transition = "all 0.3s ease";
    btn.style.fontFamily = "'Jura', sans-serif";

    btn.onmouseenter = () => {
      btn.style.background = `rgba(${info.color}, 0.3)`;
      btn.style.boxShadow = `0 0 20px rgba(${info.color}, 0.4)`;
      btn.style.transform = "translateY(-2px)";
    };
    btn.onmouseleave = () => {
      btn.style.background = `rgba(${info.color}, 0.1)`;
      btn.style.boxShadow = "none";
      btn.style.transform = "translateY(0)";
    };

    btn.onclick = () => {
      btnContainer.innerHTML = "";
      sub.innerText = "Quel modèle utiliser pour générer les images du site ?";
      
      const imgModels = ["openai", "gemini", "gemini_flash_lite", "grok"];
      const imgModelInfo: Record<string, {name: string, color: string}> = {
        "openai": { name: "gpt-image-2", color: "0, 166, 126" },
        "gemini": { name: "Imagen 4", color: "0, 200, 255" },
        "gemini_flash_lite": { name: "Gemini 3.1 Flash Lite", color: "0, 200, 255" },
        "grok": { name: "xAI Grok", color: "160, 60, 255" },
      };

      imgModels.forEach(imgId => {
        const iInfo = imgModelInfo[imgId];
        const imgBtn = document.createElement("button");
        imgBtn.innerHTML = `
          <div style="font-size: 16px; font-weight: bold; margin-bottom: 5px; font-family: 'Orbitron', sans-serif;">${iInfo.name}</div>
          <div style="font-size: 12px; opacity: 0.7;">Générer Images</div>
        `;
        imgBtn.style.flex = "1";
        imgBtn.style.minWidth = "120px";
        imgBtn.style.padding = "20px";
        imgBtn.style.background = `rgba(${iInfo.color}, 0.1)`;
        imgBtn.style.border = `1px solid rgba(${iInfo.color}, 0.5)`;
        imgBtn.style.borderRadius = "10px";
        imgBtn.style.color = "#fff";
        imgBtn.style.cursor = "pointer";
        imgBtn.style.transition = "all 0.3s ease";
        imgBtn.style.fontFamily = "'Jura', sans-serif";

        imgBtn.onmouseenter = () => {
          imgBtn.style.background = `rgba(${iInfo.color}, 0.3)`;
          imgBtn.style.boxShadow = `0 0 20px rgba(${iInfo.color}, 0.4)`;
          imgBtn.style.transform = "translateY(-2px)";
        };
        imgBtn.onmouseleave = () => {
          imgBtn.style.background = `rgba(${iInfo.color}, 0.1)`;
          imgBtn.style.boxShadow = "none";
          imgBtn.style.transform = "translateY(0)";
        };

        imgBtn.onclick = () => {
          panel.remove();
          if (ws && ws.readyState === WebSocket.OPEN) {
            ws.send(JSON.stringify({
              action: "generate_website_selected",
              prompt: promptFr,
              model: modelId,
              image_model: imgId
            }));
          } else {
            console.error("Websocket is not open.");
          }
        };
        btnContainer.appendChild(imgBtn);
      });
    };
    return btn;
  };

  availableModels.forEach(model => {
    btnContainer.appendChild(createModelBtn(model));
  });

  if (availableModels.length === 0) {
    const noModel = document.createElement("p");
    noModel.innerText = "Aucun modèle API disponible.";
    noModel.style.color = "red";
    btnContainer.appendChild(noModel);
  }

  panel.appendChild(btnContainer);
  document.body.appendChild(panel);
}


export function showWebProjectSelector(projects: string[]): void {
  const oldPanel = document.getElementById("web-project-selector-panel");
  if (oldPanel) oldPanel.remove();

  const panel = document.createElement("div");
  panel.id = "web-project-selector-panel";
  panel.className = "aurora-panel";
  panel.style.position = "fixed";
  panel.style.zIndex = "999999";
  panel.style.top = "50%";
  panel.style.left = "50%";
  panel.style.transform = "translate(-50%, -50%)";
  panel.style.margin = "0";
  panel.style.display = "flex";
  panel.style.flexDirection = "column";
  panel.style.alignItems = "center";
  panel.style.justifyContent = "center";
  panel.style.padding = "40px";
  panel.style.background = "rgba(5, 0, 20, 0.95)";
  panel.style.border = "1px solid rgba(0, 255, 100, 0.6)";
  panel.style.boxShadow = "0 0 50px rgba(0, 255, 100, 0.3), inset 0 0 20px rgba(0, 255, 100, 0.1)";
  panel.style.backdropFilter = "blur(15px)";
  panel.style.borderRadius = "15px";
  panel.style.maxHeight = "80vh";
  panel.style.overflowY = "auto";

  const header = document.createElement("div");
  header.style.textAlign = "center";
  header.style.marginBottom = "30px";

  const title = document.createElement("h2");
  title.innerText = "SÉLECTION DE PROJET WEB";
  title.style.color = "#00ff64";
  title.style.fontFamily = "'Orbitron', sans-serif";
  title.style.letterSpacing = "2px";
  title.style.margin = "0 0 10px 0";
  title.style.textShadow = "0 0 10px #00ff64";
  header.appendChild(title);

  const sub = document.createElement("p");
  sub.innerText = projects.length > 0 ? "Sélectionnez un projet web pour le rendre actif et le modifier :" : "Aucun projet web trouvé.";
  sub.style.color = "rgba(255, 255, 255, 0.8)";
  sub.style.fontSize = "14px";
  sub.style.margin = "0";
  header.appendChild(sub);

  panel.appendChild(header);

  const btnContainer = document.createElement("div");
  btnContainer.style.display = "flex";
  btnContainer.style.gap = "15px";
  btnContainer.style.width = "100%";
  btnContainer.style.justifyContent = "center";
  btnContainer.style.flexWrap = "wrap";
  btnContainer.style.maxWidth = "800px";

  projects.forEach(proj => {
    const btn = document.createElement("button");
    btn.innerHTML = `<div style="font-size: 16px; font-weight: bold; margin-bottom: 5px; font-family: 'Orbitron', sans-serif;">${proj}</div>`;
    btn.style.flex = "1 1 200px";
    btn.style.minWidth = "200px";
    btn.style.padding = "20px";
    btn.style.background = `rgba(0, 255, 100, 0.1)`;
    btn.style.border = `1px solid rgba(0, 255, 100, 0.5)`;
    btn.style.borderRadius = "10px";
    btn.style.color = "#fff";
    btn.style.cursor = "pointer";
    btn.style.transition = "all 0.3s ease";

    btn.onmouseenter = () => {
      btn.style.background = `rgba(0, 255, 100, 0.3)`;
      btn.style.boxShadow = `0 0 20px rgba(0, 255, 100, 0.4)`;
      btn.style.transform = "translateY(-2px)";
    };
    btn.onmouseleave = () => {
      btn.style.background = `rgba(0, 255, 100, 0.1)`;
      btn.style.boxShadow = "none";
      btn.style.transform = "translateY(0)";
    };

    btn.onclick = () => {
      if (ws && ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({
          action: "set_active_web_project",
          project: proj
        }));
      }
      panel.remove();
    };

    btnContainer.appendChild(btn);
  });

  panel.appendChild(btnContainer);

  const closeBtn = document.createElement("button");
  closeBtn.innerText = "ANNULER";
  closeBtn.style.marginTop = "30px";
  closeBtn.style.padding = "10px 30px";
  closeBtn.style.background = "transparent";
  closeBtn.style.border = "1px solid rgba(255, 255, 255, 0.3)";
  closeBtn.style.color = "rgba(255, 255, 255, 0.5)";
  closeBtn.style.borderRadius = "5px";
  closeBtn.style.cursor = "pointer";
  closeBtn.style.fontFamily = "'Orbitron', sans-serif";
  closeBtn.onclick = () => panel.remove();
  
  panel.appendChild(closeBtn);
  document.body.appendChild(panel);
}

// Bouger l'orbe : poignée de glisser (le canvas est pointer-events:none, on ne peut pas
// le rendre cliquable sans bloquer l'UI → une petite poignée translate le canvas).
(function makeOrbDraggable(): void {
  const c = document.getElementById("orb-canvas") as HTMLCanvasElement | null;
  if (!c) return;
  let ox = 0, oy = 0, sx = 0, sy = 0, dragging = false;
  const h = document.createElement("div");
  h.id = "orb-drag-handle";
  h.title = "Glisser pour déplacer l'orbe · double-clic pour recentrer";
  h.textContent = "✥";
  h.style.cssText =
    "position:fixed;left:50%;top:50%;width:40px;height:40px;border-radius:50%;" +
    "border:1px dashed rgba(22,176,255,.45);cursor:grab;z-index:70;display:flex;" +
    "align-items:center;justify-content:center;color:rgba(22,176,255,.7);font-size:15px;" +
    "user-select:none;touch-action:none;background:rgba(6,18,32,.12);opacity:.55;transition:opacity .2s;";
  const apply = () => {
    c.style.transform = (ox || oy) ? `translate(${ox}px, ${oy}px)` : "";
    h.style.marginLeft = (-20 + ox) + "px";
    h.style.marginTop = (-20 + oy) + "px";
  };
  try { const s = localStorage.getItem("orb_pos"); if (s) { const p = JSON.parse(s); ox = p.x || 0; oy = p.y || 0; } } catch (e) {}
  document.body.appendChild(h);
  apply();
  h.addEventListener("mouseenter", () => { h.style.opacity = "1"; });
  h.addEventListener("mouseleave", () => { if (!dragging) h.style.opacity = ".55"; });
  h.addEventListener("pointerdown", (e: PointerEvent) => {
    dragging = true; sx = e.clientX - ox; sy = e.clientY - oy;
    h.style.cursor = "grabbing"; h.style.opacity = "1";
    try { h.setPointerCapture(e.pointerId); } catch (err) {}
    e.preventDefault();
  });
  h.addEventListener("pointermove", (e: PointerEvent) => {
    if (!dragging) return;
    ox = e.clientX - sx; oy = e.clientY - sy; apply();
  });
  const end = () => {
    if (!dragging) return;
    dragging = false; h.style.cursor = "grab";
    try { localStorage.setItem("orb_pos", JSON.stringify({ x: ox, y: oy })); } catch (e) {}
  };
  h.addEventListener("pointerup", end);
  h.addEventListener("pointercancel", end);
  h.addEventListener("dblclick", () => { ox = 0; oy = 0; apply(); try { localStorage.removeItem("orb_pos"); } catch (e) {} });
})();
