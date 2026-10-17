// ── Reglages JARVIS + cles API + modeles par agent (lot 2) ───────────────
//
// Reprend les 3 panneaux de l'ancien frontend :
//   settings-modal     -> get_settings / update_settings
//   api-keys-modal     -> les memes messages (les cles vivent dans .env)
//   agent-model-modal  -> get_agent_models / set_agent_models
//
// SECURITE DES CLES API — on s'appuie sur le mecanisme deja en place dans
// main2.py, on n'en invente pas un second :
//   - get_settings renvoie les cles DEJA masquees (_masquer_cle : huit
//     puces + les 4 derniers caracteres), et tout le paquet passe par
//     _sans_secrets. Aucune cle en clair n'atteint le navigateur.
//   - update_settings ignore toute valeur encore masquee (_est_masquee).
//     Reafficher puis renvoyer la valeur masquee telle quelle est donc sans
//     effet : seule une cle reellement retapee est ecrite dans .env.
// Consequence pratique : ce composant se contente de reafficher ce qu'il
// recoit. Il ne stocke jamais de cle, ne la journalise jamais.

import { showNotification } from './notifications.js';
import { appliquerStyleOrbe } from '../config/theme.js';
import { appelerJarvis } from './appel-jarvis.js';

let reglages = {};          // derniere copie recue (cles deja masquees)
let modelesAgents = null;   // {available_models, current_models}

const CLES_API = [
  ['GEMINI_API_KEY', 'GEMINI', 'api_gemini_enabled'],
  ['GROQ_API_KEY', 'GROQ', 'api_groq_enabled'],
  ['XAI_API_KEY', 'GROK', 'api_grok_enabled'],
  ['ANTHROPIC_API_KEY', 'CLAUDE', 'api_anthropic_enabled'],
  ['MISTRAL_API_KEY', 'MISTRAL', 'api_mistral_enabled'],
  ['OPENAI_API_KEY', 'OPENAI', 'api_openai_enabled'],
  ['YOUTUBE_API_KEY', 'YOUTUBE', 'api_youtube_enabled'],
  ['SERPAPI_API_KEY', 'SERPAPI', 'api_serpapi_enabled'],
];

// Delegue a appel-jarvis.js : copie unique, et c'est la qu'est gere le
// refus 428 (niveau d'autorisation depasse -> demande d'accord -> rejeu).
const appeler = appelerJarvis;

