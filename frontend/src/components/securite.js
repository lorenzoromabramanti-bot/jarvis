// ── Securite systeme : antivirus, VPN, desinstalleur, Winget (lot 3) ─────
//
// Les quatre panneaux de l'ancien frontend qui declenchent des actions
// IRREVERSIBLES. Ils partagent le composant liste-actions : une action
// marquee danger:true y exige une confirmation explicite avant execution.
//
// Protocole repris de main2.py, sans rien inventer :
//   antivirus     av_scan_start / av_scan_cancel      -> flux av_start,
//                 av_progress, av_threat_detected, av_complete, av_cancel
//                 av_threat_action {action, threat}   -> av_action_result
//   VPN           vpn_get_countries -> vpn_countries
//                 vpn_get_status    -> vpn_status {status, ip_info}
//                 vpn_connect {country} / vpn_disconnect
//   desinstalleur get_installed_programs -> installed_programs
//                 uninstall_program {name, publisher, install_location,
//                 uninstall_string} -> flux uninstall_progress / _complete
//   winget        get_winget_upgrades -> winget_upgrades
//                 run_winget_upgrade {ids[], all} -> flux _progress

import { creerListeActions } from './liste-actions.js';
import { showNotification } from './notifications.js';
import { appelerJarvis } from './appel-jarvis.js';

// Delegue a appel-jarvis.js : copie unique, et c'est la qu'est gere le
// refus 428 (niveau d'autorisation depasse -> demande d'accord -> rejeu).
const appeler = appelerJarvis;

