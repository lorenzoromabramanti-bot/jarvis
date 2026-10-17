// ── Home Assistant + meteo (lot 4) ───────────────────────────────────────
//
// Reprend ha_dashboard.ts de l'ancien frontend (741 lignes) : memes
// categories, memes services appeles, memes regroupements.
//
// Protocole (ha_config.handle_ha_ws_message) :
//   ha_get_states    -> ha_states {success, states[]}
//   ha_call_service {domain, service, entity_id, service_data}
//                    -> ha_service_result {success, entity_id, state}
//                    + diffusion ha_state_changed a tous les clients
//
// Les etats HA sont bruts (format API Home Assistant) :
//   { entity_id, state, attributes: { friendly_name, unit_of_measurement, ... } }
//
// SECURITE : l'adaptateur borne les services appelables (SERVICES_HA_AUTORISES).
// Les domaines sensibles — serrures, alarme, scripts, automatisations — ne
// sont volontairement PAS ouverts. Ce panneau ne peut donc pas deverrouiller
// une porte, meme si l'entite apparait dans la liste : elle sera affichee en
// lecture seule.

import { showNotification } from './notifications.js';
import { appelerJarvis } from './appel-jarvis.js';

const CATEGORIES = [
  ['light', 'LUMIERES'],
  ['switch', 'INTERRUPTEURS'],
  ['fan', 'VENTILATION'],
  ['vacuum', 'ASPIRATEURS'],
  ['sensor', 'CAPTEURS'],
  ['other', 'AUTRES'],
];

// Miroir cote client de la liste blanche du serveur : sert uniquement a
// savoir s'il faut afficher un interrupteur ou une valeur en lecture seule.
// Le refus fait autorite cote serveur, pas ici.
const PILOTABLE = {
  light: ['turn_on', 'turn_off'],
  switch: ['turn_on', 'turn_off'],
  input_boolean: ['turn_on', 'turn_off'],
  valve: ['open_valve', 'close_valve'],
  fan: ['turn_on', 'turn_off'],
  vacuum: ['start', 'pause', 'stop', 'return_to_base', 'locate'],
};

let etats = [];
let filtre = '';

