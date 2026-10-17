// ── Bascules systeme JARVIS (lot 1 de la migration) ──────────────────────
//
// Reprend fidelement le comportement de l'ancien frontend (frontend/src/main.ts) :
//   micro          -> {type:'toggle_mic'}            reponse mic_state {muted}
//   ASR Nemotron   -> {type:'toggle_nemotron_asr', enabled}
//                                                    reponse nemotron_asr_state
//                                                    {enabled, gpu_available, warnings[], error}
//   vider le cache -> {type:'clear_cache'}           reponse cache_cleared {success, message}
//   plein ecran    -> voir note ci-dessous
//
// PLEIN ECRAN — ecart assume et documente :
// cote JARVIS, toggle_fullscreen appelle _WEBVIEW_WINDOW.toggle_fullscreen(),
// donc il bascule la fenetre pywebview, c'est-a-dire l'ANCIEN frontend. Depuis
// le HUD (qui tourne dans Chrome), l'envoyer mettrait une autre fenetre en
// plein ecran : surprenant et inutile. Le HUD utilise donc l'API Fullscreen du
// navigateur, qui produit le resultat attendu par l'utilisateur. Les deux
// convergeront quand le HUD passera sous pywebview (etape prevue avant le
// lot 7) ; ce jour-la, basculer sur le message backend sera un one-liner.

import { showNotification } from './notifications.js';
import { appelerJarvis } from './appel-jarvis.js';

const etat = { micCoupe: false, asrActif: false };

// Delegue a appel-jarvis.js : copie unique, et c'est la qu'est gere le
// refus 428 (niveau d'autorisation depasse -> demande d'accord -> rejeu).
const envoyer = appelerJarvis;

function majBouton(btn, actif, texteActif, texteInactif) {
  if (!btn) return;
  btn.textContent = actif ? texteActif : texteInactif;
  btn.setAttribute('aria-pressed', String(actif));
  btn.style.border = `1px solid rgba(var(--accent-rgb), ${actif ? '0.8' : '0.3'})`;
  btn.style.background = actif ? 'rgba(var(--accent-rgb), 0.15)' : 'transparent';
}

function initMicro() {
  const btn = document.getElementById('toggle-mic-btn');
  if (!btn) return;
  btn.addEventListener('click', async () => {
    btn.disabled = true;
    try {
      const r = await envoyer('toggle_mic');
      etat.micCoupe = !!r.muted;
      majBouton(btn, etat.micCoupe, 'MIC COUPE', 'MIC ACTIF');
      showNotification(etat.micCoupe ? 'MICRO COUPE' : 'MICRO REACTIVE');
    } catch (e) {
      showNotification(`MIC : ${e.message}`);
    } finally {
      btn.disabled = false;
    }
  });
  majBouton(btn, false, 'MIC COUPE', 'MIC ACTIF');
}

function initAsr() {
  const btn = document.getElementById('toggle-asr-btn');
  if (!btn) return;
  btn.addEventListener('click', async () => {
    const voulu = !etat.asrActif;
    btn.disabled = true;
    if (voulu) btn.textContent = 'CHARGEMENT...';   // le modele met du temps
    try {
      const r = await envoyer('toggle_nemotron_asr', { enabled: voulu });
      etat.asrActif = !!r.enabled;
      majBouton(btn, etat.asrActif, 'ASR ACTIF', 'ASR INACTIF');
      // On remonte les avertissements et erreurs du backend tels quels :
      // ne pas les avaler, l'ancien front les affichait aussi.
      if (r.error) showNotification(`ASR : ${r.error}`);
      else if (r.warnings && r.warnings.length) showNotification(`ASR : ${r.warnings.join(' | ')}`);
      else showNotification(etat.asrActif ? 'NEMOTRON ASR ACTIVE' : 'NEMOTRON ASR DESACTIVE');
    } catch (e) {
      majBouton(btn, etat.asrActif, 'ASR ACTIF', 'ASR INACTIF');
      showNotification(`ASR : ${e.message}`);
    } finally {
      btn.disabled = false;
    }
  });
  majBouton(btn, false, 'ASR ACTIF', 'ASR INACTIF');
}

function initCache() {
  const btn = document.getElementById('clear-cache-jarvis-btn');
  if (!btn) return;
  btn.addEventListener('click', async () => {
    // Le backend reinitialise le marqueur de version et RECHARGE la fenetre
    // pywebview : effet visible cote ancien frontend. On previent.
    if (!window.confirm('Vider le cache JARVIS ?\n\nLa fenetre JARVIS (ancien frontend) sera rechargee.')) return;
    btn.disabled = true;
    try {
      const r = await envoyer('clear_cache');
      showNotification(r.success ? 'CACHE VIDE' : 'CACHE : ECHEC');
    } catch (e) {
      showNotification(`CACHE : ${e.message}`);
    } finally {
      btn.disabled = false;
    }
  });
}

function initPleinEcran() {
  const btn = document.getElementById('toggle-fullscreen-btn');
  if (!btn) return;
  const maj = () => majBouton(btn, !!document.fullscreenElement, 'QUITTER PLEIN ECRAN', 'PLEIN ECRAN');
  btn.addEventListener('click', async () => {
    try {
      if (document.fullscreenElement) await document.exitFullscreen();
      else await document.documentElement.requestFullscreen();
    } catch (e) {
      showNotification(`PLEIN ECRAN : ${e.message}`);
    }
  });
  document.addEventListener('fullscreenchange', maj);
  maj();
}

/** Etat initial du micro, lu depuis les reglages JARVIS. */
async function synchroniserEtat() {
  try {
    const r = await fetch('/api/jarvis/get_settings', { method: 'POST' });
    if (!r.ok) return;
    const d = await r.json();
    const reglages = d.data || {};
    if (typeof reglages.nemotron_asr_enabled === 'boolean') {
      etat.asrActif = reglages.nemotron_asr_enabled;
      majBouton(document.getElementById('toggle-asr-btn'), etat.asrActif, 'ASR ACTIF', 'ASR INACTIF');
    }
  } catch { /* JARVIS injoignable : on garde les valeurs par defaut */ }
}

export function initToggles() {
  initMicro();
  initAsr();
  initCache();
  initPleinEcran();
  synchroniserEtat();
}