function ech(s) {
  return String(s ?? '').replace(/[&<>"']/g, (c) => (
    { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
}

// ── Antivirus ────────────────────────────────────────────────────────────

function initAntivirus(zone) {
  zone.innerHTML = `
    <div class="sec-barre">
      <button class="btn sec-btn" id="av-scan">LANCER UN SCAN</button>
      <button class="btn sec-btn" id="av-annuler" disabled>ANNULER</button>
    </div>
    <div class="sec-progression"><div class="sec-progression-barre" id="av-barre"></div></div>
    <div class="sec-etat" id="av-etat">PRET</div>
    <div id="av-menaces"></div>`;

  const btnScan = zone.querySelector('#av-scan');
  const btnAnnuler = zone.querySelector('#av-annuler');
  const barre = zone.querySelector('#av-barre');
  const etat = zone.querySelector('#av-etat');
  const zoneMenaces = zone.querySelector('#av-menaces');
  let menaces = [];

  const liste = creerListeActions(zoneMenaces, {
    chargement: async () => menaces,
    selectionMultiple: false,
    messageVide: 'AUCUNE MENACE DETECTEE',
    actions: [
      { nom: 'AUTORISER', executer: (sel) => agir('allow', sel) },
      { nom: 'METTRE EN QUARANTAINE', danger: true, executer: (sel) => agir('quarantine', sel) },
      { nom: 'SUPPRIMER', danger: true, executer: (sel) => agir('delete', sel) },
    ],
  });

  async function agir(action, selection) {
    for (const el of selection) {
      const r = await appeler('av_threat_action', { action, threat: el.brut });
      showNotification(`${action.toUpperCase()} : ${r.message || 'effectue'}`);
      menaces = menaces.filter((m) => m.id !== el.id);
    }
  }

  btnScan.addEventListener('click', async () => {
    menaces = [];
    await liste.recharger();
    btnScan.disabled = true; btnAnnuler.disabled = false;
    etat.textContent = 'DEMARRAGE...';
    try { await appeler('av_scan_start'); }
    catch (e) { etat.textContent = `ECHEC : ${e.message}`; btnScan.disabled = false; btnAnnuler.disabled = true; }
  });

  btnAnnuler.addEventListener('click', async () => {
    try { await appeler('av_scan_cancel'); } catch { /* le flux tranchera */ }
  });

  // Flux pousse par JARVIS pendant le scan
  window.addEventListener('jarvis-event', (e) => {
    const ev = e.detail || {};
    switch (ev.type) {
      case 'av_start':
        etat.textContent = 'SCAN EN COURS...'; barre.style.width = '0%'; break;
      case 'av_progress': {
        const pct = typeof ev.percent === 'number' ? ev.percent
                  : (ev.total ? Math.round((ev.current / ev.total) * 100) : null);
        if (pct !== null) barre.style.width = `${pct}%`;
        etat.textContent = ev.message || ev.current_file || 'SCAN EN COURS...';
        break;
      }
      case 'av_threat_detected': {
        const t = ev.threat || {};
        menaces.push({
          id: `${t.type || 'x'}:${t.target || t.name || menaces.length}`,
          titre: t.name || t.target || 'MENACE',
          sousTitre: t.class || '',
          meta: t.target || '',
          brut: t,
        });
        liste.recharger();
        break;
      }
      case 'av_complete':
        etat.textContent = `SCAN TERMINE — ${menaces.length} menace(s)`;
        barre.style.width = '100%';
        btnScan.disabled = false; btnAnnuler.disabled = true;
        break;
      case 'av_cancel':
        etat.textContent = 'SCAN ANNULE';
        btnScan.disabled = false; btnAnnuler.disabled = true;
        break;
    }
  });

  liste.recharger();
}

// ── VPN ──────────────────────────────────────────────────────────────────

function initVpn(zone) {
  zone.innerHTML = `
    <div class="sec-etat" id="vpn-etat">CHARGEMENT...</div>
    <div id="vpn-pays"></div>`;
  const etat = zone.querySelector('#vpn-etat');
  let pays = [];

  const liste = creerListeActions(zone.querySelector('#vpn-pays'), {
    chargement: async () => {
      if (!pays.length) {
        const r = await appeler('vpn_get_countries');
        // Forme reelle verifiee contre JARVIS : un TABLEAU d'objets
        // {code, name, count}, pas un dictionnaire. On tolere les deux.
        const brut = r.countries || [];
        const entrees = Array.isArray(brut)
          ? brut.map((c) => (typeof c === 'string' ? { code: c, name: c } : c))
          : Object.entries(brut).map(([code, info]) => ({
              code, name: (typeof info === 'string' ? info : info?.name) || code }));
        pays = entrees.map((c) => ({
          id: c.code,
          titre: c.name || c.code,
          sousTitre: c.code,
          meta: c.count ? `${c.count} serveur(s)` : '',
          brut: c.code,
        }));
      }
      return pays;
    },
    selectionMultiple: false,
    messageVide: 'AUCUN PAYS DISPONIBLE',
    actions: [
      // danger:true -> confirmation. Se connecter change la route reseau
      // de la machine : c'est une action a effet global, pas un reglage.
      { nom: 'CONNECTER', danger: true, executer: async (sel) => {
          if (!sel.length) return;
          etat.textContent = `CONNEXION A ${sel[0].titre}...`;
          const r = await appeler('vpn_connect', { country: sel[0].brut });
          etat.textContent = JSON.stringify(r.result ?? r).slice(0, 120);
          rafraichirEtat();
        } },
      { nom: 'DECONNECTER', danger: true, exigeSelection: false, executer: async () => {
          etat.textContent = 'DECONNEXION...';
          const r = await appeler('vpn_disconnect');
          etat.textContent = JSON.stringify(r.result ?? r).slice(0, 120);
          rafraichirEtat();
        } },
    ],
  });

  async function rafraichirEtat() {
    try {
      const r = await appeler('vpn_get_status');
      const s = r.status || {};
      const ip = r.ip_info || {};
      etat.textContent = `${s.connected ? 'CONNECTE' : 'DECONNECTE'}`
        + (s.status ? ` · ${s.status}` : '')
        + (ip.ip ? ` · IP ${ip.ip}` : '')
        + (ip.country ? ` (${ip.country})` : '');
      etat.className = `sec-etat ${s.connected ? 'ok' : ''}`;
    } catch (e) {
      // Le NameError historique sur ip_info est corrige cote main2.py
      // (variable jamais definie -> aucune reponse, 45s d'attente puis
      // echec). Ce qui reste ici couvre les vraies pannes : JARVIS eteint,
      // PowerShell qui ne rend pas la main, VPN absent de la machine.
      etat.textContent = `ETAT VPN INDISPONIBLE — ${e.message}`;
      etat.className = 'sec-etat erreur';
    }
  }

  rafraichirEtat();
  liste.recharger();
}

// ── Desinstalleur ────────────────────────────────────────────────────────

function initDesinstalleur(zone) {
  zone.innerHTML = `<div class="sec-etat" id="des-etat">—</div><div id="des-liste"></div>`;
  const etat = zone.querySelector('#des-etat');

  const liste = creerListeActions(zone.querySelector('#des-liste'), {
    chargement: async () => {
      etat.textContent = 'LECTURE DU REGISTRE...';
      const r = await appeler('get_installed_programs');
      const progs = r.programs || [];
      etat.textContent = `${progs.length} PROGRAMME(S)`;
      return progs.map((p, i) => ({
        id: `${p.name}|${i}`,
        titre: p.name || '(sans nom)',
        sousTitre: p.publisher || '',
        meta: p.version || '',
        brut: p,
      }));
    },
    selectionMultiple: false,
    messageVide: 'AUCUN PROGRAMME',
    actions: [
      { nom: 'DESINSTALLER', danger: true, executer: async (sel, progresser) => {
          const p = sel[0].brut;
          progresser(`DESINSTALLATION DE ${p.name}...`, 10);
          await appeler('uninstall_program', {
            name: p.name, publisher: p.publisher,
            install_location: p.install_location,
            uninstall_string: p.uninstall_string,
          });
          progresser('DEMANDE ENVOYEE — SUIVI CI-DESSOUS', 30);
        } },
    ],
  });

  window.addEventListener('jarvis-event', (e) => {
    const ev = e.detail || {};
    if (ev.type === 'uninstall_progress') {
      etat.textContent = ev.message || ev.step || 'DESINSTALLATION...';
    } else if (ev.type === 'uninstall_complete') {
      etat.textContent = ev.message || 'DESINSTALLATION TERMINEE';
      showNotification('DESINSTALLATION TERMINEE');
      liste.recharger();
    }
  });

  liste.recharger();
}

// ── Winget ───────────────────────────────────────────────────────────────

function initWinget(zone) {
  zone.innerHTML = `<div class="sec-etat" id="wg-etat">—</div><div id="wg-liste"></div>`;
  const etat = zone.querySelector('#wg-etat');

  const liste = creerListeActions(zone.querySelector('#wg-liste'), {
    chargement: async () => {
      etat.textContent = 'RECHERCHE DES MISES A JOUR...';
      const r = await appeler('get_winget_upgrades');
      const maj = r.upgrades || r.packages || [];
      // Un resultat vide n'est PAS une preuve que le systeme est a jour :
      // verifie le 2026-08-11, le parseur de main2.py renvoie 0 alors que
      // `winget upgrade` en annonce 50. On ne conclut donc jamais "a jour",
      // on dit exactement ce qu'on sait.
      etat.textContent = maj.length
        ? `${maj.length} MISE(S) A JOUR`
        : 'AUCUNE MISE A JOUR REMONTEE PAR JARVIS (verifier avec `winget upgrade`)';
      return maj.map((p, i) => ({
        id: p.id || `pkg-${i}`,
        titre: p.name || p.id || '(inconnu)',
        sousTitre: p.id || '',
        meta: `${p.version || '?'} -> ${p.available || p.new_version || '?'}`,
        brut: p,
      }));
    },
    selectionMultiple: true,
    messageVide: 'AUCUNE REMONTEE - RESULTAT NON FIABLE, VOIR ETAT CI-DESSUS',
    actions: [
      { nom: 'METTRE A JOUR LA SELECTION', danger: true, executer: async (sel, progresser) => {
          const ids = sel.map((e) => e.brut.id).filter(Boolean);
          if (!ids.length) throw new Error('aucun identifiant de paquet');
          progresser(`MISE A JOUR DE ${ids.length} PAQUET(S)...`, 10);
          await appeler('run_winget_upgrade', { ids });
        } },
    ],
  });

  window.addEventListener('jarvis-event', (e) => {
    const ev = e.detail || {};
    if (ev.type === 'winget_upgrade_progress') {
      etat.textContent = (ev.message || ev.line || '').slice(0, 140);
      if (ev.done) { showNotification('WINGET TERMINE'); liste.recharger(); }
    }
  });

  liste.recharger();
}

// ── Assemblage ───────────────────────────────────────────────────────────

const VUES = [
  ['antivirus', 'ANTIVIRUS', initAntivirus],
  ['vpn', 'VPN', initVpn],
  ['desinstalleur', 'DESINSTALLEUR', initDesinstalleur],
  ['winget', 'MISES A JOUR', initWinget],
];

export function initSecurite() {
  const conteneur = document.getElementById('rtab-security');
  if (!conteneur) return;

  conteneur.innerHTML = `
    <div class="rg-onglets">
      ${VUES.map(([id, libelle], i) =>
        `<button class="rg-onglet${i === 0 ? ' active' : ''}" data-sec="${id}">${ech(libelle)}</button>`
      ).join('')}
    </div>
    <div class="sec-corps" id="sec-corps"></div>`;

  const corps = conteneur.querySelector('#sec-corps');
  const montees = new Set();

  function afficher(id) {
    // Chaque vue n'est montee qu'a la premiere ouverture : eviter de
    // relancer un scan ou de relire le registre a chaque changement
    // d'onglet, ces operations sont couteuses.
    for (const enfant of corps.children) enfant.hidden = enfant.dataset.sec !== id;
    if (montees.has(id)) return;
    const zone = document.createElement('div');
    zone.dataset.sec = id;
    corps.appendChild(zone);
    montees.add(id);
    const vue = VUES.find((v) => v[0] === id);
    try { vue[2](zone); } catch (e) {
      zone.innerHTML = `<div class="rg-note erreur">${ech(e.message)}</div>`;
    }
    for (const enfant of corps.children) enfant.hidden = enfant.dataset.sec !== id;
  }

  conteneur.querySelectorAll('.rg-onglet').forEach((b) => {
    b.addEventListener('click', () => {
      conteneur.querySelectorAll('.rg-onglet').forEach((x) => x.classList.remove('active'));
      b.classList.add('active');
      afficher(b.dataset.sec);
    });
  });

  afficher('antivirus');
}
