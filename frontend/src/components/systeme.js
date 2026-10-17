// ── Onglet SYSTEME : JARVIS OS, applications, navigateur ancre (lot 8) ───
//
// Trois vues, trois dependances externes bien distinctes — et chacune le DIT
// quand elle manque, au lieu d'afficher un panneau vide :
//
//   OS          conteneur Docker 'jarvis_os' sur le port 3000. Sans Docker,
//               rien de tout ca n'existe.
//   APPS        inventaire des applications installees (detect_apps).
//   NAVIGATEUR  fenetre Chrome pilotee par secure_browser.py, ancrable dans
//               la fenetre JARVIS via l'API Win32. Windows uniquement.
//
// Les actions lourdes passent par les niveaux d'autorisation : installer est
// en 7, desinstaller en 9. appel-jarvis.js gere le 428 et demande l'accord.

import { appelerJarvis } from './appel-jarvis.js';
import { showNotification } from './notifications.js';

function ech(s) {
  return String(s ?? '').replace(/[&<>"']/g, (c) => (
    { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
}

// ── JARVIS OS ────────────────────────────────────────────────────────────

function initOs(zone) {
  zone.innerHTML = `
    <div class="rg-note">Conteneur Docker <code>jarvis_os</code>, servi sur le
    port 3000. Exige Docker Desktop en fonctionnement.</div>
    <div class="sec-barre">
      <button class="btn sec-btn" id="os-etat-btn">VERIFIER L'ETAT</button>
      <button class="btn sec-btn" id="os-start">DEMARRER</button>
      <button class="btn sec-btn" id="os-stop">ARRETER</button>
      <button class="btn sec-btn" id="os-ouvrir">OUVRIR</button>
    </div>
    <div class="sec-etat" id="os-etat">etat inconnu</div>`;

  const etat = zone.querySelector('#os-etat');
  const dire = (t, classe = '') => { etat.textContent = t; etat.className = 'sec-etat ' + classe; };

  async function agir(type, texte, corps = {}) {
    dire(texte + '...');
    try {
      const r = await appelerJarvis(type, corps);
      return r;
    } catch (e) {
      // Un refus d'autorisation n'est pas une panne : on le distingue.
      dire(e.message, 'erreur');
      return null;
    }
  }

  zone.querySelector('#os-etat-btn').addEventListener('click', async () => {
    // check_jarvis_os_status DEMARRE le conteneur s'il est arrete : ce n'est
    // pas une simple lecture, d'ou le niveau 5 et l'avertissement ici.
    const r = await agir('check_jarvis_os_status', 'INTERROGATION DE DOCKER');
    if (!r) return;
    const installe = r.installed ?? r.installe;
    dire(installe ? `INSTALLE — port ${r.port || 3000}` : 'NON INSTALLE (ou Docker absent)',
         installe ? 'ok' : '');
  });

  zone.querySelector('#os-start').addEventListener('click', async () => {
    if (await agir('jarvis_os_start', 'DEMARRAGE DU CONTENEUR')) dire('DEMARRAGE DEMANDE', 'ok');
  });
  zone.querySelector('#os-stop').addEventListener('click', async () => {
    if (await agir('jarvis_os_stop', 'ARRET DU CONTENEUR')) dire('ARRET DEMANDE', 'ok');
  });
  zone.querySelector('#os-ouvrir').addEventListener('click', () => {
    window.open(`http://${location.hostname || 'localhost'}:3000`, '_blank', 'noopener');
  });
}

// ── Applications installees ──────────────────────────────────────────────

function initApps(zone) {
  zone.innerHTML = `
    <div class="sec-barre">
      <button class="btn sec-btn" id="ap-scan">INVENTORIER</button>
      <input class="rg-input sy-filtre" id="ap-filtre" placeholder="FILTRER..." />
    </div>
    <div class="sec-etat" id="ap-etat">non inventorie</div>
    <div id="ap-liste"></div>`;

  const etat = zone.querySelector('#ap-etat');
  const liste = zone.querySelector('#ap-liste');
  const filtre = zone.querySelector('#ap-filtre');
  let apps = [];

  // detect_apps renvoie des cles FRANCAISES ({nom, chemin}), verifie sur la
  // vraie sortie : 153 applications. Lire seulement `name` afficherait 153
  // lignes vides.
  const nomDe = (a) => (typeof a === 'string' ? a : (a.nom || a.name || ''));
  const detailDe = (a) => (typeof a === 'string' ? '' : (a.version || a.chemin || a.path || ''));

  function rendre() {
    const q = (filtre.value || '').toLowerCase();
    const vues = apps.filter((a) => !q || nomDe(a).toLowerCase().includes(q));
    liste.innerHTML = vues.slice(0, 200).map((a) => `
      <div class="sy-app" title="${ech(detailDe(a))}">
        <span class="sy-app-nom">${ech(nomDe(a))}</span>
        ${detailDe(a) ? `<span class="sy-app-ver">${ech(detailDe(a).split(/[\\/]/).pop())}</span>` : ''}
      </div>`).join('')
      + (vues.length > 200 ? `<div class="rg-note">... ${vues.length - 200} de plus</div>` : '');
  }

  filtre.addEventListener('input', rendre);
  zone.querySelector('#ap-scan').addEventListener('click', async () => {
    etat.textContent = 'INVENTAIRE EN COURS...';
    etat.className = 'sec-etat';
    try {
      const r = await appelerJarvis('detect_apps', {});
      apps = r.apps || r.applications || r.detected || [];
      etat.textContent = `${apps.length} application(s)`;
      etat.className = 'sec-etat ok';
      rendre();
    } catch (e) {
      etat.textContent = e.message;
      etat.className = 'sec-etat erreur';
    }
  });
}

// ── Navigateur ancre ─────────────────────────────────────────────────────

function initNavigateur(zone) {
  zone.innerHTML = `
    <div class="rg-note">Fenetre Chrome pilotee par JARVIS, ancrable dans la
    fenetre principale (API Win32 — Windows uniquement).</div>
    <div class="sec-barre">
      <input class="rg-input sy-url" id="nv-url" placeholder="RECHERCHE OU URL" />
      <button class="btn sec-btn" id="nv-ouvrir">OUVRIR</button>
    </div>
    <div class="sec-barre">
      <button class="btn sec-btn" id="nv-ancrer">ANCRER</button>
      <button class="btn sec-btn" id="nv-detacher">DETACHER</button>
      <button class="btn sec-btn" id="nv-fermer">FERMER</button>
    </div>
    <div class="sec-etat" id="nv-etat">aucune fenetre</div>`;

  const etat = zone.querySelector('#nv-etat');
  const agir = async (type, texte, corps = {}) => {
    etat.textContent = texte + '...';
    etat.className = 'sec-etat';
    try {
      await appelerJarvis(type, corps);
      etat.textContent = texte + ' — demande envoyee';
      etat.className = 'sec-etat ok';
    } catch (e) {
      etat.textContent = e.message;
      etat.className = 'sec-etat erreur';
    }
  };

  zone.querySelector('#nv-ouvrir').addEventListener('click', () => {
    const q = zone.querySelector('#nv-url').value.trim();
    if (!q) { etat.textContent = 'Saisis une recherche ou une URL.'; return; }
    agir('open_browser', 'OUVERTURE', { query: q });
  });
  zone.querySelector('#nv-ancrer').addEventListener('click', () => agir('dock_browser', 'ANCRAGE'));
  zone.querySelector('#nv-detacher').addEventListener('click', () => agir('undock_browser', 'DETACHEMENT'));
  zone.querySelector('#nv-fermer').addEventListener('click', () => agir('close_browser', 'FERMETURE'));
}

// ── Assemblage ───────────────────────────────────────────────────────────

const VUES = [
  ['os', 'JARVIS OS', initOs],
  ['apps', 'APPLICATIONS', initApps],
  ['navigateur', 'NAVIGATEUR', initNavigateur],
];

export function initSysteme() {
  const conteneur = document.getElementById('rtab-systeme');
  if (!conteneur) return;

  let dessine = false;
  document.querySelector('.tab-btn-r[data-rtab="systeme"]')?.addEventListener('click', () => {
    if (dessine) return;
    dessine = true;

    conteneur.innerHTML = `
      <div class="rg-onglets">
        ${VUES.map(([id, lib], i) =>
          `<button class="rg-onglet${i === 0 ? ' active' : ''}" data-s="${id}">${ech(lib)}</button>`
        ).join('')}
      </div>
      <div class="sec-corps" id="sy-corps"></div>`;

    const corps = conteneur.querySelector('#sy-corps');
    const montees = new Set();

    function afficher(id) {
      if (!montees.has(id)) {
        const z = document.createElement('div');
        z.dataset.s = id;
        corps.appendChild(z);
        montees.add(id);
        VUES.find((v) => v[0] === id)[2](z);
      }
      for (const enfant of corps.children) enfant.hidden = enfant.dataset.s !== id;
    }

    conteneur.querySelectorAll('.rg-onglet').forEach((b) => {
      b.addEventListener('click', () => {
        conteneur.querySelectorAll('.rg-onglet').forEach((x) => x.classList.remove('active'));
        b.classList.add('active');
        afficher(b.dataset.s);
      });
    });
    afficher('os');
  });
}
