// ── OpenClaw JARVIS UI — 主入口 ──

// 設定載入（最先）
import { loadConfig } from './config/config-loader.js';
import { initTheme } from './config/theme.js';

// 核心
import { initScene, animateScene, onWindowResize, setDistortion, setResolution, resetAnomaly, getOrbScreenPosition } from './core/scene.js';
// core/audio.js supprime avec le panneau AUDIO : il n'ouvrait un AudioContext
// que pour le visualiseur de musique d'OpenClaw, sans jamais aucune source.
import { initFloatingParticles } from './core/particles.js';

// 元件
import { initChat, updateUserActivity } from './components/chat.js';
import { showNotification } from './components/notifications.js';
import { initSystemMonitor } from './components/system-monitor.js';
import { initTabs } from './components/tabs.js';
import { initTasks } from './components/tasks.js';
import { initSkills } from './components/skills.js';
import { initMemory } from './components/memory.js';
import { initSchedule } from './components/schedule.js';
import { initControls, setCallbacks, getAudioReactivity, getAudioSensitivity } from './components/controls.js';
import { drawCircularVisualizer, initVisualizers, resizeAllCanvases } from './components/spectrum.js';
import { setupPreloader } from './components/preloader.js';
import { initDraggablePanels } from './components/draggable.js';
import { initTimestamp } from './components/timestamp.js';
import { initOrbMessages } from './components/orb-messages.js';
// thought-stream : retiré — texte purement décoratif d'OpenClaw (30 fausses
// « pensées » en chinois et en anglais). Le fichier reste sur disque.
import { initMobileToolbar } from './components/mobile-toolbar.js';
import { initPowerSave, isPowerSave } from './components/powersave.js';
import { initDefenseConsole } from './components/defense-console.js';
import { initToggles } from './components/toggles.js';
import { initReglages } from './components/reglages.js';
import { initSecurite } from './components/securite.js';
import { initDomotique } from './components/domotique.js';
import { initQuotidien } from './components/quotidien.js';
import { initMedia } from './components/media.js';
import { initAutoAmelioration } from './components/auto-amelioration.js';
import { initAgents } from './components/agents.js';
import { initCapture } from './components/capture.js';
import { initSysteme } from './components/systeme.js';

// Spectre nul figé : même longueur que l'ancien frequencyBinCount (fftSize
// 2048 / 2). Alimente les anneaux de l'orbe depuis la suppression du panneau
// AUDIO. Alloué une fois, jamais réécrit.
const SPECTRE_NUL = new Uint8Array(1024);