function ech(s) {
  return String(s ?? '').replace(/[&<>"']/g, (c) => (
    { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
}

// Delegue a appel-jarvis.js : copie unique, et c'est la qu'est gere le
// refus 428 (niveau d'autorisation depasse -> demande d'accord -> rejeu).
const appeler = appelerJarvis;

function domaineDe(entiteId) { return String(entiteId || '').split('.')[0]; }

/** Meme regroupement que getDomainCategory() de l'ancien dashboard. */
function categorieDe(entiteId) {
  const d = domaineDe(entiteId);
  if (d === 'light') return 'light';
  if (d === 'switch' || d === 'input_boolean' || d === 'valve') return 'switch';
  if (d === 'sensor' || d === 'binary_sensor' || d === 'climate') return 'sensor';
  if (d === 'fan') return 'fan';
  if (d === 'vacuum') return 'vacuum';
  return 'other';
}

function nomLisible(e) {
  return e.attributes?.friendly_name || e.entity_id;
}

function etatLisible(e) {
  const unite = e.attributes?.unit_of_measurement;
  if (unite) return `${e.state} ${unite}`;
  return { on: 'ALLUME', off: 'ETEINT', unavailable: 'INDISPONIBLE',
           unknown: 'INCONNU', home: 'PRESENT', not_home: 'ABSENT' }[e.state] || e.state;
}

function estAllume(e) {
  return ['on', 'open', 'cleaning', 'home'].includes(String(e.state));
}

// ── Rendu ────────────────────────────────────────────────────────────────

function carte(e) {
  const dom = domaineDe(e.entity_id);
  const pilotable = !!PILOTABLE[dom] && e.state !== 'unavailable';
  const allume = estAllume(e);

  let controle = `<span class="ha-valeur">${ech(etatLisible(e))}</span>`;
  if (pilotable && dom === 'vacuum') {
    controle = ['start', 'pause', 'return_to_base'].map((a) =>
      `<button class="ha-btn" data-entite="${ech(e.entity_id)}" data-domaine="vacuum"
        data-service="${a}">${a === 'return_to_base' ? 'BASE' : a.toUpperCase()}</button>`
    ).join('');
  } else if (pilotable) {
    const on = dom === 'valve' ? 'open_valve' : 'turn_on';
    const off = dom === 'valve' ? 'close_valve' : 'turn_off';
    controle = `<button class="ha-bascule${allume ? ' active' : ''}"
      data-entite="${ech(e.entity_id)}" data-domaine="${ech(dom)}"
      data-service="${allume ? off : on}">${allume ? 'ON' : 'OFF'}</button>`;
  }

  return `<div class="ha-carte${allume ? ' allumee' : ''}" data-id="${ech(e.entity_id)}">
    <div class="ha-nom">${ech(nomLisible(e))}</div>
    <div class="ha-bas">
      <span class="ha-id">${ech(e.entity_id)}</span>
      ${controle}
    </div>
  </div>`;
}

function dessiner(zone) {
  const q = filtre.toLowerCase();
  const visibles = etats.filter((e) =>
    !q || nomLisible(e).toLowerCase().includes(q) || e.entity_id.toLowerCase().includes(q));

  const sections = CATEGORIES.map(([cle, libelle]) => {
    const lot = visibles.filter((e) => categorieDe(e.entity_id) === cle);
    if (!lot.length) return '';
    return `<div class="ha-section">${ech(libelle)} <span class="ha-compte">${lot.length}</span></div>
            <div class="ha-grille">${lot.map(carte).join('')}</div>`;
  }).join('');

  zone.querySelector('#ha-corps').innerHTML =
    sections || '<div class="rg-note">AUCUNE ENTITE</div>';

  zone.querySelectorAll('.ha-bascule, .ha-btn').forEach((b) => {
    b.addEventListener('click', () => agir(zone, b));
  });
}

async function agir(zone, bouton) {
  const entity_id = bouton.dataset.entite;
  const domain = bouton.dataset.domaine;
  const service = bouton.dataset.service;
  bouton.disabled = true;
  try {
    const r = await appeler('ha_call_service', { domain, service, entity_id });
    if (r.success === false) {
      showNotification(`HA : ${entity_id} a refuse`);
    } else if (r.state) {
      // On applique l'etat REEL renvoye par Home Assistant, jamais l'etat
      // qu'on a demande : si la lampe n'a pas repondu, l'interface ne doit
      // pas afficher "allumee".
      const i = etats.findIndex((e) => e.entity_id === entity_id);
      if (i >= 0) etats[i] = r.state;
      dessiner(zone);
    }
  } catch (e) {
    showNotification(`HA : ${e.message}`);
    zone.querySelector('#ha-etat').textContent = e.message;
  } finally {
    bouton.disabled = false;
  }
}

async function charger(zone) {
  const etat = zone.querySelector('#ha-etat');
  etat.textContent = 'INTERROGATION DE HOME ASSISTANT...';
  try {
    const r = await appeler('ha_get_states');
    etats = r.states || [];
    if (!r.success && !etats.length) {
      etat.textContent = 'HOME ASSISTANT INJOIGNABLE (verifier HA_URL / HA_TOKEN)';
      etat.className = 'sec-etat erreur';
      zone.querySelector('#ha-corps').innerHTML = '';
      return;
    }
    etat.textContent = `${etats.length} ENTITE(S)`;
    etat.className = 'sec-etat';
    dessiner(zone);
  } catch (e) {
    etat.textContent = `ECHEC : ${e.message}`;
    etat.className = 'sec-etat erreur';
  }
}

export function initDomotique() {
  const zone = document.getElementById('rtab-home');
  if (!zone) return;

  zone.innerHTML = `
    <div class="sec-barre">
      <input class="rg-input ha-recherche" id="ha-recherche" type="text"
             placeholder="FILTRER..." autocomplete="off" />
      <button class="btn sec-btn" id="ha-recharger">RAFRAICHIR</button>
    </div>
    <div class="sec-etat" id="ha-etat">—</div>
    <div id="ha-corps"></div>`;

  zone.querySelector('#ha-recharger').addEventListener('click', () => charger(zone));
  zone.querySelector('#ha-recherche').addEventListener('input', (e) => {
    filtre = e.target.value;
    dessiner(zone);
  });

  // Un changement declenche ailleurs (voix, autre client, automatisation HA)
  // est diffuse par JARVIS : on garde l'affichage synchronise.
  window.addEventListener('jarvis-event', (e) => {
    const ev = e.detail || {};
    if (ev.type !== 'ha_state_changed' || !ev.state) return;
    const i = etats.findIndex((x) => x.entity_id === ev.entity_id);
    if (i >= 0) { etats[i] = ev.state; dessiner(zone); }
  });

  charger(zone);
}
