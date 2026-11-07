// ── Creation : images, videos, sites, prompts (lot 10) ───────────────────
//
// JARVIS demande « avec quel modele ? » (ask_image_model, ask_website_model),
// annonce le travail (generation_loading, coding_started) puis pousse le
// resultat (show_generated_image / _video / _prompt). Rien de tout cela
// n'atteignait le HUD : JARVIS disait « clique sur les boutons a l'ecran »
// sans aucun bouton, et annoncait une image qui n'apparaissait nulle part.
//
// Une seule <dialog> modale sert au choix du modele et au resultat. Elle vit
// dans la couche superieure : le backdrop-filter des panneaux piege les
// position:fixed (meme raison que le AGRANDIR du panneau scolaire).
// Les resultats restent ensuite dans MEDIA > CREATIONS.

import { showNotification } from './notifications.js';
import { appelerJarvis } from './appel-jarvis.js';

// Identifiants attendus par generate_image_selected cote main2.py.
const MODELES_IMAGE = [
  ['openai', 'gpt-image-2'], ['gemini', 'Imagen 4'],
  ['gemini_flash_lite', 'Gemini 3.1 Flash Lite'], ['grok', 'xAI Grok'],
];
// ask_image_model SANS prompt = images d'un site demande a la voix : JARVIS
// attend alors le NOM du modele dans une phrase, et ne connait que ces trois.
const MODELES_IMAGE_PHRASE = [['ChatGPT', 'gpt-image-2'], ['Gemini', 'Imagen 4'], ['Grok', 'xAI Grok']];
const NOMS_SITE = {
  gemini: 'Gemini', claude: 'Claude', groq: 'Groq', mistral: 'Mistral', grok: 'Grok', openai: 'ChatGPT',
};

