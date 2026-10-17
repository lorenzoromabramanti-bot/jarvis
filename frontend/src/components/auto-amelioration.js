// ── Onglet JARVIS : auto-diagnostic et propositions ──────────────────────
//
// Deux moities :
//   ETAT        ce que JARVIS constate sur lui-meme (modele ecarte, outil
//               qui leve, module absent). Le HUD surveille la machine ;
//               personne ne surveillait JARVIS.
//   PROPOSITIONS ce qu'il voudrait voir corrige, sous forme d'un PROMPT
//               destine a un agent de code. JARVIS n'ecrit pas le code.
//
// LE PROMPT EST AFFICHE EN ENTIER AVANT TOUT ENVOI.
// C'est le coeur du dispositif, pas un detail d'ergonomie : le texte affiche
// deviendra des instructions pour un agent ayant acces en ecriture au disque.
// Le bouton d'envoi ne s'active qu'apres l'avoir deplie.

import { appelerJarvis } from './appel-jarvis.js';
import { showNotification } from './notifications.js';

let constats = [];
let propositions = [];
let depot = { pret: false, motif: '' };
let agents = ['claude'];
let deplies = new Set();

function ech(s) {
  return String(s ?? '').replace(/[&<>"']/g, (c) => (
    { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
}

function rendreConstats() {
  if (!constats.length) {
    return '<div class="aa-vide">AUCUN CONSTAT — JARVIS NE VOIT RIEN A SIGNALER</div>';
  }
  return constats.map((c) => `
    <div class="aa-constat aa-${ech(c.gravite)}">
      <div class="aa-ligne-titre">
        <span class="aa-gravite">${ech(c.gravite.toUpperCase())}</span>
        <span class="aa-titre">${ech(c.titre)}</span>
      </div>
      <div class="aa-preuve">${ech(c.preuve)}</div>
      ${c.fichier ? `<div class="aa-fichier">${ech(c.fichier)}</div>` : ''}
    </div>`).join('');
}

function rendrePropositions() {
  if (!propositions.length) {
    return '<div class="aa-vide">AUCUNE PROPOSITION</div>';
  }
  return propositions.map((p) => {
    const ouvert = deplies.has(p.cle);
    return `
    <div class="aa-prop aa-${ech(p.gravite)}" data-cle="${ech(p.cle)}">
      <div class="aa-ligne-titre">
        <span class="aa-gravite">${ech(p.gravite.toUpperCase())}</span>
        <span class="aa-titre">${ech(p.titre)}</span>
      </div>
      <div class="aa-preuve">${ech(p.preuve)}</div>
      <div class="aa-meta">branche : ${ech(p.branche)}</div>
      <div class="aa-actions">
        <button class="btn aa-btn" data-action="basculer">${ouvert ? 'MASQUER' : 'LIRE'} LE PROMPT</button>
        <select class="rg-input aa-agent" data-action="agent">
          ${agents.map((a) => `<option value="${ech(a)}">${ech(a.toUpperCase())}</option>`).join('')}
        </select>
        <button class="btn aa-btn aa-envoyer" data-action="envoyer" ${ouvert && depot.pret ? '' : 'disabled'}>
          ENVOYER A L'AGENT
        </button>
      </div>
      ${ouvert ? `<pre class="aa-prompt">${ech(p.prompt)}</pre>` : ''}
      ${!depot.pret ? `<div class="aa-bloque">ENVOI BLOQUE — ${ech(depot.motif)}</div>` : ''}
      <div class="aa-resultat" data-resultat="${ech(p.cle)}"></div>
    </div>`;
  }).join('');
}

function dessiner(conteneur) {
  const critiques = constats.filter((c) => c.gravite === 'critique').length;
  conteneur.innerHTML = `
    <div class="aa-entete">
      <span class="aa-compteur ${critiques ? 'aa-alerte' : ''}">
        ${constats.length} CONSTAT(S) · ${critiques} CRITIQUE(S)
      </span>
      <button class="btn aa-btn" id="aa-rafraichir">RELANCER LE DIAGNOSTIC</button>
    </div>
    <div class="aa-section">ETAT DE JARVIS</div>
    ${rendreConstats()}
    <div class="aa-section">PROPOSITIONS — JARVIS N'ECRIT PAS LE CODE</div>
    <div class="aa-note">Chaque proposition produit un prompt pour un agent de
    code. Relis-le avant d'envoyer : il modifiera de vrais fichiers, sur une
    branche git dediee.</div>
    ${rendrePropositions()}`;

  conteneur.querySelector('#aa-rafraichir')?.addEventListener('click', () => charger(conteneur));

  conteneur.querySelectorAll('.aa-prop').forEach((bloc) => {
    const cle = bloc.dataset.cle;
    const prop = propositions.find((p) => p.cle === cle);

    bloc.querySelector('[data-action="basculer"]')?.addEventListener('click', () => {
      if (deplies.has(cle)) deplies.delete(cle); else deplies.add(cle);
      dessiner(conteneur);
    });

    bloc.querySelector('[data-action="envoyer"]')?.addEventListener('click', async () => {
      const agent = bloc.querySelector('[data-action="agent"]').value;
      // Deuxieme garde-fou, apres celui du serveur : on nomme l'agent, la
      // branche, et le fait que des fichiers vont changer.
      const accord = window.confirm(
        `ENVOYER CE PROMPT A ${agent.toUpperCase()} ?\n\n`
        + `${prop.titre}\n\nL'agent va modifier de vrais fichiers de JARVIS, `
        + `sur la branche ${prop.branche}.\nAnnulable par : git checkout `
        + `<branche precedente> && git branch -D ${prop.branche}\n\nContinuer ?`);
      if (!accord) return;

      const zone = bloc.querySelector(`[data-resultat="${CSS.escape(cle)}"]`);
      zone.textContent = 'AGENT EN COURS — CELA PEUT PRENDRE PLUSIEURS MINUTES...';
      try {
        const r = await appelerJarvis('envoyer_proposition', { cle, agent, confirme: true });
        zone.innerHTML = r.ok
          ? `<div class="aa-ok">TERMINE sur ${ech(r.branche)} — ${(r.fichiers_modifies || []).length} fichier(s) modifie(s)`
            + `<br>${ech((r.fichiers_modifies || []).join(', '))}`
            + `<br>annuler : <code>${ech(r.annuler || '')}</code></div>`
          : `<div class="aa-echec">ECHEC — ${ech(r.erreur || r.message || 'raison inconnue')}</div>`;
        showNotification(r.ok ? 'AGENT TERMINE' : 'AGENT EN ECHEC');
      } catch (e) {
        zone.innerHTML = `<div class="aa-echec">${ech(e.message)}</div>`;
      }
    });
  });
}

async function charger(conteneur) {
  conteneur.innerHTML = '<div class="aa-vide">DIAGNOSTIC EN COURS...</div>';
  try {
    const d = await appelerJarvis('get_auto_diagnostic', {});
    constats = d.constats || [];
    const p = await appelerJarvis('get_propositions', {});
    propositions = p.propositions || [];
    depot = { pret: !!p.depot_pret, motif: p.depot_motif || '' };
    if (p.agents?.length) agents = p.agents;
  } catch (e) {
    conteneur.innerHTML = `<div class="aa-vide">DIAGNOSTIC INDISPONIBLE — ${ech(e.message)}</div>`;
    return;
  }
  dessiner(conteneur);
}

export function initAutoAmelioration() {
  const conteneur = document.getElementById('rtab-jarvis');
  if (!conteneur) return;
  let charge = false;
  // Chargement paresseux : le diagnostic lit le disque et interroge git,
  // inutile de le faire au demarrage si l'onglet n'est jamais ouvert.
  document.querySelector('.tab-btn-r[data-rtab="jarvis"]')
    ?.addEventListener('click', () => {
      if (charge) return;
      charge = true;
      charger(conteneur);
    });
}