document.addEventListener('DOMContentLoaded', async function () {
  // 載入設定
  const config = await loadConfig();
  
  // 初始化主題系統（最早執行，確保 CSS 變數正確）
  initTheme();

  // 動態更新 HTML 中的個人化文字
  document.title = config.name || 'JARVIS';
  const agentName = config.agent?.name || 'JARVIS';
  const chatLabel = document.querySelector('.terminal-panel.chat-panel .terminal-header span');
  if (chatLabel) chatLabel.textContent = `${agentName} CHAT`;

  // 設定 agent prefix CSS 變數
  const emoji = config.agent?.emoji || '⚡';
  document.documentElement.style.setProperty('--agent-prefix', `"${agentName} ${emoji} "`);

  // 載入畫面
  setupPreloader();

  // 元件初始化
  initChat();
  initTabs();
  initTasks();
  initSkills();
  initMemory();
  initSchedule();
  initControls();
  initPowerSave();
  initDefenseConsole();
  initToggles();
  initReglages();
  initSecurite();
  initDomotique();
  initQuotidien();
  initMedia();
  initAutoAmelioration();
  initAgents();
  initCapture();
  initSysteme();
  initSystemMonitor();
  initVisualizers();
  initTimestamp();

  // 控制滑桿回呼（連結場景）
  setCallbacks({
    onDistortion: setDistortion,
    onResolution: setResolution,
  });

  // Orb 狀態文字（agent-state → #orb-status）
  const orbStatus = document.getElementById('orb-status');
  if (orbStatus) {
    const labels = { idle: 'IDLE · EN VEILLE', thinking: 'THINKING · REFLEXION...', responding: 'RESPONDING · REPONSE...' };
    window.addEventListener('agent-state', (e) => {
      orbStatus.textContent = labels[e.detail] || e.detail.toUpperCase();
      orbStatus.className = 'scanner-id state-' + (e.detail || 'idle');

      // 狀態視覺回饋：掃描線速度 + 粒子活躍度
      const scannerLine = document.querySelector('.scanner-line');
      const scannerFrame = document.querySelector('.scanner-frame');
      if (scannerLine) {
        switch (e.detail) {
          case 'thinking':
            scannerLine.style.animationDuration = '1.5s';
            scannerFrame?.classList.add('state-active');
            break;
          case 'responding':
            scannerLine.style.animationDuration = '2.5s';
            scannerFrame?.classList.add('state-active');
            break;
          default:
            scannerLine.style.animationDuration = '4s';
            scannerFrame?.classList.remove('state-active');
        }
      }
    });
  }

  // Meta sous l'orbe : neutralisé.
  //
  // Affichait « WHATSAPP · N MSGS ». Les deux moitiés étaient fausses :
  //   - le canal venait de ~/.openclaw/openclaw.json, où OpenClaw déclare
  //     whatsapp/discord. JARVIS n'a aucun canal de messagerie de ce type.
  //   - le compteur s'incrémentait à chaque événement 'thinking', qui peut
  //     survenir plusieurs fois par échange — d'où une valeur qui n'avait
  //     aucun rapport avec un nombre de messages.
  // Rebrancher ici le jour où une vraie métrique JARVIS mérite cette place.
  const orbMeta = document.getElementById('orb-meta');
  if (orbMeta) orbMeta.textContent = '';

  // 使用者活動追蹤
  document.addEventListener('mousemove', updateUserActivity);
  document.addEventListener('keydown', updateUserActivity);

  // 載入完成後啟動
  const loadingOverlay = document.getElementById('loading-overlay');
  setTimeout(() => {
    loadingOverlay.style.opacity = 0;
    setTimeout(() => {
      loadingOverlay.style.display = 'none';
      initFloatingParticles();
      initDraggablePanels();
      initOrbMessages(getOrbScreenPosition);
      initMobileToolbar();
    }, 500);
  }, 3000);

  // Three.js 場景
  initScene();
  
  // 暴露 resetAnomaly 供 Controls 使用
  window.__jarvisResetAnomaly = resetAnomaly;
  
  // 重新觸發主題，確保 Three.js 顏色同步
  initTheme();

  // 視窗大小變更
  window.addEventListener('resize', () => {
    onWindowResize(resizeAllCanvases);
  });

  // 主動畫循環
  let lastFrameTime = 0;
  function animate(now) {
    requestAnimationFrame(animate);

    // 頁面隱藏時完全暫停
    if (window.__jarvisHiddenPause?.()) return;

    // 省電模式：限制 15fps
    if (isPowerSave()) {
      if (now - lastFrameTime < 66) return; // ~15fps
      lastFrameTime = now;
    }

    const audioSensitivity = getAudioSensitivity();
    const audioReactivity = getAudioReactivity();

    // Anneaux autour de l'orbe. Ils étaient dessinés à partir de l'analyseur
    // audio ; celui-ci n'ayant jamais eu de source, ils traçaient déjà des
    // cercles parfaits. Le spectre nul assumé donne exactement le même rendu,
    // sans AudioContext.
    if (!isPowerSave()) {
      drawCircularVisualizer(SPECTRE_NUL, audioSensitivity, audioReactivity);
    }

    // 3D 場景
    const rotationSpeed = parseFloat(document.getElementById('rotation-slider')?.value || 1);
    animateScene(0, rotationSpeed, audioReactivity);
  }
  animate(0);

  // 1. 頁面切背景自動暫停渲染
  let hiddenPause = false;
  document.addEventListener('visibilitychange', () => {
    hiddenPause = document.hidden;
  });
  // 暴露給 animate loop
  window.__jarvisHiddenPause = () => hiddenPause;
});

// PWA Service Worker 註冊
if ('serviceWorker' in navigator) {
  navigator.serviceWorker.register('/sw.js').catch(() => {});
}