function ech(s) {
  return String(s ?? '').replace(/[&<>"']/g, (c) => (
    { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
}

function ligneTexte(id, libelle, valeur, type = 'text') {
  return `<div class="rg-ligne">
    <label class="rg-label" for="${id}">${ech(libelle)}</label>
    <input class="rg-input" id="${id}" type="${type}" value="${ech(valeur ?? '')}" />
  </div>`;
}

function ligneCase(id, libelle, coche) {
  return `<div class="rg-ligne">
    <label class="rg-label" for="${id}">${ech(libelle)}</label>
    <input class="rg-case" id="${id}" type="checkbox" ${coche ? 'checked' : ''} />
  </div>`;
}

function ligneListe(id, libelle, valeur, options) {
  const opts = options.map((o) => {
    const v = typeof o === 'string' ? o : o.valeur;
    const t = typeof o === 'string' ? o : o.texte;
    return `<option value="${ech(v)}" ${String(v) === String(valeur) ? 'selected' : ''}>${ech(t)}</option>`;
  }).join('');
  return `<div class="rg-ligne">
    <label class="rg-label" for="${id}">${ech(libelle)}</label>
    <select class="rg-input" id="${id}">${opts}</select>
  </div>`;
}

// ── Rendu ────────────────────────────────────────────────────────────────

function rendreProfil() {
  const micros = (reglages.mic_list || []).map((m) => ({ valeur: m.index, texte: m.name }));
  return `<div class="rg-section">PROFIL</div>
    ${ligneTexte('rg-name', 'NOM', reglages.user_name)}
    ${ligneTexte('rg-age', 'AGE', reglages.user_age, 'number')}
    ${ligneTexte('rg-city', 'VILLE', reglages.user_city)}
    ${ligneTexte('rg-wakeword', 'MOT DE REVEIL', reglages.wake_word)}
    <div class="rg-section">AUDIO</div>
    ${micros.length ? ligneListe('rg-mic', 'MICRO', reglages.mic_device_index, micros)
                    : '<div class="rg-note">AUCUN MICRO DETECTE</div>'}
    ${ligneCase('rg-mic-dyn', 'SENSIBILITE DYNAMIQUE', reglages.mic_dynamic_sensitivity)}
    ${ligneTexte('rg-mic-sens', 'SENSIBILITE', reglages.mic_sensitivity, 'number')}
    ${ligneListe('rg-voice', 'VOIX', reglages.voice, ['male', 'female'])}
    <div class="rg-section">INTERFACE</div>
    ${ligneListe('rg-orb', 'STYLE ORBE', reglages.orb_style, ['grey', 'classic', 'neon', 'aurum'])}
    ${ligneCase('rg-clock', 'HORLOGE HUD', reglages.show_clock_hud)}
    ${ligneCase('rg-startup', 'LANCER AU DEMARRAGE', reglages.launch_on_startup)}
    ${ligneCase('rg-briefing', 'BRIEFING AU DEMARRAGE', reglages.startup_briefing)}
    <div class="rg-section">LOCALISATION</div>
    ${ligneTexte('rg-lat', 'LATITUDE', reglages.user_lat, 'number')}
    ${ligneTexte('rg-lon', 'LONGITUDE', reglages.user_lon, 'number')}
    ${ligneCase('rg-sky', 'VEILLE CIEL', reglages.sky_watch)}
    ${ligneCase('rg-rocket', 'VEILLE FUSEES', reglages.rocket_watch)}`;
}

function rendreCles() {
  const cles = reglages.api_keys || {};
  const lignes = CLES_API.map(([nom, libelle, drapeau]) => {
    const valeur = cles[nom] || '';
    const configuree = !!valeur;
    return `<div class="rg-cle">
      <div class="rg-cle-entete">
        <span class="rg-label">${ech(libelle)}</span>
        <span class="rg-etat ${configuree ? 'ok' : 'vide'}">${configuree ? 'CONFIGUREE' : 'ABSENTE'}</span>
        <input class="rg-case" id="rg-flag-${ech(drapeau)}" type="checkbox"
               ${reglages[drapeau] ? 'checked' : ''} title="Activer ce fournisseur" />
      </div>
      <input class="rg-input rg-cle-champ" id="rg-key-${ech(nom)}" type="text"
             value="${ech(valeur)}" spellcheck="false" autocomplete="off" />
    </div>`;
  }).join('');
  return `<div class="rg-section">CLES API</div>
    <div class="rg-note">Les cles arrivent masquees. Laisser telle quelle pour
    conserver la cle existante ; retaper la valeur complete pour la remplacer.</div>
    ${lignes}`;
}

function rendreModeles() {
  if (!modelesAgents) return '<div class="rg-note">CHARGEMENT DES MODELES...</div>';
  const dispo = modelesAgents.available_models || {};
  const actuels = modelesAgents.current_models || {};
  const lignes = Object.keys(dispo).map((fournisseur) => ligneListe(
    `rg-agent-${ech(fournisseur)}`, fournisseur, actuels[fournisseur], dispo[fournisseur]
  )).join('');
  return `<div class="rg-section">MODELE PAR FOURNISSEUR</div>${lignes}`;
}

function dessiner(conteneur) {
  conteneur.innerHTML = `
    <div class="rg-onglets">
      <button class="rg-onglet active" data-vue="profil">PROFIL</button>
      <button class="rg-onglet" data-vue="cles">CLES API</button>
      <button class="rg-onglet" data-vue="modeles">MODELES</button>
    </div>
    <div class="rg-corps" id="rg-corps">${rendreProfil()}</div>
    <div class="rg-barre">
      <button class="btn rg-enregistrer" id="rg-enregistrer">ENREGISTRER</button>
      <button class="btn" id="rg-recharger">RECHARGER</button>
      <span class="rg-message" id="rg-message"></span>
    </div>`;

  const corps = conteneur.querySelector('#rg-corps');
  conteneur.querySelectorAll('.rg-onglet').forEach((b) => {
    b.addEventListener('click', async () => {
      conteneur.querySelectorAll('.rg-onglet').forEach((x) => x.classList.remove('active'));
      b.classList.add('active');
      const vue = b.dataset.vue;
      if (vue === 'modeles' && !modelesAgents) {
        corps.innerHTML = '<div class="rg-note">CHARGEMENT DES MODELES...</div>';
        try { modelesAgents = (await appeler('get_agent_models')).data; } catch (e) {
          corps.innerHTML = `<div class="rg-note erreur">${ech(e.message)}</div>`; return;
        }
      }
      corps.innerHTML = vue === 'profil' ? rendreProfil()
                      : vue === 'cles' ? rendreCles() : rendreModeles();
    });
  });

  // STYLE ORBE : applique tout de suite, sans attendre ENREGISTRER.
  // Delegue sur #rg-corps parce que le <select> est recree a chaque bascule
  // de vue — un listener pose sur l'element lui-meme disparaitrait.
  // Le choix passe par appliquerStyleOrbe -> setThemeHue, donc par le meme
  // chemin que les pastilles de couleur de l'onglet CONTROLS.
  corps.addEventListener('change', (e) => {
    if (e.target.id !== 'rg-orb') return;
    if (appliquerStyleOrbe(e.target.value)) {
      showNotification(`STYLE ORBE : ${e.target.value.toUpperCase()}`);
    }
  });

  conteneur.querySelector('#rg-recharger').addEventListener('click', () => charger(conteneur));
  conteneur.querySelector('#rg-enregistrer').addEventListener('click', () => enregistrer(conteneur));
}

function message(conteneur, texte, erreur = false) {
  const el = conteneur.querySelector('#rg-message');
  if (!el) return;
  el.textContent = texte;
  el.className = `rg-message${erreur ? ' erreur' : ''}`;
}

// ── Collecte + envoi ─────────────────────────────────────────────────────

function valeur(id) { return document.getElementById(id)?.value; }
function coche(id) { return !!document.getElementById(id)?.checked; }

async function enregistrer(conteneur) {
  const vue = conteneur.querySelector('.rg-onglet.active')?.dataset.vue;
  try {
    if (vue === 'modeles') {
      if (!modelesAgents) return;
      const modeles = {};
      for (const f of Object.keys(modelesAgents.available_models || {})) {
        const v = valeur(`rg-agent-${f}`);
        if (v) modeles[f] = v;
      }
      const r = await appeler('set_agent_models', { models: modeles });
      modelesAgents.current_models = r.models || modeles;
      message(conteneur, 'MODELES ENREGISTRES');
      showNotification('MODELES PAR AGENT MIS A JOUR');
      return;
    }

    const settings = {};
    if (vue === 'profil') {
      // On n'envoie QUE les champs de la vue affichee : envoyer un objet
      // partiel est sans risque, main2.py fusionne avec la config existante.
      Object.assign(settings, {
        user_name: valeur('rg-name'),
        user_age: valeur('rg-age'),
        wake_word: valeur('rg-wakeword'),
        mic_dynamic_sensitivity: coche('rg-mic-dyn'),
        mic_sensitivity: Number(valeur('rg-mic-sens')) || reglages.mic_sensitivity,
        voice: valeur('rg-voice'),
        orb_style: valeur('rg-orb'),
        show_clock_hud: coche('rg-clock'),
        launch_on_startup: coche('rg-startup'),
        startup_briefing: coche('rg-briefing'),
        user_lat: Number(valeur('rg-lat')),
        user_lon: Number(valeur('rg-lon')),
        sky_watch: coche('rg-sky'),
        rocket_watch: coche('rg-rocket'),
      });
      const mic = valeur('rg-mic');
      if (mic !== undefined && mic !== '') settings.mic_device_index = Number(mic);

      // user_city n'est envoye QUE s'il a reellement change.
      // Raison : cote main2.py, ce champ declenche geocoder_ville(), un
      // requests.get() SYNCHRONE appele directement dans le handler async.
      // Il bloque toute la boucle d'evenements pendant l'appel reseau, et
      // si l'API de geocodage ne repond pas, JARVIS se fige entierement
      // (constate en vrai pendant ce lot : plus aucune reponse WebSocket,
      // nouvelles connexions refusees, redemarrage necessaire).
      // Ne pas le renvoyer a chaque enregistrement limite l'exposition.
      const ville = valeur('rg-city');
      if (ville !== undefined && ville !== (reglages.user_city ?? '')) {
        settings.user_city = ville;
      }
    } else if (vue === 'cles') {
      const api = {};
      for (const [nom, , drapeau] of CLES_API) {
        const v = valeur(`rg-key-${nom}`);
        // On renvoie la valeur telle quelle, masquee comprise : main2.py
        // detecte le masque (_est_masquee) et conserve la vraie cle.
        if (v !== undefined) api[nom] = v;
        settings[drapeau] = coche(`rg-flag-${drapeau}`);
      }
      settings.api_keys = api;
    }

    await appeler('update_settings', { settings });
    message(conteneur, 'ENREGISTRE');
    showNotification('REGLAGES ENREGISTRES');
    await charger(conteneur, vue);   // relit l'etat reel apres ecriture
  } catch (e) {
    message(conteneur, e.message, true);
    showNotification(`REGLAGES : ${e.message}`);
  }
}

async function charger(conteneur, vueVoulue = null) {
  const corps = conteneur.querySelector('#rg-corps');
  if (corps) corps.innerHTML = '<div class="rg-note">CHARGEMENT...</div>';
  try {
    const r = await appeler('get_settings');
    reglages = r.data || {};
    const onglet = vueVoulue
      ? conteneur.querySelector(`.rg-onglet[data-vue="${vueVoulue}"]`)
      : conteneur.querySelector('.rg-onglet.active');
    if (onglet) onglet.click();
    else if (corps) corps.innerHTML = rendreProfil();
  } catch (e) {
    if (corps) corps.innerHTML = `<div class="rg-note erreur">JARVIS INJOIGNABLE : ${ech(e.message)}</div>`;
  }
}

export function initReglages() {
  const conteneur = document.getElementById('rtab-settings');
  if (!conteneur) return;
  dessiner(conteneur);
  charger(conteneur);
}
