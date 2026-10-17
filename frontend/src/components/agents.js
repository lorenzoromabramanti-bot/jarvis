// ── Onglet AGENTS : recensement des IA de la machine ─────────────────────
//
// Montre TOUS les agents IA présents, actifs ou éteints, regroupés par
// catégorie. Le fond de commerce du panneau, c'est l'honnêteté : un service
// éteint est affiché comme éteint, pas masqué. C'est même l'information la
// plus utile — c'est ainsi qu'on découvre qu'Ollama ne tourne pas alors que
// JARVIS est censé s'en servir.
//
// Rafraîchissement manuel. Le scan parcourt tous les processus de la machine
// et sonde six ports : le faire tourner en boucle coûterait cher pour une
// information qui bouge lentement.

import { appelerJarvis } from './appel-jarvis.js';

let agents = [];
let derniereMaj = null;

const TITRES = {
  jarvis: 'JARVIS',
  assistant: 'ASSISTANTS DE CODE',
  mcp: 'SERVEURS MCP',
  modele: 'MOTEURS DE MODELES',
};

function ech(s) {
  return String(s ?? '').replace(/[&<>"']/g, (c) => (
    { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
}

function rendreAgent(a) {
  const mesures = [
    a.processus ? `${a.processus} proc` : '',
    a.memoire_mo ? `${a.memoire_mo} Mo` : '',
    a.depuis ? `depuis ${a.depuis}` : '',
    a.port ? `:${a.port}` : '',
  ].filter(Boolean).join(' · ');

  return `<div class="ag-item ${a.actif ? 'ag-actif' : 'ag-eteint'}">
    <span class="ag-point"></span>
    <div class="ag-corps">
      <div class="ag-ligne">
        <span class="ag-nom">${ech(a.nom)}</span>
        <span class="ag-mesures">${ech(mesures)}</span>
      </div>
      ${a.detail ? `<div class="ag-detail">${ech(a.detail)}</div>` : ''}
    </div>
  </div>`;
}

function dessiner(conteneur) {
  const actifs = agents.filter((a) => a.actif).length;
  const eteints = agents.length - actifs;

  const categories = [...new Set(agents.map((a) => a.categorie))]
    .sort((x, y) => (Object.keys(TITRES).indexOf(x) - Object.keys(TITRES).indexOf(y)));

  conteneur.innerHTML = `
    <div class="ag-entete">
      <span class="ag-compteur">${actifs} ACTIF(S) · ${eteints} ETEINT(S)</span>
      <button class="btn ag-btn" id="ag-rescanner">RESCANNER</button>
    </div>
    ${derniereMaj ? `<div class="ag-maj">dernier scan : ${ech(derniereMaj)}</div>` : ''}
    ${categories.map((c) => `
      <div class="ag-section">${ech(TITRES[c] || c.toUpperCase())}</div>
      ${agents.filter((a) => a.categorie === c).map(rendreAgent).join('')}
    `).join('')}`;

  conteneur.querySelector('#ag-rescanner')?.addEventListener('click', () => charger(conteneur));
}

async function charger(conteneur) {
  conteneur.innerHTML = '<div class="ag-maj">SCAN DE LA MACHINE EN COURS...</div>';
  try {
    const r = await appelerJarvis('get_agents', {});
    agents = r.agents || [];
    derniereMaj = new Date().toLocaleTimeString('fr-FR');
  } catch (e) {
    conteneur.innerHTML = `<div class="ag-maj">SCAN INDISPONIBLE — ${ech(e.message)}</div>`;
    return;
  }
  dessiner(conteneur);
}

export function initAgents() {
  const conteneur = document.getElementById('rtab-agents');
  if (!conteneur) return;
  let charge = false;
  document.querySelector('.tab-btn-r[data-rtab="agents"]')
    ?.addEventListener('click', () => {
      if (charge) return;
      charge = true;
      charger(conteneur);
    });
}