function ech(s) {
  return String(s ?? '').replace(/[&<>"']/g, (c) => (
    { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
}

const recues = [];           // derniers resultats, pour MEDIA > CREATIONS
let redessiner = () => {};

const titre = (r) => ({ image: 'IMAGE GENEREE', video: 'VIDEO GENEREE', prompt: 'PROMPT GENERE' })[r.genre];

function rendu(r) {
  const lien = /^https?:/i.test(r.url || '')
    ? `<a class="cr-lien" href="${ech(r.url)}" target="_blank" rel="noopener noreferrer">OUVRIR</a>` : '';
  const media = r.genre === 'image'
    ? `<img class="cr-media" src="${ech(r.url)}" alt="${ech(r.prompt)}" />`
    : r.genre === 'video'
      ? `<video class="cr-media" src="${ech(r.url)}" controls playsinline></video>`
      : `<pre class="cr-texte">${ech(r.prompt)}</pre>`;
  return `
    <div class="cr-titre">${titre(r)}
      <span class="cr-source">${ech(r.source || '')} · ${r.t.toLocaleTimeString()}</span></div>
    ${media}
    ${r.genre === 'prompt' ? '' : `<div class="cr-prompt">${ech(r.prompt)}</div>`}
    <div class="cr-actions">${r.genre === 'prompt' ? '<button class="btn cr-copier">COPIER</button>' : ''}${lien}</div>`;
}

function brancherCopie(racine, texte) {
  const b = racine.querySelector('.cr-copier');
  if (!b) return;
  b.addEventListener('click', () => navigator.clipboard.writeText(texte)
    .then(() => { b.textContent = 'COPIE'; })
    .catch(() => { b.textContent = 'COPIE IMPOSSIBLE'; }));
}

/** Vue MEDIA > CREATIONS : historique des resultats de la session. */
export function initCreations(zone) {
  zone.innerHTML = `
    <div class="rg-note">Images, videos et prompts generes par JARVIS
      (« genere une image de ... »). Le dernier s'affiche aussi en grand.</div>
    <div class="sec-etat" id="cr-hist-etat">AUCUNE CREATION</div>
    <div id="cr-hist"></div>`;
  const etat = zone.querySelector('#cr-hist-etat');
  const liste = zone.querySelector('#cr-hist');
  redessiner = () => {
    etat.textContent = `${recues.length} CREATION(S)`;
    liste.innerHTML = recues.map((r, i) => `<div class="cr-carte" data-i="${i}">${rendu(r)}</div>`).join('');
    liste.querySelectorAll('.cr-carte').forEach((c) => brancherCopie(c, recues[Number(c.dataset.i)].prompt));
  };
  redessiner();
}

export function initCreation() {
  const dlg = document.createElement('dialog');
  dlg.className = 'cr-dialog';
  dlg.setAttribute('closedby', 'any');
  document.body.appendChild(dlg);

  const bandeau = document.createElement('div');
  bandeau.className = 'cr-bandeau';
  bandeau.hidden = true;
  document.body.appendChild(bandeau);
  let filet = null;

  function ouvrir(html, sorte) {
    dlg.dataset.sorte = sorte;
    dlg.innerHTML = `<button class="cr-fermer" aria-label="Fermer">✕</button>${html}`;
    dlg.querySelector('.cr-fermer').addEventListener('click', () => dlg.close());
    if (!dlg.open) dlg.showModal();
  }

  function fermerChoix() {
    if (dlg.open && dlg.dataset.sorte === 'choix') dlg.close();
  }

  function enCours(texte) {
    bandeau.textContent = texte;
    bandeau.hidden = false;
    clearTimeout(filet);
    // Si JARVIS plante sans jamais signaler la fin, on n'affiche pas
    // « en cours » indefiniment.
    filet = setTimeout(() => { bandeau.hidden = true; }, 6 * 60 * 1000);
  }

  function fini() {
    bandeau.hidden = true;
    clearTimeout(filet);
  }

  function boutons(liste) {
    return `<div class="cr-choix">${liste.map(([id, nom]) =>
      `<button class="btn cr-modele" data-id="${ech(id)}">${ech(nom)}</button>`).join('')}</div>`;
  }

  /** Envoie le choix ; la fenetre se ferme si JARVIS l'a recu, sinon elle dit pourquoi. */
  function surChoix(appel) {
    dlg.querySelectorAll('.cr-modele').forEach((b) => b.addEventListener('click', async () => {
      const tous = dlg.querySelectorAll('.cr-modele');
      tous.forEach((x) => { x.disabled = true; });
      try {
        await appel(b.dataset.id);
        dlg.close();
      } catch (e) {
        const etat = dlg.querySelector('.cr-etat');
        etat.textContent = `ECHEC : ${e.message}`;
        etat.classList.add('erreur');
        tous.forEach((x) => { x.disabled = false; });
      }
    }));
  }

  async function phrase(texte) {
    const r = await fetch('/api/chat', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message: texte }),
    });
    if (!r.ok) throw new Error((await r.json().catch(() => ({}))).error || `HTTP ${r.status}`);
  }

  function choisirImage(prompt) {
    if (prompt) {
      ouvrir(`<div class="cr-titre">GENERATION D'IMAGE</div>
        <div class="cr-prompt">${ech(prompt)}</div>
        <div class="cr-question">Avec quel modele ?</div>${boutons(MODELES_IMAGE)}
        <div class="sec-etat cr-etat"></div>`, 'choix');
      surChoix((model) => appelerJarvis('generate_image_selected', { prompt, model }));
    } else {
      ouvrir(`<div class="cr-titre">IMAGES DU SITE</div>
        <div class="cr-question">Avec quel modele generer les images du site ?</div>
        ${boutons(MODELES_IMAGE_PHRASE)}<div class="sec-etat cr-etat"></div>`, 'choix');
      surChoix(phrase);
    }
  }

  function choisirSite(prompt, modeles) {
    ouvrir(`<div class="cr-titre">CREATION DE SITE WEB</div>
      <div class="cr-prompt">${ech(prompt)}</div>
      <div class="cr-question">Quel modele code le site ?</div>
      ${modeles.length ? boutons(modeles.map((m) => [m, NOMS_SITE[m] || m]))
        : '<div class="sec-etat erreur">AUCUN MODELE DISPONIBLE COTE JARVIS</div>'}
      <div class="sec-etat cr-etat"></div>`, 'choix');
    // Deux questions, un seul envoi : generate_website_selected porte les
    // deux modeles, comme le faisait l'ancien frontend.
    dlg.querySelectorAll('.cr-modele').forEach((b) => b.addEventListener('click', () => {
      const model = b.dataset.id;
      dlg.querySelector('.cr-question').textContent = 'Et pour les images du site ?';
      dlg.querySelector('.cr-choix').outerHTML = boutons(MODELES_IMAGE);
      surChoix((image_model) => appelerJarvis('generate_website_selected', { prompt, model, image_model }));
    }));
  }

  function montrer(r) {
    fini();
    recues.unshift({ ...r, t: new Date() });
    if (recues.length > 8) recues.pop();
    redessiner();
    ouvrir(rendu(recues[0]), 'resultat');
    brancherCopie(dlg, recues[0].prompt);
    showNotification(titre(r));
  }

  window.addEventListener('jarvis-event', (e) => {
    const ev = e.detail || {};
    switch (ev.type) {
      case 'ask_image_model': choisirImage(ev.prompt || ''); break;
      case 'ask_website_model': choisirSite(ev.prompt || '', ev.available_models || []); break;
      case 'close_image_model_selector':
      case 'close_website_model_selector': fermerChoix(); break;
      case 'generation_loading':
        enCours(ev.media_type === 'video' ? 'GENERATION DE LA VIDEO...' : "GENERATION DE L'IMAGE...");
        break;
      case 'coding_started': enCours('JARVIS CODE LE SITE...'); break;
      case 'hide_generation_loading':
      case 'coding_finished': fini(); break;
      case 'show_generated_image':
        montrer({ genre: 'image', url: ev.url, prompt: ev.prompt || ev.prompt_fr || '', source: ev.source });
        break;
      case 'show_generated_video':
        montrer({ genre: 'video', url: ev.url, prompt: ev.prompt_fr || '', source: ev.source });
        break;
      case 'show_generated_prompt':
        montrer({ genre: 'prompt', prompt: ev.prompt || '', source: 'JARVIS' });
        break;
      default: break;
    }
  });
}
