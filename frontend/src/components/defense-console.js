// ── Console défense + bandeau statut + pastilles (donnees reelles) ──
//
// N'apparait QUE sur un vrai evenement de securite JARVIS
// (av_live_threat_intercepted, antivirus_scanner.py -> main2.py -> gateway.js
// -> broadcastEvent('av-threat', ...)). Rien de simule ici.
//
// NEURAL LINK ACTIVE reflete la vraie connexion HUD<->JARVIS (poll /api/status).
// CORE STABLE / ALL SYSTEMS NORMAL basculent uniquement pendant une menace active.
// ENCRYPTION AES-256 et PROTOCOL // SENTINEL n'ont pas d'equivalent cote JARVIS :
// affichage statique assume (voir .status-pill.static), pas invente comme reel.

const DUREE_AFFICHAGE_MS = 15000;

const consoleEl = document.getElementById('defense-console');
const bodyEl = document.getElementById('defense-console-body');
const topStatusEl = document.getElementById('top-status');
const pillNeural = document.getElementById('pill-neural');
const pillCore = document.getElementById('pill-core');
const pillSystems = document.getElementById('pill-systems');

let masquageTimer = null;
let menaceActive = false;
let dernierEtatAgent = 'idle';

function ligne(texte) {
  const l = document.createElement('div');
  l.className = 'dc-line';
  l.textContent = texte;
  return l;
}

function afficherMenace(detail) {
  const threat = detail.threat || {};
  menaceActive = true;
  clearTimeout(masquageTimer);

  bodyEl.innerHTML = '';
  bodyEl.appendChild(ligne(`JARVIS> Live-protection triggered`));
  bodyEl.appendChild(ligne(`>> target: ${threat.target || threat.name || 'unknown'}`));
  if (threat.class) bodyEl.appendChild(ligne(`>> class: ${threat.class}`));
  bodyEl.appendChild(ligne(`>> ${threat.desc || 'Threat intercepted.'}`));
  if (detail.quarantineFile) bodyEl.appendChild(ligne(`>> quarantine: ${detail.quarantineFile}`));

  consoleEl.hidden = false;
  requestAnimationFrame(() => consoleEl.classList.add('visible'));

  pillCore?.classList.add('warn');
  pillSystems?.classList.add('warn');
  majStatut();

  masquageTimer = setTimeout(() => {
    consoleEl.classList.remove('visible');
    setTimeout(() => { consoleEl.hidden = true; }, 400);
    pillCore?.classList.remove('warn');
    pillSystems?.classList.remove('warn');
    menaceActive = false;
    majStatut();
  }, DUREE_AFFICHAGE_MS);
}

function majStatut() {
  if (!topStatusEl) return;
  topStatusEl.classList.remove('status-busy', 'status-defense');
  if (menaceActive) {
    topStatusEl.textContent = 'DEFENSE MODE';
    topStatusEl.classList.add('status-defense');
    return;
  }
  if (dernierEtatAgent === 'idle') {
    topStatusEl.textContent = 'ONLINE';
  } else {
    topStatusEl.textContent = 'BUSY';
    topStatusEl.classList.add('status-busy');
  }
}

// NEURAL LINK = les DEUX conditions reunies :
//   - JARVIS repond derriere l'adaptateur (/api/status -> gateway)
//   - le flux SSE arrive reellement (chien de garde de chat.js)
// Se fier au seul /api/status etait trompeur : un fetch reussit encore alors
// que le SSE est mort, donc la pastille restait verte pendant que le HUD ne
// recevait plus rien. Constate en vrai lors du test du lot 0.
let jarvisJoignable = false;
let fluxVivant = true;   // optimiste au demarrage, le 1er cycle tranche

function majNeural() {
  pillNeural?.classList.toggle('warn', !(jarvisJoignable && fluxVivant));
}

async function pollConnexion() {
  try {
    const r = await fetch('/api/status');
    const d = await r.json();
    jarvisJoignable = !!d.gateway;
  } catch {
    jarvisJoignable = false;
  }
  majNeural();
}

export function initDefenseConsole() {
  if (!consoleEl || !bodyEl) return;

  window.addEventListener('av-threat', (e) => afficherMenace(e.detail || {}));

  // Reutilise l'evenement 'agent-state' deja emis par chat.js (idle / thinking
  // / responding) pour le mot ONLINE/BUSY du bandeau — pas de 2e source d'etat.
  window.addEventListener('agent-state', (e) => {
    dernierEtatAgent = e.detail || 'idle';
    if (!menaceActive) majStatut();
  });

  // Sante du flux SSE, emise par le chien de garde de chat.js
  window.addEventListener('sse-health', (e) => {
    fluxVivant = !!(e.detail && e.detail.vivant);
    majNeural();
  });

  pollConnexion();
  setInterval(pollConnexion, 5000);
}
